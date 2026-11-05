from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_quant_models_home_discloses_project_scope_and_placeholders() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app" / "Home.py"

    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert app.title[0].value == "Quant Models Explained"
    assert any("self-directed academic project" in item.value for item in app.caption)
    assert any("pages are scaffolding" in item.value for item in app.info)
