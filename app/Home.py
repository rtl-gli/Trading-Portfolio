"""Home page for the Quant Models Explained Streamlit application."""

import streamlit as st

st.set_page_config(page_title="Quant Models Explained", layout="wide")
st.title("Quant Models Explained")
st.caption(
    "A self-directed academic project: four quantitative models, built from "
    "first principles, validated honestly, and taught to a beginner."
)
st.info(
    "The factor-regression module is the first planned model page. The other "
    "pages are scaffolding until their numerical implementations pass tests."
)
st.markdown(
    """
    **Project principle:** anyone can build a model that looks good. This
    project is designed to show when it does not.

    Choose a model from the pages in the sidebar. Each completed module will
    include intuition, equations and assumptions, tested code, an interactive
    demonstration, a worked example of its limitations, and a short quiz.

    This is educational research only. It is not investment advice, a live
    trading system, or evidence of professional or real-money performance.
    """
)
