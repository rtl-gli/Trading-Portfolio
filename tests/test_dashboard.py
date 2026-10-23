from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from portfolio_research import dashboard
from portfolio_research.market_data import DataQualityReport, MarketDataResult


def test_streamlit_app_renders_held_out_metrics_with_local_data(
    monkeypatch, tmp_path
) -> None:
    prices = pd.Series(
        100 * (1.0002 ** pd.Series(range(500)).to_numpy()),
        index=pd.bdate_range("2019-01-01", periods=500),
        name="SPY",
    ).to_frame()
    result = MarketDataResult(
        prices=prices,
        quality=DataQualityReport(
            symbols=("SPY",),
            first_date=prices.index[0].date(),
            last_date=prices.index[-1].date(),
            observation_count=len(prices),
            missing_by_symbol=(("SPY", 0),),
        ),
        source="yfinance",
        retrieved_at=datetime.now(UTC),
    )
    monkeypatch.setattr(dashboard, "load_prices", lambda *args: result)
    original_audit_signal_run = dashboard.audit_signal_run
    monkeypatch.setattr(
        dashboard,
        "audit_signal_run",
        lambda *args: original_audit_signal_run(
            *args,
            log_path=tmp_path / "audit.jsonl",
        ),
    )
    original_load_paper_portfolio = dashboard.load_paper_portfolio
    monkeypatch.setattr(
        dashboard,
        "load_paper_portfolio",
        lambda initial_cash: original_load_paper_portfolio(
            database_path=tmp_path / "paper.sqlite3",
            initial_cash=initial_cash,
        ),
    )
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"

    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception
    assert any("prediction before" in item.value for item in app.info)
    app.button[0].click()
    app.run()

    assert not app.exception
    assert len(app.metric) == 11
    assert any("out-of-sample comparison" in item.value for item in app.subheader)
