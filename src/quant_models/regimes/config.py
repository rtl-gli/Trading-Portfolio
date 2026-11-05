"""Validated configuration for the regime-switching research page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGIME_CONFIG = PROJECT_ROOT / "config" / "regimes.yaml"


@dataclass(frozen=True)
class RegimeSettings:
    """Data request and default Gaussian HMM fitting settings."""

    symbol: str
    start_date: date
    train_fraction: float
    n_states: int
    n_restarts: int
    max_iterations: int
    random_seed: int


def load_regime_settings(path: Path = DEFAULT_REGIME_CONFIG) -> RegimeSettings:
    """Load regime settings from a YAML mapping and validate their ranges."""
    try:
        with Path(path).open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"Unable to load regime configuration: {path}") from error
    if not isinstance(config, dict):
        raise TypeError("Regime configuration must be a YAML mapping.")

    symbol = config.get("symbol")
    start_date = config.get("start_date")
    train_fraction = config.get("train_fraction")
    n_states = config.get("n_states")
    n_restarts = config.get("n_restarts")
    max_iterations = config.get("max_iterations")
    random_seed = config.get("random_seed")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty ticker.")
    if not isinstance(start_date, str):
        raise TypeError("start_date must be an ISO date string.")
    try:
        parsed_start = date.fromisoformat(start_date)
    except ValueError as error:
        raise ValueError("start_date must use YYYY-MM-DD format.") from error
    if parsed_start.isoformat() != start_date:
        raise ValueError("start_date must use YYYY-MM-DD format.")
    if (
        isinstance(train_fraction, bool)
        or not isinstance(train_fraction, (int, float))
        or not 0.5 <= train_fraction <= 0.9
    ):
        raise ValueError("train_fraction must be between 0.5 and 0.9.")
    if (
        isinstance(n_states, bool)
        or not isinstance(n_states, int)
        or not 2 <= n_states <= 4
    ):
        raise ValueError("n_states must be an integer from 2 to 4.")
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
    return RegimeSettings(
        symbol=symbol.strip().upper(),
        start_date=parsed_start,
        train_fraction=float(train_fraction),
        n_states=n_states,
        n_restarts=n_restarts,
        max_iterations=max_iterations,
        random_seed=random_seed,
    )
