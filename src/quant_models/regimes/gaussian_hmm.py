"""Gaussian hidden-Markov regime estimates with causal forward filtering."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

import numpy as np
import pandas as pd
from hmmlearn.base import ConvergenceMonitor
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from scipy.stats import norm


class RegimeModelError(RuntimeError):
    """Raised when regime inputs or model estimates are invalid."""


class _LikelihoodMonitor(ConvergenceMonitor):
    """Track non-monotone EM steps while preserving hmmlearn diagnostics."""

    def __init__(self, tolerance: float, max_iterations: int, verbose: bool) -> None:
        super().__init__(tolerance, max_iterations, verbose)
        self.likelihood_decreased = False

    def report(self, log_probability: float) -> None:
        precision = np.finfo(float).eps ** 0.5
        if self.history and log_probability - self.history[-1] < -precision:
            self.likelihood_decreased = True
        super().report(log_probability)


@dataclass(frozen=True)
class RegimeResult:
    """Training-fitted regime parameters and filtered/smoothed probabilities."""

    state_names: tuple[str, ...]
    filtered_probabilities: pd.DataFrame
    smoothed_probabilities: pd.DataFrame
    filtered_states: pd.Series
    transition_matrix: pd.DataFrame
    daily_means: pd.Series
    daily_volatilities: pd.Series
    training_end: pd.Timestamp
    out_of_sample_start: pd.Timestamp
    training_observations: int
    out_of_sample_observations: int
    training_log_likelihood: float
    converged: bool
    iterations: int
    selected_restart: int
    restarts_with_likelihood_decreases: int
    selected_restart_had_likelihood_decrease: bool


def _validate_log_returns(log_returns: pd.Series) -> pd.Series:
    if not isinstance(log_returns, pd.Series) or log_returns.empty:
        raise RegimeModelError("Daily log returns must be a non-empty Series.")
    if not isinstance(log_returns.index, pd.DatetimeIndex):
        raise RegimeModelError("Daily log returns must have a DatetimeIndex.")
    if log_returns.index.hasnans:
        raise RegimeModelError("Daily log-return dates cannot be missing.")
    if log_returns.index.tz is not None:
        raise RegimeModelError("Daily log-return dates must not have a time zone.")
    if (
        log_returns.index.has_duplicates
        or not log_returns.index.is_monotonic_increasing
    ):
        raise RegimeModelError(
            "Daily log-return dates must be unique and chronological."
        )
    values = pd.to_numeric(log_returns, errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise RegimeModelError("Daily log returns must be finite and complete.")
    if values.index.size < 3 or values.nunique() < 2:
        raise RegimeModelError("Daily log returns need variation across several dates.")
    return values.astype(float).rename("daily_log_return")


def _log_probabilities(probabilities: np.ndarray) -> np.ndarray:
    log_values = np.full(probabilities.shape, -np.inf, dtype=float)
    np.log(probabilities, out=log_values, where=probabilities > 0.0)
    return log_values


def _forward_filter(
    observations: np.ndarray,
    start_probabilities: np.ndarray,
    transition_matrix: np.ndarray,
    means: np.ndarray,
    variances: np.ndarray,
) -> np.ndarray:
    """Calculate P(state_t | observations through t), never using future rows."""
    log_start = _log_probabilities(start_probabilities)
    log_transition = _log_probabilities(transition_matrix)
    log_emissions = norm.logpdf(
        observations[:, None],
        loc=means[None, :],
        scale=np.sqrt(variances)[None, :],
    )
    filtered_log = np.empty_like(log_emissions)
    first = log_start + log_emissions[0]
    filtered_log[0] = first - logsumexp(first)

    for row in range(1, len(observations)):
        predicted = logsumexp(
            filtered_log[row - 1, :, None] + log_transition,
            axis=0,
        )
        current = predicted + log_emissions[row]
        filtered_log[row] = current - logsumexp(current)
    return np.exp(filtered_log)


def _state_names(count: int) -> tuple[str, ...]:
    if count == 2:
        return ("Lower-volatility state", "Higher-volatility state")
    return tuple(
        f"State {rank + 1} (volatility rank {rank + 1})" for rank in range(count)
    )


def fit_gaussian_regime_model(
    daily_log_returns: pd.Series,
    *,
    n_states: int = 2,
    train_fraction: float = 0.7,
    n_restarts: int = 5,
    max_iterations: int = 200,
    random_seed: int = 42,
) -> RegimeResult:
    """Fit Gaussian emissions on an early sample and filter chronologically.

    Parameters are estimated only from the first ``train_fraction`` of rows.
    Filtered probabilities then process each observation in order with those
    fixed parameters. Smoothed probabilities are returned for teaching only;
    unlike filtered probabilities, they use observations from both past and
    future dates.
    """
    values = _validate_log_returns(daily_log_returns)
    if (
        isinstance(n_states, bool)
        or not isinstance(n_states, int)
        or not 2 <= n_states <= 4
    ):
        raise ValueError("n_states must be an integer from 2 to 4.")
    if (
        isinstance(train_fraction, bool)
        or not isinstance(train_fraction, Real)
        or not math.isfinite(train_fraction)
        or not 0.5 <= train_fraction <= 0.9
    ):
        raise ValueError("train_fraction must be between 0.5 and 0.9.")
    if (
        isinstance(n_restarts, bool)
        or not isinstance(n_restarts, int)
        or not 1 <= n_restarts <= 10
    ):
        raise ValueError("n_restarts must be an integer from 1 to 10.")
    if (
        isinstance(max_iterations, bool)
        or not isinstance(max_iterations, int)
        or not 20 <= max_iterations <= 1000
    ):
        raise ValueError("max_iterations must be an integer from 20 to 1000.")
    if (
        isinstance(random_seed, bool)
        or not isinstance(random_seed, int)
        or random_seed < 0
    ):
        raise ValueError("random_seed must be a non-negative integer.")

    split_index = int(len(values) * train_fraction)
    if split_index < max(100, n_states * 25) or split_index >= len(values):
        raise RegimeModelError(
            "The chronological training sample is too short for this state count."
        )
    observations = values.to_numpy(dtype=float)
    training = observations[:split_index, None]
    if not np.isfinite(training).all() or np.var(training) <= 0.0:
        raise RegimeModelError("Training returns must have finite, non-zero variance.")

    candidates: list[tuple[float, int, GaussianHMM, bool]] = []
    failures: list[str] = []
    restarts_with_likelihood_decreases = 0
    for restart in range(n_restarts):
        model = GaussianHMM(
            n_components=n_states,
            covariance_type="diag",
            n_iter=max_iterations,
            tol=1e-4,
            min_covar=1e-6,
            random_state=random_seed + restart,
            implementation="log",
        )
        monitor = _LikelihoodMonitor(model.tol, model.n_iter, model.verbose)
        model.monitor_ = monitor
        try:
            model.fit(training)
            score = float(model.score(training))
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            failures.append(str(error))
            continue
        likelihood_decreased = monitor.likelihood_decreased
        restarts_with_likelihood_decreases += likelihood_decreased
        if math.isfinite(score):
            candidates.append((score, restart, model, likelihood_decreased))
        else:
            failures.append("a restart returned a non-finite training score")
    if not candidates:
        detail = failures[0] if failures else "no valid restart was produced"
        raise RegimeModelError(f"Every Gaussian HMM restart failed: {detail}")

    (
        best_score,
        selected_restart,
        best_model,
        selected_restart_had_likelihood_decrease,
    ) = max(candidates, key=lambda item: item[0])
    model_means = np.asarray(best_model.means_, dtype=float).reshape(-1)
    model_covariances = np.asarray(best_model.covars_, dtype=float)
    if model_covariances.ndim == 3:
        model_variances = model_covariances[:, 0, 0]
    elif model_covariances.ndim == 2:
        model_variances = model_covariances[:, 0]
    else:
        raise RegimeModelError("The fitted model returned unexpected covariance data.")
    if (
        not np.isfinite(model_means).all()
        or not np.isfinite(model_variances).all()
        or (model_variances <= 0.0).any()
    ):
        raise RegimeModelError("The fitted model returned invalid emission parameters.")

    ordered_states = np.argsort(model_variances, kind="stable")
    names = _state_names(n_states)
    sorted_means = model_means[ordered_states]
    sorted_variances = model_variances[ordered_states]
    sorted_transition = np.asarray(best_model.transmat_, dtype=float)[
        np.ix_(ordered_states, ordered_states)
    ]

    filtered = _forward_filter(
        observations,
        np.asarray(best_model.startprob_, dtype=float),
        np.asarray(best_model.transmat_, dtype=float),
        model_means,
        model_variances,
    )[:, ordered_states]
    smoothed = np.asarray(best_model.predict_proba(observations[:, None]))[
        :, ordered_states
    ]
    index = values.index
    filtered_frame = pd.DataFrame(filtered, index=index, columns=names)
    smoothed_frame = pd.DataFrame(smoothed, index=index, columns=names)
    filtered_states = pd.Series(
        np.asarray(names, dtype=object)[filtered.argmax(axis=1)],
        index=index,
        name="most_likely_filtered_state",
    )
    transition_frame = pd.DataFrame(
        sorted_transition,
        index=pd.Index(names, name="from state"),
        columns=pd.Index(names, name="to state"),
    )

    return RegimeResult(
        state_names=names,
        filtered_probabilities=filtered_frame,
        smoothed_probabilities=smoothed_frame,
        filtered_states=filtered_states,
        transition_matrix=transition_frame,
        daily_means=pd.Series(sorted_means, index=names, name="daily_mean_log_return"),
        daily_volatilities=pd.Series(
            np.sqrt(sorted_variances),
            index=names,
            name="daily_return_standard_deviation",
        ),
        training_end=index[split_index - 1],
        out_of_sample_start=index[split_index],
        training_observations=split_index,
        out_of_sample_observations=len(values) - split_index,
        training_log_likelihood=best_score,
        converged=bool(best_model.monitor_.converged),
        iterations=int(best_model.monitor_.iter),
        selected_restart=selected_restart,
        restarts_with_likelihood_decreases=restarts_with_likelihood_decreases,
        selected_restart_had_likelihood_decrease=(
            selected_restart_had_likelihood_decrease
        ),
    )
