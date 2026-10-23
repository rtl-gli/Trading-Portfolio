"""Chronological holdout evaluation for fixed, causally generated signals."""

from dataclasses import dataclass

import pandas as pd

from portfolio_research.backtest import (
    BacktestResult,
    run_buy_and_hold_backtest,
    run_signal_backtest,
)
from portfolio_research.config import SmaSettings
from portfolio_research.market_data import validate_prices
from portfolio_research.strategies import walk_forward_start


@dataclass(frozen=True)
class WalkForwardSignalResult:
    """Held-out backtests and the first date of the untouched evaluation period."""

    split_date: pd.Timestamp
    warmup_observations: int
    strategy: BacktestResult
    buy_and_hold: BacktestResult


def evaluate_signals_out_of_sample(
    prices: pd.Series,
    signals: pd.Series,
    *,
    settings: SmaSettings | None = None,
    train_fraction: float = 0.7,
) -> WalkForwardSignalResult:
    """Reserve a chronological holdout, using the prefix only as signal history.

    Parameters are treated as fixed before the holdout; this helper does not
    tune them. It restarts the portfolio in cash at the holdout boundary and
    charges costs for its held-out entry and liquidation.
    """
    if not isinstance(prices, pd.Series):
        raise TypeError("Walk-forward prices must be a pandas Series.")
    validated, _ = validate_prices(prices.rename("ASSET").to_frame(), ["ASSET"])
    validated_prices = validated["ASSET"]
    if validated_prices.isna().any():
        raise ValueError("Walk-forward prices contain missing observations.")
    if not signals.index.equals(validated_prices.index):
        raise ValueError("Signal dates must match the walk-forward price dates.")
    split = walk_forward_start(validated_prices.index, train_fraction)
    holdout_prices = validated_prices.iloc[split:]
    holdout_signals = signals.iloc[split:]
    return WalkForwardSignalResult(
        split_date=holdout_prices.index[0],
        warmup_observations=split,
        strategy=run_signal_backtest(holdout_prices, holdout_signals, settings),
        buy_and_hold=run_buy_and_hold_backtest(holdout_prices, settings),
    )
