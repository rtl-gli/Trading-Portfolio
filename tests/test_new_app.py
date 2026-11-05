from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_quant_models_home_discloses_project_scope_and_model_status() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "Home.py"

    app = AppTest.from_file(str(app_path)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Quant Models Explained"
    assert any("self-directed academic project" in item.value for item in app.caption)
    assert any("FF3/FF5 estimates" in item.value for item in app.info)


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
