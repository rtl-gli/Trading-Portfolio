from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_quant_models_home_discloses_project_scope_and_model_status() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "Home.py"

    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert app.title[0].value == "Quant Models Explained"
    assert any("self-directed academic project" in item.value for item in app.caption)
    assert any("reference models" in item.value for item in app.info)


def test_option_pricing_page_runs_and_requires_a_prediction() -> None:
    app_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "pages"
        / "3_Longstaff_Schwartz.py"
    )

    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert app.title[0].value == "Option pricing: Black-Scholes and binomial tree"
    assert any("Before calculating" in item.label for item in app.radio)
