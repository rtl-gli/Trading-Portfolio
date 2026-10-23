"""Performance and risk metrics for daily backtest returns."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from portfolio_research.config import MetricSettings, load_metric_settings


@dataclass(frozen=True)
class PerformanceMetrics:
    """Core risk and performance statistics with explicit diagnostics."""

    cagr: float
    sharpe_ratio: float | None
    max_drawdown: float
    annualized_volatility: float
    historical_var: float
    var_confidence: float
    beta: float | None
    observations: int
    warnings: tuple[str, ...]


def _validate_returns(returns: pd.Series, name: str) -> pd.Series:
    if not isinstance(returns, pd.Series):
        raise TypeError(f"{name} must be a pandas Series.")
    if not isinstance(returns.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must have a DatetimeIndex.")
    if returns.empty:
        raise ValueError(f"{name} must contain at least one return.")
    if returns.index.hasnans or returns.index.has_duplicates:
        raise ValueError(f"{name} dates must be present and unique.")
    if not returns.index.is_monotonic_increasing:
        raise ValueError(f"{name} dates must be chronological.")
    if not is_numeric_dtype(returns.dtype):
        raise TypeError(f"{name} values must be numeric.")
    values = returns.to_numpy()
    if not np.isfinite(values).all():
        raise ValueError(f"{name} contains missing or infinite values.")
    if (values < -1).any():
        raise ValueError(f"{name} cannot contain returns below -100%.")
    return returns.astype(float)


def calculate_metrics(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    settings: MetricSettings | None = None,
) -> PerformanceMetrics:
    """Calculate CAGR, Sharpe, drawdown, volatility, historical VaR, and beta.

    CAGR uses actual elapsed calendar time between the first and last daily
    return observations. VaR is the negated empirical lower-tail return, so a
    negative value means that the tail quantile was a gain.
    """
    selected_settings = settings or load_metric_settings()
    strategy = _validate_returns(returns, "returns")
    benchmark = _validate_returns(benchmark_returns, "benchmark_returns")
    elapsed_days = (strategy.index[-1] - strategy.index[0]).total_seconds() / 86400
    if elapsed_days <= 0:
        raise ValueError(
            "At least two return dates spanning positive time are required."
        )

    wealth = (1 + strategy).cumprod()
    years = elapsed_days / 365.25
    final_wealth = float(wealth.iloc[-1])
    cagr = final_wealth ** (1 / years) - 1 if final_wealth > 0 else -1.0
    running_peak = wealth.cummax().clip(lower=1.0)
    drawdown = wealth / running_peak - 1
    max_drawdown = float(drawdown.min())
    annualized_volatility = float(
        strategy.std(ddof=1) * math.sqrt(selected_settings.periods_per_year)
    )
    daily_risk_free = (1 + selected_settings.annual_risk_free_rate) ** (
        1 / selected_settings.periods_per_year
    ) - 1
    daily_excess = strategy - daily_risk_free
    daily_volatility = float(strategy.std(ddof=1))
    warnings: list[str] = []
    sharpe_ratio = None
    if len(strategy) < 2 or daily_volatility == 0:
        warnings.append(
            "Sharpe ratio is undefined for fewer than two or zero-volatility returns."
        )
    else:
        sharpe_ratio = float(
            daily_excess.mean()
            / daily_volatility
            * math.sqrt(selected_settings.periods_per_year)
        )

    historical_var = float(
        -strategy.quantile(1 - selected_settings.var_confidence, interpolation="linear")
    )
    aligned = pd.concat(
        [strategy.rename("strategy"), benchmark.rename("benchmark")],
        axis=1,
        join="inner",
    )
    beta: float | None = None
    if len(aligned) < 2 or aligned["benchmark"].var(ddof=1) == 0:
        warnings.append(
            "Beta is undefined: insufficient aligned returns or zero benchmark variance."
        )
    else:
        beta = float(
            aligned["strategy"].cov(aligned["benchmark"])
            / aligned["benchmark"].var(ddof=1)
        )

    return PerformanceMetrics(
        cagr=cagr,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        annualized_volatility=annualized_volatility,
        historical_var=historical_var,
        var_confidence=selected_settings.var_confidence,
        beta=beta,
        observations=len(strategy),
        warnings=tuple(warnings),
    )
