from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest


def test_quant_models_home_discloses_project_scope_and_model_status() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "Home.py"

    app = AppTest.from_file(str(app_path)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Quant Models Explained"
    assert any(
        "self-directed academic learning project" in item.value for item in app.caption
    )
    assert any("Gaussian hidden-state" in item.value for item in app.info)


def test_option_pricing_page_runs_and_requires_a_prediction() -> None:
    app_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "pages"
        / "3_Longstaff_Schwartz.py"
    )

    app = AppTest.from_file(str(app_path)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Option pricing: Black-Scholes and binomial tree"
    assert any("Before calculating" in item.label for item in app.radio)


def test_factor_page_loads_without_requesting_live_data_before_prediction() -> None:
    app_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "pages"
        / "1_Fama_French_Factors.py"
    )

    app = AppTest.from_file(str(app_path)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Fama-French factor regressions"
    assert any("Before running the regressions" in item.label for item in app.radio)
    assert not app.metric


def test_regime_page_loads_without_requesting_market_data_before_submission() -> None:
    app_path = (
        Path(__file__).resolve().parents[1] / "app" / "pages" / "2_Regime_Switching.py"
    )

    app = AppTest.from_file(str(app_path)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Market regimes with a hidden Markov model"
    assert any("Before fitting" in item.label for item in app.radio)
    assert not app.metric


def test_regime_page_renders_model_and_visuals_after_submission(monkeypatch) -> None:
    random = np.random.default_rng(16)
    dates = pd.bdate_range("2022-01-03", periods=800)
    log_returns = random.normal(0.0002, 0.012, len(dates))
    prices = pd.DataFrame(
        {"SPY": 100.0 * np.exp(np.cumsum(log_returns))},
        index=dates,
    )
    market_data = SimpleNamespace(
        prices=prices,
        source="cache",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    monkeypatch.setattr(
        "portfolio_research.market_data.load_prices",
        lambda symbols, start, end: market_data,
    )
    app_path = (
        Path(__file__).resolve().parents[1] / "app" / "pages" / "2_Regime_Switching.py"
    )
    app = AppTest.from_file(str(app_path)).run(timeout=20)
    app.form_submit_button[0].click().run(timeout=60)

    assert not app.exception
    assert len(app.metric) == 3
    assert any("Filtered probabilities" in item.value for item in app.markdown)
    assert len(app.get("plotly_chart")) >= 3


def test_model_guide_explains_all_four_models() -> None:
    app_path = (
        Path(__file__).resolve().parents[1] / "app" / "pages" / "0_Model_Guide.py"
    )

    app = AppTest.from_file(str(app_path)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "A beginner's guide to the models"
    assert len(app.tabs) == 4
    assert len(app.get("plotly_chart")) == 1
    assert any("synthetic" in item.value.lower() for item in app.markdown)
    assert len(app.latex) >= 4
    assert all("$$" not in item.value for item in app.markdown)
    assert any(r"\qquad\,r_t" in item.value for item in app.latex)


def test_heston_page_teaches_equations_and_marks_surface_as_synthetic() -> None:
    app_path = (
        Path(__file__).resolve().parents[1] / "app" / "pages" / "4_Heston_Model.py"
    )

    app = AppTest.from_file(str(app_path)).run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "Heston stochastic-volatility model"
    assert any(
        "does not yet implement Heston option pricing" in item.value
        for item in app.info
    )
    assert len(app.latex) >= 4
    assert "dS_t" in app.latex[0].value
    assert len(app.get("plotly_chart")) == 1
    assert any(
        "not guaranteed to be arbitrage-free" in item.value for item in app.caption
    )
