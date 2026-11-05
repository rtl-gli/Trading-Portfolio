"""Regime-switching model implementations."""

from quant_models.regimes.gaussian_hmm import (
    RegimeModelError,
    RegimeResult,
    fit_gaussian_regime_model,
)

__all__ = ["RegimeModelError", "RegimeResult", "fit_gaussian_regime_model"]
