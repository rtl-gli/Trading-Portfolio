import numpy as np
import pandas as pd
import pytest

from portfolio_research.backtest import run_portfolio_backtest, run_signal_backtest
from portfolio_research.config import (
    SmaSettings,
    load_strategy_settings,
)
from portfolio_research.strategies import (
    equal_weight_targets,
    mean_reversion_signals,
    momentum_signals,
    rolling_markowitz_weights,
    sma_signals,
    walk_forward_start,
)
from portfolio_research.validation import evaluate_signals_out_of_sample


def test_strategy_parameters_are_loaded_from_project_yaml() -> None:
    settings = load_strategy_settings()

    assert settings.momentum_lookback_sessions == 126
    assert settings.mean_reversion_lookback_sessions == 20
    assert settings.markowitz_lookback_sessions == 252


def test_momentum_signal_uses_only_prices_available_at_signal_date() -> None:
    prices = pd.Series(
        np.linspace(100, 150, 30),
        index=pd.bdate_range("2024-01-01", periods=30),
    )
    changed_future = prices.copy()
    changed_future.iloc[20:] *= 2

    first = momentum_signals(prices, lookback_sessions=5)
    second = momentum_signals(changed_future, lookback_sessions=5)

    pd.testing.assert_series_equal(first.iloc[:20], second.iloc[:20])
    assert first.iloc[5] == 1


def test_mean_reversion_enters_on_trailing_oversold_observation() -> None:
    prices = pd.Series(
        [100, 100, 100, 100, 70, 75, 80, 90],
        index=pd.bdate_range("2024-01-01", periods=8),
    )

    signals = mean_reversion_signals(
        prices, lookback_sessions=3, entry_z_score=1.3, exit_z_score=0.0
    )

    assert signals.iloc[:3].isna().all()
    assert signals.iloc[4] == 1
    assert signals.iloc[-1] == 0


def test_sma_crossover_returns_unknown_until_both_averages_exist() -> None:
    prices = pd.Series(
        [10, 11, 12, 13, 14, 15],
        index=pd.bdate_range("2024-01-01", periods=6),
    )

    signals = sma_signals(prices, fast_window=2, slow_window=3)

    assert signals.iloc[:2].isna().all()
    assert signals.iloc[2] == 1


def test_signal_backtest_delays_execution_and_charges_turnover() -> None:
    index = pd.bdate_range("2024-01-01", periods=6)
    prices = pd.Series([100, 101, 102, 103, 104, 105], index=index)
    signals = pd.Series([np.nan, np.nan, 1, 1, 1, 1], index=index)

    result = run_signal_backtest(prices, signals, SmaSettings(2, 3, 5, 5, 1))

    assert result.positions.iloc[3] == 0
    assert result.positions.iloc[4] == 1
    assert result.transaction_costs.iloc[4] == pytest.approx(0.001)
    assert result.transaction_costs.iloc[-1] == pytest.approx(0.001)


def test_markowitz_weights_are_long_only_capped_and_sum_to_one() -> None:
    rng = np.random.default_rng(13)
    returns = rng.normal(0.0005, 0.01, size=(80, 3))
    prices = pd.DataFrame(
        100 * (1 + returns).cumprod(axis=0),
        index=pd.bdate_range("2022-01-03", periods=80),
        columns=["AAA", "BBB", "CCC"],
    )

    weights = rolling_markowitz_weights(
        prices,
        lookback_sessions=20,
        rebalance_every_sessions=10,
        risk_aversion=5,
        maximum_weight=0.6,
    )
    available = weights.dropna(how="all")

    assert not available.empty
    assert available.min().min() >= 0
    assert available.max().max() <= 0.60000001
    assert np.allclose(available.sum(axis=1), 1.0)


def test_equal_weight_targets_rebalance_on_configured_sessions() -> None:
    index = pd.bdate_range("2024-01-01", periods=8)
    prices = pd.DataFrame(
        {"AAA": np.arange(100, 108), "BBB": np.arange(200, 208)}, index=index
    )

    weights = equal_weight_targets(prices, rebalance_every_sessions=3)

    assert weights.loc[index[[0, 3, 6]]].notna().all().all()
    assert weights.loc[index[[1, 2, 4, 5, 7]]].isna().all().all()
    assert np.allclose(weights.dropna().sum(axis=1), 1.0)
    assert np.allclose(weights.dropna().to_numpy(), 0.5)


def test_equal_weight_targets_reject_invalid_frequency_and_gaps() -> None:
    prices = pd.DataFrame(
        {"AAA": [10, 11, 12], "BBB": [10, 9, 11]},
        index=pd.bdate_range("2024-01-01", periods=3),
    )
    with pytest.raises(ValueError, match="positive integer"):
        equal_weight_targets(prices, 0)
    prices.iloc[1, 0] = np.nan
    with pytest.raises(ValueError, match="missing observations"):
        equal_weight_targets(prices, 1)


