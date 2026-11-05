# Quant Models Explained

**A self-directed academic project** building four quantitative-finance models
from first principles, validating them against known results, and explaining
how they can mislead. This is a learning project—not investment advice, live
trading, real-money performance, or professional client work.

> Anyone can build a model that looks good. This project is designed to show
> when it isn't.

## Current milestone

The project has changed direction from the earlier portfolio-strategy
playground. This first setup milestone establishes the package, pinned
environment, Streamlit page skeleton, secrets checks, and a local SPY option
chain snapshot tool. The models below are planned; no estimates or prices are
presented until their implementations and validation tests exist.

| Module | Model | Validation and built-in limitation |
| --- | --- | --- |
| 1 | Fama-French factor regressions | Align factor data and returns, convert percent units, handle missing-code sentinels, use Newey-West errors, and test whether alpha differs from zero. The trap: alpha is not evidence of skill unless uncertainty is considered. |
| 2 | Regime switching | Implement and test filtered probabilities, compare with a trusted implementation, and keep smoothed probabilities visibly separate. The trap: smoothed probabilities use future observations. |
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

The model pages are placeholders until their calculations pass their
validation tests. The earlier portfolio-strategy code is retained under
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

Only the repository/app scaffolding and the option snapshot pipeline are in
Stage 1. The factor regression, regime model, option pricers, Heston
calibration, quizzes, and public deployment remain future work. No investment
recommendation or claim of predictive ability is made.
