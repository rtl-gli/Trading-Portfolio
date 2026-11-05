import numpy as np
import pandas as pd
import pytest

from quant_models.regimes.gaussian_hmm import (
    RegimeModelError,
    _forward_filter,
    fit_gaussian_regime_model,
)


def _synthetic_regime_returns(
    observations: int = 800,
) -> pd.Series:
    random = np.random.default_rng(42)
    states = np.empty(observations, dtype=int)
    states[0] = 0
    for row in range(1, observations):
        switch_probability = 0.025
        states[row] = (
            1 - states[row - 1]
            if random.random() < switch_probability
            else states[row - 1]
        )
    volatilities = np.array([0.006, 0.028])
    means = np.array([0.0002, -0.0005])
    returns = random.normal(means[states], volatilities[states])
    dates = pd.bdate_range("2020-01-01", periods=observations)
    return pd.Series(returns, index=dates, name="daily_log_return")


def test_hmm_fits_early_sample_and_returns_ordered_probabilities() -> None:
    returns = _synthetic_regime_returns()

    result = fit_gaussian_regime_model(
        returns,
        n_states=2,
        train_fraction=0.7,
        n_restarts=3,
        max_iterations=120,
    )

    assert result.training_observations == 560
    assert result.out_of_sample_observations == 240
    assert result.training_end == returns.index[559]
    assert result.out_of_sample_start == returns.index[560]
    assert result.daily_volatilities.iloc[0] < result.daily_volatilities.iloc[1]
    assert result.filtered_probabilities.index.equals(returns.index)
    assert result.smoothed_probabilities.index.equals(returns.index)
    assert np.allclose(result.filtered_probabilities.sum(axis=1), 1.0)
    assert np.allclose(result.smoothed_probabilities.sum(axis=1), 1.0)
    assert np.allclose(result.transition_matrix.sum(axis=1), 1.0)
    assert np.isfinite(result.training_log_likelihood)
    assert 0 <= result.selected_restart < 3
    assert 0 <= result.restarts_with_likelihood_decreases <= 3
    assert isinstance(result.selected_restart_had_likelihood_decrease, bool)


def test_forward_filter_does_not_use_future_observations() -> None:
    parameters = {
        "start_probabilities": np.array([0.5, 0.5]),
        "transition_matrix": np.array([[0.95, 0.05], [0.1, 0.9]]),
        "means": np.array([0.0, 0.0]),
        "variances": np.array([0.01**2, 0.04**2]),
    }
    original = np.array([0.001, -0.003, 0.006, 0.002, -0.05])
    changed_future = original.copy()
    changed_future[3:] = [0.08, 0.12]

    original_probabilities = _forward_filter(original, **parameters)
    changed_probabilities = _forward_filter(changed_future, **parameters)

    assert np.allclose(original_probabilities[:3], changed_probabilities[:3])
    assert not np.allclose(original_probabilities[3:], changed_probabilities[3:])


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (pd.Series([], dtype=float), "non-empty Series"),
        (
            pd.Series([0.1, 0.2], index=[0, 1]),
            "DatetimeIndex",
        ),
    ],
)
def test_hmm_rejects_invalid_return_inputs(
    values: pd.Series,
    message: str,
) -> None:
    with pytest.raises(RegimeModelError, match=message):
        fit_gaussian_regime_model(values)


def test_hmm_rejects_duplicate_dates_and_invalid_parameters() -> None:
    returns = _synthetic_regime_returns()
    duplicate_dates = pd.concat([returns.iloc[:3], returns.iloc[[2]]])

    with pytest.raises(RegimeModelError, match="unique and chronological"):
        fit_gaussian_regime_model(duplicate_dates)
    with pytest.raises(ValueError, match="n_states"):
        fit_gaussian_regime_model(returns, n_states=1)
    with pytest.raises(ValueError, match="train_fraction"):
        fit_gaussian_regime_model(returns, train_fraction=0.4)
