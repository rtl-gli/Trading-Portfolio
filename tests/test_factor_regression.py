import numpy as np
import pandas as pd
import pytest

from quant_models.factors.data import FF5_COLUMNS, FactorDataError
from quant_models.factors.regression import (
    align_monthly_data,
    run_factor_regression,
)


@pytest.fixture
def synthetic_factor_data() -> tuple[pd.Series, pd.DataFrame]:
    random = np.random.default_rng(42)
    dates = pd.date_range("2010-01-31", periods=180, freq="ME")
    factors = pd.DataFrame(
        random.normal(0.0, 0.03, (len(dates), len(FF5_COLUMNS))),
        index=dates,
        columns=FF5_COLUMNS,
    )
    factors["RF"] = random.normal(0.001, 0.0002, len(dates))
    noise = random.normal(0.0, 0.004, len(dates))
    excess_return = (
        0.005
        + 1.1 * factors["Mkt-RF"]
        + 0.2 * factors["SMB"]
        - 0.1 * factors["HML"]
        + 0.3 * factors["RMW"]
        - 0.2 * factors["CMA"]
        + noise
    )
    portfolio_returns = (excess_return + factors["RF"]).rename("portfolio_return")
    return portfolio_returns, factors


def test_ff5_regression_recovers_synthetic_alpha_with_hac_inference(
    synthetic_factor_data: tuple[pd.Series, pd.DataFrame],
) -> None:
    returns, factors = synthetic_factor_data

    result = run_factor_regression(returns, factors, "ff5", hac_lags=3)

    assert result.observations == 180
    assert result.alpha == pytest.approx(0.005, abs=0.0015)
    assert result.alpha_p_value < 0.05
    assert result.alpha_confidence_interval[0] < result.alpha
    assert result.alpha_confidence_interval[1] > result.alpha
    assert result.hac_lags == 3
    assert "newey_west_standard_error" in result.coefficients
    assert {"RMW", "CMA"}.issubset(result.coefficients.index)


def test_ff3_uses_only_three_factors_from_ff5_dataset(
    synthetic_factor_data: tuple[pd.Series, pd.DataFrame],
) -> None:
    returns, factors = synthetic_factor_data

    result = run_factor_regression(returns, factors, "ff3", hac_lags=3)

    assert result.observations == len(returns)
    assert {"Mkt-RF", "SMB", "HML"}.issubset(result.coefficients.index)
    assert "RMW" not in result.coefficients.index


def test_alignment_reports_sentinel_months_and_unmatched_dates(
    synthetic_factor_data: tuple[pd.Series, pd.DataFrame],
) -> None:
    returns, factors = synthetic_factor_data
    factors = factors.drop(factors.index[-1]).copy()
    factors.loc[factors.index[5], "RF"] = np.nan

    aligned, diagnostics = align_monthly_data(returns, factors, "ff5")

    assert len(aligned) == 178
    assert diagnostics.overlapping_months == 179
    assert diagnostics.incomplete_factor_months == 1
    assert diagnostics.portfolio_months_without_factors == 1
    assert diagnostics.used_months == 178


def test_alignment_rejects_duplicate_months_after_normalization(
    synthetic_factor_data: tuple[pd.Series, pd.DataFrame],
) -> None:
    returns, factors = synthetic_factor_data
    duplicated = pd.concat([returns.iloc[:2], returns.iloc[[1]]])

    with pytest.raises(FactorDataError, match="more than one observation per month"):
        align_monthly_data(duplicated, factors, "ff3")


def test_regression_rejects_invalid_hac_lags(
    synthetic_factor_data: tuple[pd.Series, pd.DataFrame],
) -> None:
    returns, factors = synthetic_factor_data

    with pytest.raises(ValueError, match="hac_lags"):
        run_factor_regression(returns, factors, "ff5", hac_lags=len(returns))


def test_regression_rejects_rank_deficient_factor_data(
    synthetic_factor_data: tuple[pd.Series, pd.DataFrame],
) -> None:
    returns, factors = synthetic_factor_data
    factors.loc[:, "SMB"] = factors["Mkt-RF"]

    with pytest.raises(FactorDataError, match="rank deficient"):
        run_factor_regression(returns, factors, "ff5", hac_lags=3)
