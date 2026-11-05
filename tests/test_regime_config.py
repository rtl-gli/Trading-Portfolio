import pytest

from quant_models.regimes.config import load_regime_settings


def test_regime_settings_load_project_defaults() -> None:
    settings = load_regime_settings()

    assert settings.symbol == "SPY"
    assert settings.start_date.isoformat() == "2000-01-01"
    assert settings.n_states == 2
    assert settings.train_fraction == 0.7
    assert settings.n_restarts == 5


def test_regime_settings_reject_invalid_state_count(tmp_path) -> None:
    config = tmp_path / "regimes.yaml"
    config.write_text(
        "symbol: SPY\n"
        "start_date: '2000-01-01'\n"
        "train_fraction: 0.7\n"
        "n_states: 1\n"
        "n_restarts: 5\n"
        "max_iterations: 200\n"
        "random_seed: 42\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="n_states"):
        load_regime_settings(config)
