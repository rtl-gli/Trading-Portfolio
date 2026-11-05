"""Clearly synthetic visual aids for option-model lessons."""

from __future__ import annotations

import math

import numpy as np
import plotly.graph_objects as go


def synthetic_implied_volatility_surface(
    *,
    skew_strength: float = 0.12,
    smile_curvature: float = 0.18,
) -> go.Figure:
    """Build an illustrative, non-calibrated implied-volatility surface.

    The surface is a teaching aid, not an option-pricing result or a Heston
    model output. Its coefficients are deliberately user-adjustable.
    """
    for name, value in (
        ("skew_strength", skew_strength),
        ("smile_curvature", smile_curvature),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a finite number.")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative.")

    log_moneyness = np.linspace(-0.4, 0.4, 25)
    maturities = np.linspace(0.1, 2.0, 16)
    moneyness_grid, maturity_grid = np.meshgrid(log_moneyness, maturities)
    volatility_surface = 100 * (
        0.22
        - skew_strength * moneyness_grid * np.exp(-maturity_grid / 1.5)
        + smile_curvature * moneyness_grid**2
        + 0.025 * np.exp(-maturity_grid / 0.75)
    )

    figure = go.Figure(
        go.Surface(
            x=moneyness_grid,
            y=maturity_grid,
            z=volatility_surface,
            colorscale="Viridis",
            colorbar={"title": "Implied volatility (%)"},
            hovertemplate=(
                "Log-moneyness: %{x:.2f}<br>"
                "Maturity: %{y:.2f} years<br>"
                "Illustrative volatility: %{z:.1f}%<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        scene={
            "xaxis_title": "log(K / S)",
            "yaxis_title": "Maturity (years)",
            "zaxis_title": "Implied volatility (%)",
            "camera": {"eye": {"x": 1.5, "y": 1.7, "z": 1.25}},
        },
        height=560,
        margin={"l": 15, "r": 15, "t": 10, "b": 40},
        template="plotly_white",
    )
    return figure
