# Student research notebook and dissertation planning

The app's **My Researcher's Notebook** page is a prompt sheet for the student,
not an automatically written personal statement. Its learning-log export
contains only text the student entered and the date they selected. Entries are
kept in Streamlit session state and are not written to the repository or
persistent disk by this page. A hosted app's server receives form entries.
Download an entry to keep it, then review and edit the file before using it
elsewhere. Do not enter private or identifying information.

## A suitable focused investigation

One possible question using code already in the project is:

> How does a Cox-Ross-Rubinstein binomial tree's European option price approach
> the Black-Scholes price as the number of time steps increases, and how does
> allowing early exercise change the comparison?

This can be investigated with controlled synthetic contract inputs. Change one
factor at a time, compare numerical prices against a benchmark, plot error
against the number of tree steps, and test multiple strikes or maturities.
Record the input assumptions and units. Do not interpret convergence to a
benchmark as proof that either model describes market prices accurately.

Other possible questions include:

- On a synthetic series with known hidden states, how do HMM state count and
  training fraction affect filtered state probabilities?
- How do FF3 and FF5 alpha estimates and uncertainty differ on the same
  aligned sample, and what limitations affect the comparison?
- Which assumptions distinguish constant-volatility Black-Scholes from a
  stochastic-volatility model?

Choose a question the student can explain and investigate with the available
time, data, and code. These are suggestions, not claims about work completed.

## Suggested write-up structure

1. **Question and motivation:** define the question and explain the student's
   own reason for choosing it.
2. **Background:** introduce the finance and mathematics in the student's own
   words and cite primary or reliable sources.
3. **Method:** state equations, assumptions, units, data, implementation, and
   experimental design.
4. **Validation:** describe tests, analytical or numerical benchmarks, edge
   cases, and data checks.
5. **Results:** show labeled plots and tables, including unexpected or failed
   results.
6. **Discussion:** explain what the results support, what they do not, and
   relevant uncertainty, bias, and model limitations.
7. **Reflection and assistance disclosure:** record choices, corrections,
   understanding gained, and how tools—including AI—were used and checked.
8. **Conclusion and next step:** answer the question cautiously and propose a
   feasible follow-up.

## Showing authorship honestly

- Keep dated entries before and after experiments, including false starts and
  changed predictions.
- Point to evidence for claims: tests, plots, calculations, source material,
  and relevant version-control changes.
- Explain the reasoning behind design choices, not just the final code.
- Follow the school's rules for AI use and citation. Describe assistance
  accurately (for example, code drafting, debugging, or concept explanation)
  and say what the student reviewed, changed, tested, and can explain.
- Do not claim independent derivation, implementation, or testing without
  being able to explain and evidence it.

The notebook prompts are intended to help a student develop their own account;
they do not guarantee that work meets a school's assessment or academic
integrity requirements.
