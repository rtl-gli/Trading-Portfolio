# Quant Models Explained

**A self-directed academic project** building four quantitative-finance models
from first principles, validating them against known results, and explaining
how they can mislead. This is a learning project—not investment advice, live
trading, real-money performance, or professional client work.

> Anyone can build a model that looks good. This project is designed to show
> when it isn't.

## Current milestone

The project has changed direction from the earlier portfolio-strategy
playground. Stage 1 established the package, pinned environment, Streamlit
scaffold, secrets checks, and a local SPY option-chain snapshot tool. Stage 2
adds validated local snapshot loading plus tested Black-Scholes and
Cox-Ross-Rubinstein reference pricers. Stage 3 adds the FF3/FF5 monthly
regression, validated data alignment, and Newey-West inference. Stage 4 adds a
beginner's guide to all four models and a Gaussian hidden-Markov regime
experiment with chronological filtering. Longstaff-Schwartz and Heston remain
explained roadmap items, not implemented models.

| Module | Model | Validation and built-in limitation |
| --- | --- | --- |
| 1 | Fama-French factor regressions | Align factor data and returns, convert percent units, handle missing-code sentinels, use Newey-West errors, and test whether alpha differs from zero. The trap: alpha is not evidence of skill unless uncertainty is considered. |
| 2 | Regime switching | Fit a Gaussian HMM on an early sample, filter later returns chronologically, and keep smoothed probabilities visibly separate. The trap: smoothed probabilities use future data. |
| 3 | Longstaff-Schwartz American options | Compare with Black-Scholes for European options and a binomial benchmark for American puts. The trap: a fitted exercise rule can underprice. |
| 4 | Heston stochastic-volatility calibration | Validate a Black-Scholes limiting case, use multiple starts, and track parameter stability across saved option snapshots. The trap: different parameter sets may fit similarly and optimisation may find local minima. |

The intended first public version is modules 1–2, the learning app, and a
carefully limited write-up by early January 2027. The full project target is
31 March 2027. These are targets, not claims that unfinished modules exist.

## Stage 1: setup and option snapshot

### Windows / PowerShell setup

Use Python 3.11 or newer. From the project folder in the VS Code terminal:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m pre_commit install
```

`requirements.txt` pins runtime and development tools. `pre-commit` checks
formatting, YAML, and potential secrets before each commit. If you add a new
secret type or intentionally change a scanner finding, review the baseline
deliberately—never use it to hide a real credential.

Run local quality checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pre_commit run --all-files
.\.venv\Scripts\pip-audit.exe -r requirements.txt
```

