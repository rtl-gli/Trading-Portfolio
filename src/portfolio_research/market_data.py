"""Validated, locally cached daily adjusted-price data."""

from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import yfinance as yf
from pandas.api.types import is_numeric_dtype

from portfolio_research.config import load_data_settings

_SYMBOL_PATTERN = re.compile(r"[A-Z0-9.^=-]{1,15}\Z")


class MarketDataError(RuntimeError):
    """Raised when market data cannot be fetched or fails validation."""


@dataclass(frozen=True)
class DataQualityReport:
    """A compact record of the validated price panel's coverage."""

    symbols: tuple[str, ...]
    first_date: date
    last_date: date
    observation_count: int
    missing_by_symbol: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class MarketDataResult:
    """Prices, quality diagnostics, and an explicit cache/source label."""

    prices: pd.DataFrame
    quality: DataQualityReport
    source: Literal["yfinance", "cache", "stale_cache"]
    retrieved_at: datetime


def validate_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    """Normalize symbols and reject empty, invalid, or duplicate requests."""
    if isinstance(symbols, (str, bytes)) or len(symbols) == 0:
        raise ValueError("Provide a non-empty sequence of ticker symbols.")

    normalized: list[str] = []
    for symbol in symbols:
        if not isinstance(symbol, str):
            raise TypeError("Every ticker symbol must be a string.")
        candidate = symbol.strip().upper()
        if not _SYMBOL_PATTERN.fullmatch(candidate):
            raise ValueError(f"Invalid ticker symbol: {symbol!r}")
        normalized.append(candidate)

    if len(normalized) != len(set(normalized)):
        raise ValueError("Ticker symbols must not contain duplicates.")
    return tuple(normalized)


def validate_prices(
    prices: pd.DataFrame, symbols: Sequence[str] | None = None
) -> tuple[pd.DataFrame, DataQualityReport]:
    """Validate daily prices without imputing or dropping missing values."""
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise MarketDataError("The price data is empty or is not a DataFrame.")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise MarketDataError("Price data must have a DatetimeIndex.")
    if prices.columns.has_duplicates:
        raise MarketDataError("Price data contains duplicate ticker columns.")
    if any(not isinstance(column, str) for column in prices.columns):
        raise MarketDataError("Every price column must be a ticker string.")

    expected_symbols = (
        validate_symbols(symbols)
        if symbols is not None
        else validate_symbols(tuple(prices.columns))
    )
    actual_symbols = validate_symbols(tuple(prices.columns))
    if set(actual_symbols) != set(expected_symbols):
        missing = sorted(set(expected_symbols) - set(actual_symbols))
        unexpected = sorted(set(actual_symbols) - set(expected_symbols))
        raise MarketDataError(
            f"Ticker columns do not match the request; missing={missing}, "
            f"unexpected={unexpected}."
        )

    validated = prices.copy()
    validated.columns = actual_symbols
    index = validated.index
    if index.hasnans:
        raise MarketDataError("Price dates contain missing timestamps.")
    if index.tz is not None:
        index = index.tz_localize(None)
    index = index.normalize()
    if index.has_duplicates:
        raise MarketDataError("Price data contains duplicate daily dates.")
    if not index.is_monotonic_increasing:
        raise MarketDataError("Price dates must be in chronological order.")
    validated.index = index
    validated.index.name = None
    validated = validated.loc[:, expected_symbols]
    if validated.isna().all(axis=1).any():
        raise MarketDataError("Price data contains dates with no observations.")

    for symbol in expected_symbols:
        if not is_numeric_dtype(validated[symbol].dtype):
            raise MarketDataError(f"Prices for {symbol} must be numeric.")
        observations = validated[symbol].dropna().to_numpy()
        if observations.size == 0:
            raise MarketDataError(f"Price data has no observations for {symbol}.")
        if not np.isfinite(observations).all():
            raise MarketDataError(f"Prices for {symbol} contain infinite values.")
        if (observations <= 0).any():
            raise MarketDataError(f"Prices for {symbol} must be positive.")

    report = DataQualityReport(
        symbols=expected_symbols,
        first_date=index[0].date(),
        last_date=index[-1].date(),
        observation_count=len(index),
        missing_by_symbol=tuple(
            (symbol, int(validated[symbol].isna().sum())) for symbol in expected_symbols
        ),
    )
    return validated, report


