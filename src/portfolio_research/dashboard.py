"""Streamlit research playground for the tested SMA backtest."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from portfolio_research.backtest import run_sma_vs_buy_and_hold
from portfolio_research.config import (
    SmaSettings,
    load_dashboard_settings,
    load_sma_settings,
    load_universe,
)
from portfolio_research.market_data import MarketDataError, load_prices
from portfolio_research.metrics import calculate_metrics

METRIC_LEARNING = {
    "CAGR": (
        "Compounded annual growth rate over the observed calendar period.",
        "One start and end date can dominate CAGR; it does not describe the path taken.",
    ),
    "Sharpe": (
        "Annualised excess return per unit of daily return volatility.",
        "It treats upside and downside variation alike and is unstable on short samples.",
    ),
    "Max drawdown": (
        "Largest percentage fall from a previous portfolio-value peak.",
        "The result depends on this historical window and says nothing about recovery time.",
    ),
    "Volatility": (
        "Annualised standard deviation of daily returns.",
        "Volatility is not the same as permanent loss and does not capture every tail event.",
    ),
    "Historical VaR": (
        "Negated empirical return quantile at the configured confidence level.",
        "It is a sample quantile, not a worst-case loss or a forecast.",
    ),
    "Beta vs SPY": (
        "Return covariance with SPY divided by SPY return variance.",
        "Beta depends on the benchmark and sample; it does not measure all portfolio risk.",
    ),
}


def _display_metric(label: str, value: float | None, help_text: str) -> None:
    if value is None:
        rendered = "Not available"
    elif label == "Beta vs SPY":
        rendered = f"{value:.2f}"
    else:
        rendered = f"{value:.2%}"
    st.metric(label, rendered, help=help_text)


def main() -> None:
    st.set_page_config(page_title="Portfolio Research Lab", layout="wide")
    dashboard_settings = load_dashboard_settings()
    sma_defaults = load_sma_settings()
    universe = load_universe()
    if dashboard_settings.default_asset not in universe.symbols:
        st.error("dashboard.default_asset must appear in config/universe.yaml.")
        return

    st.title("Portfolio Research Lab")
    st.caption(
        "Self-directed academic research. Paper results only—not investment advice "
        "or live performance."
    )
    st.warning(
        "The fixed universe uses companies known today. Survivorship bias means "
        "failed and former index constituents are missing."
    )

    with st.sidebar:
        st.header("Research inputs")
        asset = st.selectbox(
            "Asset",
            options=universe.symbols,
            index=universe.symbols.index(dashboard_settings.default_asset),
            help="Choose the single asset for this SMA demonstration.",
        )
        date_range = st.date_input(
            "Date range (end date exclusive)",
            value=(
                dashboard_settings.default_start_date,
                dashboard_settings.default_end_date,
            ),
            help="Daily bars before the selected start or on/after the end are excluded.",
        )
        fast_window = st.number_input(
            "Fast SMA window (sessions)",
            min_value=2,
            max_value=500,
            value=sma_defaults.fast_window,
            step=1,
            help="Number of past daily adjusted closes in the fast average.",
        )
        slow_window = st.number_input(
            "Slow SMA window (sessions)",
            min_value=2,
            max_value=500,
            value=sma_defaults.slow_window,
            step=1,
            help="Must exceed the fast window. All settings are stored in YAML.",
        )
        transaction_cost = st.number_input(
            "Transaction cost (bps per side)",
            min_value=0.0,
            max_value=100.0,
            value=sma_defaults.transaction_cost_bps_per_side,
            step=1.0,
            help="One basis point is 0.01%; charged on each unit of turnover.",
        )
        slippage = st.number_input(
            "Slippage (bps per side)",
            min_value=0.0,
            max_value=100.0,
            value=sma_defaults.slippage_bps_per_side,
            step=1.0,
            help="An explicit execution-friction assumption, charged with transaction cost.",
        )
        learning_mode = st.toggle(
            "Learning mode",
            value=True,
            help="Show plain-English metric and chart explanations plus caveats.",
        )

    if (
        not isinstance(date_range, tuple)
        or len(date_range) != 2
        or date_range[0] is None
        or date_range[1] is None
    ):
        st.info("Select both a start and end date to run the comparison.")
        return
    start_date, end_date = date_range
    if start_date >= end_date:
        st.error("The start date must be earlier than the exclusive end date.")
        return
    if fast_window >= slow_window:
        st.error("The fast SMA window must be shorter than the slow SMA window.")
        return

    symbols = [asset] if asset == "SPY" else [asset, "SPY"]
    settings = SmaSettings(
        fast_window=int(fast_window),
        slow_window=int(slow_window),
        transaction_cost_bps_per_side=float(transaction_cost),
        slippage_bps_per_side=float(slippage),
        execution_delay_bars=sma_defaults.execution_delay_bars,
    )
    try:
        with st.spinner("Loading and validating adjusted daily prices..."):
            data = load_prices(symbols, start_date, end_date)
        common_start = max(
            data.prices[symbol].first_valid_index() for symbol in symbols
        )
        excluded_initial_bars = int((data.prices.index < common_start).sum())
        aligned_prices = data.prices.loc[common_start:, symbols]
        if aligned_prices.isna().any().any():
            raise ValueError(
                "There are missing observations after the assets first overlap. "
                "Investigate the data before comparing returns; this dashboard "
                "does not fill or silently drop those bars."
            )
        comparison = run_sma_vs_buy_and_hold(aligned_prices[asset], settings)
        spy_returns = aligned_prices["SPY"].pct_change(fill_method=None)
        spy_returns.iloc[0] = 0.0
        sma_metrics = calculate_metrics(comparison.sma.net_returns, spy_returns)
        hold_metrics = calculate_metrics(
            comparison.buy_and_hold.net_returns, spy_returns
        )
    except (MarketDataError, ValueError) as error:
        st.error(f"Research run stopped: {error}")
        return

    if data.source == "stale_cache":
        st.warning(
            "Using an expired local cache because offline data was requested. "
            "Verify the retrieval date before interpreting results."
        )
    st.caption(
        f"Data source: {data.source} · Retrieved: {data.retrieved_at.isoformat()} · "
        f"Observed dates: {data.quality.first_date} to {data.quality.last_date}"
    )
    st.caption(f"Missing data by requested asset: {data.quality.missing_by_symbol}")
    if excluded_initial_bars:
        st.info(
            f"Excluded {excluded_initial_bars} leading sessions before {asset} and "
            "SPY both had prices. No missing prices were imputed."
        )

    st.subheader(f"{asset}: SMA crossover versus buy-and-hold")
    metric_columns = st.columns(6)
    metric_values = (
        ("CAGR", sma_metrics.cagr, hold_metrics.cagr),
        ("Sharpe", sma_metrics.sharpe_ratio, hold_metrics.sharpe_ratio),
        ("Max drawdown", sma_metrics.max_drawdown, hold_metrics.max_drawdown),
        (
            "Volatility",
            sma_metrics.annualized_volatility,
            hold_metrics.annualized_volatility,
        ),
        ("Historical VaR", sma_metrics.historical_var, hold_metrics.historical_var),
        ("Beta vs SPY", sma_metrics.beta, hold_metrics.beta),
    )
    for column, (label, strategy_value, benchmark_value) in zip(
        metric_columns, metric_values, strict=True
    ):
        with column:
            _display_metric(label, strategy_value, METRIC_LEARNING[label][0])
            st.caption(f"Buy-and-hold: {_format_metric(label, benchmark_value)}")
            if learning_mode:
                explanation, caveat = METRIC_LEARNING[label]
                st.caption(f"**What it means:** {explanation}")
                st.caption(f"**Why it can mislead:** {caveat}")

    wealth = (
        (1 + comparison.sma.net_returns)
        .cumprod()
        .rename("SMA, net of costs")
        .to_frame()
    )
    wealth["Buy-and-hold, net of costs"] = (
        1 + comparison.buy_and_hold.net_returns
    ).cumprod()
    st.subheader("Growth of a notional $1")
    st.line_chart(wealth)
    if learning_mode:
        st.caption(
            "**What it means:** cumulative portfolio value after modeled costs. "
            "**Why it can mislead:** this historical path is sensitive to the selected "
            "dates and assumptions; it is not a forecast."
        )

    st.subheader("Position and modeled costs")
    daily_detail = pd.DataFrame(
        {
            "SMA position": comparison.sma.positions,
            "SMA transaction cost": comparison.sma.transaction_costs,
            "Buy-and-hold transaction cost": comparison.buy_and_hold.transaction_costs,
        }
    )
    st.line_chart(daily_detail)
    if learning_mode:
        st.caption(
            "Positions change only after delayed signals. Costs are fractions of "
            "portfolio value on the simulated execution date, including final exit."
        )

    warnings = (*sma_metrics.warnings, *hold_metrics.warnings)
    if warnings:
        st.warning("Metric limitations: " + " ".join(dict.fromkeys(warnings)))

    with st.expander("Glossary"):
        st.markdown(
            """
            - **SMA:** simple moving average of past prices.
            - **Signal:** rule output computed from information available at that close.
            - **Position:** exposure held after the configured execution delay.
            - **Basis point (bp):** one hundredth of one percent.
            - **CAGR:** compounded annual growth rate over the measured calendar period.
            - **Sharpe ratio:** annualised excess return divided by return volatility.
            - **Drawdown:** decline from a previous portfolio-value high.
            - **Volatility:** annualised standard deviation of daily returns.
            - **VaR:** historical lower-tail return quantile, shown as a loss number.
            - **Beta:** sensitivity to the supplied SPY benchmark in this sample.
            """
        )


def _format_metric(label: str, value: float | None) -> str:
    if value is None:
        return "not available"
    if label == "Beta vs SPY":
        return f"{value:.2f}"
    return f"{value:.2%}"


if __name__ == "__main__":
    main()
