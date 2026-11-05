import pytest

from quant_models.options.config import load_pricing_example_settings


def test_pricing_defaults_are_loaded_from_options_yaml() -> None:
    settings = load_pricing_example_settings()

    assert settings.spot == 100
    assert settings.strike == 100
    assert settings.tree_steps == 100


def test_pricing_defaults_reject_nonpositive_spot(tmp_path) -> None:
    config = tmp_path / "options.yaml"
    config.write_text(
        "pricing_example:\n"
        "  spot: 0\n"
        "  strike: 100\n"
        "  days_to_expiry: 30\n"
        "  risk_free_rate: 0.05\n"
        "  dividend_yield: 0.02\n"
        "  volatility: 0.2\n"
        "  tree_steps: 100\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="spot and strike must be positive"):
        load_pricing_example_settings(config)
