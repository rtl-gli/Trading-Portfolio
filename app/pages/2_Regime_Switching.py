"""Fit and inspect a chronological Gaussian hidden-Markov regime model."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from portfolio_research.market_data import (
    MarketDataError,
    MarketDataResult,
    load_prices,
)
from quant_models.regimes.config import load_regime_settings
from quant_models.regimes.gaussian_hmm import (
    RegimeModelError,
    RegimeResult,
    fit_gaussian_regime_model,
)


@st.cache_data(ttl="1h", max_entries=8)
def _load_prices_cached(
    symbols: tuple[str, ...], start: date, end: date
) -> MarketDataResult:
    return load_prices(symbols, start, end)


@st.cache_data(ttl="1h", max_entries=16)
def _fit_regime_cached(
    daily_log_returns: pd.Series,
    n_states: int,
    train_fraction: float,
    n_restarts: int,
    max_iterations: int,
    random_seed: int,
) -> RegimeResult:
    return fit_gaussian_regime_model(
        daily_log_returns,
        n_states=n_states,
        train_fraction=train_fraction,
        n_restarts=n_restarts,
        max_iterations=max_iterations,
        random_seed=random_seed,
    )


st.title("Market regimes with a hidden Markov model")
st.markdown(
    """
    A hidden Markov model (HMM) treats a market's state as unobserved. It
    estimates a small set of return distributions and how likely each state
    is to persist or switch. State names here are assigned by fitted
    volatility—not by economic meaning.
    """
)
st.warning(
    "Filtered probabilities use returns through each date. Smoothed probabilities "
    "use future returns to revise the past and are for teaching only. Even the "
    "filtered series is not a trading backtest: model parameters are estimated "
    "once on the early training sample."
)

try:
    settings = load_regime_settings()
except (OSError, TypeError, ValueError) as error:
    st.error(f"Cannot load regime configuration: {error}")
    st.stop()

today = date.today()
with st.form("regime-model-inputs"):
    symbol = st.selectbox(
        "Asset",
        options=["SPY", "QQQ", "TLT", "GLD"],
        index=["SPY", "QQQ", "TLT", "GLD"].index(settings.symbol),
        help="Adjusted closing prices are requested only after you submit.",
    )
    start_date = st.date_input(
        "Start date",
        value=settings.start_date,
        min_value=date(1990, 1, 1),
        max_value=today,
    )
    n_states = st.slider(
        "Number of hidden states",
        min_value=2,
        max_value=4,
        value=settings.n_states,
        help=(
            "More states increase flexibility but also make a short sample easier "
            "to overfit."
        ),
    )
    train_fraction = st.slider(
        "Early sample used to estimate model parameters",
        min_value=50,
        max_value=90,
        value=round(settings.train_fraction * 100),
        step=5,
        format="%d%%",
        help=(
            "The model is fitted only on this initial chronological fraction. "
            "The remaining observations are then filtered sequentially."
        ),
    )
    n_restarts = st.slider(
        "Random initialisations",
        min_value=1,
        max_value=10,
        value=settings.n_restarts,
        help="Keeps the valid fit with the highest training-sample log likelihood.",
    )
    max_iterations = st.slider(
        "Maximum EM iterations per fit",
        min_value=20,
        max_value=500,
        value=settings.max_iterations,
        step=20,
    )
    expected_persistent_state = st.radio(
        "Before fitting: which state do you expect to be more persistent?",
        ("Lower-volatility state", "Higher-volatility state", "Not sure"),
    )
    submitted = st.form_submit_button("Fit regime model")

if submitted:
    try:
        with st.spinner("Loading adjusted prices and fitting training-sample HMMs..."):
            market_data = _load_prices_cached(
                (symbol,),
                start_date,
                today + timedelta(days=1),
            )
            adjusted_prices = market_data.prices[symbol].dropna()
            daily_log_returns = np.log(adjusted_prices).diff().dropna()
            result = _fit_regime_cached(
                daily_log_returns,
                n_states,
                train_fraction / 100.0,
                n_restarts,
                max_iterations,
                settings.random_seed,
            )
    except (
        MarketDataError,
        RegimeModelError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        st.error(f"Regime model could not be completed: {error}")
    else:
        high_vol_name = result.state_names[-1]
        high_vol_persistence = float(
            result.transition_matrix.loc[high_vol_name, high_vol_name]
        )
        low_vol_name = result.state_names[0]
        low_vol_persistence = float(
            result.transition_matrix.loc[low_vol_name, low_vol_name]
        )
        measured_more_persistent = (
            high_vol_name
            if high_vol_persistence > low_vol_persistence
            else low_vol_name
        )

        st.subheader("What the fitted model says")
        st.caption(
            f"Price source: **{market_data.source}**, retrieved "
            f"{market_data.retrieved_at.isoformat()}. The model uses "
            f"{result.training_observations:,} early returns for fitting and "
            f"{result.out_of_sample_observations:,} later returns for chronological "
            f"filtering. No future returns enter the filtered probability recursion."
        )
        with st.container(horizontal=True):
            st.metric("Training observations", f"{result.training_observations:,}")
            st.metric(
                "Later observations filtered",
                f"{result.out_of_sample_observations:,}",
            )
            st.metric(
                "Training fit converged",
                "Yes" if result.converged else "Not within iteration limit",
            )
        if not result.converged:
            st.warning(
                "The best restart did not meet the EM convergence criterion. "
                "Treat its parameters and state probabilities cautiously."
            )
        st.caption(
            f"Best of {n_restarts} starts: restart {result.selected_restart + 1}; "
            f"{result.iterations} iterations; training log likelihood "
            f"{result.training_log_likelihood:.2f}. The highest training likelihood "
            "does not establish that this model will forecast well."
        )
        if result.restarts_with_likelihood_decreases:
            st.warning(
                "The EM likelihood decreased at least once in "
                f"{result.restarts_with_likelihood_decreases} of {n_restarts} "
                "initialisations. "
                + (
                    "The selected restart also had a decrease; interpret the fit "
                    "cautiously and compare settings."
                    if result.selected_restart_had_likelihood_decrease
                    else "The selected restart did not raise one, but the result "
                    "can still depend on initialisation."
                )
            )

        prediction_match = (
            expected_persistent_state == measured_more_persistent
            if expected_persistent_state != "Not sure"
            else None
        )
        if prediction_match is None:
            st.info(
                f"Training-sample estimate: the {measured_more_persistent.lower()} "
                "has the higher diagonal transition probability."
            )
        elif prediction_match:
            st.success(
                f"Your prediction matched: the {measured_more_persistent.lower()} "
                "has the higher estimated self-transition probability."
            )
        else:
            st.info(
                f"Your prediction did not match: the {measured_more_persistent.lower()} "
                "has the higher estimated self-transition probability."
            )

        st.markdown("### Adjusted price and filtered state")
        price_for_returns = adjusted_prices.loc[result.filtered_states.index]
        price_figure = go.Figure()
        state_colors = {
            state_name: color
            for state_name, color in zip(
                result.state_names,
                ["#2563eb", "#d97706", "#7c3aed", "#0f766e"][: len(result.state_names)],
                strict=True,
            )
        }
        state_changes = result.filtered_states.ne(
            result.filtered_states.shift()
        ).cumsum()
        state_groups = list(result.filtered_states.groupby(state_changes))
        for group_number, (_, state_series) in enumerate(state_groups):
            group_start = state_series.index[0]
            if group_number + 1 < len(state_groups):
                group_end = state_groups[group_number + 1][1].index[0]
            else:
                group_end = state_series.index[-1] + pd.Timedelta(days=1)
            state_name = str(state_series.iloc[0])
            price_figure.add_vrect(
                x0=group_start,
                x1=group_end,
                fillcolor=state_colors[state_name],
                opacity=0.12,
                line_width=0,
                layer="below",
                annotation_text=state_name if group_number == 0 else None,
            )
        price_figure.add_trace(
            go.Scatter(
                x=price_for_returns.index,
                y=price_for_returns.to_numpy(),
                mode="lines",
                name=f"{symbol} adjusted close",
                line={"color": "#111827", "width": 1.6},
            )
        )
        price_figure.add_vline(
            x=result.training_end,
            line_dash="dash",
            line_color="#7c3aed",
            annotation_text="End of parameter-training sample",
        )
        price_figure.update_layout(
            xaxis_title="Date",
            yaxis_title="Adjusted close (USD)",
            height=460,
            template="plotly_white",
            legend={"orientation": "h", "y": 1.1},
        )
        st.plotly_chart(
            price_figure,
            width="stretch",
            alt=(
                f"{symbol} adjusted closing prices with filtered volatility-state "
                "backgrounds and a marker at the end of the training sample"
            ),
        )

        st.markdown("### Filtered probabilities")
        filtered_figure = go.Figure()
        for state_name in result.state_names:
            filtered_figure.add_trace(
                go.Scatter(
                    x=result.filtered_probabilities.index,
                    y=result.filtered_probabilities[state_name],
                    mode="lines",
                    name=state_name,
                    line={"color": state_colors[state_name], "width": 2},
                )
            )
        filtered_figure.add_vline(
            x=result.training_end,
            line_dash="dash",
            line_color="#7c3aed",
        )
        filtered_figure.update_layout(
            xaxis_title="Date",
            yaxis_title="Probability based on data through this date",
            yaxis={"range": [0, 1]},
            height=380,
            template="plotly_white",
        )
        st.plotly_chart(
            filtered_figure,
            width="stretch",
            alt=(
                "Chronological filtered probabilities for each volatility state; "
                "probabilities sum to one on each date"
            ),
        )
        st.caption(
            "The vertical line marks the end of the training sample. The HMM "
            "parameters stay fixed after that line; later state probabilities "
            "are updated one return at a time."
        )

        with st.expander(
            "Compare with smoothed probabilities (uses future observations)"
        ):
            st.warning(
                "These probabilities use the entire observed return series, "
                "including observations after each date. They revise historical "
                "state assignments and are not valid for a historical live signal."
            )
            smoothed_figure = go.Figure()
            for state_name in result.state_names:
                smoothed_figure.add_trace(
                    go.Scatter(
                        x=result.smoothed_probabilities.index,
                        y=result.smoothed_probabilities[state_name],
                        mode="lines",
                        name=state_name,
                        line={"color": state_colors[state_name], "width": 2},
                    )
                )
            smoothed_figure.update_layout(
                title="Smoothed probabilities (look-ahead for historical decisions)",
                xaxis_title="Date",
                yaxis_title="Probability using the full sample",
                yaxis={"range": [0, 1]},
                height=360,
                template="plotly_white",
            )
            st.plotly_chart(
                smoothed_figure,
                width="stretch",
                alt="Smoothed regime probabilities that use future observations",
            )

        st.markdown("### Estimated states and transition probabilities")
        parameters = pd.DataFrame(
            {
                "Mean daily log return (%)": result.daily_means * 100,
                "Daily return volatility (%)": result.daily_volatilities * 100,
                "Self-transition probability": np.diag(
                    result.transition_matrix.to_numpy()
                ),
            },
            index=result.state_names,
        )
        st.dataframe(
            parameters.style.format(
                {
                    "Mean daily log return (%)": "{:.4f}",
                    "Daily return volatility (%)": "{:.4f}",
                    "Self-transition probability": "{:.3f}",
                }
            ),
            alt="Estimated mean returns, volatilities, and state persistence",
        )

        transition_figure = go.Figure(
            go.Heatmap(
                z=result.transition_matrix.to_numpy(),
                x=result.state_names,
                y=result.state_names,
                zmin=0,
                zmax=1,
                colorscale="Blues",
                text=np.round(result.transition_matrix.to_numpy(), 2),
                texttemplate="%{text:.2f}",
                hovertemplate=(
                    "From %{y}<br>To %{x}<br>Probability %{z:.3f}<extra></extra>"
                ),
            )
        )
        transition_figure.update_layout(
            title="Estimated one-day transition matrix",
            xaxis_title="State tomorrow",
            yaxis_title="State today",
            height=360,
            template="plotly_white",
        )
        st.plotly_chart(
            transition_figure,
            width="stretch",
            alt="Estimated probabilities of moving between the fitted volatility states",
        )
        st.caption(
            "State names are ordered by fitted daily volatility. Matrix rows show "
            "the current state and columns the next state; each row sums to one. "
            "These are model estimates, not stable laws of the market."
        )

st.subheader("What to learn from this experiment")
st.markdown(
    """
    - Baum-Welch (the EM algorithm) finds parameters that make the training
      return sequence more likely; different starting values can find
      different local solutions.
    - A filtered probability is causal only for fixed parameters. This page
      estimates parameters on one early sample and freezes them for the later
      period, but it does not retrain walk-forward.
    - A high-volatility state describes the fitted distribution. It does not
      identify the cause of volatility or tell you when a crash will occur.
    - Try changing the state count and training fraction. If your story changes
      sharply, that is model uncertainty—not a reason to cherry-pick the prettiest fit.
    """
)
