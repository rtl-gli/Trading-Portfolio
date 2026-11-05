"""Beginner-friendly explanations and illustrative diagrams for every model."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import norm

st.title("A beginner's guide to the models")
st.markdown(
    """
    These models answer different questions. None can reliably tell you what
    markets will do next. This page starts with intuition, shows the moving
    parts, and labels every example graph as **synthetic** so it cannot be
    mistaken for a backtest or a real market estimate.
    """
)
st.info(
    "This is a self-directed academic project. A model can describe historical "
    "data well and still fail to predict the future."
)

st.subheader("How to use this app")
st.markdown(
    """
    ```mermaid
    flowchart TD
        A[Question] --> B[Choose a model]
        B --> C[Check its assumptions]
        C --> D[Run a controlled experiment]
        D --> E[Inspect the graph and uncertainty]
        E --> F[Ask how the result could mislead]
    ```
    """
)

factor_tab, regime_tab, lsm_tab, heston_tab = st.tabs(
    [
        "1. Fama-French",
        "2. Regime switching",
        "3. Longstaff-Schwartz",
        "4. Heston",
    ],
    on_change="rerun",
)

with factor_tab:
    st.header("Fama-French: explain portfolio returns with common factors")
    st.markdown(
        """
        **In plain English:** instead of judging a portfolio by its return alone,
        ask whether its returns move with broad market patterns such as the
        market, company size, and value. The regression estimates how exposed
        the portfolio was to each pattern.

        $$R_{p,t}-R_{f,t}=\\alpha+\\beta_m(MKT-RF)_t+\\beta_s SMB_t+\\beta_h HML_t+\\epsilon_t$$

        - **Inputs:** portfolio returns and factor returns on matching dates.
        - **Outputs:** factor exposures (the betas), an unexplained intercept
          (alpha), and uncertainty estimates.
        - **Factor names:** `MKT-RF` is the market's excess return; `SMB` is
          small-company minus big-company returns; `HML` is high book-to-market
          (value) minus low (growth). FF5 adds `RMW` (robust minus weak
          profitability) and `CMA` (conservative minus aggressive investment).
          `RF` is the risk-free return.
        - **What it does not do:** prove skill or forecast the next return.
          FF3/FF5 results can change with the factor specification.
        - **Main trap:** look at alpha's standard error, confidence interval,
          and p-value—not only the alpha estimate. The current stock list also
          has survivorship bias, and this portfolio is gross of costs.
        """
    )
    st.markdown(
        """
        ```mermaid
        flowchart LR
            A[Portfolio return] --> C[Regression]
            B[Market, size, value factors] --> C
            C --> D[Exposure betas]
            C --> E[Residual alpha and uncertainty]
        ```
        """
    )
    contributions = pd.DataFrame(
        {
            "Illustrative contribution (%)": [0.10, 0.44, 0.02, -0.02],
        },
        index=["Alpha", "Market", "Size", "Value"],
    )
    fig = go.Figure(
        go.Bar(
            x=contributions["Illustrative contribution (%)"],
            y=contributions.index,
            orientation="h",
            marker_color=["#7c3aed", "#2563eb", "#0f766e", "#d97706"],
        )
    )
    fig.update_layout(
        title="Example return decomposition (invented numbers)",
        xaxis_title="Contribution to one hypothetical month's return (%)",
        xaxis={
            "range": [-0.05, 0.48],
            "zeroline": True,
            "zerolinecolor": "#64748b",
            "zerolinewidth": 2,
        },
        yaxis_title=None,
        height=330,
        template="plotly_white",
    )
    if factor_tab.open:
        st.plotly_chart(
            fig,
            width="stretch",
            alt="Synthetic example showing market exposure as the largest return contribution",
        )

with regime_tab:
    st.header("Regime switching: allow the return pattern to change")
    st.markdown(
        """
        **In plain English:** imagine the market has a hidden mode—perhaps
        quieter or more volatile. A hidden Markov model assumes the mode tends
        to persist, can switch, and changes the distribution of returns. A
        Markov chain means the next state's probability depends on the current
        state, not the full earlier path.

        $$P(S_t=j\\mid S_{t-1}=i)=A_{ij},\\qquad r_t\\mid S_t=k\\sim\\mathcal{N}(\\mu_k,\\sigma_k^2)$$

        - **Inputs:** a time-ordered return series and a chosen number of states.
        - **Outputs:** estimated state means, volatilities, transition
          probabilities, and a probability for each state at each date.
        - **Filtered probability:** uses observations only up to that date.
          It is the relevant version for a real-time decision rule, though
          parameters also need to have been estimated without future data.
        - **Smoothed probability:** uses the full sample, including later
          returns, to revise the past. It is useful for explanation, not for
          a historical trading signal.
        - **Main trap:** state labels are mathematical labels, not economic
          truths. A fitted "high-volatility state" is not a reliable crash alarm.
        """
    )
    st.markdown(
        """
        ```mermaid
        stateDiagram-v2
            [*] --> Quiet
            Quiet --> Quiet: likely to persist
            Quiet --> Stress: possible switch
            Stress --> Stress: likely to persist
            Stress --> Quiet: possible switch
            Quiet --> Return: lower fitted volatility
            Stress --> Return: higher fitted volatility
        ```
        """
    )
    returns = np.linspace(-0.08, 0.08, 300)
    figure = go.Figure()
    for label, volatility, color in (
        ("Lower-volatility state", 0.008, "#2563eb"),
        ("Higher-volatility state", 0.022, "#d97706"),
    ):
        figure.add_trace(
            go.Scatter(
                x=returns * 100,
                y=norm.pdf(returns, loc=0.0, scale=volatility),
                mode="lines",
                name=label,
                line={"color": color, "width": 3},
            )
        )
    figure.update_layout(
        title="Illustrative return distributions (assumed, not fitted)",
        xaxis_title="One-day return (%)",
        yaxis_title="Probability density",
        height=330,
        template="plotly_white",
    )
    if regime_tab.open:
        st.plotly_chart(
            figure,
            width="stretch",
            alt="Synthetic normal distributions illustrating a wider return spread in the higher-volatility state",
        )

with lsm_tab:
    st.header(
        "Longstaff-Schwartz: estimate when an American option should be exercised"
    )
    st.markdown(
        """
        **In plain English:** an American option can be exercised before it
        expires. The method simulates many possible price paths, then walks
        backwards in time. For paths where exercising now pays something, it
        estimates the value of waiting and compares the two.

        $$V_t=\\max\\left(\\text{exercise value},\\;\\mathbb{E}[e^{-r\\Delta t}V_{t+\\Delta t}\\mid S_t]\\right)$$

        - **Inputs:** simulated underlying paths, an option payoff, rates, and
          a regression basis (a small set of simple functions used to fit a
          continuation-value curve).
        - **Output:** an estimated option value and an approximate exercise rule.
        - **Main trap:** a poor regression can estimate continuation value
          badly. Too few paths or basis functions can distort the price.
        - **Benchmark:** a European option should agree with a suitable
          analytical or tree reference; an American put can be compared with
          a fine binomial tree. Convergence is evidence, not proof.
        """
    )
    st.markdown(
        """
        ```mermaid
        flowchart TD
            A[Simulate price paths] --> B[Start at expiry]
            B --> C[Step backwards]
            C --> D[Estimate value of waiting]
            D --> E{Exercise now worth more?}
            E -->|Yes| F[Exercise on path]
            E -->|No| G[Continue on path]
            F --> C
            G --> C
            C --> H[Average discounted cash flows]
        ```
        """
    )
    stock_prices = np.linspace(55.0, 145.0, 250)
    exercise_value = np.maximum(100.0 - stock_prices, 0.0)
    continuation_value = 17.0 * np.exp(-(((stock_prices - 88.0) / 30.0) ** 2))
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=stock_prices,
            y=exercise_value,
            mode="lines",
            name="Exercise now",
            line={"color": "#2563eb", "width": 3},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=stock_prices,
            y=continuation_value,
            mode="lines",
            name="Wait (schematic estimate)",
            line={"color": "#d97706", "width": 3},
        )
    )
    figure.update_layout(
        title="American put decision (schematic, not a model result)",
        xaxis_title="Underlying price",
        yaxis_title="Value",
        height=330,
        template="plotly_white",
    )
    if lsm_tab.open:
        st.plotly_chart(
            figure,
            width="stretch",
            alt="Schematic American put exercise payoff and illustrative continuation value",
        )
    st.caption(
        "The continuation curve above is deliberately illustrative; the project "
        "has not implemented or fitted Longstaff-Schwartz yet."
    )

with heston_tab:
    st.header("Heston: let volatility change randomly over time")
    st.markdown(
        """
        **In plain English:** basic option formulas often assume volatility is
        constant. Heston lets variance itself move randomly and tend to return
        toward a long-run level. The stock and variance shocks can be
        correlated, which helps represent the skew seen in equity options.

        $$dS_t=rS_tdt+\\sqrt{v_t}S_t dW_t^S,\\qquad
        dv_t=\\kappa(\\theta-v_t)dt+\\xi\\sqrt{v_t}dW_t^v$$
        $$dW_t^S dW_t^v=\\rho\\,dt$$

        - **Parameters:** `v₀` initial variance, `κ` mean-reversion speed,
          `θ` long-run variance, `ξ` volatility of variance, and `ρ` correlation.
          In the equation, `S` is the underlying price, `v` is variance, and
          `r` is the risk-free rate.
        - **Output:** option prices that can be compared across strikes and
          maturities, plus a calibrated parameter set.
        - **Main trap:** several parameter sets may fit the same option prices;
          optimisation can settle in local minima. A good fit today may be
          unstable tomorrow.
        - **Checks:** use multiple starting guesses, compare prices with a
          Black-Scholes limiting case, and track parameter stability.
        """
    )
    st.markdown(
        """
        ```mermaid
        flowchart TD
            A[Variance today] --> B[Mean reversion to long-run variance]
            C[Random variance shock] --> B
            B --> D[Changes stock return volatility]
            E[Correlated stock shock] --> D
            D --> F[Option prices across strikes and maturities]
            F --> G[Calibration search]
        ```
        """
    )
    if heston_tab.open:
        time = np.linspace(0.0, 5.0, 200)
        initial_variance, long_run_variance, reversion_speed = 0.36, 0.16, 1.2
        expected_variance = long_run_variance + (
            initial_variance - long_run_variance
        ) * np.exp(-reversion_speed * time)
        figure = go.Figure(
            go.Scatter(
                x=time,
                y=np.sqrt(expected_variance) * 100,
                mode="lines",
                name="Illustrative expected volatility",
                line={"color": "#0f766e", "width": 3},
            )
        )
        figure.update_layout(
            title="Mean-reversion intuition (illustrative parameter choices)",
            xaxis_title="Time (years)",
            yaxis_title="Expected volatility (%)",
            height=330,
            template="plotly_white",
        )
        st.plotly_chart(
            figure,
            width="stretch",
            alt="Illustrative volatility curve returning from an elevated starting level toward a long-run level",
        )
        st.caption(
            "This curve isolates deterministic mean reversion; it does not include "
            "random variance shocks and is not a Heston price or calibration."
        )
        st.markdown(
            """
            **3D surface intuition:** implied volatility is often visualized
            across option strike (here represented by log-moneyness) and time
            to maturity. A skew or smile shows how option prices vary across
            strikes; curvature across maturity shows term structure.

            The surface below is generated from a simple illustrative equation,
            **not** from Heston pricing, market option quotes, or a calibration.
            Heston implementation and calibration remain future work.

            For this example, the plotted volatility is
            $22\\%-12\\%k e^{-T/1.5}+18\\%k^2+2.5\\%e^{-T/0.75}$, where
            $k=\\log(K/S)$ and $T$ is maturity in years. These coefficients
            are invented to create a visible skew and maturity shape.
            """
        )
        st.markdown("#### Synthetic 3D volatility surface")
        log_moneyness = np.linspace(-0.4, 0.4, 25)
        maturities = np.linspace(0.1, 2.0, 16)
        moneyness_grid, maturity_grid = np.meshgrid(log_moneyness, maturities)
        volatility_surface = 100 * (
            0.22
            - 0.12 * moneyness_grid * np.exp(-maturity_grid / 1.5)
            + 0.18 * moneyness_grid**2
            + 0.025 * np.exp(-maturity_grid / 0.75)
        )
        surface_figure = go.Figure(
            go.Surface(
                x=moneyness_grid,
                y=maturity_grid,
                z=volatility_surface,
                colorscale="Viridis",
                colorbar={"title": "Implied volatility (%)"},
                hovertemplate=(
                    "Log-moneyness: %{x:.2f}<br>"
                    "Maturity: %{y:.2f} years<br>"
                    "Illustrative volatility: %{z:.1f}%<extra></extra>"
                ),
            )
        )
        surface_figure.update_layout(
            scene={
                "xaxis_title": "log(K / S)",
                "yaxis_title": "Maturity (years)",
                "zaxis_title": "Implied volatility (%)",
                "camera": {"eye": {"x": 1.5, "y": 1.7, "z": 1.25}},
            },
            height=560,
            margin={"l": 15, "r": 15, "t": 10, "b": 40},
            template="plotly_white",
        )
        st.plotly_chart(
            surface_figure,
            width="stretch",
            alt=(
                "Synthetic three-dimensional implied-volatility surface across "
                "log-moneyness and maturity; not calculated from Heston"
            ),
        )
        st.caption(
            "Rotate the graph to compare the strike skew and maturity shape. "
            "Every value is synthetic and included only to explain the chart form."
        )

st.divider()
st.subheader("A quick comparison")
st.table(
    pd.DataFrame(
        [
            {
                "Model": "Fama-French",
                "Main question": "What common return factors explain a portfolio?",
                "Current app status": "Implemented: FF3 and FF5",
            },
            {
                "Model": "Regime switching",
                "Main question": "Does the return distribution change between hidden states?",
                "Current app status": "Implemented: Gaussian HMM",
            },
            {
                "Model": "Longstaff-Schwartz",
                "Main question": "When might early exercise be valuable?",
                "Current app status": "Explained; implementation is planned",
            },
            {
                "Model": "Heston",
                "Main question": "Can random, mean-reverting volatility explain option prices?",
                "Current app status": "Explained; implementation is planned",
            },
        ]
    ),
    alt="Comparison of the four models, their research questions, and implementation status",
)
