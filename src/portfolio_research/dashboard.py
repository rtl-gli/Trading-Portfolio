"""Streamlit research playground for the tested SMA backtest."""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from portfolio_research.audit import audit_signal_run
from portfolio_research.backtest import (
    run_buy_and_hold_backtest,
    run_portfolio_backtest,
    run_signal_backtest,
)
from portfolio_research.bias_lab import (
    compare_portfolio_biases,
    compare_signal_biases,
    select_sma_on_full_sample,
)
from portfolio_research.config import (
    SmaSettings,
    load_dashboard_settings,
    load_paper_trading_settings,
    load_sma_settings,
    load_strategy_settings,
    load_universe,
)
from portfolio_research.market_data import MarketDataError, load_prices
from portfolio_research.metrics import calculate_metrics
from portfolio_research.paper_trading import (
    add_trade_review,
    load_paper_portfolio,
    record_paper_trade,
)
from portfolio_research.quiz import select_question
from portfolio_research.strategies import (
    equal_weight_targets,
    mean_reversion_signals,
    momentum_signals,
    rolling_markowitz_weights,
    sma_signals,
    walk_forward_start,
)

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

METRIC_FIELDS = {
    "CAGR": "cagr",
    "Sharpe": "sharpe_ratio",
    "Max drawdown": "max_drawdown",
    "Volatility": "annualized_volatility",
    "Historical VaR": "historical_var",
    "Beta vs SPY": "beta",
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
    paper_settings = load_paper_trading_settings()
    sma_defaults = load_sma_settings()
    strategy_defaults = load_strategy_settings()
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
        strategy_name = st.selectbox(
            "Strategy",
            options=[
                "SMA crossover",
                "Momentum",
                "Mean reversion",
                "Walk-forward Markowitz",
            ],
            help="Compare fixed rules or rolling mean-variance allocation.",
        )
        if strategy_name == "Walk-forward Markowitz":
            selected_assets = st.multiselect(
                "Portfolio assets",
                options=tuple(universe.etfs),
                default=list(universe.etfs),
                help="Choose at least two ETFs for the long-only portfolio.",
            )
            asset = None
        else:
            asset = st.selectbox(
                "Asset",
                options=universe.symbols,
                index=universe.symbols.index(dashboard_settings.default_asset),
                help="Choose a single asset for this signal strategy.",
            )
            selected_assets = []
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
        train_fraction = st.slider(
            "Warm-up / estimation share",
            min_value=0.5,
            max_value=0.9,
            value=0.7,
            step=0.05,
            help=(
                "Only the final share is evaluated. Earlier data supplies trailing "
                "signal history or rolling parameter estimates."
            ),
        )
        if strategy_name == "Momentum":
            momentum_lookback = st.number_input(
                "Momentum lookback (sessions)",
                min_value=2,
                max_value=500,
                value=strategy_defaults.momentum_lookback_sessions,
                step=1,
            )
        else:
            momentum_lookback = strategy_defaults.momentum_lookback_sessions
        if strategy_name == "Mean reversion":
            reversion_lookback = st.number_input(
                "Mean-reversion lookback (sessions)",
                min_value=2,
                max_value=250,
                value=strategy_defaults.mean_reversion_lookback_sessions,
                step=1,
            )
            entry_z_score = st.slider(
                "Entry z-score",
                min_value=0.5,
                max_value=4.0,
                value=strategy_defaults.mean_reversion_entry_z_score,
                step=0.1,
            )
        else:
            reversion_lookback = strategy_defaults.mean_reversion_lookback_sessions
            entry_z_score = strategy_defaults.mean_reversion_entry_z_score
        learning_mode = st.toggle(
            "Learning mode",
            value=True,
            help="Show plain-English metric and chart explanations plus caveats.",
        )
        st.subheader("Bias lab")
        show_cost_bias = st.checkbox("Show results with costs ignored")
        show_lookahead_bias = st.checkbox("Show look-ahead biased results")
        show_overfit_bias = st.checkbox("Search SMA settings on the full sample")
        st.subheader("Predict then run")
        predicted_to_beat = st.radio(
            "Will the strategy beat its benchmark?",
            options=("Yes", "No"),
            horizontal=True,
        )
        predicted_drawdown = st.slider(
            "Guess maximum drawdown (loss %)",
            min_value=0.0,
            max_value=80.0,
            value=20.0,
            step=1.0,
        )
        lock_prediction = st.button("Lock prediction and run", type="primary")

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
    if strategy_name == "SMA crossover" and fast_window >= slow_window:
        st.error("The fast SMA window must be shorter than the slow SMA window.")
        return
    if strategy_name == "Walk-forward Markowitz" and len(selected_assets) < 2:
        st.error("Select at least two ETFs for Markowitz optimisation.")
        return

    equal_weight_returns = None
    equal_weight_positions = None
    equal_weight_targets_panel = None
    run_signature = (
        strategy_name,
        tuple(selected_assets),
        asset,
        start_date,
        end_date,
        int(fast_window),
        int(slow_window),
        float(transaction_cost),
        float(slippage),
        float(train_fraction),
        int(momentum_lookback),
        int(reversion_lookback),
        float(entry_z_score),
    )
    if lock_prediction:
        st.session_state["locked_prediction"] = (
            run_signature,
            predicted_to_beat,
            float(predicted_drawdown),
        )
    locked_prediction = st.session_state.get("locked_prediction")
    if not locked_prediction or locked_prediction[0] != run_signature:
        st.info(
            "Make and lock your prediction before the backtest runs. Changing "
            "research inputs requires a new prediction."
        )
        return

    symbols = (
        sorted(set(selected_assets) | {"SPY"})
        if strategy_name == "Walk-forward Markowitz"
        else ([asset] if asset == "SPY" else [asset, "SPY"])
    )
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
        split = walk_forward_start(aligned_prices.index, train_fraction)
        holdout_prices = aligned_prices.iloc[split:]
        if strategy_name == "Walk-forward Markowitz":
            weights = rolling_markowitz_weights(
                aligned_prices.loc[:, selected_assets],
                lookback_sessions=strategy_defaults.markowitz_lookback_sessions,
                rebalance_every_sessions=(
                    strategy_defaults.markowitz_rebalance_every_sessions
                ),
                risk_aversion=strategy_defaults.markowitz_risk_aversion,
                maximum_weight=strategy_defaults.markowitz_maximum_weight,
                settings=strategy_defaults,
            )
            strategy_result = run_portfolio_backtest(
                holdout_prices.loc[:, selected_assets],
                weights.loc[holdout_prices.index],
                settings,
            )
            strategy_returns = strategy_result.net_returns
            strategy_positions = strategy_result.positions
            benchmark_result = run_buy_and_hold_backtest(
                holdout_prices["SPY"], settings
            )
            benchmark_returns = benchmark_result.net_returns
            benchmark_label = "SPY buy-and-hold"
            strategy_label = "Rolling Markowitz, net of costs"
            equal_weight_targets_panel = equal_weight_targets(
                holdout_prices.loc[:, selected_assets],
                strategy_defaults.markowitz_rebalance_every_sessions,
            )
            equal_weight_result = run_portfolio_backtest(
                holdout_prices.loc[:, selected_assets],
                equal_weight_targets_panel,
                settings,
            )
            equal_weight_returns = equal_weight_result.net_returns
            equal_weight_positions = equal_weight_result.positions
            audit_run_id = audit_signal_run(
                strategy_name,
                selected_assets,
                weights.loc[:, selected_assets],
                strategy_positions,
                settings,
            )
            equal_weight_audit_run_id = audit_signal_run(
                "Equal-weight ETF benchmark",
                selected_assets,
                equal_weight_targets_panel,
                equal_weight_positions,
                settings,
            )
        else:
            if strategy_name == "SMA crossover":
                signals = sma_signals(
                    aligned_prices[asset],
                    int(fast_window),
                    int(slow_window),
                )
            elif strategy_name == "Momentum":
                signals = momentum_signals(
                    aligned_prices[asset],
                    int(momentum_lookback),
                    strategy_defaults.momentum_entry_return_threshold,
                    strategy_defaults.momentum_exit_return_threshold,
                )
            else:
                signals = mean_reversion_signals(
                    aligned_prices[asset],
                    int(reversion_lookback),
                    float(entry_z_score),
                    strategy_defaults.mean_reversion_exit_z_score,
                )
            strategy_result = run_signal_backtest(
                holdout_prices[asset],
                signals.loc[holdout_prices.index],
                settings,
            )
            benchmark_result = run_buy_and_hold_backtest(
                holdout_prices[asset], settings
            )
            strategy_returns = strategy_result.net_returns
            strategy_positions = strategy_result.positions.rename(asset).to_frame()
            benchmark_returns = benchmark_result.net_returns
            benchmark_label = f"{asset} buy-and-hold, net of costs"
            strategy_label = f"{strategy_name}, net of costs"
            audit_run_id = audit_signal_run(
                strategy_name,
                [asset],
                signals,
                strategy_positions,
                settings,
            )
            equal_weight_audit_run_id = None
        spy_returns = holdout_prices["SPY"].pct_change(fill_method=None)
        spy_returns.iloc[0] = 0.0
        strategy_metrics = calculate_metrics(strategy_returns, spy_returns)
        benchmark_metrics = calculate_metrics(benchmark_returns, spy_returns)
        equal_weight_metrics = (
            calculate_metrics(equal_weight_returns, spy_returns)
            if equal_weight_returns is not None
            else None
        )
    except (MarketDataError, RuntimeError, ValueError) as error:
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
    st.caption(f"Signal audit run ID: `{audit_run_id}` (local hash-chained log)")
    if equal_weight_audit_run_id:
        st.caption(
            "Equal-weight audit run ID: "
            f"`{equal_weight_audit_run_id}` (local hash-chained log)"
        )
    st.caption(f"Missing data by requested asset: {data.quality.missing_by_symbol}")
    if excluded_initial_bars:
        st.info(
            f"Excluded {excluded_initial_bars} leading sessions before the selected "
            "assets and SPY all had prices. No missing prices were imputed."
        )

    st.subheader(f"{strategy_name}: out-of-sample comparison")
    st.caption(
        f"Performance shown from {holdout_prices.index[0].date()}. The earlier "
        "period provides signal warm-up or rolling parameter estimates."
    )
    if strategy_name == "Walk-forward Markowitz":
        st.info(
            "Markowitz weights use trailing historical means and covariance. "
            "These estimates are noisy, and optimizer sensitivity can concentrate "
            "the portfolio at the configured weight cap."
        )
    metric_columns = st.columns(6)
    metric_values = (
        ("CAGR", strategy_metrics.cagr, benchmark_metrics.cagr),
        ("Sharpe", strategy_metrics.sharpe_ratio, benchmark_metrics.sharpe_ratio),
        ("Max drawdown", strategy_metrics.max_drawdown, benchmark_metrics.max_drawdown),
        (
            "Volatility",
            strategy_metrics.annualized_volatility,
            benchmark_metrics.annualized_volatility,
        ),
        (
            "Historical VaR",
            strategy_metrics.historical_var,
            benchmark_metrics.historical_var,
        ),
        ("Beta vs SPY", strategy_metrics.beta, benchmark_metrics.beta),
    )
    for column, (label, strategy_value, benchmark_value) in zip(
        metric_columns, metric_values, strict=True
    ):
        with column:
            _display_metric(label, strategy_value, METRIC_LEARNING[label][0])
            st.caption(f"{benchmark_label}: {_format_metric(label, benchmark_value)}")
            if equal_weight_metrics is not None:
                st.caption(
                    "Equal-weight ETF basket: "
                    f"{_format_metric(label, getattr(equal_weight_metrics, METRIC_FIELDS[label]))}"
                )
            if learning_mode:
                explanation, caveat = METRIC_LEARNING[label]
                st.caption(f"**What it means:** {explanation}")
                st.caption(f"**Why it can mislead:** {caveat}")

    realized_outperformance = strategy_metrics.cagr > benchmark_metrics.cagr
    realized_drawdown = (
        abs(strategy_metrics.max_drawdown) * 100
        if strategy_metrics.max_drawdown is not None
        else None
    )
    _, predicted_beat, predicted_drawdown_value = locked_prediction
    st.subheader("Your prediction")
    prediction_columns = st.columns(2)
    with prediction_columns[0]:
        st.metric(
            "Benchmark prediction",
            predicted_beat,
            "Correct"
            if (predicted_beat == "Yes") == realized_outperformance
            else "Incorrect",
        )
    with prediction_columns[1]:
        if realized_drawdown is None:
            st.metric("Drawdown prediction", f"{predicted_drawdown_value:.0f}%")
            st.caption("Actual drawdown is unavailable.")
        else:
            st.metric(
                "Drawdown prediction",
                f"{predicted_drawdown_value:.0f}%",
                f"{realized_drawdown - predicted_drawdown_value:+.1f} percentage points actual minus guess",
            )

    wealth = (1 + strategy_returns).cumprod().rename(strategy_label).to_frame()
    wealth[benchmark_label] = (1 + benchmark_returns).cumprod()
    if equal_weight_returns is not None:
        wealth["Equal-weight ETF basket, net of costs"] = (
            1 + equal_weight_returns
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
    st.line_chart(strategy_positions)
    if strategy_name == "Walk-forward Markowitz":
        st.dataframe(strategy_positions.tail(), width="stretch")
    if learning_mode:
        st.caption(
            "Positions change only after delayed signals or optimizer weights. "
            "Transaction costs and slippage are charged on all turnover and final exit."
        )

    warnings = (
        *strategy_metrics.warnings,
        *benchmark_metrics.warnings,
        *(equal_weight_metrics.warnings if equal_weight_metrics else ()),
    )
    if warnings:
        st.warning("Metric limitations: " + " ".join(dict.fromkeys(warnings)))

    with st.expander("Bias lab results"):
        st.warning(
            "These toggles deliberately break research safeguards. Biased numbers "
            "are teaching examples, not valid performance estimates."
        )
        if show_cost_bias or show_lookahead_bias:
            if strategy_name == "Walk-forward Markowitz":
                portfolio_bias = compare_portfolio_biases(
                    holdout_prices.loc[:, selected_assets],
                    weights.loc[holdout_prices.index],
                    settings,
                )
                cost_returns = portfolio_bias.costs_ignored.net_returns
                lookahead_returns = (
                    portfolio_bias.future_weights_used.net_returns
                    if portfolio_bias.future_weights_used is not None
                    else None
                )
            else:
                bias_comparison = compare_signal_biases(
                    holdout_prices[asset],
                    signals.loc[holdout_prices.index],
                    settings,
                )
                cost_returns = bias_comparison.costs_ignored.net_returns
                lookahead_returns = bias_comparison.future_signal_used.net_returns
            bias_rows = {"Honest OOS baseline": strategy_metrics.cagr}
            if show_cost_bias:
                bias_rows["Costs ignored"] = calculate_metrics(
                    cost_returns,
                    spy_returns,
                ).cagr
            if show_lookahead_bias:
                if lookahead_returns is None:
                    st.warning(
                        "Look-ahead portfolio example unavailable: no future "
                        "rebalance target exists in this holdout."
                    )
                else:
                    bias_rows["Future signal leaked into return period"] = (
                        calculate_metrics(
                            lookahead_returns,
                            spy_returns,
                        ).cagr
                    )
            st.dataframe(
                pd.DataFrame.from_dict(bias_rows, orient="index", columns=["CAGR"]),
                width="stretch",
            )
            st.caption(
                "The look-ahead variant uses a future signal or portfolio target "
                "from the end of a return interval to choose exposure for that "
                "same interval. It is intentionally invalid."
            )
        if show_overfit_bias:
            if strategy_name == "Walk-forward Markowitz":
                overfit_prices = aligned_prices["SPY"]
            else:
                overfit_prices = aligned_prices[asset]
            try:
                overfit = select_sma_on_full_sample(overfit_prices, settings)
            except ValueError as error:
                st.warning(f"Overfit demonstration unavailable: {error}")
            else:
                st.write(
                    f"Best full-sample SMA: {overfit.selected_fast_window}/"
                    f"{overfit.selected_slow_window}; tested "
                    f"{overfit.combinations_tested} parameter pairs."
                )
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Full-sample baseline": [overfit.baseline_growth],
                            "Selected full-sample strategy": [overfit.selected_growth],
                        },
                        index=["Terminal wealth per $1 before visualization"],
                    ),
                    width="stretch",
                )
                st.warning(overfit.warning)

    with st.expander("Quiz-me"):
        if "quiz_question" not in st.session_state:
            st.session_state["quiz_question"] = select_question()
            st.session_state["quiz_number"] = 0
        question = st.session_state["quiz_question"]
        st.write(question.prompt)
        answer_key = f"quiz_answer_{st.session_state['quiz_number']}"
        answer = st.radio(
            "Choose an answer",
            options=question.options,
            key=answer_key,
        )
        if st.button("Check answer", key="check_quiz_answer"):
            if answer == question.options[question.answer_index]:
                st.success("Correct. " + question.explanation)
            else:
                st.error(
                    f"Not quite. The answer is: "
                    f"{question.options[question.answer_index]}. "
                    f"{question.explanation}"
                )
        if st.button("Next question", key="next_quiz_question"):
            st.session_state["quiz_question"] = select_question()
            st.session_state["quiz_number"] += 1

    with st.expander("Paper-trading simulator and journal"):
        st.warning(
            "Local educational simulation only. This app sends no orders to a "
            "broker. Enter a reference price yourself; costs and slippage are "
            "deducted using the current sidebar assumptions."
        )
        try:
            paper_portfolio = load_paper_portfolio(
                initial_cash=paper_settings.initial_cash_usd
            )
        except (OSError, sqlite3.Error, ValueError) as error:
            st.error(f"Paper account could not be loaded: {error}")
            return
        portfolio_columns = st.columns(3)
        portfolio_columns[0].metric("Paper cash", f"${paper_portfolio.cash:,.2f}")
        portfolio_columns[1].metric(
            "Initial cash", f"${paper_portfolio.initial_cash:,.2f}"
        )
        portfolio_columns[2].metric(
            "Cumulative modeled costs",
            f"${paper_portfolio.cumulative_costs:,.2f}",
        )
        st.write(
            "Current holdings:",
            dict(paper_portfolio.holdings) or "No open holdings",
        )
        with st.form("paper_trade_form"):
            trade_symbol = st.selectbox("Ticker", options=universe.symbols)
            trade_side = st.selectbox("Simulated action", options=("buy", "sell"))
            trade_quantity = st.number_input(
                "Quantity (shares)",
                min_value=0.000001,
                value=1.0,
                step=1.0,
            )
            trade_price = st.number_input(
                "Reference price (USD per share)",
                min_value=0.000001,
                value=100.0,
                step=1.0,
            )
            trade_rationale = st.text_area(
                "Reasoning before the simulated trade",
                max_chars=5_000,
                help="Record the hypothesis, evidence and risks before submitting.",
            )
            submit_trade = st.form_submit_button("Record simulated trade")
        if submit_trade:
            try:
                trade = record_paper_trade(
                    symbol=trade_symbol,
                    side=trade_side,
                    quantity=trade_quantity,
                    reference_price=trade_price,
                    rationale=trade_rationale,
                    transaction_cost_bps_per_side=settings.transaction_cost_bps_per_side,
                    slippage_bps_per_side=settings.slippage_bps_per_side,
                    initial_cash=paper_settings.initial_cash_usd,
                )
            except (OSError, sqlite3.Error, TypeError, ValueError) as error:
                st.error(f"Paper trade was not recorded: {error}")
            else:
                st.success(f"Recorded paper trade #{trade.trade_id}.")
                st.rerun()

        if paper_portfolio.trades:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "ID": trade.trade_id,
                            "Time (UTC)": trade.created_at,
                            "Ticker": trade.symbol,
                            "Side": trade.side,
                            "Quantity": trade.quantity,
                            "Reference price": trade.reference_price,
                            "Rationale": trade.rationale,
                            "Review": trade.review or "",
                        }
                        for trade in reversed(paper_portfolio.trades)
                    ]
                ),
                width="stretch",
            )
            trade_to_review = st.selectbox(
                "Trade to review",
                options=tuple(trade.trade_id for trade in paper_portfolio.trades),
                format_func=lambda trade_id: f"Trade #{trade_id}",
            )
            with st.form("paper_trade_review_form"):
                review_text = st.text_area(
                    "Post-trade review",
                    max_chars=5_000,
                    help="What happened, what did you learn, and what would you change?",
                )
                submit_review = st.form_submit_button("Save review")
            if submit_review:
                try:
                    add_trade_review(trade_to_review, review_text)
                except (OSError, sqlite3.Error, ValueError) as error:
                    st.error(f"Trade review was not saved: {error}")
                else:
                    st.success(f"Saved review for paper trade #{trade_to_review}.")
                    st.rerun()

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
