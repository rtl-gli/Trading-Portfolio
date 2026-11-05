"""Build a validated monthly return series for the configured stock universe."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from numbers import Real

import numpy as np
import pandas as pd

from portfolio_research.market_data import (
    MarketDataError,
    validate_prices,
    validate_symbols,
)


def monthly_portfolio_returns(
    prices: pd.DataFrame,
    symbols: Sequence[str],
    start_date: str | date | datetime,
    weights: Mapping[str, float] | None = None,
) -> pd.Series:
    """Create monthly rebalanced portfolio returns from adjusted daily closes.

    Equal weights are used by default. Custom weights must cover exactly the
    requested symbols, be long-only, and sum to one. Missing prices are never
    imputed; the model refuses an incomplete universe.
    """
    selected_symbols = validate_symbols(symbols)
    validated_prices, _ = validate_prices(prices, selected_symbols)
    missing_counts = validated_prices.isna().sum()
    if missing_counts.any():
        missing = {
            symbol: int(count) for symbol, count in missing_counts.items() if count
        }
        raise MarketDataError(
            f"Monthly factor portfolio requires complete prices; missing={missing}."
        )

    try:
        start = pd.Timestamp(start_date)
    except (TypeError, ValueError) as error:
        raise ValueError("start_date must be a valid date.") from error
    if pd.isna(start):
        raise ValueError("start_date must be a valid date.")
    if start.tzinfo is not None:
        start = start.tz_localize(None)
    first_month = start.to_period("M")

    if weights is None:
        weight_values = {
            symbol: 1.0 / len(selected_symbols) for symbol in selected_symbols
        }
    else:
        if not isinstance(weights, Mapping) or set(weights) != set(selected_symbols):
            raise ValueError("Custom weights must cover exactly the selected symbols.")
        weight_values = {}
        for symbol in selected_symbols:
            weight = weights[symbol]
            if isinstance(weight, bool) or not isinstance(weight, Real):
                raise TypeError(f"Weight for {symbol} must be a finite number.")
            if not math.isfinite(weight) or weight < 0:
                raise ValueError(
                    f"Weight for {symbol} must be finite and non-negative."
                )
            weight_values[symbol] = float(weight)
        if not math.isclose(sum(weight_values.values()), 1.0, abs_tol=1e-8):
            raise ValueError("Custom portfolio weights must sum to 1.")

    monthly_prices = validated_prices.resample("ME").last()
    if monthly_prices.isna().any().any():
        raise MarketDataError(
            "Monthly price aggregation produced missing values; no values were filled."
        )
    asset_returns = monthly_prices.pct_change(fill_method=None)
    portfolio_weights = pd.Series(weight_values, index=selected_symbols)
    portfolio_returns = asset_returns.dot(portfolio_weights).dropna()
    portfolio_returns = portfolio_returns.loc[
        portfolio_returns.index.to_period("M") >= first_month
    ]
    if portfolio_returns.empty:
        raise MarketDataError("No complete monthly returns exist for this date range.")
    if not np.isfinite(portfolio_returns.to_numpy(dtype=float)).all():
        raise MarketDataError("Monthly portfolio returns contain non-finite values.")
    portfolio_returns.name = "portfolio_return"
    return portfolio_returns