def test_equal_weight_targets_use_delayed_costed_portfolio_execution() -> None:
    from portfolio_research.backtest import run_portfolio_backtest

    index = pd.bdate_range("2024-01-01", periods=8)
    prices = pd.DataFrame(
        {"AAA": np.arange(100, 108), "BBB": np.arange(200, 208)}, index=index
    )
    targets = equal_weight_targets(prices, rebalance_every_sessions=3)

    result = run_portfolio_backtest(prices, targets, SmaSettings(2, 3, 5, 5, 1))

    assert np.allclose(result.positions.iloc[0], [0.0, 0.0])
    assert np.allclose(result.positions.iloc[2], [0.5, 0.5])
    assert result.transaction_costs.iloc[2] == pytest.approx(0.001)
    assert result.transaction_costs.iloc[-1] == pytest.approx(0.001)


def test_markowitz_weights_at_date_do_not_use_future_prices() -> None:
    rng = np.random.default_rng(9)
    returns = rng.normal(0.0003, 0.01, size=(65, 2))
    prices = pd.DataFrame(
        100 * (1 + returns).cumprod(axis=0),
        index=pd.bdate_range("2022-01-03", periods=65),
        columns=["AAA", "BBB"],
    )
    changed_future = prices.copy()
    changed_future.iloc[45:] *= 3
    arguments = {
        "lookback_sessions": 20,
        "rebalance_every_sessions": 5,
        "risk_aversion": 4,
        "maximum_weight": 0.8,
    }

    original_weights = rolling_markowitz_weights(prices, **arguments)
    changed_weights = rolling_markowitz_weights(changed_future, **arguments)

    pd.testing.assert_frame_equal(original_weights.iloc[:45], changed_weights.iloc[:45])


def test_portfolio_backtest_charges_entries_rebalances_and_final_exit() -> None:
    index = pd.bdate_range("2024-01-01", periods=8)
    prices = pd.DataFrame(
        {
            "AAA": [100, 101, 100, 102, 101, 103, 102, 104],
            "BBB": [100, 99, 101, 100, 102, 100, 103, 101],
        },
        index=index,
    )
    weights = pd.DataFrame(np.nan, index=index, columns=prices.columns)
    weights.iloc[0] = [0.5, 0.5]
    weights.iloc[4] = [0.7, 0.3]

    result = run_portfolio_backtest(prices, weights, SmaSettings(2, 3, 5, 5, 1))

    assert result.transaction_costs.iloc[2] == pytest.approx(0.001)
    assert result.transaction_costs.iloc[3:6].sum() == 0
    assert result.transaction_costs.iloc[6] == pytest.approx(0.00039522097)
    assert result.transaction_costs.iloc[-1] == pytest.approx(0.001)


def test_portfolio_backtest_rejects_weights_that_do_not_sum_to_one() -> None:
    index = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame(
        {"AAA": [10, 11, 12, 13], "BBB": [10, 9, 11, 12]}, index=index
    )
    weights = pd.DataFrame({"AAA": [0.8] * 4, "BBB": [0.1] * 4}, index=index)

    with pytest.raises(ValueError, match="sum to 1"):
        run_portfolio_backtest(prices, weights, SmaSettings(2, 3, 5, 5, 1))


def test_markowitz_rejects_missing_data_and_impossible_weight_cap() -> None:
    prices = pd.DataFrame(
        {"AAA": [10, 11, 12, 13], "BBB": [10, 9, 11, 12]},
        index=pd.bdate_range("2024-01-01", periods=4),
    )

    with pytest.raises(ValueError, match="maximum_weight"):
        rolling_markowitz_weights(
            prices,
            lookback_sessions=2,
            maximum_weight=0.4,
        )

    prices.iloc[1, 0] = np.nan
    with pytest.raises(ValueError, match="missing observations"):
        rolling_markowitz_weights(prices, lookback_sessions=2)


def test_walk_forward_split_is_chronological() -> None:
    index = pd.RangeIndex(10)

    assert walk_forward_start(index, train_fraction=0.7) == 7

    with pytest.raises(ValueError):
        walk_forward_start(index, train_fraction=1.0)


def test_out_of_sample_evaluation_excludes_training_returns() -> None:
    index = pd.bdate_range("2022-01-03", periods=20)
    prices = pd.Series(np.linspace(100, 120, 20), index=index)
    signals = pd.Series(1.0, index=index)
    settings = SmaSettings(2, 3, 5, 5, 1)

    result = evaluate_signals_out_of_sample(
        prices, signals, settings=settings, train_fraction=0.7
    )

    assert result.warmup_observations == 14
    assert result.split_date == index[14]
    assert len(result.strategy.net_returns) == len(index) - 14
    assert result.strategy.transaction_costs.iloc[0] == pytest.approx(0)
    assert result.strategy.transaction_costs.iloc[2] == pytest.approx(0.001)