Launch the new multipage app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/Home.py
```

The beginner guide explains all four models, and its diagrams are explicitly
illustrative rather than estimates. The regime page fits a Gaussian HMM to
adjusted daily log returns: it estimates parameters on an early chronological
training sample, then freezes those parameters and filters later returns
sequentially. A separate teaching-only view displays smoothed probabilities,
which use future observations. This is not a walk-forward trading strategy or
a crash predictor. The factor page includes tested FF3/FF5 regression
calculations. The options page includes Black-Scholes and binomial reference
models, but not Longstaff-Schwartz yet; Heston calibration is also unfinished.
The earlier
portfolio-strategy code is retained under
`src/portfolio_research/` and documented separately in
[`docs/portfolio-research-legacy.md`](docs/portfolio-research-legacy.md); it
is not the new app's model implementation.

### Daily SPY option-chain snapshot

The script requests every expiration currently listed by yfinance, validates
the quote fields, and writes one compressed CSV plus a JSON manifest for the
New York calendar date:

```powershell
.\.venv\Scripts\python.exe scripts\snapshot_spy_options.py
```

Configuration is in `config/options.yaml`. Each successful run is stored under
`data/options/snapshots/YYYY-MM-DD/`; the manifest records retrieval time in
UTC, the listed expirations, call/put counts, and the CSV's SHA-256 digest.
Snapshots are local and excluded from Git. The script refuses to overwrite an
existing date's snapshot; inspect any existing file before removing or moving
it. The provider may revise, delay, omit, or rate-limit data, and the snapshot
is not guaranteed to be an exchange-timestamped or complete market record.
This project uses yfinance for personal and educational research; do not
publish downloaded option-chain data.

There is no scheduled GitHub job yet. Keeping the first snapshots local makes
their storage and data-use terms explicit; an automated archival destination
can be selected later if appropriate.

## Stage 2: option-pricing foundations

The option-pricing page compares an analytical European Black-Scholes value
with a recombining Cox-Ross-Rubinstein binomial tree. The tree can use European
or American exercise. Before showing the calculation, the page asks for a
prediction. Defaults come from `config/options.yaml` and describe a synthetic
contract; they are not current SPY market inputs.

Run the learning notebook with Jupyter, or open it in VS Code:
[`notebooks/02_option_pricing_basics.ipynb`](notebooks/02_option_pricing_basics.ipynb).
The app page is available at **Option pricing: Black-Scholes and binomial tree**
in the sidebar. Both pricers accept annualized rates and volatility as decimals,
continuous dividend yield, and time to expiry on an ACT/365 basis. The binomial
tree rejects inputs whose risk-neutral probability is outside `[0, 1]` rather
than hiding the problem by clipping it.

Saved option snapshots are read only from local disk. The loader checks the
manifest schema, row and side counts, contract symbols, and the CSV's SHA-256
digest before showing a sample. The digest detects accidental changes when the
manifest is unchanged; it is not a digital signature or proof of provenance.
Snapshot quotes may be stale or unsynchronized and are not used as calibrated
model inputs in this stage. See [`docs/options-pricing.md`](docs/options-pricing.md)
for formulas, assumptions, and limitations.

## Stage 3: Fama-French factors

The factor page fits both FF3 and FF5 regressions. It builds monthly portfolio
returns from validated adjusted daily closes, lets you edit long-only weights,
and aligns those returns by calendar month with the official Ken French factor
library. Factor values and `RF` are converted from percent to decimal units;
missing sentinels are left missing and reported, never filled. The dependent
variable is portfolio return minus `RF`. Coefficient uncertainty uses
Newey-West/HAC standard errors with the configured default lag count.

The first request can download monthly factor ZIP files from
[Ken French's Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html);
later runs use the SHA-256-verified local cache in `data/cache/factors/`.
Adjusted prices use the existing yfinance cache. The page asks for an alpha
prediction before requesting the data or showing estimates.

Run the learning experiment in
[`notebooks/fama_french_regression.ipynb`](notebooks/fama_french_regression.ipynb).
The regression and data-source details are in
[`docs/fama-french.md`](docs/fama-french.md). The default sample begins at the
date in `config/factors.yaml`. This fixed, present-day stock universe is
survivorship-biased, and its monthly rebalanced returns are gross of costs;
they are explanatory inputs, not an investable backtest.

## Stage 4: regime switching

The regime page starts with SPY and allows QQQ, TLT, or GLD. It fits 2–4
Gaussian return states on an early chronological sample using multiple
deterministic EM initialisations. State volatility, transition probabilities,
and filtered probabilities are graphed, with the training cutoff shown on the
price chart. Filtered probabilities only use observations through their date;
the separately labeled smoothed view uses future data and must not be used as
a historical signal. The fit is not retrained walk-forward and does not
constitute a trading rule. See
[`docs/regime-switching.md`](docs/regime-switching.md) and run the synthetic
experiment in
[`notebooks/regime_switching_basics.ipynb`](notebooks/regime_switching_basics.ipynb).

Use **A beginner's guide to the models** in the sidebar for plain-English
explanations and diagrams of Fama-French, regime switching, Longstaff-Schwartz,
and Heston. Every diagram uses schematic or synthetic values and is labeled
accordingly; explaining a future model does not mean that model has already
been implemented.

### Secrets and local data

`.env` is ignored by Git; `.env.example` contains no credentials.
The current yfinance workflow needs no API key. Never put keys in code,
configuration, tests, logs, notebooks, or a public issue. Downloaded option
chains, caches, audit logs, and local generated outputs are excluded from Git.
See [`docs/threat-model.md`](docs/threat-model.md).

## Intended data and assumptions

- **Factor portfolio:** 30 present-day large-cap US stocks across 11 sectors,
  equal-weighted by default, with user-adjustable weights. The exact list is in
  `config/universe.yaml`. Because it is chosen today, it has survivorship bias;
  it does not include firms that failed, were acquired, or left the market.
- **Factor benchmarks:** SPY, QQQ, TLT, and GLD.
- **Factor sample:** begins 2013-01-01 (META listed in 2012) and ends at the
  latest available Fama-French publication date.
- **Regime sample:** SPY from 2000 onward, subject to validated data coverage.
- **Option underlying:** SPY. For option pricing, use a clearly dated
  risk-free-rate assumption and a documented SPY dividend yield; do not
  silently substitute a current rate for a historical one.
- **Fama-French risk-free rate:** use the factor library's RF series and align
  it exactly to portfolio-return dates.

`yfinance` prices and option quotes can be missing, revised, delayed, or
adjusted. The project will report coverage and fail clearly rather than
silently filling missing prices or claiming point-in-time data. The fixed
present-day stock universe and provider history remain research limitations.

## Repository layout

```text
app/                         Streamlit home and one page per model
config/                      Non-secret YAML settings and fixed universe
data/options/snapshots/       Local-only downloaded option chains (Git-ignored)
docs/                        Threat model, sources, maths, and honesty notes
notebooks/                   Concept experiments, one per module
scripts/                     Reproducible data and research commands
src/quant_models/data/        Validated data loading and snapshots
src/quant_models/factors/     Fama-French model
src/quant_models/regimes/     Hidden-state model and probability filters
src/quant_models/options/     Black-Scholes, binomial, LSM, and Heston
src/quant_models/metrics/     Shared validated metrics
tests/                       Numerical, input-validation, and app tests
```

`src/portfolio_research/` is retained from the previous project direction
during migration; new work belongs in `src/quant_models/`.

## Quality and release checks

GitHub Actions runs tests and code-quality checks on Python 3.11 and 3.13.
Before a release, run the dependency vulnerability audit and secret scan. Do
not commit downloaded raw market data. Any published derived results must
include their data source, retrieval date, assumptions, validation, and
limitations.

## Learning template

Each model will include:

1. Plain-English intuition and an analogy.
2. A maths box defining symbols, assumptions, and the original paper.
3. A typed, documented, tested implementation and a notebook experiment.
4. An interactive page that changes model inputs.
5. A working demonstration of how the model can mislead.
6. Quiz questions, glossary terms, and a note on what the author understands
   and does not yet understand.

## Current scope

Stages 1–4 provide the application foundation, local option snapshots,
Black-Scholes/binomial reference pricers, tested FF3/FF5 regressions, a
chronological Gaussian HMM experiment, and a beginner guide to all four models.
Longstaff-Schwartz, Heston calibration, quizzes, and public deployment remain
future work. No investment recommendation or claim of predictive ability is
made.
