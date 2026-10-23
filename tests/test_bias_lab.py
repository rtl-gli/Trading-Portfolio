import numpy as np
import pandas as pd
import pytest

from portfolio_research.backtest import run_signal_backtest
from portfolio_research.bias_lab import (
    compare_portfolio_biases,
    compare_signal_biases,
    select_sma_on_full_sample,
)
from portfolio_research.config import SmaSettings


def test_signal_bias_comparison_exposes_cost_and_future_signal_variants() -> None:
    index = pd.bdate_range("2024-01-01", periods=12)
    prices = pd.Series(np.linspace(100, 120, len(index)), index=index)
    signals = pd.Series(1.0, index=index)
    settings = SmaSettings(2, 3, 5, 5, 1)

    result = compare_signal_biases(prices, signals, settings)

    assert result.costs_ignored.net_returns.sum() > result.baseline.net_returns.sum()
    expected_leaky = run_signal_backtest(prices, signals.shift(-1), settings)
    pd.testing.assert_series_equal(
        result.future_signal_used.net_returns, expected_leaky.net_returns
    )
    assert len(result.warnings) == 2


def test_portfolio_bias_comparison_uses_selected_portfolio() -> None:
    index = pd.bdate_range("2024-01-01", periods=12)
    prices = pd.DataFrame(
        {
            "AAA": np.linspace(100, 120, len(index)),
            "BBB": np.linspace(100, 105, len(index)),
        },
        index=index,
    )
    weights = pd.DataFrame(np.nan, index=index, columns=prices.columns)
    weights.iloc[0] = [1.0, 0.0]
    weights.iloc[5] = [0.0, 1.0]
    settings = SmaSettings(2, 3, 5, 5, 1)

    result = compare_portfolio_biases(prices, weights, settings)

    assert result.costs_ignored.net_returns.sum() > result.baseline.net_returns.sum()
    assert result.future_weights_used is not None
    assert result.future_weights_used.net_returns.index.equals(index)


def test_overfit_demo_reports_full_sample_selection_and_limitation() -> None:
    index = pd.bdate_range("2022-01-01", periods=80)
    prices = pd.Series(100 * (1.001 ** np.arange(80)), index=index)
    settings = SmaSettings(2, 5, 5, 5, 1)

    result = select_sma_on_full_sample(
        prices,
        settings,
        fast_candidates=(2, 3),
        slow_candidates=(5, 8),
    )

    assert result.combinations_tested == 4
    assert result.selected_fast_window < result.selected_slow_window
    assert "same observations" in result.warning


def test_overfit_demo_rejects_history_shorter_than_all_candidates() -> None:
    prices = pd.Series(
        [100.0, 101.0, 102.0, 103.0, 104.0],
        index=pd.bdate_range("2024-01-01", periods=5),
    )

    with pytest.raises(ValueError, match="too short"):
        select_sma_on_full_sample(
            prices,
            SmaSettings(2, 3, 5, 5, 1),
            fast_candidates=(2,),
            slow_candidates=(20,),
        )
