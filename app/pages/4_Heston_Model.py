"""Educational walkthrough of the Heston stochastic-volatility model."""

import streamlit as st

from quant_models.options.visualization import synthetic_implied_volatility_surface

st.title("Heston stochastic-volatility model")
st.caption("Quantitative-finance learning module")
st.info(
    "This page teaches the Heston model's equations and intuition. The project "
    "does not yet implement Heston option pricing or calibrate parameters to "
    "market quotes; its 3D surface below is synthetic."
)

st.header("1. Why model volatility?")
st.markdown(
    r"""
    **Start with the familiar idea:** a stock price can move up or down. In the
    Black-Scholes model, the size of those random moves is governed by one
    constant volatility number.

    **Heston's change:** volatility is not fixed. Heston models the stock price
    and its variance together. Variance tends to move back toward a long-run
    level, but random shocks can push it around. This can produce richer option
    prices across strike prices and expiry dates than a constant-volatility
    model.

    Think of the variance as a room's temperature: it wanders with random
    disturbances, but a thermostat pulls it toward a typical level.
    """
)

st.header("2. The two linked equations")
st.markdown(
    "In the risk-neutral pricing model, the stock and its instantaneous "
    "variance evolve together:"
)
st.latex(
    r"\frac{dS_t}{S_t}=(r-q)\,dt+\sqrt{v_t}\,dW_t^S"
    r",\qquad S_0>0"
)
st.latex(r"dv_t=\kappa(\theta-v_t)\,dt+\xi\sqrt{v_t}\,dW_t^v")
st.latex(r"dW_t^S\,dW_t^v=\rho\,dt")

st.markdown(
    r"""
    Read the first equation as a small percentage change in the stock price:
    it has a predictable risk-neutral drift, $(r-q)dt$, plus a random shock.
    The shock is scaled by current volatility, $\sqrt{v_t}$, so variance is
    volatility squared.

    In the second equation, $\kappa(\theta-v_t)$ pulls current variance toward
    the long-run level $\theta$. The final term is the random variance shock.
    The last equation describes whether the stock and variance shocks tend to
    occur together or in opposite directions.
    """
)

st.header("3. What each symbol means")
st.table(
    [
        {
            "Symbol": "S(t)",
            "Meaning": "Underlying asset price at time t.",
            "Units / intuition": "Price units.",
        },
        {
            "Symbol": "v(t), v(0)",
            "Meaning": "Instantaneous variance now and at the start.",
            "Units / intuition": "Annualized variance; volatility is its square root.",
        },
        {
            "Symbol": "r, q",
            "Meaning": "Risk-free rate and continuous dividend yield.",
            "Units / intuition": "Annual rates used in the pricing measure.",
        },
        {
            "Symbol": "kappa",
            "Meaning": "Speed at which variance returns toward its average.",
            "Units / intuition": "Per year; larger means faster reversion.",
        },
        {
            "Symbol": "theta",
            "Meaning": "Long-run average variance.",
            "Units / intuition": "Annualized variance.",
        },
        {
            "Symbol": "xi",
            "Meaning": "Volatility of variance; controls how rough variance is.",
            "Units / intuition": "Often called vol-of-vol.",
        },
        {
            "Symbol": "rho",
            "Meaning": "Correlation between the two random shocks.",
            "Units / intuition": "Between -1 and +1.",
        },
    ],
    hide_index=True,
)

with st.expander("Why can correlation create a volatility skew?"):
    st.markdown(
        """
        If stock and variance shocks have negative correlation, a negative stock
        move tends to arrive with a positive variance shock. That relationship
        can make downside equity options more expensive, relative to a
        constant-volatility Black-Scholes model, and produce a downward skew in
        implied volatility. This is an economic interpretation of a model
        assumption—not a guarantee that every market or sample behaves this way.
        """
    )

st.header("4. Explore a synthetic volatility surface")
st.markdown(
    """
    An implied-volatility surface places strike on one horizontal axis and
    time-to-expiry on another. Its height is implied volatility: the volatility
    that, when inserted into Black-Scholes, gives the observed option price.

    The surface is **not Heston output**. It is generated from a simple
    illustrative equation so you can learn how skew (variation across strikes)
    and term structure (variation across maturities) look in 3D.
    """
)
st.latex(
    r"\sigma_{\mathrm{illustrative}}(k,T)="
    r"0.22-a k e^{-T/1.5}+b k^2+0.025e^{-T/0.75}"
)
st.markdown(
    """
    Here $k=\\log(K/S)$ is log-moneyness: $k=0$ is at-the-money,
    negative $k$ means a strike below spot, and positive $k$ means a strike
    above spot. $T$ is maturity in years. The sliders adjust the invented
    coefficients $a$ and $b$ only; they do not set Heston parameters or price
    options.
    """
)
skew, curvature = st.columns(2)
with skew:
    skew_strength = st.slider(
        "Illustrative skew strength (a)",
        min_value=0,
        max_value=30,
        value=12,
        help="Controls the synthetic slope across strikes; not a calibrated value.",
    )
with curvature:
    smile_curvature = st.slider(
        "Illustrative smile curvature (b)",
        min_value=0,
        max_value=50,
        value=18,
        help="Controls synthetic curvature across strikes; not a model parameter.",
    )
st.plotly_chart(
    synthetic_implied_volatility_surface(
        skew_strength=skew_strength / 100,
        smile_curvature=smile_curvature / 100,
    ),
    width="stretch",
    alt=(
        "Synthetic three-dimensional implied-volatility surface across "
        "log-moneyness and maturity; not calculated from Heston"
    ),
)
st.caption(
    "Rotate the graph to compare its strike and maturity dimensions. The "
    "invented surface is not guaranteed to be arbitrage-free."
)

st.header("5. What a real calibration project would do")
st.markdown(
    """
    Calibration means choosing model parameters so that model prices are close
    to observed option prices. It is a numerical estimation problem, not a
    visual curve-fitting exercise.

    1. Validate option quotes, contract details, timestamps, rates, dividends,
       and units; remove or explain unreliable observations.
    2. Price options at multiple strikes and expiries for a candidate parameter
       set $(v_0,\\kappa,\\theta,\\xi,\\rho)$.
    3. Minimize a documented error measure. Price errors and implied-volatility
       errors weight the option chain differently.
    4. Try multiple starting points and check parameter bounds, residuals,
       convergence, and stability on dates not used for fitting.
    5. Compare against simpler benchmarks and explain where the model fails.
    """
)
st.warning(
    "A low fitting error does not prove Heston is true or predicts future "
    "prices. Noisy quotes, parameters that compensate for one another, and "
    "local optimization minima can all make a fit look better than it is."
)

with st.expander("Optional numerical note: the Feller condition"):
    st.markdown(
        """
        The condition $2\\kappa\\theta\\geq\\xi^2$ is often called the Feller
        condition. For the continuous-time variance process, it makes zero
        unattainable when variance starts positive. It is not a blanket test of
        whether a Heston model is valid; numerical simulation also needs a
        suitable discretization scheme.
        """
    )
