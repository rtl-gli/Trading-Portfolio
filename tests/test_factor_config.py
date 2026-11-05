import pytest

from quant_models.factors.config import load_factor_settings


def test_factor_settings_load_both_models_and_resolve_local_cache() -> None:
    settings = load_factor_settings()

    assert settings.provider == "ken_french"
    assert settings.default_models == ("ff3", "ff5")
    assert settings.portfolio_start_date.isoformat() == "2013-01-01"
    assert settings.cache_directory.is_absolute()


def test_factor_settings_reject_invalid_hac_lags(tmp_path) -> None:
    config = tmp_path / "factors.yaml"
    config.write_text(
        "provider: ken_french\n"
        "cache_directory: cache\n"
        "portfolio_start_date: '2013-01-01'\n"
        "hac_lags: -1\n"
        "default_models: [ff3, ff5]\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hac_lags"):
        load_factor_settings(config)
