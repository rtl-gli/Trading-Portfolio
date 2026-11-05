"""Validated illustrative defaults for the option-pricing learning page."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

from quant_models.options.pricing import MAX_TREE_STEPS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPTIONS_CONFIG = PROJECT_ROOT / "config" / "options.yaml"


@dataclass(frozen=True)
class PricingExampleSettings:
    """Synthetic contract and model defaults, not current market observations."""

    spot: float
    strike: float
    days_to_expiry: int
    risk_free_rate: float
    dividend_yield: float
    volatility: float
    tree_steps: int


def load_pricing_example_settings(
    path: Path = DEFAULT_OPTIONS_CONFIG,
) -> PricingExampleSettings:
    """Load illustrative option-pricing defaults from the project YAML file."""
    try:
        with Path(path).open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(
            f"Unable to load option-pricing configuration: {path}"
        ) from error
    if not isinstance(config, dict):
        raise TypeError("Options configuration must be a YAML mapping.")
    example = config.get("pricing_example")
    if not isinstance(example, dict):
        raise TypeError("Options configuration must include pricing_example.")

    required = (
        "spot",
        "strike",
        "days_to_expiry",
        "risk_free_rate",
        "dividend_yield",
        "volatility",
        "tree_steps",
    )
    missing = sorted(set(required) - set(example))
    if missing:
        raise ValueError(f"pricing_example is missing required fields: {missing}.")

    numeric_fields = (
        "spot",
        "strike",
        "risk_free_rate",
        "dividend_yield",
        "volatility",
    )
    values: dict[str, float] = {}
    for field in numeric_fields:
        value = example[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"pricing_example.{field} must be a finite number.")
        if not math.isfinite(value):
            raise ValueError(f"pricing_example.{field} must be a finite number.")
        values[field] = float(value)

    days = example["days_to_expiry"]
    steps = example["tree_steps"]
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("pricing_example.days_to_expiry must be a positive integer.")
    if (
        isinstance(steps, bool)
        or not isinstance(steps, int)
        or not 1 <= steps <= MAX_TREE_STEPS
    ):
        raise ValueError(
            f"pricing_example.tree_steps must be an integer from 1 to {MAX_TREE_STEPS}."
        )
    if values["spot"] <= 0 or values["strike"] <= 0:
        raise ValueError("pricing_example spot and strike must be positive.")
    if values["volatility"] < 0:
        raise ValueError("pricing_example.volatility must not be negative.")

    return PricingExampleSettings(
        spot=values["spot"],
        strike=values["strike"],
        days_to_expiry=days,
        risk_free_rate=values["risk_free_rate"],
        dividend_yield=values["dividend_yield"],
        volatility=values["volatility"],
        tree_steps=steps,
    )