def normalize_yfinance_prices(
    downloaded: pd.DataFrame, symbols: Sequence[str]
) -> pd.DataFrame:
    """Extract adjusted close prices from yfinance's column layouts."""
    expected_symbols = validate_symbols(symbols)
    if not isinstance(downloaded, pd.DataFrame) or downloaded.empty:
        raise MarketDataError("yfinance returned no price data.")

    if isinstance(downloaded.columns, pd.MultiIndex):
        extracted: dict[str, pd.Series] = {}
        for symbol in expected_symbols:
            matches = [
                column
                for column in downloaded.columns
                if symbol in column
                and "close" in {str(part).lower() for part in column}
            ]
            if len(matches) != 1:
                raise MarketDataError(
                    f"Expected one adjusted-close column for {symbol}; "
                    f"found {len(matches)}."
                )
            extracted[symbol] = downloaded[matches[0]]
        return pd.DataFrame(extracted, index=downloaded.index)

    if len(expected_symbols) == 1 and "Close" in downloaded.columns:
        return pd.DataFrame(
            {expected_symbols[0]: downloaded["Close"]}, index=downloaded.index
        )

    if set(expected_symbols).issubset(downloaded.columns):
        return downloaded.loc[:, expected_symbols].copy()

    raise MarketDataError(
        "Could not identify adjusted-close columns in the yfinance response."
    )


def _parse_date(value: str | date | datetime, name: str) -> date:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a valid date.") from error
    if pd.isna(parsed):
        raise ValueError(f"{name} must be a valid date.")
    return parsed.date()


def _cache_path(
    symbols: tuple[str, ...], start: date, end: date, interval: str
) -> Path:
    request = {
        "provider": "yfinance",
        "adjusted": True,
        "symbols": symbols,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "interval": interval,
        "format_version": 1,
    }
    fingerprint = hashlib.sha256(
        json.dumps(request, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return Path(f"yfinance_{fingerprint}.csv.gz")


def _download_yfinance(
    symbols: tuple[str, ...], start: date, end: date, interval: str
) -> pd.DataFrame:
    downloaded = yf.download(
        list(symbols),
        start=start.isoformat(),
        end=end.isoformat(),
        interval=interval,
        auto_adjust=True,
        actions=False,
        progress=False,
        group_by="column",
        threads=False,
    )
    return normalize_yfinance_prices(downloaded, symbols)


def load_prices(
    symbols: Sequence[str],
    start: str | date | datetime,
    end: str | date | datetime,
    *,
    cache_directory: Path | None = None,
    cache_ttl_hours: float | None = None,
    offline: bool = False,
) -> MarketDataResult:
    """Fetch or load adjusted daily prices, validate them, and report source.

    The end date follows yfinance's exclusive convention. Offline mode may
    return an expired cache, but marks it as ``stale_cache`` rather than
    presenting it as fresh.
    """
    requested_symbols = validate_symbols(symbols)
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")
    if start_date >= end_date:
        raise ValueError("start must be earlier than end (end is exclusive).")
    settings = load_data_settings()
    selected_cache_directory = (
        Path(cache_directory)
        if cache_directory is not None
        else settings.cache_directory
    )
    selected_ttl_hours = (
        settings.cache_ttl_hours if cache_ttl_hours is None else cache_ttl_hours
    )
    if (
        isinstance(selected_ttl_hours, bool)
        or not isinstance(selected_ttl_hours, (int, float))
        or not math.isfinite(selected_ttl_hours)
        or selected_ttl_hours < 0
    ):
        raise ValueError("cache_ttl_hours must be a finite non-negative number.")

    cache_path = selected_cache_directory / _cache_path(
        requested_symbols, start_date, end_date, settings.interval
    )
    cache_exists = cache_path.is_file()
    cache_age_seconds = (
        max(0.0, datetime.now(UTC).timestamp() - cache_path.stat().st_mtime)
        if cache_exists
        else None
    )
    ttl_seconds = selected_ttl_hours * 60 * 60
    use_cache = cache_exists and (
        offline or (cache_age_seconds is not None and cache_age_seconds < ttl_seconds)
    )

    if use_cache:
        try:
            cached_prices = pd.read_csv(
                cache_path,
                compression="gzip",
                index_col=0,
                parse_dates=True,
            )
        except (OSError, ValueError, pd.errors.ParserError) as error:
            raise MarketDataError(
                f"Could not read price cache {cache_path}."
            ) from error
        prices, quality = validate_prices(cached_prices, requested_symbols)
        retrieved_at = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=UTC)
        source: Literal["cache", "stale_cache"] = (
            "cache"
            if cache_age_seconds is not None and cache_age_seconds < ttl_seconds
            else "stale_cache"
        )
        return MarketDataResult(prices, quality, source, retrieved_at)

    if offline:
        raise MarketDataError(
            f"No cached data is available for this request: {cache_path.name}"
        )

    prices, quality = validate_prices(
        _download_yfinance(requested_symbols, start_date, end_date, settings.interval),
        requested_symbols,
    )
    if prices.index[0].date() < start_date or prices.index[-1].date() >= end_date:
        raise MarketDataError(
            "Provider returned observations outside the requested date range."
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=cache_path.parent,
        prefix=f".{cache_path.stem}-",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
    try:
        prices.to_csv(temporary_path, compression="gzip", index_label="date")
        temporary_path.replace(cache_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return MarketDataResult(
        prices=prices,
        quality=quality,
        source="yfinance",
        retrieved_at=datetime.now(UTC),
    )
