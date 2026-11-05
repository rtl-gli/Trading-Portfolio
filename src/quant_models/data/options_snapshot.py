"""Validated local snapshots of listed SPY option-chain quotes."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPTIONS_CONFIG = PROJECT_ROOT / "config" / "options.yaml"
REQUIRED_CHAIN_COLUMNS = (
    "contractSymbol",
    "lastTradeDate",
    "strike",
    "lastPrice",
    "bid",
    "ask",
    "change",
    "percentChange",
    "volume",
    "openInterest",
    "impliedVolatility",
    "inTheMoney",
    "contractSize",
    "currency",
)
NUMERIC_CHAIN_COLUMNS = (
    "strike",
    "lastPrice",
    "bid",
    "ask",
    "change",
    "percentChange",
    "volume",
    "openInterest",
    "impliedVolatility",
)
_SPY_OPTION_SYMBOL = re.compile(r"SPY(?P<expiration>\d{6})(?P<side>[CP])\d{8}\Z")


class OptionSnapshotError(RuntimeError):
    """Raised when an option chain cannot be safely validated or saved."""


class OptionsClient(Protocol):
    """Minimal yfinance ticker interface used by the snapshotter."""

    @property
    def options(self) -> tuple[str, ...]: ...

    def option_chain(self, date: str) -> object: ...


@dataclass(frozen=True)
class SnapshotSettings:
    """Validated options snapshot source, underlying, timezone, and location."""

    provider: str
    underlying: str
    timezone: str
    snapshot_directory: Path


@dataclass(frozen=True)
class SnapshotResult:
    """Paths and contract counts for one completed daily snapshot."""

    snapshot_date: date
    manifest_path: Path
    data_path: Path
    contract_count: int
    expiration_count: int


def load_snapshot_settings(path: Path = DEFAULT_OPTIONS_CONFIG) -> SnapshotSettings:
    """Load and validate the non-secret options snapshot YAML configuration."""
    try:
        with Path(path).open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
    except yaml.YAMLError as error:
        raise OptionSnapshotError(
            f"Invalid options YAML configuration: {path}"
        ) from error
    if not isinstance(config, dict):
        raise OptionSnapshotError("Options configuration must be a YAML mapping.")
    provider = config.get("provider")
    underlying = config.get("underlying")
    timezone = config.get("timezone")
    directory = config.get("snapshot_directory")
    if provider != "yfinance":
        raise OptionSnapshotError("Only the configured yfinance provider is supported.")
    if underlying != "SPY":
        raise OptionSnapshotError("The initial option snapshot underlying must be SPY.")
    if not isinstance(timezone, str) or not timezone.strip():
        raise OptionSnapshotError("timezone must be a non-empty IANA time-zone name.")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise OptionSnapshotError(f"Unknown time zone: {timezone!r}") from error
    if not isinstance(directory, str) or not directory.strip():
        raise OptionSnapshotError("snapshot_directory must be a non-empty path.")
    output_directory = Path(directory)
    if not output_directory.is_absolute():
        output_directory = PROJECT_ROOT / output_directory
    return SnapshotSettings(
        provider=provider,
        underlying=underlying,
        timezone=timezone,
        snapshot_directory=output_directory.resolve(),
    )


def _validate_expirations(expirations: tuple[str, ...]) -> tuple[str, ...]:
    if not expirations:
        raise OptionSnapshotError("The provider returned no listed expirations.")
    validated: list[str] = []
    for expiration in expirations:
        if not isinstance(expiration, str):
            raise OptionSnapshotError("Every option expiration must be a date string.")
        try:
            parsed = date.fromisoformat(expiration)
        except ValueError as error:
            raise OptionSnapshotError(
                f"Invalid option expiration date: {expiration!r}"
            ) from error
        if parsed.isoformat() != expiration:
            raise OptionSnapshotError(
                f"Option expiration must use YYYY-MM-DD: {expiration!r}"
            )
        validated.append(expiration)
    if len(set(validated)) != len(validated):
        raise OptionSnapshotError("The provider returned duplicate expiration dates.")
    return tuple(sorted(validated))


def _normalize_option_side(
    options: pd.DataFrame, expiration: str, option_type: str
) -> pd.DataFrame:
    if not isinstance(options, pd.DataFrame):
        raise OptionSnapshotError(
            f"The provider returned a non-DataFrame for {option_type}s."
        )
    missing_columns = sorted(set(REQUIRED_CHAIN_COLUMNS) - set(options.columns))
    if missing_columns:
        raise OptionSnapshotError(
            f"The {option_type} chain is missing required columns: {missing_columns}."
        )
    normalized = options.loc[:, REQUIRED_CHAIN_COLUMNS].copy()
    contract_symbols = normalized["contractSymbol"].astype(str).str.strip()
    symbol_matches = contract_symbols.map(_SPY_OPTION_SYMBOL.fullmatch)
    if symbol_matches.isna().any():
        raise OptionSnapshotError("Option contract symbols must match the SPY format.")
    expected_expiration = expiration[2:].replace("-", "")
    expected_side = "C" if option_type == "call" else "P"
    if not symbol_matches.map(
        lambda match: (
            match.group("expiration") == expected_expiration
            and match.group("side") == expected_side
        )
    ).all():
        raise OptionSnapshotError(
            "Option contract symbols must match their expiration and option type."
        )
    normalized["contractSymbol"] = contract_symbols
    for column in NUMERIC_CHAIN_COLUMNS:
        original = normalized[column]
        converted = pd.to_numeric(original, errors="coerce")
        if (original.notna() & converted.isna()).any():
            raise OptionSnapshotError(
                f"Option chain column {column!r} contains non-numeric values."
            )
        finite_values = converted.dropna().to_numpy(dtype=float)
        if not all(math.isfinite(value) for value in finite_values):
            raise OptionSnapshotError(
                f"Option chain column {column!r} contains infinite values."
            )
        normalized[column] = converted
    if normalized["strike"].isna().any() or (normalized["strike"] <= 0).any():
        raise OptionSnapshotError("Every option strike must be present and positive.")
    for column in (
        "lastPrice",
        "bid",
        "ask",
        "volume",
        "openInterest",
        "impliedVolatility",
    ):
        if (normalized[column].dropna() < 0).any():
            raise OptionSnapshotError(
                f"Option chain column {column!r} must not contain negative values."
            )
    trade_dates = pd.to_datetime(normalized["lastTradeDate"], errors="coerce", utc=True)
    invalid_trade_dates = normalized["lastTradeDate"].notna() & trade_dates.isna()
    if invalid_trade_dates.any():
        raise OptionSnapshotError("Option last-trade dates must be valid timestamps.")
    normalized["lastTradeDate"] = trade_dates.map(
        lambda value: value.isoformat() if not pd.isna(value) else None
    )
    normalized["expiration"] = expiration
    normalized["option_type"] = option_type
    return normalized


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_option_snapshot(
    ticker: OptionsClient,
    settings: SnapshotSettings,
    retrieved_at: datetime | None = None,
) -> SnapshotResult:
    """Fetch, validate, and atomically save every listed SPY option expiration."""
    instant = retrieved_at or datetime.now(UTC)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise OptionSnapshotError("retrieved_at must include a time zone.")
    retrieved_utc = instant.astimezone(UTC)
    local_date = retrieved_utc.astimezone(ZoneInfo(settings.timezone)).date()
    expirations = _validate_expirations(tuple(ticker.options))
    chains: list[pd.DataFrame] = []
    for expiration in expirations:
        chain = ticker.option_chain(expiration)
        calls = _normalize_option_side(chain.calls, expiration, "call")
        puts = _normalize_option_side(chain.puts, expiration, "put")
        chains.extend((calls, puts))
    snapshot = pd.concat(chains, ignore_index=True)
    if snapshot.empty:
        raise OptionSnapshotError("The provider returned no option contracts.")
    if snapshot.duplicated(["expiration", "option_type", "contractSymbol"]).any():
        raise OptionSnapshotError("The provider returned duplicate option contracts.")
    snapshot = snapshot.sort_values(
        ["expiration", "option_type", "strike", "contractSymbol"],
        kind="stable",
        ignore_index=True,
    )

    snapshot_directory = settings.snapshot_directory
    snapshot_directory.mkdir(parents=True, exist_ok=True)
    destination = snapshot_directory / local_date.isoformat()
    if destination.exists():
        raise FileExistsError(
            f"A snapshot already exists for {local_date}: {destination}. "
            "Existing data is never overwritten by this script."
        )
    with tempfile.TemporaryDirectory(
        prefix=f".{local_date.isoformat()}-", dir=snapshot_directory
    ) as temporary_name:
        temporary_directory = Path(temporary_name)
        data_path = temporary_directory / "spy_options.csv.gz"
        snapshot.to_csv(data_path, index=False, compression="gzip")
        manifest = {
            "schema_version": 1,
            "provider": settings.provider,
            "underlying": settings.underlying,
            "retrieved_at_utc": retrieved_utc.isoformat(),
            "snapshot_date": local_date.isoformat(),
            "timezone": settings.timezone,
            "expiration_dates": list(expirations),
            "contract_count": len(snapshot),
            "call_count": int(snapshot["option_type"].eq("call").sum()),
            "put_count": int(snapshot["option_type"].eq("put").sum()),
            "data_file": data_path.name,
            "data_sha256": _sha256_file(data_path),
        }
        manifest_path = temporary_directory / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_directory, destination)

    return SnapshotResult(
        snapshot_date=local_date,
        manifest_path=destination / "manifest.json",
        data_path=destination / "spy_options.csv.gz",
        contract_count=len(snapshot),
        expiration_count=len(expirations),
    )


def load_option_snapshot(manifest_path: Path) -> pd.DataFrame:
    """Load a local snapshot only after verifying its manifest and data."""
    manifest_path = Path(manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OptionSnapshotError(
            f"Unable to read option snapshot manifest: {manifest_path}"
        ) from error
    if not isinstance(manifest, dict):
        raise OptionSnapshotError("Option snapshot manifest must be a JSON object.")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        raise OptionSnapshotError("Unsupported option snapshot schema version.")
    if manifest.get("provider") != "yfinance" or manifest.get("underlying") != "SPY":
        raise OptionSnapshotError("Snapshot provider or underlying is not supported.")
    if manifest.get("data_file") != "spy_options.csv.gz":
        raise OptionSnapshotError(
            "Snapshot manifest contains an invalid data filename."
        )

    snapshot_date_text = manifest.get("snapshot_date")
    timezone = manifest.get("timezone")
    retrieved_text = manifest.get("retrieved_at_utc")
    try:
        snapshot_date = date.fromisoformat(snapshot_date_text)
        zone = ZoneInfo(timezone)
        retrieved_at = datetime.fromisoformat(retrieved_text)
    except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
        raise OptionSnapshotError(
            "Snapshot manifest contains an invalid date, time zone, or timestamp."
        ) from error
    if snapshot_date.isoformat() != snapshot_date_text:
        raise OptionSnapshotError("Snapshot date must use YYYY-MM-DD format.")
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise OptionSnapshotError(
            "Snapshot retrieval timestamp must include a time zone."
        )
    if retrieved_at.astimezone(zone).date() != snapshot_date:
        raise OptionSnapshotError(
            "Snapshot date does not match the retrieval time and configured time zone."
        )

    expiration_dates = manifest.get("expiration_dates")
    if not isinstance(expiration_dates, list) or not expiration_dates:
        raise OptionSnapshotError("Snapshot manifest must list its expiration dates.")
    if not all(isinstance(item, str) for item in expiration_dates):
        raise OptionSnapshotError("Snapshot expiration dates must be strings.")
    try:
        parsed_expirations = [date.fromisoformat(item) for item in expiration_dates]
    except (TypeError, ValueError) as error:
        raise OptionSnapshotError(
            "Snapshot manifest contains an invalid expiration date."
        ) from error
    if [
        item.isoformat() for item in parsed_expirations
    ] != expiration_dates or expiration_dates != sorted(set(expiration_dates)):
        raise OptionSnapshotError(
            "Snapshot expiration dates must be unique and sorted as YYYY-MM-DD."
        )

    expected_counts = ("contract_count", "call_count", "put_count")
    counts = {key: manifest.get(key) for key in expected_counts}
    if any(
        isinstance(count, bool) or not isinstance(count, int) or count < 0
        for count in counts.values()
    ):
        raise OptionSnapshotError("Snapshot manifest contains invalid contract counts.")
    if (
        counts["contract_count"] <= 0
        or counts["call_count"] + counts["put_count"] != counts["contract_count"]
    ):
        raise OptionSnapshotError("Snapshot manifest contract counts are inconsistent.")
    data_path = manifest_path.parent / "spy_options.csv.gz"
    expected_digest = manifest.get("data_sha256")
    if (
        not isinstance(expected_digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", expected_digest) is None
    ):
        raise OptionSnapshotError(
            "Snapshot manifest contains an invalid SHA-256 digest."
        )
    try:
        actual_digest = _sha256_file(data_path)
    except OSError as error:
        raise OptionSnapshotError(
            f"Unable to read option snapshot data: {data_path}"
        ) from error
    if actual_digest != expected_digest:
        raise OptionSnapshotError(
            "Option snapshot data does not match its SHA-256 digest."
        )

    try:
        snapshot = pd.read_csv(data_path)
    except (
        OSError,
        UnicodeDecodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as error:
        raise OptionSnapshotError(
            f"Unable to parse option snapshot data: {data_path}"
        ) from error
    required_columns = set(REQUIRED_CHAIN_COLUMNS) | {"expiration", "option_type"}
    missing_columns = sorted(required_columns - set(snapshot.columns))
    if missing_columns:
        raise OptionSnapshotError(
            f"Option snapshot is missing required columns: {missing_columns}."
        )
    if len(snapshot) != counts["contract_count"]:
        raise OptionSnapshotError("Snapshot row count does not match its manifest.")
    if snapshot.empty:
        raise OptionSnapshotError("Option snapshot contains no contracts.")
    if (~snapshot["option_type"].isin(("call", "put"))).any():
        raise OptionSnapshotError("Snapshot option_type must be 'call' or 'put'.")
    if (~snapshot["expiration"].isin(expiration_dates)).any():
        raise OptionSnapshotError("Snapshot contains an unlisted expiration date.")
    if set(snapshot["expiration"].unique()) != set(expiration_dates):
        raise OptionSnapshotError("Snapshot expirations do not match its manifest.")
    if int(snapshot["option_type"].eq("call").sum()) != counts["call_count"]:
        raise OptionSnapshotError("Snapshot call count does not match its manifest.")
    if int(snapshot["option_type"].eq("put").sum()) != counts["put_count"]:
        raise OptionSnapshotError("Snapshot put count does not match its manifest.")
    if snapshot.duplicated(["expiration", "option_type", "contractSymbol"]).any():
        raise OptionSnapshotError("Snapshot contains duplicate option contracts.")
    trade_dates = pd.to_datetime(snapshot["lastTradeDate"], errors="coerce", utc=True)
    if (snapshot["lastTradeDate"].notna() & trade_dates.isna()).any():
        raise OptionSnapshotError("Snapshot last-trade dates must be valid timestamps.")

    symbol_matches = (
        snapshot["contractSymbol"]
        .astype(str)
        .str.strip()
        .map(_SPY_OPTION_SYMBOL.fullmatch)
    )
    if symbol_matches.isna().any():
        raise OptionSnapshotError("Snapshot contains an invalid SPY option symbol.")
    for row_index, match in symbol_matches.items():
        expiration = snapshot.at[row_index, "expiration"]
        option_type = snapshot.at[row_index, "option_type"]
        expected_side = "C" if option_type == "call" else "P"
        if (
            match.group("expiration") != expiration[2:].replace("-", "")
            or match.group("side") != expected_side
        ):
            raise OptionSnapshotError(
                "Snapshot option symbols do not match their expiration and type."
            )

    for column in NUMERIC_CHAIN_COLUMNS:
        original = snapshot[column]
        converted = pd.to_numeric(original, errors="coerce")
        if (original.notna() & converted.isna()).any():
            raise OptionSnapshotError(
                f"Option snapshot column {column!r} contains non-numeric values."
            )
        if not all(math.isfinite(value) for value in converted.dropna()):
            raise OptionSnapshotError(
                f"Option snapshot column {column!r} contains infinite values."
            )
        snapshot[column] = converted
    if snapshot["strike"].isna().any() or (snapshot["strike"] <= 0).any():
        raise OptionSnapshotError("Every snapshot strike must be present and positive.")
    for column in (
        "lastPrice",
        "bid",
        "ask",
        "volume",
        "openInterest",
        "impliedVolatility",
    ):
        if (snapshot[column].dropna() < 0).any():
            raise OptionSnapshotError(
                f"Snapshot column {column!r} must not contain negative values."
            )
    return snapshot
