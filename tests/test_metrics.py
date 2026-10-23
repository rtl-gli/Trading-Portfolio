import math

import pandas as pd
import pytest

from portfolio_research.config import load_metric_settings
from portfolio_research.metrics import calculate_metrics


def test_calculate_metrics_matches_known_drawdown_and_beta() -> None:
    dates = pd.to_datetime(["2023-01-01", "2023-07-02", "2024-01-01"])
    strategy_returns = pd.Series([0.0, 0.1, -0.1], index=dates)
    benchmark_returns = pd.Series([0.0, 0.05, -0.05], index=dates)

    metrics = calculate_metrics(strategy_returns, benchmark_returns)

    assert metrics.cagr == pytest.approx(0.99 ** (365.25 / 365.0) - 1)
    assert metrics.max_drawdown == pytest.approx(-0.1)
    assert metrics.beta == pytest.approx(2.0)
    assert metrics.historical_var > 0
    assert metrics.var_confidence == 0.95
    assert metrics.observations == 3
    assert math.isfinite(metrics.annualized_volatility)
    assert metrics.sharpe_ratio is not None


def test_metric_settings_come_from_project_configuration() -> None:
    settings = load_metric_settings()

    assert settings.periods_per_year == 252
    assert settings.annual_risk_free_rate == 0
    assert settings.var_confidence == 0.95


def test_undefined_sharpe_and_beta_are_explicit() -> None:
    dates = pd.date_range("2024-01-01", periods=3)
    returns = pd.Series([0.01, 0.01, 0.01], index=dates)
    benchmark = pd.Series([0.0, 0.0, 0.0], index=dates)

    metrics = calculate_metrics(returns, benchmark)

    assert metrics.sharpe_ratio is None
    assert metrics.beta is None
    assert len(metrics.warnings) == 2


def test_drawdown_includes_initial_transaction_costs() -> None:
    dates = pd.date_range("2024-01-01", periods=2)
    returns = pd.Series([-0.01, 0.02], index=dates)
    benchmark = pd.Series([0.0, 0.01], index=dates)

    metrics = calculate_metrics(returns, benchmark)

    assert metrics.max_drawdown == pytest.approx(-0.01)


def test_metrics_reject_missing_returns() -> None:
    dates = pd.date_range("2024-01-01", periods=3)
    returns = pd.Series([0.0, float("nan"), 0.01], index=dates)
    benchmark = pd.Series([0.0, 0.01, 0.02], index=dates)

    with pytest.raises(ValueError, match="missing or infinite"):
        calculate_metrics(returns, benchmark)
