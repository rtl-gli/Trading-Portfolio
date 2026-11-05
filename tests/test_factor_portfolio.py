import pandas as pd
import pytest

from portfolio_research.market_data import MarketDataError
from quant_models.factors.portfolio import monthly_portfolio_returns


@pytest.fixture
def daily_prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "AAA": [100.0, 110.0, 121.0, 133.1],
            "BBB": [100.0, 90.0, 81.0, 72.9],
        },
        index=pd.to_datetime(["2023-12-29", "2024-01-31", "2024-02-29", "2024-03-28"]),
    )


def test_monthly_portfolio_returns_are_equal_weighted_and_rebalanced(
    daily_prices: pd.DataFrame,
) -> None:
    returns = monthly_portfolio_returns(daily_prices, ["AAA", "BBB"], "2024-01-01")

    assert returns.index.equals(
        pd.DatetimeIndex(["2024-01-31", "2024-02-29", "2024-03-31"])
    )
    assert returns.to_numpy() == pytest.approx([0.0, 0.0, 0.0])


def test_monthly_portfolio_returns_accept_custom_long_only_weights(
    daily_prices: pd.DataFrame,
) -> None:
    returns = monthly_portfolio_returns(
        daily_prices,
        ["AAA", "BBB"],
        "2024-01-01",
        weights={"AAA": 0.75, "BBB": 0.25},
    )

    assert returns.to_numpy() == pytest.approx([0.05, 0.05, 0.05])


def test_monthly_portfolio_rejects_incomplete_price_panel(
    daily_prices: pd.DataFrame,
) -> None:
    daily_prices.loc["2024-02-29", "BBB"] = None

    with pytest.raises(MarketDataError, match="complete prices"):
        monthly_portfolio_returns(daily_prices, ["AAA", "BBB"], "2024-01-01")


def test_monthly_portfolio_rejects_weights_not_summing_to_one(
    daily_prices: pd.DataFrame,
) -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        monthly_portfolio_returns(
            daily_prices,
            ["AAA", "BBB"],
            "2024-01-01",
            weights={"AAA": 0.5, "BBB": 0.4},
        )
