"""Download, cache, parse, and validate monthly Ken French factor data."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeAlias
from urllib.error import URLError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

FactorModel: TypeAlias = Literal["ff3", "ff5"]
FF3_COLUMNS = ("Mkt-RF", "SMB", "HML")
FF5_COLUMNS = (*FF3_COLUMNS, "RMW", "CMA")
_FACTOR_COLUMNS = {"ff3": FF3_COLUMNS, "ff5": FF5_COLUMNS}
_ARCHIVE_SPECS = {
    "ff3": (
        (
            "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
            "F-F_Research_Data_Factors_CSV.zip"
        ),
        "F-F_Research_Data_Factors",
    ),
    "ff5": (
        (
            "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
            "F-F_Research_Data_5_Factors_2x3_CSV.zip"
        ),
        "F-F_Research_Data_5_Factors_2x3",
    ),
}
_MISSING_SENTINELS = {-99.99, -999.0, -999.99}
_MAX_ARCHIVE_BYTES = 5_000_000
_MAX_CSV_BYTES = 10_000_000
_MONTH_CODE = re.compile(r"\d{6}\Z")


class FactorDataError(RuntimeError):
    """Raised when factor data cannot be retrieved or fails validation."""


@dataclass(frozen=True)
class FactorDataset:
    """Monthly factor values and the cache/download provenance."""

    model: FactorModel
    factors: pd.DataFrame
    source: Literal["cache", "ken_french"]
    retrieved_at: datetime
    source_url: str
    sha256: str


def _validate_model(model: str) -> FactorModel:
    if not isinstance(model, str) or model not in _ARCHIVE_SPECS:
        raise ValueError("model must be 'ff3' or 'ff5'.")
    return model


def parse_fama_french_monthly_csv(
    content: bytes | str, model: FactorModel
) -> pd.DataFrame:
    """Parse monthly factor rows, convert percent units, and mark sentinels.

    The Ken French files also contain annual data below the monthly table.
    Parsing stops at the first non-monthly row so annual observations cannot
    accidentally enter a monthly regression.
    """
    model = _validate_model(model)
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise FactorDataError("Factor CSV is not valid UTF-8 text.") from error
    elif isinstance(content, str):
        text = content.lstrip("\ufeff")
    else:
        raise TypeError("Factor CSV content must be bytes or text.")

    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as error:
        raise FactorDataError("Factor CSV contains malformed rows.") from error
    required_columns = (*_FACTOR_COLUMNS[model], "RF")
    header_index = None
    header: list[str] = []
    for row_index, row in enumerate(rows):
        candidate = [cell.strip() for cell in row]
        if all(column in candidate for column in required_columns):
            header_index = row_index
            header = candidate
            break
    if header_index is None:
        raise FactorDataError(f"Could not find the {model.upper()} monthly header.")
    if len(header) != len(set(header)):
        raise FactorDataError("Factor CSV header contains duplicate columns.")
    positions = {column: header.index(column) for column in required_columns}

    month_codes: list[str] = []
    observations: list[list[float]] = []
    for row in rows[header_index + 1 :]:
        if not row:
            if month_codes:
                break
            continue
        month_code = row[0].strip()
        if not _MONTH_CODE.fullmatch(month_code):
            if month_codes:
                break
            continue
        if len(row) <= max(positions.values()):
            raise FactorDataError(
                f"Factor row {month_code} is missing one or more values."
            )
        try:
            period = pd.Period(month_code, freq="M")
        except (ValueError, TypeError) as error:
            raise FactorDataError(f"Invalid factor month: {month_code!r}.") from error
        if period.strftime("%Y%m") != month_code:
            raise FactorDataError(f"Invalid factor month: {month_code!r}.")

        values: list[float] = []
        for column in required_columns:
            try:
                value = float(row[positions[column]].strip())
            except ValueError as error:
                raise FactorDataError(
                    f"Factor {column} for {month_code} is not numeric."
                ) from error
            if value in _MISSING_SENTINELS:
                values.append(float("nan"))
            elif not math.isfinite(value):
                raise FactorDataError(
                    f"Factor {column} for {month_code} is not finite."
                )
            else:
                values.append(value / 100.0)
        month_codes.append(month_code)
        observations.append(values)

    if not month_codes:
        raise FactorDataError(f"The {model.upper()} CSV contains no monthly rows.")
    if month_codes != sorted(set(month_codes)):
        raise FactorDataError("Monthly factor dates must be unique and chronological.")
    periods = pd.PeriodIndex(month_codes, freq="M")
    dates = periods.to_timestamp(how="end").normalize()
    factors = pd.DataFrame(observations, index=dates, columns=required_columns)
    factors.index.name = "date"
    if np.isinf(factors.to_numpy(dtype=float)).any():
        raise FactorDataError("Factor data contains infinite values.")
    return factors


def _extract_csv(archive_bytes: bytes, model: FactorModel) -> bytes:
    if len(archive_bytes) > _MAX_ARCHIVE_BYTES:
        raise FactorDataError("Factor archive exceeds the configured size limit.")
    expected_stem = _ARCHIVE_SPECS[model][1].lower()
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = archive.infolist()
            if len(members) > 10:
                raise FactorDataError("Factor archive contains too many files.")
            matching = [
                member
                for member in members
                if Path(member.filename).name.lower().startswith(expected_stem)
                and Path(member.filename).suffix.lower() == ".csv"
            ]
            if len(matching) != 1:
                raise FactorDataError(
                    f"Factor archive must contain one {model.upper()} CSV file."
                )
            member = matching[0]
            if member.flag_bits & 0x1:
                raise FactorDataError("Encrypted factor archives are not supported.")
            if member.file_size > _MAX_CSV_BYTES:
                raise FactorDataError("Factor CSV exceeds the configured size limit.")
            with archive.open(member) as csv_file:
                content = csv_file.read(_MAX_CSV_BYTES + 1)
    except FactorDataError:
        raise
    except (
        OSError,
        RuntimeError,
        NotImplementedError,
        zipfile.BadZipFile,
    ) as error:
        raise FactorDataError("Ken French returned an invalid ZIP archive.") from error
    if len(content) > _MAX_CSV_BYTES:
        raise FactorDataError("Factor CSV exceeds the configured size limit.")
    return content


def _download_archive(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": "QuantModelsExplained/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise FactorDataError(
                    f"Ken French data request returned HTTP {response.status}."
                )
            content = response.read(_MAX_ARCHIVE_BYTES + 1)
    except (OSError, TimeoutError, URLError) as error:
        raise FactorDataError(
            "Unable to download factor data from Ken French."
        ) from error
    if len(content) > _MAX_ARCHIVE_BYTES:
        raise FactorDataError("Factor archive exceeds the configured size limit.")
    return content


def _archive_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_cache(
    archive_path: Path, manifest_path: Path, model: FactorModel, source_url: str
) -> FactorDataset:
    try:
        if archive_path.stat().st_size > _MAX_ARCHIVE_BYTES:
            raise FactorDataError(
                "Cached factor archive exceeds the configured size limit."
            )
    except OSError as error:
        raise FactorDataError("Unable to read the cached factor archive.") from error
    try:
        archive_bytes = archive_path.read_bytes()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FactorDataError(
            "Unable to read the cached factor archive or manifest."
        ) from error
    if not isinstance(manifest, dict):
        raise FactorDataError("Factor cache manifest must be a JSON object.")
    if (
        type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
        or manifest.get("model") != model
        or manifest.get("source_url") != source_url
    ):
        raise FactorDataError(
            "Factor cache manifest does not match the requested model."
        )
    expected_digest = manifest.get("sha256")
    actual_digest = _archive_sha256(archive_bytes)
    if expected_digest != actual_digest:
        raise FactorDataError(
            "Cached factor archive does not match its SHA-256 manifest."
        )
    try:
        retrieved_at = datetime.fromisoformat(manifest["retrieved_at_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise FactorDataError("Factor cache timestamp is invalid.") from error
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise FactorDataError("Factor cache timestamp must include a time zone.")
    factors = parse_fama_french_monthly_csv(_extract_csv(archive_bytes, model), model)
    return FactorDataset(
        model=model,
        factors=factors,
        source="cache",
        retrieved_at=retrieved_at.astimezone(UTC),
        source_url=source_url,
        sha256=actual_digest,
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}-",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_fama_french_factors(
    model: FactorModel,
    cache_directory: Path,
    *,
    refresh: bool = False,
    offline: bool = False,
    timeout_seconds: float = 30.0,
) -> FactorDataset:
    """Load cached or fetch official monthly factors without extracting files.

    Cache integrity is checked before use. An invalid cache raises an explicit
    error; pass ``refresh=True`` to replace it rather than silently discarding
    the existing data.
    """
    model = _validate_model(model)
    if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds):
        raise ValueError("timeout_seconds must be finite and positive.")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive.")
    source_url, _ = _ARCHIVE_SPECS[model]
    archive_path = Path(cache_directory) / f"ken_french_{model}_monthly.zip"
    manifest_path = archive_path.with_suffix(".json")
    cache_exists = archive_path.exists() or manifest_path.exists()
    if cache_exists and not refresh:
        if not archive_path.is_file() or not manifest_path.is_file():
            raise FactorDataError(
                "Factor cache is incomplete; refresh it explicitly to replace it."
            )
        return _read_cache(archive_path, manifest_path, model, source_url)
    if offline:
        raise FactorDataError(
            "Offline mode requested, but no valid factor cache is available."
        )

    content = _download_archive(source_url, timeout_seconds)
    factors = parse_fama_french_monthly_csv(_extract_csv(content, model), model)
    retrieved_at = datetime.now(UTC)
    digest = _archive_sha256(content)
    manifest = {
        "schema_version": 1,
        "model": model,
        "source_url": source_url,
        "retrieved_at_utc": retrieved_at.isoformat(),
        "sha256": digest,
    }
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(archive_path, content)
    _atomic_write(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return FactorDataset(
        model=model,
        factors=factors,
        source="ken_french",
        retrieved_at=retrieved_at,
        source_url=source_url,
        sha256=digest,
    )
