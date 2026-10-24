"""Causal signal generation and rolling long-only Markowitz allocations."""

from collections.abc import Sequence

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from portfolio_research.config import StrategySettings, load_strategy_settings
from portfolio_research.market_data import validate_prices


def sma_signals(
    prices: pd.Series, fast_window: int = 50, slow_window: int = 200
) -> pd.Series:
    """Create a long/flat SMA crossover signal at each available close."""
    validated = _clean_single_asset(prices)
    if (
        isinstance(fast_window, bool)
        or not isinstance(fast_window, int)
        or isinstance(slow_window, bool)
        or not isinstance(slow_window, int)
        or fast_window <= 0
        or slow_window <= fast_window
    ):
        raise ValueError("SMA windows must be positive integers with fast < slow.")
    fast = validated.rolling(fast_window, min_periods=fast_window).mean()
    slow = validated.rolling(slow_window, min_periods=slow_window).mean()
    available = fast.notna() & slow.notna()
    return fast.gt(slow).where(available).astype(float).rename("sma_signal")


def _clean_single_asset(prices: pd.Series) -> pd.Series:
    if not isinstance(prices, pd.Series):
        raise TypeError("Strategy prices must be a pandas Series.")
    panel, _ = validate_prices(prices.rename("ASSET").to_frame(), ["ASSET"])
    validated = panel["ASSET"]
    if validated.isna().any():
        raise ValueError("Strategy input contains missing prices.")
    return validated


def momentum_signals(
    prices: pd.Series,
    lookback_sessions: int = 126,
    entry_return_threshold: float = 0.0,
    exit_return_threshold: float = 0.0,
) -> pd.Series:
    """Go long after trailing momentum exceeds entry and exit below threshold."""
    validated = _clean_single_asset(prices)
    if (
        isinstance(lookback_sessions, bool)
        or not isinstance(lookback_sessions, int)
        or lookback_sessions <= 0
    ):
        raise ValueError("Momentum lookback must be a positive integer.")
    if not np.isfinite([entry_return_threshold, exit_return_threshold]).all():
        raise ValueError("Momentum thresholds must be finite.")
    if exit_return_threshold > entry_return_threshold:
        raise ValueError("Momentum exit threshold must not exceed the entry threshold.")

    trailing_return = validated.pct_change(lookback_sessions, fill_method=None)
    signals = pd.Series(np.nan, index=validated.index, name="momentum_signal")
    in_market = False
    for index in range(len(validated)):
        value = trailing_return.iloc[index]
        if pd.isna(value):
            continue
        if not in_market and value > entry_return_threshold:
            in_market = True
        elif in_market and value < exit_return_threshold:
            in_market = False
        signals.iloc[index] = float(in_market)
    return signals


def mean_reversion_signals(
    prices: pd.Series,
    lookback_sessions: int = 20,
    entry_z_score: float = 2.0,
    exit_z_score: float = 0.0,
) -> pd.Series:
    """Buy below a trailing mean by entry z and exit after mean reversion."""
    validated = _clean_single_asset(prices)
    if (
        isinstance(lookback_sessions, bool)
        or not isinstance(lookback_sessions, int)
        or lookback_sessions < 2
    ):
        raise ValueError("Mean-reversion lookback must be an integer of at least 2.")
    if not np.isfinite([entry_z_score, exit_z_score]).all():
        raise ValueError("Mean-reversion z-score thresholds must be finite.")
    if entry_z_score <= 0 or exit_z_score < 0 or exit_z_score >= entry_z_score:
        raise ValueError(
            "Mean-reversion entry z-score must exceed its non-negative exit."
        )

    rolling_mean = validated.rolling(
        lookback_sessions, min_periods=lookback_sessions
    ).mean()
    rolling_std = validated.rolling(
        lookback_sessions, min_periods=lookback_sessions
    ).std(ddof=0)
    z_score = (validated - rolling_mean) / rolling_std.where(rolling_std > 0)
    signals = pd.Series(np.nan, index=validated.index, name="mean_reversion_signal")
    in_market = False
    for index in range(len(validated)):
        value = z_score.iloc[index]
        if pd.isna(value):
            continue
        if not in_market and value <= -entry_z_score:
            in_market = True
        elif in_market and value >= -exit_z_score:
            in_market = False
        signals.iloc[index] = float(in_market)
    return signals


