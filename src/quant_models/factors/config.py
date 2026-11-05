"""Validated configuration for the Fama-French research module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FACTOR_CONFIG = PROJECT_ROOT / "config" / "factors.yaml"


@dataclass(frozen=True)
class FactorSettings:
    """Data source, cache, sample start, and regression defaults."""

    provider: str
    cache_directory: Path
    portfolio_start_date: date
    hac_lags: int
    default_models: tuple[str, ...]


def load_factor_settings(path: Path = DEFAULT_FACTOR_CONFIG) -> FactorSettings:
    """Load factor research settings and resolve the local cache directory."""
    try:
        with Path(path).open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"Unable to load factor configuration: {path}") from error
    if not isinstance(config, dict):
        raise TypeError("Factor configuration must be a YAML mapping.")

    provider = config.get("provider")
    cache_directory = config.get("cache_directory")
    start_date = config.get("portfolio_start_date")
    hac_lags = config.get("hac_lags")
    models = config.get("default_models")
    if provider != "ken_french":
        raise ValueError("Only the configured Ken French data library is supported.")
    if not isinstance(cache_directory, str) or not cache_directory.strip():
        raise ValueError("cache_directory must be a non-empty path.")
    if not isinstance(start_date, str):
        raise TypeError("portfolio_start_date must be an ISO date string.")
    try:
        parsed_start_date = date.fromisoformat(start_date)
    except ValueError as error:
        raise ValueError("portfolio_start_date must use YYYY-MM-DD format.") from error
    if parsed_start_date.isoformat() != start_date:
        raise ValueError("portfolio_start_date must use YYYY-MM-DD format.")
    if (
        isinstance(hac_lags, bool)
        or not isinstance(hac_lags, int)
        or not 0 <= hac_lags <= 24
    ):
        raise ValueError("hac_lags must be an integer from 0 to 24.")
    if (
        not isinstance(models, list)
        or not models
        or any(model not in ("ff3", "ff5") for model in models)
        or len(set(models)) != len(models)
    ):
        raise ValueError("default_models must contain unique 'ff3' and/or 'ff5' names.")

    cache_path = Path(cache_directory)
    if not cache_path.is_absolute():
        cache_path = PROJECT_ROOT / cache_path
    return FactorSettings(
        provider=provider,
        cache_directory=cache_path.resolve(),
        portfolio_start_date=parsed_start_date,
        hac_lags=hac_lags,
        default_models=tuple(models),
    )
