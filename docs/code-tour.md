# Code tour for new Python learners

This project uses real finance and statistics, so some formulas are
unavoidably technical. The code is kept modular and tested rather than reduced
to one large script. This guide gives a reading order and explains the main
steps in plain language. It is not a claim that every line is beginner-level.

## Start here

1. `app/Home.py` is the welcome page.
2. `app/pages/0_Model_Guide.py` explains what each model is for.
3. `app/pages/3_Longstaff_Schwartz.py` runs the implemented Black-Scholes and
   binomial pricing examples. The page name is a roadmap label; Longstaff-
   Schwartz itself is not implemented.
4. `src/quant_models/options/pricing.py` contains the option-pricing formulas.
5. `tests/test_option_pricing.py` shows examples that the pricing functions
   must pass.
6. `app/pages/2_Regime_Switching.py` connects price data, a model fit, and
   charts; `src/quant_models/regimes/gaussian_hmm.py` contains the HMM.
7. `app/pages/1_Fama_French_Factors.py` connects returns to the factor model;
   the underlying regression is in `src/quant_models/factors/regression.py`.
8. `app/pages/5_Research_Notebook.py` helps record your own questions,
   decisions, results, and understanding.

The older portfolio-strategy code is archived under `src/portfolio_research/`.
It remains in the project for its tests and learning examples, but it is not
the focus of the current app.

## A worked example: pricing an option

In `src/quant_models/options/pricing.py`, `black_scholes_price` receives the
contract details, checks that they are valid, handles special boundary cases,
and then evaluates the formula. Its inputs use annualized decimal rates and
volatility: `0.20` means 20%, not 0.20%.

The key sequence is:

1. Check that price and strike are positive and that volatility and time are
   not negative.
2. If the option expires immediately, return its payoff.
3. If volatility is zero, use the discounted deterministic outcome.
4. Otherwise calculate `d1` and `d2`, then combine discounted stock and strike
   values with normal-distribution probabilities.

`binomial_tree_price` uses the same contract checks, then creates possible up
and down stock-price moves. At expiry it calculates each option payoff. It
then steps backward: each earlier node is the discounted average of its two
possible next values. For an American option it also compares that value with
the payoff from exercising at the current node.

The backward loop is the key idea. A price tree is not a prediction of which
path will happen; it is a numerical method for calculating a model price under
specified assumptions.

## A worked example: interpreting factor regression

In `src/quant_models/factors/regression.py`, the input returns and factor rows
are first aligned by calendar month. Months without all required factor values
are excluded and counted; the code does not fill them in.

The dependent value is portfolio return minus the risk-free return (`RF`).
The explanatory values are the selected market, size, value, profitability,
and investment factors. A constant is added to the design matrix; that
constant's fitted coefficient is called alpha. The other coefficients are
factor exposures, not forecasts.

Newey-West/HAC settings change the estimated uncertainty around coefficients.
They do not change the source data, repair a poor model choice, or turn alpha
into proof of skill. Tests in `tests/test_factor_regression.py` check the
alignment and regression outputs.

## A worked example: hidden market states

In `src/quant_models/regimes/gaussian_hmm.py`, the HMM is fitted on an early
part of the return series. The code then applies the fitted transition and
return-distribution parameters in date order.

- A **filtered** probability uses observations only through that date.
- A **smoothed** probability uses the full sample, including later dates, to
  revise the past. It is useful for teaching but contains future information.
- Model states are ordered by fitted volatility so their displayed names are
  consistent. The labels do not establish that the states are real economic
  regimes.

The extra log-probability calculations prevent very small probabilities from
underflowing to zero during long sequences. This is a numerical safeguard, not
a different finance assumption. Tests in `tests/test_regime_hmm.py` check
probability totals, date order, and that filtering does not use future rows.

## What common Python features mean here

- **A function** (`def`) names one job so it can be read, tested, and reused.
- **A type hint** (`prices: pd.Series`) documents the expected kind of input;
  it does not replace runtime validation.
- **A dataclass** groups named results, such as a price series and its source.
- **A `try` / `except` block** handles a known failure explicitly, such as an
  unavailable data source. It should not hide unexpected errors.
- **NumPy arrays** carry out numerical calculations. **Pandas Series and
  DataFrames** carry values together with dates and labels.
- **A test** records an input and expected behavior so later changes can be
  checked automatically.

## A safe way to make a change

1. Pick one small behavior and find its function and tests.
2. Write down what you expect before changing it.
3. Change one thing at a time; keep the same inputs and units.
4. Run its focused test, then run the full suite.
5. Explain the result and any limitation in your own words.

To run the checks from PowerShell in the repository folder:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

When AI or another tool helps with a change, record what it did, what you
reviewed, and how you checked the result. Follow your school's rules for
disclosure and citation.
