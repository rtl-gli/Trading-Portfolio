import hashlib
import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from quant_models.data.options_snapshot import (
    OptionSnapshotError,
    SnapshotSettings,
    capture_option_snapshot,
    load_snapshot_settings,
)

CHAIN_COLUMNS = (
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


def _chain(contract_prefix: str, strike: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            [
                f"{contract_prefix}260101C{int(strike * 1000):08d}",
                pd.Timestamp("2026-10-30T15:00:00Z"),
                strike,
                1.0,
                0.9,
                1.1,
                0.1,
                10.0,
                2,
                10,
                0.2,
                False,
                "REGULAR",
                "USD",
            ]
        ],
        columns=CHAIN_COLUMNS,
    )


class FakeOptionChain:
    """Deterministic yfinance-like option chain for network-free tests."""

    options = ("2026-12-18", "2026-11-20")

    def option_chain(self, date: str) -> object:
        return type(
            "OptionChain",
            (),
            {
                "calls": _chain("SPY", 500.0),
                "puts": _chain("SPY", 450.0),
            },
        )()


def test_snapshot_saves_all_expirations_and_hash_manifest(tmp_path) -> None:
    settings = SnapshotSettings(
        provider="yfinance",
        underlying="SPY",
        timezone="America/New_York",
        snapshot_directory=tmp_path,
    )
    result = capture_option_snapshot(
        FakeOptionChain(),
        settings,
        retrieved_at=datetime(2026, 11, 5, 15, 0, tzinfo=UTC),
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert result.snapshot_date.isoformat() == "2026-11-05"
    assert result.contract_count == 4
    assert result.expiration_count == 2
    assert manifest["expiration_dates"] == ["2026-11-20", "2026-12-18"]
    assert manifest["call_count"] == 2
    assert manifest["put_count"] == 2
    assert (
        manifest["data_sha256"]
        == hashlib.sha256(result.data_path.read_bytes()).hexdigest()
    )
    saved = pd.read_csv(result.data_path)
    assert len(saved) == 4
    assert set(saved["option_type"]) == {"call", "put"}


def test_snapshot_will_not_overwrite_existing_daily_directory(tmp_path) -> None:
    settings = SnapshotSettings(
        provider="yfinance",
        underlying="SPY",
        timezone="America/New_York",
        snapshot_directory=tmp_path,
    )
    capture_option_snapshot(
        FakeOptionChain(),
        settings,
        retrieved_at=datetime(2026, 11, 5, 15, 0, tzinfo=UTC),
    )

    with pytest.raises(FileExistsError, match="never overwritten"):
        capture_option_snapshot(
            FakeOptionChain(),
            settings,
            retrieved_at=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
        )


def test_snapshot_rejects_bad_market_values_and_missing_columns(tmp_path) -> None:
    settings = SnapshotSettings(
        provider="yfinance",
        underlying="SPY",
        timezone="America/New_York",
        snapshot_directory=tmp_path,
    )
    invalid_ticker = FakeOptionChain()
    invalid_ticker.option_chain = lambda date: type(
        "OptionChain",
        (),
        {
            "calls": _chain("SPY", 0.0),
            "puts": _chain("SPY", 450.0),
        },
    )()
    with pytest.raises(OptionSnapshotError, match="positive"):
        capture_option_snapshot(
            invalid_ticker,
            settings,
            retrieved_at=datetime(2026, 11, 5, 15, 0, tzinfo=UTC),
        )

    missing_column_ticker = FakeOptionChain()
    missing_column_ticker.option_chain = lambda date: type(
        "OptionChain",
        (),
        {
            "calls": pd.DataFrame({"strike": [500.0]}),
            "puts": _chain("SPY", 450.0),
        },
    )()
    with pytest.raises(OptionSnapshotError, match="missing required columns"):
        capture_option_snapshot(
            missing_column_ticker,
            settings,
            retrieved_at=datetime(2026, 11, 6, 15, 0, tzinfo=UTC),
        )

    invalid_symbol_ticker = FakeOptionChain()
    invalid_calls = _chain("SPY", 500.0)
    invalid_calls.loc[0, "contractSymbol"] = "=1+1"
    invalid_symbol_ticker.option_chain = lambda date: type(
        "OptionChain",
        (),
        {
            "calls": invalid_calls,
            "puts": _chain("SPY", 450.0),
        },
    )()
    with pytest.raises(OptionSnapshotError, match="SPY format"):
        capture_option_snapshot(
            invalid_symbol_ticker,
            settings,
            retrieved_at=datetime(2026, 11, 7, 15, 0, tzinfo=UTC),
        )


def test_snapshot_refuses_timezone_naive_timestamps(tmp_path) -> None:
    settings = SnapshotSettings(
        provider="yfinance",
        underlying="SPY",
        timezone="America/New_York",
        snapshot_directory=tmp_path,
    )

    with pytest.raises(OptionSnapshotError, match="include a time zone"):
        capture_option_snapshot(
            FakeOptionChain(),
            settings,
            retrieved_at=datetime(2026, 11, 5, 15, 0),
        )


def test_snapshot_configuration_resolves_local_path_and_validates(tmp_path) -> None:
    config = tmp_path / "options.yaml"
    config.write_text(
        "provider: yfinance\n"
        "underlying: SPY\n"
        "timezone: America/New_York\n"
        "snapshot_directory: options\n",
        encoding="utf-8",
    )

    settings = load_snapshot_settings(config)

    assert settings.snapshot_directory.is_absolute()
    assert settings.snapshot_directory.name == "options"

    config.write_text(
        "provider: unknown\n"
        "underlying: SPY\n"
        "timezone: America/New_York\n"
        "snapshot_directory: options\n",
        encoding="utf-8",
    )
    with pytest.raises(OptionSnapshotError, match="yfinance"):
        load_snapshot_settings(config)
