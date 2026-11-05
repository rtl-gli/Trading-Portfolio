"""Aligned monthly Fama-French regressions with Newey-West uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
import pandas as pd

from quant_models.factors.data import (
    FF3_COLUMNS,
    FF5_COLUMNS,
    FactorDataError,
    FactorModel,
)

_MODEL_COLUMNS = {"ff3": FF3_COLUMNS, "ff5": FF5_COLUMNS}
FactorIndex: TypeAlias = pd.DatetimeIndex | pd.PeriodIndex


@dataclass(frozen=True)
class AlignmentDiagnostics:
    """Counts that explain how portfolio and factor dates were aligned."""

    portfolio_months: int
    factor_months: int
    overlapping_months: int
    incomplete_factor_months: int
    portfolio_months_without_factors: int
    factor_months_without_portfolio: int
    used_months: int


@dataclass(frozen=True)
class FactorRegressionResult:
    """Coefficient estimates and HAC-robust inference for one factor model."""

    model: FactorModel
    coefficients: pd.DataFrame
    observations: int
    sample_start: pd.Timestamp
    sample_end: pd.Timestamp
    r_squared: float
    adjusted_r_squared: float
    alpha: float
    alpha_standard_error: float
    alpha_t_statistic: float
    alpha_p_value: float
    alpha_confidence_interval: tuple[float, float]
    hac_lags: int
    alignment: AlignmentDiagnostics


def _month_end_index(index: FactorIndex, name: str) -> pd.DatetimeIndex:
    if index.hasnans:
        raise FactorDataError(f"{name} contains missing monthly dates.")
    if isinstance(index, pd.PeriodIndex):
        periods = index.asfreq("M")
    elif isinstance(index, pd.DatetimeIndex):
        timestamps = index.tz_localize(None) if index.tz is not None else index
        periods = timestamps.to_period("M")
    else:
        raise TypeError(f"{name} must use a DatetimeIndex or PeriodIndex.")
    if periods.has_duplicates:
        raise FactorDataError(f"{name} contains more than one observation per month.")
    return periods.to_timestamp(how="end").normalize()


def align_monthly_data(
    portfolio_returns: pd.Series,
    factor_data: pd.DataFrame,
    model: FactorModel,
) -> tuple[pd.DataFrame, AlignmentDiagnostics]:
    """Align portfolio total returns and factor rows by calendar month.

    Missing factor sentinels remain missing here. Their overlapping months are
    counted and excluded explicitly; no forward-fill or interpolation occurs.
    """
    if model not in _MODEL_COLUMNS:
        raise ValueError("model must be 'ff3' or 'ff5'.")
    if not isinstance(portfolio_returns, pd.Series) or portfolio_returns.empty:
        raise FactorDataError("Portfolio returns must be a non-empty Series.")
    if not isinstance(factor_data, pd.DataFrame) or factor_data.empty:
        raise FactorDataError("Factor data must be a non-empty DataFrame.")
    if factor_data.columns.has_duplicates:
        raise FactorDataError("Factor data contains duplicate columns.")

    required = (*_MODEL_COLUMNS[model], "RF")
    missing = sorted(set(required) - set(factor_data.columns))
    if missing:
        raise FactorDataError(f"{model.upper()} data is missing columns: {missing}.")

    portfolio = portfolio_returns.copy()
    portfolio.index = _month_end_index(portfolio.index, "Portfolio returns")
    portfolio = pd.to_numeric(portfolio, errors="coerce")
    if portfolio.isna().any() or not np.isfinite(portfolio.to_numpy(dtype=float)).all():
        raise FactorDataError("Portfolio returns must be finite and complete.")
    if (portfolio < -1.0).any():
        raise FactorDataError("Portfolio simple returns cannot be below -100%.")
    portfolio = portfolio.sort_index().rename("portfolio_return")

    factors = factor_data.loc[:, required].copy()
    factors.index = _month_end_index(factors.index, "Factor data")
    factors = factors.sort_index()
    for column in required:
        original = factors[column]
        converted = pd.to_numeric(original, errors="coerce")
        if (original.notna() & converted.isna()).any():
            raise FactorDataError(
                f"Factor column {column!r} contains non-numeric data."
            )
        if not np.isfinite(converted.dropna().to_numpy(dtype=float)).all():
            raise FactorDataError(f"Factor column {column!r} contains infinite values.")
        factors[column] = converted

    common = portfolio.to_frame().join(factors, how="inner")
    incomplete = common.loc[:, required].isna().any(axis=1)
    aligned = common.loc[~incomplete].copy()
    if aligned.empty:
        raise FactorDataError(
            "No complete overlapping monthly observations remain after date alignment."
        )
    diagnostics = AlignmentDiagnostics(
        portfolio_months=len(portfolio),
        factor_months=len(factors),
        overlapping_months=len(common),
        incomplete_factor_months=int(incomplete.sum()),
        portfolio_months_without_factors=len(portfolio.index.difference(factors.index)),
        factor_months_without_portfolio=len(factors.index.difference(portfolio.index)),
        used_months=len(aligned),
    )
    return aligned, diagnostics


def run_factor_regression(
    portfolio_returns: pd.Series,
    factor_data: pd.DataFrame,
    model: FactorModel,
    hac_lags: int = 3,
) -> FactorRegressionResult:
    """Fit excess portfolio returns with Newey-West (HAC) standard errors."""
    import statsmodels.api as sm

    aligned, diagnostics = align_monthly_data(portfolio_returns, factor_data, model)
    if (
        isinstance(hac_lags, bool)
        or not isinstance(hac_lags, int)
        or hac_lags < 0
        or hac_lags >= len(aligned)
    ):
        raise ValueError("hac_lags must be an integer from 0 to observations - 1.")

    factor_columns = _MODEL_COLUMNS[model]
    response = aligned["portfolio_return"] - aligned["RF"]
    design = sm.add_constant(aligned.loc[:, factor_columns], has_constant="add")
    if len(aligned) <= design.shape[1]:
        raise FactorDataError(
            "Regression requires more observations than estimated parameters."
        )
    if np.linalg.matrix_rank(design.to_numpy(dtype=float)) < design.shape[1]:
        raise FactorDataError("Factor design matrix is rank deficient.")

    fitted = sm.OLS(response, design, missing="raise").fit(
        cov_type="HAC",
        cov_kwds={"maxlags": hac_lags},
        use_t=True,
    )
    confidence_intervals = fitted.conf_int(alpha=0.05)
    coefficient_table = pd.DataFrame(
        {
            "coefficient": fitted.params,
            "newey_west_standard_error": fitted.bse,
            "t_statistic": fitted.tvalues,
            "p_value": fitted.pvalues,
            "ci_95_lower": confidence_intervals.iloc[:, 0],
            "ci_95_upper": confidence_intervals.iloc[:, 1],
        }
    )
    alpha_interval = (
        float(confidence_intervals.loc["const"].iloc[0]),
        float(confidence_intervals.loc["const"].iloc[1]),
    )
    return FactorRegressionResult(
        model=model,
        coefficients=coefficient_table,
        observations=len(aligned),
        sample_start=aligned.index[0],
        sample_end=aligned.index[-1],
        r_squared=float(fitted.rsquared),
        adjusted_r_squared=float(fitted.rsquared_adj),
        alpha=float(fitted.params["const"]),
        alpha_standard_error=float(fitted.bse["const"]),
        alpha_t_statistic=float(fitted.tvalues["const"]),
        alpha_p_value=float(fitted.pvalues["const"]),
        alpha_confidence_interval=alpha_interval,
        hac_lags=hac_lags,
        alignment=diagnostics,
    )