def _solve_long_only_weights(
    expected_returns: np.ndarray,
    covariance: np.ndarray,
    risk_aversion: float,
    maximum_weight: float,
) -> np.ndarray:
    asset_count = len(expected_returns)
    if asset_count * maximum_weight < 1 - 1e-12:
        raise ValueError(
            "Markowitz maximum_weight is too low to fully allocate the universe."
        )

    def objective(weights: np.ndarray) -> float:
        return float(
            0.5 * risk_aversion * weights @ covariance @ weights
            - expected_returns @ weights
        )

    result = minimize(
        objective,
        x0=np.full(asset_count, 1 / asset_count),
        method="SLSQP",
        bounds=[(0.0, maximum_weight)] * asset_count,
        constraints={"type": "eq", "fun": lambda weights: weights.sum() - 1},
        options={"maxiter": 500, "ftol": 1e-12},
    )
    if not result.success:
        raise RuntimeError(f"Markowitz optimisation failed: {result.message}")
    weights = np.clip(result.x, 0.0, maximum_weight)
    weights /= weights.sum()
    return weights


def equal_weight_targets(
    prices: pd.DataFrame, rebalance_every_sessions: int = 21
) -> pd.DataFrame:
    """Create sparse, periodically rebalanced equal-weight portfolio targets."""
    if (
        isinstance(rebalance_every_sessions, bool)
        or not isinstance(rebalance_every_sessions, int)
        or rebalance_every_sessions < 1
    ):
        raise ValueError("Rebalance frequency must be a positive integer.")
    validated, _ = validate_prices(prices)
    if validated.isna().any().any():
        raise ValueError("Equal-weight price panel contains missing observations.")
    weights = pd.DataFrame(np.nan, index=validated.index, columns=validated.columns)
    weights.iloc[::rebalance_every_sessions] = 1 / len(validated.columns)
    return weights


def rolling_markowitz_weights(
    prices: pd.DataFrame,
    symbols: Sequence[str] | None = None,
    *,
    lookback_sessions: int | None = None,
    rebalance_every_sessions: int | None = None,
    risk_aversion: float | None = None,
    maximum_weight: float | None = None,
    settings: StrategySettings | None = None,
) -> pd.DataFrame:
    """Estimate rolling long-only mean-variance weights without future data.

    At each rebalance date, expected returns and covariance use only the
    configured trailing daily returns through that date. The weights then go
    through the portfolio backtest's execution delay before taking exposure.
    """
    selected = settings or load_strategy_settings()
    lookback = (
        selected.markowitz_lookback_sessions
        if lookback_sessions is None
        else lookback_sessions
    )
    rebalance = (
        selected.markowitz_rebalance_every_sessions
        if rebalance_every_sessions is None
        else rebalance_every_sessions
    )
    risk_penalty = (
        selected.markowitz_risk_aversion if risk_aversion is None else risk_aversion
    )
    weight_cap = (
        selected.markowitz_maximum_weight if maximum_weight is None else maximum_weight
    )
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 2:
        raise ValueError("Markowitz lookback must be an integer of at least 2.")
    if isinstance(rebalance, bool) or not isinstance(rebalance, int) or rebalance < 1:
        raise ValueError("Rebalance frequency must be a positive integer.")
    if (
        isinstance(risk_penalty, bool)
        or not isinstance(risk_penalty, (int, float))
        or isinstance(weight_cap, bool)
        or not isinstance(weight_cap, (int, float))
        or not np.isfinite([risk_penalty, weight_cap]).all()
        or risk_penalty <= 0
    ):
        raise ValueError("Risk aversion must be positive and inputs finite.")
    if not 0 < weight_cap <= 1:
        raise ValueError("Maximum weight must be in (0, 1].")

    validated, _ = validate_prices(prices, symbols)
    if validated.isna().any().any():
        raise ValueError("Markowitz price panel contains missing observations.")
    if len(validated.columns) < 2:
        raise ValueError("Markowitz optimisation requires at least two assets.")
    if len(validated) <= lookback:
        raise ValueError("Not enough daily observations for the Markowitz lookback.")

    daily_returns = validated.pct_change(fill_method=None)
    weights = pd.DataFrame(np.nan, index=validated.index, columns=validated.columns)
    for position in range(lookback, len(validated), rebalance):
        training_returns = daily_returns.iloc[position - lookback + 1 : position + 1]
        expected_returns = training_returns.mean().to_numpy() * 252
        covariance = training_returns.cov().to_numpy() * 252
        covariance = (covariance + covariance.T) / 2
        target = _solve_long_only_weights(
            expected_returns, covariance, risk_penalty, weight_cap
        )
        weights.iloc[position] = target
    return weights


def walk_forward_start(index: pd.Index, train_fraction: float = 0.7) -> int:
    """Return the first held-out row after a chronological training prefix."""
    if isinstance(train_fraction, bool) or not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be strictly between 0 and 1.")
    split = int(len(index) * train_fraction)
    if split < 1 or split >= len(index):
        raise ValueError("Need at least two observations for a walk-forward split.")
    return split
