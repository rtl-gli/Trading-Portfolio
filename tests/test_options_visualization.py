import numpy as np
import pytest

from quant_models.options.visualization import (
    synthetic_implied_volatility_surface,
)


def test_synthetic_surface_is_labeled_and_has_positive_volatility() -> None:
    figure = synthetic_implied_volatility_surface()

    assert figure.data[0].type == "surface"
    assert figure.layout.scene.xaxis.title.text == "log(K / S)"
    assert figure.layout.scene.yaxis.title.text == "Maturity (years)"
    assert figure.layout.scene.zaxis.title.text == "Implied volatility (%)"
    assert np.asarray(figure.data[0].z).shape == (16, 25)
    assert np.asarray(figure.data[0].z).min() > 0


def test_synthetic_surface_controls_change_only_the_illustration() -> None:
    default = np.asarray(synthetic_implied_volatility_surface().data[0].z)
    changed = np.asarray(
        synthetic_implied_volatility_surface(
            skew_strength=0.2,
            smile_curvature=0.3,
        )
        .data[0]
        .z
    )

    assert not np.allclose(default, changed)


@pytest.mark.parametrize(
    ("name", "value", "error"),
    [
        ("skew_strength", -0.1, ValueError),
        ("smile_curvature", float("nan"), ValueError),
        ("skew_strength", True, TypeError),
    ],
)
def test_synthetic_surface_rejects_invalid_controls(
    name: str,
    value: float,
    error: type[Exception],
) -> None:
    with pytest.raises(error, match=name):
        synthetic_implied_volatility_surface(**{name: value})
