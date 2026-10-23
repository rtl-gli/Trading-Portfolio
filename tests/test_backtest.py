import json
from pathlib import Path

import pandas as pd
import pytest

from portfolio_research.backtest import run_sma_vs_buy_and_hold
from portfolio_research.config import (
    SmaSettings,
    load_dashboard_settings,
    load_sma_settings,
)


def test_sma_waits_until_after_signal_and_fill_before_earning_returns() -> None:
    prices = pd.Series(
        [100, 101, 102, 103, 104, 105],
        index=pd.date_range("2024-01-02", periods=6),
    )
    settings = SmaSettings(2, 3, 5, 5, 1)

    result = run_sma_vs_buy_and_hold(prices, settings)

    assert result.sma.signals.iloc[2] == 1
    assert result.sma.positions.iloc[2] == 0
    assert result.sma.positions.iloc[3] == 0
    assert result.sma.positions.iloc[4] == 1
    assert result.sma.transaction_costs.iloc[3] == pytest.approx(0.001)
    assert result.sma.net_returns.iloc[3] < result.sma.gross_returns.iloc[3]


def test_terminal_exit_cost_is_not_charged_twice() -> None:
    prices = pd.Series(
        [10, 11, 12, 13, 14, 15, 13, 12],
        index=pd.date_range("2024-01-02", periods=8),
    )
    settings = SmaSettings(2, 3, 5, 5, 1)

    result = run_sma_vs_buy_and_hold(prices, settings)

    assert result.sma.signals.iloc[-2] == 0
    assert result.sma.transaction_costs.iloc[-1] == pytest.approx(0.001)


def test_buy_and_hold_pays_entry_and_terminal_exit_costs() -> None:
    prices = pd.Series(
        [100, 101, 102, 103, 104],
        index=pd.date_range("2024-01-02", periods=5),
    )

    result = run_sma_vs_buy_and_hold(prices, SmaSettings(2, 3, 5, 5, 1))

    assert result.buy_and_hold.transaction_costs.iloc[0] == pytest.approx(0.001)
    assert result.buy_and_hold.transaction_costs.iloc[-1] == pytest.approx(0.001)


def test_backtest_rejects_missing_prices() -> None:
    prices = pd.Series(
        [10.0, None, 12.0, 13.0, 14.0],
        index=pd.date_range("2024-01-02", periods=5),
    )

    with pytest.raises(ValueError, match="missing prices"):
        run_sma_vs_buy_and_hold(prices, SmaSettings(2, 3, 5, 5, 1))


def test_configured_sma_parameters_are_loaded_from_yaml() -> None:
    settings = load_sma_settings()

    assert (settings.fast_window, settings.slow_window) == (50, 200)
    assert settings.transaction_cost_bps_per_side == 5
    assert settings.slippage_bps_per_side == 5
    assert settings.execution_delay_bars >= 1


def test_dashboard_defaults_match_configured_universe() -> None:
    dashboard_settings = load_dashboard_settings()

    assert dashboard_settings.default_asset == "SPY"
    assert dashboard_settings.default_start_date < dashboard_settings.default_end_date


def test_learning_notebooks_are_valid_json_with_compilable_code_cells() -> None:
    notebook_directory = Path(__file__).resolve().parents[1] / "notebooks"
    for notebook_name in ("03_sma_backtest.ipynb", "04_performance_metrics.ipynb"):
        notebook_path = notebook_directory / notebook_name
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

        assert notebook["nbformat"] == 4
        for cell_number, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                compile(
                    "".join(cell["source"]),
                    f"{notebook_name} cell {cell_number}",
                    "exec",
                )
