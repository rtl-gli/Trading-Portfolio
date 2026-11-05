"""Home page for the Quant Models Explained Streamlit application."""

import streamlit as st

st.set_page_config(page_title="Quant Models Explained", layout="wide")
st.title("Quant Models Explained")
st.caption(
    "A self-directed academic learning project for understanding quantitative "
    "models, their assumptions, and how to test their limits."
)
st.info(
    "Explore the model guide, factor regressions, Black-Scholes and binomial "
    "option pricing, a Gaussian hidden-state model, and a beginner's Heston "
    "walkthrough. Longstaff-Schwartz and Heston pricing/calibration are not "
    "implemented yet."
)
st.markdown(
    """
    **Project principle:** understand what a model assumes, how its mathematics
    becomes code, and where its results can mislead—not just whether it runs.

    Choose a model from the sidebar to explore its question, intuition,
    equations, assumptions, and illustrative graphs. Implemented calculations
    are separated clearly from teaching examples and unfinished model ideas.

    This is an educational coding project, not a portfolio recommendation,
    investment service, or live trading system.
    """
)
