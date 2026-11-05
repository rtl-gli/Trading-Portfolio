"""European and American reference pricing with a prediction-before-run prompt."""

import streamlit as st

from quant_models.data.options_snapshot import (
    OptionSnapshotError,
    load_option_snapshot,
    load_snapshot_settings,
)
from quant_models.options import binomial_tree_price, black_scholes_price
from quant_models.options.config import load_pricing_example_settings

st.title("Option pricing: Black-Scholes and binomial tree")
st.caption(
    "Stage 2 reference models. Longstaff-Schwartz regression is not implemented yet."
)
st.markdown(
    """
    Black-Scholes prices **European** options analytically. The Cox-Ross-Rubinstein
    binomial tree prices European or American options by working backward through
    possible share prices. Both models assume a simplified market; neither output
    is a live quote or investment recommendation.
    """
)

try:
    defaults = load_pricing_example_settings()
except (TypeError, ValueError) as error:
    st.error(f"Cannot load the configured pricing example: {error}")
    st.stop()

with st.form("option-pricing-inputs"):
    spot_column, strike_column, expiry_column = st.columns(3)
    with spot_column:
        spot = st.number_input("Spot price ($)", min_value=0.01, value=defaults.spot)
    with strike_column:
        strike = st.number_input(
            "Strike price ($)", min_value=0.01, value=defaults.strike
        )
    with expiry_column:
        days_to_expiry = st.number_input(
            "Days to expiry (ACT/365)",
            min_value=1,
            max_value=3650,
            value=defaults.days_to_expiry,
        )

    rate_column, dividend_column, volatility_column = st.columns(3)
    with rate_column:
        risk_free_rate = (
            st.number_input(
                "Risk-free rate (%)",
                min_value=-10.0,
                max_value=30.0,
                value=defaults.risk_free_rate * 100,
                step=0.1,
            )
            / 100
        )
    with dividend_column:
        dividend_yield = (
            st.number_input(
                "Continuous dividend yield (%)",
                min_value=-10.0,
                max_value=30.0,
                value=defaults.dividend_yield * 100,
                step=0.1,
            )
            / 100
        )
    with volatility_column:
        volatility = (
            st.number_input(
                "Annual volatility (%)",
                min_value=0.0,
                max_value=300.0,
                value=defaults.volatility * 100,
                step=0.5,
            )
            / 100
        )

    type_column, exercise_column, steps_column = st.columns(3)
    with type_column:
        option_type = st.selectbox("Option type", ("call", "put"))
    with exercise_column:
        exercise_style = st.selectbox(
            "Binomial exercise style", ("european", "american")
        )
    with steps_column:
        tree_steps = st.slider(
            "Binomial time steps",
            min_value=1,
            max_value=2000,
            value=defaults.tree_steps,
        )

    prediction = st.radio(
        "Before calculating, what do you expect the tree price to be versus "
        "Black-Scholes?",
        ("Higher", "Within $0.01", "Lower"),
        horizontal=True,
    )
    submitted = st.form_submit_button("Calculate and compare")

if submitted:
    time_to_expiry = days_to_expiry / 365
    try:
        analytic_price = black_scholes_price(
            spot=spot,
            strike=strike,
            time_to_expiry_years=time_to_expiry,
            risk_free_rate=risk_free_rate,
            volatility=volatility,
            option_type=option_type,
            dividend_yield=dividend_yield,
        )
        tree_price = binomial_tree_price(
            spot=spot,
            strike=strike,
            time_to_expiry_years=time_to_expiry,
            risk_free_rate=risk_free_rate,
            volatility=volatility,
            option_type=option_type,
            steps=tree_steps,
            dividend_yield=dividend_yield,
            exercise_style=exercise_style,
        )
    except ValueError as error:
        st.error(f"Pricing inputs are invalid: {error}")
    else:
        difference = tree_price - analytic_price
        if abs(difference) <= 0.01:
            observed = "Within $0.01"
        elif difference > 0:
            observed = "Higher"
        else:
            observed = "Lower"

        st.subheader("Model comparison")
        st.caption(
            f"Your prediction: **{prediction}**. "
            f"The observed tree price was **{observed}**."
        )
        analytic_column, tree_column, difference_column = st.columns(3)
        analytic_column.metric("Black-Scholes (European)", f"${analytic_price:.4f}")
        tree_column.metric(f"CRR binomial ({exercise_style})", f"${tree_price:.4f}")
        difference_column.metric("Tree minus Black-Scholes", f"${difference:.4f}")
        if prediction == observed:
            st.success("Your predicted direction was correct for these inputs.")
        else:
            st.info("The model comparison did not match your prediction.")
        st.warning(
            "Black-Scholes is European-only. When the tree uses American exercise, "
            "the two prices need not match; the difference depends on the contract "
            "and assumptions. More tree steps do not fix unrealistic model inputs."
        )

st.divider()
st.subheader("Validate a saved SPY option snapshot")
try:
    snapshot_settings = load_snapshot_settings()
except OptionSnapshotError as error:
    st.error(f"Cannot read the option-data configuration: {error}")
else:
    manifests = sorted(
        snapshot_settings.snapshot_directory.glob("*/manifest.json"),
        reverse=True,
    )
    if not manifests:
        st.info(
            "No local option snapshots found. To capture one, run "
            "`python scripts/snapshot_spy_options.py` from the project root. "
            "This page does not download market data."
        )
    else:
        manifest_path = st.selectbox(
            "Saved snapshot date",
            manifests,
            format_func=lambda path: path.parent.name,
        )
        try:
            snapshot = load_option_snapshot(manifest_path)
        except OptionSnapshotError as error:
            st.error(f"Snapshot validation failed: {error}")
        else:
            st.caption(
                "The SHA-256 manifest detects accidental data changes, but is not "
                "a digital signature proving the provider's source."
            )
            st.write(
                f"Validated {len(snapshot):,} contracts across "
                f"{snapshot['expiration'].nunique()} expirations."
            )
            visible_columns = [
                "expiration",
                "option_type",
                "strike",
                "bid",
                "ask",
                "impliedVolatility",
                "volume",
                "openInterest",
            ]
            st.dataframe(
                snapshot.loc[:, visible_columns].head(100),
                hide_index=True,
                use_container_width=True,
            )

st.subheader("What can mislead you?")
st.markdown(
    """
    - The Black-Scholes result assumes constant volatility and rates, continuous
      trading, and a lognormal underlying price. Real markets violate these
      assumptions.
    - The binomial tree is a discrete approximation. Its output can oscillate as
      the number of steps changes, and invalid risk-neutral probabilities are
      rejected rather than clipped.
    - The defaults in `config/options.yaml` are synthetic teaching inputs, not
      today's SPY price, volatility, dividend yield, or risk-free rate.
    - Saved yfinance option quotes can be stale, delayed, or revised. A saved
      snapshot is not a synchronized or exchange-certified market record.
    """
)
