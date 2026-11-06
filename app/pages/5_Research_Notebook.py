"""Student-authored learning log and dissertation planning prompts."""

from datetime import date

import streamlit as st

st.title("My researcher's notebook")
st.caption("A space for your own questions, decisions, and learning")
st.markdown(
    """
    A strong sixth-form project is not just a polished app. It shows how you
    chose a question, what you expected, what the evidence changed, and what
    you still do not know. This page gives you prompts; **it does not write
    personal experiences or conclusions for you**.
    """
)
st.info(
    "Your draft is held in Streamlit session state and is not written to the "
    "repository or persistent disk by this page. A hosted app's server receives "
    "form entries, so avoid entering private or identifying information."
)

st.header("What makes the work genuinely yours?")
st.markdown(
    """
    - Keep a dated record of decisions, failed attempts, and changes of mind.
    - Be able to explain each model's question, assumptions, inputs, and outputs
      without simply reading the code or memorizing a definition.
    - Show evidence: a test, a small calculation, a graph, a cited source, or a
      before-and-after comparison.
    - Explain why you selected one method over another and what would make you
      distrust its result.
    - Keep the distinction between code assistance and your own understanding
      honest. Do not claim to have derived, tested, or written something unless
      you can describe what you actually did.
    """
)

st.header("AI use: be specific and transparent")
st.markdown(
    """
    AI assistance has been part of building this project. A credible account
    should say which tasks involved assistance (for example, generating a code
    draft, debugging, or explaining a concept), what you checked or changed,
    and which decisions are yours. Follow your school's rules for AI use and
    citation. Do not describe AI-generated work as entirely unaided.

    A useful disclosure is a record of **tool, task, your review, and evidence
    of understanding**. Fill in the notebook prompt below with what really
    happened; this page deliberately does not invent a first-person statement.
    """
)

st.header("A manageable dissertation-style investigation")
st.markdown(
    """
    One focused question is stronger than trying to cover every model. A
    practical starting question, using methods already in the project, is:

    > **How does a Cox-Ross-Rubinstein binomial tree's European option price
    > approach the Black-Scholes price as the number of time steps increases,
    > and how does allowing early exercise change the comparison?**

    This lets you state assumptions, vary one factor at a time, plot pricing
    error against tree steps, and explain why numerical convergence is not
    proof that market assumptions are true. Treat the question as a suggestion:
    check that you understand it and adapt it before adopting it.
    """
)
with st.expander("Other possible questions to choose or adapt"):
    st.markdown(
        """
        - On a **synthetic series with known hidden states**, how do the number
          of states or training fraction affect a Gaussian HMM's filtered
          probabilities? Compare with the known simulated states, not a claim
          that real market states are observable.
        - How do FF3 and FF5 regression estimates differ on the same aligned
          sample, and how much uncertainty remains around alpha? Explain
          survivorship, data alignment, and model specification limits.
        - Which assumptions make a constant-volatility Black-Scholes model
          useful, and what does a stochastic-volatility model attempt to add?
          Keep the Heston surface labelled synthetic unless actual pricing and
          calibration have been implemented.
        """
    )

st.header("Dissertation structure")
st.markdown(
    """
    1. **Question and motivation:** what you want to understand and why.
    2. **Background:** define the financial and mathematical ideas in your
       own words; cite textbooks, papers, and data sources.
    3. **Method:** state equations, assumptions, units, implementation, and
       the experiment you designed.
    4. **Validation:** tests, a benchmark, edge cases, and how you checked the
       code and data.
    5. **Results:** figures and numerical comparisons, including failed or
       surprising results.
    6. **Discussion:** what the evidence supports, what it does not, and
       possible sources of error or bias.
    7. **Reflection and AI disclosure:** specific decisions you made, skills
       you learned, what assistance you used, and what you independently
       reviewed or can explain.
    8. **Conclusion and next steps:** answer the question cautiously and
       describe the next experiment.
    """
)
st.caption(
    "This is a planning framework, not a claim that an experiment or result "
    "has already been completed."
)

st.header("Write a learning-log entry")
with st.form("research-notebook-entry"):
    entry_date = st.date_input("Entry date", value=date.today())
    question = st.text_area(
        "What question were you trying to answer?",
        placeholder="Write the specific question in your own words.",
    )
    prediction = st.text_area(
        "What did you expect, and why?",
        placeholder="Record your prediction before looking at the result.",
    )
    decision = st.text_area(
        "What choice did you make yourself?",
        placeholder="For example: a modelling assumption, test, graph, or comparison.",
    )
    evidence = st.text_area(
        "What did you observe or verify?",
        placeholder="Point to a test, calculation, graph, source, or error message.",
    )
    changed = st.text_area(
        "What surprised you or changed your mind?",
        placeholder="It is fine if nothing changed; explain what you checked.",
    )
    explanation = st.text_area(
        "What can you now explain without notes?",
        placeholder="Name the concept and explain it simply.",
    )
    limitation = st.text_area(
        "What remains uncertain, and what will you investigate next?",
        placeholder="State a limitation and one feasible next step.",
    )
    ai_use = st.text_area(
        "What AI or other assistance did you use for this entry?",
        placeholder=(
            "Describe the actual task, what you reviewed or changed, and how "
            "you checked your understanding. Write 'none' if none."
        ),
    )
    submitted = st.form_submit_button("Prepare my learning-log export")

if submitted:
    st.session_state.pop("research_notebook_export", None)
    fields = {
        "Question": question,
        "Prediction": prediction,
        "My decision": decision,
        "Evidence": evidence,
        "Surprise or change of mind": changed,
        "What I can now explain": explanation,
        "Uncertainty and next step": limitation,
        "AI and other assistance": ai_use,
    }
    completed_fields = {
        label: value.strip() for label, value in fields.items() if value.strip()
    }
    if not completed_fields:
        st.warning("Add at least one of your own notes before preparing an export.")
    else:
        export = [
            f"# Learning-log entry — {entry_date.isoformat()}",
            "",
            "This entry records the author's own notes; it is not an automated assessment.",
            "",
        ]
        for label, value in completed_fields.items():
            export.extend((f"## {label}", "", value, ""))
        st.session_state["research_notebook_export"] = "\n".join(export).rstrip() + "\n"
        st.success(
            "Your notes are ready to download. Review the file and edit it before "
            "using it in a dissertation."
        )

if export_text := st.session_state.get("research_notebook_export"):
    st.download_button(
        "Download my learning log (.md)",
        data=export_text,
        file_name=f"learning-log-{date.today().isoformat()}.md",
        mime="text/markdown",
    )
