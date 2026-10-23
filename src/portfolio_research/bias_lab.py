"""Explicitly biased backtest variants for educational comparisons."""

from dataclasses import dataclass, replace
from itertools import product

import pandas as pd

from portfolio_research.backtest import (
    BacktestResult,
    PortfolioBacktestResult,
    run_portfolio_backtest,
    run_signal_backtest,
    run_sma_vs_buy_and_hold,
)
from portfolio_research.config import SmaSettings


@dataclass(frozen=True)
class BiasDemonstration:
    """Baseline and deliberately invalid signal-execution comparisons."""

    baseline: BacktestResult
    costs_ignored: BacktestResult
    future_signal_used: BacktestResult
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OverfitDemonstration:
    """Full-sample SMA parameter selection, explicitly marked in-sample."""

    selected_fast_window: int
    selected_slow_window: int
    selected_growth: float
    baseline_growth: float
    combinations_tested: int
    warning: str


@dataclass(frozen=True)
class PortfolioBiasDemonstration:
    """Portfolio-weight equivalents of costs-off and look-ahead variants."""

    baseline: PortfolioBacktestResult
    costs_ignored: PortfolioBacktestResult
    future_weights_used: PortfolioBacktestResult | None


def compare_signal_biases(
    prices: pd.Series, signals: pd.Series, settings: SmaSettings
) -> BiasDemonstration:
    """Compare costs-off and future-signal variants against the honest baseline."""
    baseline = run_signal_backtest(prices, signals, settings)
    costs_ignored = run_signal_backtest(
        prices,
        signals,
        replace(
            settings,
            transaction_cost_bps_per_side=0.0,
            slippage_bps_per_side=0.0,
        ),
    )
    future_signal_used = run_signal_backtest(prices, signals.shift(-1), settings)
    return BiasDemonstration(
        baseline=baseline,
        costs_ignored=costs_ignored,
        future_signal_used=future_signal_used,
        warnings=(
            "Costs-off results are not implementable; real execution has friction.",
            "Look-ahead results use tomorrow's signal today and are invalid.",
        ),
    )


def compare_portfolio_biases(
    prices: pd.DataFrame, target_weights: pd.DataFrame, settings: SmaSettings
) -> PortfolioBiasDemonstration:
    """Compare portfolio weights with costs removed and future weights leaked."""
    baseline = run_portfolio_backtest(prices, target_weights, settings)
    costs_ignored = run_portfolio_backtest(
        prices,
        target_weights,
        replace(
            settings,
            transaction_cost_bps_per_side=0.0,
            slippage_bps_per_side=0.0,
        ),
    )
    shifted_weights = target_weights.shift(-1)
    has_future_target = shifted_weights.notna().all(axis=1).any()
    future_weights_used = (
        run_portfolio_backtest(prices, shifted_weights, settings)
        if has_future_target
        else None
    )
    return PortfolioBiasDemonstration(
        baseline=baseline,
        costs_ignored=costs_ignored,
        future_weights_used=future_weights_used,
    )


def select_sma_on_full_sample(
    prices: pd.Series,
    settings: SmaSettings,
    fast_candidates: tuple[int, ...] = (10, 20, 50),
    slow_candidates: tuple[int, ...] = (50, 100, 200),
) -> OverfitDemonstration:
    """Select the strongest net terminal wealth using the entire sample.

    This intentionally invalid selection exercise illustrates overfitting.
    Its selected performance must never be reported as out-of-sample evidence.
    """
    baseline = run_sma_vs_buy_and_hold(prices, settings)
    baseline_growth = float((1 + baseline.sma.net_returns).prod())
    candidates = [
        (fast, slow)
        for fast, slow in product(fast_candidates, slow_candidates)
        if fast < slow and slow + settings.execution_delay_bars + 1 <= len(prices)
    ]
    if not candidates:
        raise ValueError(
            "The selected history is too short for the configured overfit candidates."
        )

    best_pair: tuple[int, int] | None = None
    best_growth = float("-inf")
    for fast, slow in candidates:
        candidate_settings = replace(settings, fast_window=fast, slow_window=slow)
        result = run_sma_vs_buy_and_hold(prices, candidate_settings)
        growth = float((1 + result.sma.net_returns).prod())
        if growth > best_growth:
            best_pair = (fast, slow)
            best_growth = growth

    if best_pair is None:
        raise RuntimeError("No valid SMA parameter combination was evaluated.")
    return OverfitDemonstration(
        selected_fast_window=best_pair[0],
        selected_slow_window=best_pair[1],
        selected_growth=best_growth,
        baseline_growth=baseline_growth,
        combinations_tested=len(candidates),
        warning=(
            "The parameters were selected on these same observations. "
            "This is in-sample and optimistically biased, not a valid forecast."
        ),
    )
