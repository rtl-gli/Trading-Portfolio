"""Interactive, prediction-first Fama-French factor regression page."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from portfolio_research.config import load_universe
from portfolio_research.market_data import (
    MarketDataError,
    MarketDataResult,
    load_prices,
)
from quant_models.factors.config import load_factor_settings
from quant_models.factors.data import FactorDataError, load_fama_french_factors
from quant_models.factors.portfolio import monthly_portfolio_returns
from quant_models.factors.regression import run_factor_regression

st.title("Fama-French factor regressions")
st.markdown(
    """
    A factor regression asks whether broad return patterns help explain a
    portfolio's **excess return**. The intercept (alpha) is what remains after
    the selected factors; an estimate near zero is not proof of no skill, and
    an estimate away from zero is not proof of skill.
    """
)
st.info(
    "This page compares the classic three-factor (FF3) and five-factor (FF5) "
    "specifications. Factor data comes from the official Ken French Data Library; "
    "adjusted stock prices come from the project's validated yfinance cache."
)


@st.cache_data(ttl="1h", max_entries=8)
def _load_prices_cached(
    symbols: tuple[str, ...], start: date, end: date
) -> MarketDataResult:
    return load_prices(symbols, start, end)


try:
    settings = load_factor_settings()
    universe = load_universe()
except (OSError, TypeError, ValueError) as error:
    st.error(f"Cannot load factor or stock-universe configuration: {error}")
    st.stop()

today = date.today()
with st.form("factor-regression-inputs"):
    selected_symbols = st.multiselect(
        "Stocks to include in the portfolio",
        options=list(universe.stock_symbols),
        default=list(universe.stock_symbols),
        help=(
            "The default is the fixed 30-stock list. The chosen constituents are "
            "survivorship-biased; there is no historical point-in-time universe."
        ),
    )
    weight_frame = pd.DataFrame(
        {
            "symbol": selected_symbols,
            "weight": (
                [1.0 / len(selected_symbols)] * len(selected_symbols)
                if selected_symbols
                else []
            ),
        }
    )
    st.caption("Weights must be long-only and sum to 1. They are reset monthly.")
    edited_weights = st.data_editor(
        weight_frame,
        hide_index=True,
        num_rows="fixed",
        disabled=["symbol"],
        column_config={
            "weight": st.column_config.NumberColumn(
                "Target weight",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                format="%.4f",
            )
        },
    )
    start_date = st.date_input(
        "First regression month",
        value=settings.portfolio_start_date,
        min_value=date(1990, 1, 1),
        max_value=today,
    )
    models = st.multiselect(
        "Factor specifications",
        options=["ff3", "ff5"],
        default=list(settings.default_models),
        format_func=lambda value: value.upper(),
    )
    hac_lags = st.slider(
        "Newey-West HAC lags (months)",
        min_value=0,
        max_value=24,
        value=settings.hac_lags,
        help=(
            "The covariance estimator allows residual autocorrelation through "
            "this many monthly lags. The choice is a modelling assumption."
        ),
    )
    refresh_factor_cache = st.checkbox(
        "Refresh cached Ken French factor files",
        value=False,
        help="A refresh downloads the latest file from the official source.",
    )
    alpha_prediction = st.radio(
        "Before running the regressions, what do you expect about alpha?",
        ("Not statistically distinguishable from zero", "Statistically significant"),
    )
    submitted = st.form_submit_button("Run factor regressions")

if submitted:
    if not selected_symbols:
        st.error("Select at least one stock.")
    elif not models:
        st.error("Select at least one factor specification.")
    else:
        weights = {
            str(row["symbol"]): float(row["weight"])
            for _, row in edited_weights.iterrows()
        }
        price_start = start_date - timedelta(days=45)
        price_end = today + timedelta(days=1)
        try:
            with st.spinner(
                "Loading adjusted prices, validating factor data, and fitting models..."
            ):
                market_data = _load_prices_cached(
                    tuple(selected_symbols),
                    price_start,
                    price_end,
                )
                portfolio_returns = monthly_portfolio_returns(
                    market_data.prices,
                    selected_symbols,
                    start_date,
                    weights=weights,
                )
                model_results = []
                for model in models:
                    factor_dataset = load_fama_french_factors(
                        model,
                        settings.cache_directory,
                        refresh=refresh_factor_cache,
                    )
                    regression = run_factor_regression(
                        portfolio_returns,
                        factor_dataset.factors,
                        model,
                        hac_lags=hac_lags,
                    )
                    model_results.append((factor_dataset, regression))
        except (
            FactorDataError,
            MarketDataError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            st.error(f"Factor regression could not be completed: {error}")
        else:
            st.subheader("What the data say")
            st.caption(
                f"Your prediction: **{alpha_prediction}**. "
                f"Portfolio weights are reset monthly; reported returns are "
                f"before transaction costs. Price source: **{market_data.source}** "
                f"(retrieved {market_data.retrieved_at.isoformat()})."
            )
            st.warning(
                "The fixed present-day stock list has survivorship bias. This is "
                "an explanatory model, not a strategy backtest; alpha is not "
                "evidence of investment skill."
            )
            for factor_dataset, result in model_results:
                alpha_significant = result.alpha_p_value < 0.05
                result_alpha_status = (
                    "Statistically significant"
                    if alpha_significant
                    else "Not statistically distinguishable from zero"
                )
                st.markdown(f"### {result.model.upper()}")
                if result_alpha_status == alpha_prediction:
                    st.success(
                        f"Your prediction matched the 5% test: "
                        f"{result_alpha_status.lower()}."
                    )
                else:
                    st.info(
                        f"Your prediction did not match the 5% test: "
                        f"{result_alpha_status.lower()}."
                    )

                alpha_column, error_column, interval_column, fit_column = st.columns(4)
                alpha_column.metric(
                    "Monthly alpha",
                    f"{result.alpha * 100:.3f}%",
                    help="Intercept in monthly excess-return units.",
                )
                error_column.metric(
                    "Newey-West standard error",
                    f"{result.alpha_standard_error * 100:.3f}%",
                )
                interval_column.metric(
                    "Alpha p-value",
                    f"{result.alpha_p_value:.4f}",
                    help="HAC-robust two-sided test of alpha equal to zero.",
                )
                fit_column.metric("R-squared", f"{result.r_squared:.3f}")
                st.caption(
                    f"95% HAC confidence interval: "
                    f"[{result.alpha_confidence_interval[0] * 100:.3f}%, "
                    f"{result.alpha_confidence_interval[1] * 100:.3f}%] monthly. "
                    f"{result.observations} months, "
                    f"{result.sample_start:%Y-%m} to {result.sample_end:%Y-%m}, "
                    f"{result.hac_lags} HAC lags."
                )
                st.dataframe(
                    result.coefficients.style.format(
                        {
                            "coefficient": "{:.4f}",
                            "newey_west_standard_error": "{:.4f}",
                            "t_statistic": "{:.2f}",
                            "p_value": "{:.4f}",
                            "ci_95_lower": "{:.4f}",
                            "ci_95_upper": "{:.4f}",
                        }
                    ),
                    use_container_width=True,
                )
                st.caption(
                    f"Factor file: {factor_dataset.source}; retrieved "
                    f"{factor_dataset.retrieved_at.isoformat()}; "
                    f"SHA-256 {factor_dataset.sha256}."
                )
                st.caption(
                    f"Date alignment used {result.alignment.used_months} months; "
                    f"{result.alignment.incomplete_factor_months} overlapping "
                    f"months had missing factor values, and "
                    f"{result.alignment.portfolio_months_without_factors} portfolio "
                    f"months had no factor row. No values were filled."
                )

st.subheader("How to read this without fooling yourself")
st.markdown(
    """
    - The dependent variable is portfolio return **minus RF**. The library's
      factor values, including `RF`, are published in percent and converted to
      decimals before alignment.
    - Newey-West errors adjust inference for heteroskedasticity and serial
      correlation; they do not repair a wrong portfolio, bad data, or model
      misspecification.
    - FF3 omits profitability and investment factors. FF5 may explain patterns
      that otherwise appear in FF3 alpha; neither model is automatically true.
    - A 5% p-value is not the probability that skill is real. Survivorship,
      specification search, data revisions, and multiple testing remain risks.
    """
)
