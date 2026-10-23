from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from portfolio_research import dashboard
from portfolio_research.market_data import DataQualityReport, MarketDataResult


def test_streamlit_app_renders_held_out_metrics_with_local_data(
    monkeypatch,
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
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"

    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert len(app.metric) == 6
    assert any("out-of-sample comparison" in item.value for item in app.subheader)
