import os
import time
from pathlib import Path

import pandas as pd
import pytest

from portfolio_research.config import load_universe
from portfolio_research.market_data import (
    MarketDataError,
    load_prices,
    normalize_yfinance_prices,
    validate_prices,
    validate_symbols,
)


def test_configured_universe_has_30_stocks_and_four_etfs() -> None:
    universe = load_universe()

    assert len(universe.stocks_by_sector) == 11
    assert len(universe.stock_symbols) == 30
    assert len(universe.etfs) == 4
    assert len(universe.symbols) == 34
    assert {"SPY", "QQQ", "TLT", "GLD"} == set(universe.etfs)
    assert len(universe.symbols) == len(set(universe.symbols))


def test_validate_symbols_normalizes_and_rejects_duplicates() -> None:
    assert validate_symbols([" aapl ", "brk-b"]) == ("AAPL", "BRK-B")

    with pytest.raises(ValueError, match="duplicates"):
        validate_symbols(["aapl", "AAPL"])


def test_validate_prices_reports_missing_values_without_filling_them() -> None:
    source = pd.DataFrame(
        {"SPY": [100.0, None], "GLD": [50.0, 51.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    prices, report = validate_prices(source, ["SPY", "GLD"])

    assert pd.isna(prices.loc["2024-01-03", "SPY"])
    assert report.missing_by_symbol == (("SPY", 1), ("GLD", 0))
    assert report.observation_count == 2


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ([100.0, 0.0], "positive"),
        ([100.0, float("inf")], "infinite"),
    ],
)
def test_validate_prices_rejects_invalid_values(
    values: list[float], message: str
) -> None:
    source = pd.DataFrame({"SPY": values}, index=pd.date_range("2024-01-02", periods=2))

    with pytest.raises(MarketDataError, match=message):
        validate_prices(source, ["SPY"])


def test_validate_prices_rejects_duplicate_daily_dates() -> None:
    source = pd.DataFrame(
        {"SPY": [100.0, 101.0]},
        index=pd.to_datetime(["2024-01-02 09:30", "2024-01-02 16:00"]),
    )

    with pytest.raises(MarketDataError, match="duplicate daily dates"):
        validate_prices(source, ["SPY"])


def test_normalize_yfinance_prices_handles_multiindex_columns() -> None:
    columns = pd.MultiIndex.from_tuples(
        [("Close", "SPY"), ("Close", "GLD"), ("Volume", "SPY")]
    )
    downloaded = pd.DataFrame(
        [[100.0, 50.0, 1000], [101.0, 51.0, 1100]],
        columns=columns,
        index=pd.date_range("2024-01-02", periods=2),
    )

    prices = normalize_yfinance_prices(downloaded, ["SPY", "GLD"])

    assert list(prices.columns) == ["SPY", "GLD"]
    assert prices.iloc[-1].tolist() == [101.0, 51.0]


def test_load_prices_uses_cache_and_marks_stale_offline_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from portfolio_research import market_data

    calls = 0
    expected_prices = pd.DataFrame(
        {"SPY": [100.0, 101.0]},
        index=pd.date_range("2024-01-02", periods=2),
    )

    def fake_download(*args: object) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return expected_prices

    monkeypatch.setattr(market_data, "_download_yfinance", fake_download)
    first = load_prices(
        ["SPY"],
        "2024-01-01",
        "2024-01-05",
        cache_directory=tmp_path,
    )
    second = load_prices(
        ["SPY"],
        "2024-01-01",
        "2024-01-05",
        cache_directory=tmp_path,
    )

    assert first.source == "yfinance"
    assert second.source == "cache"
    assert calls == 1
    pd.testing.assert_frame_equal(first.prices, second.prices)

    cache_file = next(tmp_path.iterdir())
    old_timestamp = time.time() - 3 * 24 * 60 * 60
    os.utime(cache_file, (old_timestamp, old_timestamp))
    stale = load_prices(
        ["SPY"],
        "2024-01-01",
        "2024-01-05",
        cache_directory=tmp_path,
        offline=True,
    )

    assert stale.source == "stale_cache"
    assert calls == 1


def test_load_prices_rejects_missing_cache_in_offline_mode(tmp_path: Path) -> None:
    with pytest.raises(MarketDataError, match="No cached data"):
        load_prices(
            ["SPY"],
            "2024-01-01",
            "2024-01-05",
            cache_directory=tmp_path,
            offline=True,
        )
