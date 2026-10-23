import pytest

from portfolio_research.config import load_paper_trading_settings


def test_paper_account_starting_balance_is_loaded_from_yaml() -> None:
    settings = load_paper_trading_settings()

    assert settings.initial_cash_usd == 10_000


def test_paper_account_rejects_invalid_starting_balance(tmp_path) -> None:
    config = tmp_path / "project.yaml"
    config.write_text(
        "paper_trading:\n  initial_cash_usd: 0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="positive and finite"):
        load_paper_trading_settings(config)
