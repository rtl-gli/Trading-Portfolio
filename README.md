# Portfolio Research Lab

**A self-directed academic project** for learning how to test portfolio
strategies rigorously—not a live-trading system or investment advice.

> Anyone can build a strategy that looks good. This project is designed to
> find out when it isn't.

## Research principles

- Compare strategies with explicit transaction-cost and slippage assumptions.
- Keep signals and portfolio weights from using information that was not
  available at the time.
- Use out-of-sample or walk-forward evaluation; treat in-sample results as
  exploratory, not evidence of future performance.
- Record failed approaches and limitations as carefully as successful tests.
- Keep configuration and secrets out of source code. The planned initial
  market-data source, `yfinance`, does not require an API key.
- Treat the planned fixed list of today's large US companies as survivorship-
  biased: companies that failed, shrank, or left the market are not represented.

## Planned research scope

The platform is intended to cover approximately 30 large-cap US stocks across
all 11 sectors, plus SPY, QQQ, TLT, and GLD. Planned comparisons include SMA
crossover, momentum, mean reversion, mean-variance optimisation, equal weight,
and buy-and-hold.

Evaluation includes CAGR, Sharpe ratio, maximum drawdown, volatility, VaR, and
beta versus SPY. A free historical-data source can revise or omit observations;
locally cached data is not automatically point-in-time or survivorship-bias-free.

## Build roadmap

1. Repository setup, environment, folder structure, and secrets handling
   (**complete**)
2. Validated market-data ingestion and local caching (**complete**)
3. Notebook-first, cost-aware SMA backtest versus buy-and-hold (**complete**)
4. Tested performance and risk metrics (**complete**)
5. Streamlit strategy playground and learning mode (**complete**)
6. Additional strategies and out-of-sample testing (**complete**)
7. Bias lab, predict-then-run, and quiz (**complete**)
8. Paper-trading simulator and trade journal (**complete**)
9. Audit logging, input validation, and threat model (**complete**)
10. Results, limitations, and project write-up (**methods complete; empirical run pending**)

Each stage is intended to add a small learning notebook before the corresponding
production module. Features are described as planned until implemented and
tested.

## Local setup (PowerShell)

Requires Python 3.11 or newer.

```powershell
# Open the project folder in VS Code and run these in its integrated PowerShell terminal.
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Using the virtual environment's interpreter directly avoids PowerShell
activation-policy issues and ensures each command uses the project's
dependencies. Run the automated tests and lint check with:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

GitHub Actions runs formatting, lint, and the complete test suite on Python
3.11 and 3.13 for pushes to `main`, pull requests, and manual workflow runs.

Launch the dashboard from the repository root:

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The first run needs internet access for yfinance; matching later requests use
the local cache. Stop the dashboard with `Ctrl+C`.

## Repository layout

```text
config/                  Version-controlled, non-secret project settings
data/                    Local market data (ignored by Git)
docs/                    Research and security documentation
notebooks/               Stage-by-stage learning experiments
src/portfolio_research/  Importable Python package
tests/                   Automated tests
```

## Secrets and local data

Do not commit API keys, passwords, account details, or private data. `.env`,
Streamlit's local `secrets.toml`, private key files, downloaded market data,
logs, and generated outputs are excluded by `.gitignore`. The checked-in
`.env.example` is documentation only and contains no credentials.

The initial data provider is planned to be keyless. If another provider is
introduced, its credentials should be supplied through environment variables
or an ignored local secrets file; the project must never print or audit-log
secret values.

## Stage 2: market data

The fixed universe is in `config/universe.yaml`: 30 present-day US stocks
labelled across all 11 sectors, plus SPY, QQQ, TLT, and GLD. Load the list and
request adjusted daily prices with `portfolio_research.config.load_universe`
and `portfolio_research.market_data.load_prices`. The end date is exclusive,
matching yfinance's convention.

The pipeline validates symbols, date order, duplicate daily bars, numeric and
positive prices, infinite values, and requested ticker coverage. It reports
missing observations per symbol and does **not** fill or discard them. Results
are cached as compressed CSV files under `data/cache/` (ignored by Git).
Fresh cache entries are reused; offline mode can return an expired entry, but
labels it `stale_cache`. The configured cache lifetime is in
`config/project.yaml`.

`yfinance` is a convenient, free research source, not a point-in-time or
institutional data feed. `auto_adjust=True` supplies adjusted prices, but
adjustments and historical records can change; delisted companies and past
index constituents are not restored by this present-day universe. Cache
timestamps identify when data was retrieved locally, not whether the provider's
history is immutable or survivorship-bias-free.

## Stages 3–4: SMA backtest and analytics

The first experiment compares one configured, long-only SMA crossover on
adjusted daily closes with buy-and-hold. Fast/slow windows, per-side transaction
cost, per-side slippage, and execution delay live in `config/strategies.yaml`;
metric conventions live under `analytics` in `config/project.yaml`.

An SMA signal uses the closing price at its signal date. The backtest waits for
the configured execution delay to fill the signal at a later close, then waits
until the next return interval before crediting market performance. This avoids
earning a return from before the assumed fill. Costs apply on signal-driven
trades and final liquidation; buy-and-hold also pays entry and liquidation
costs. Missing prices fail the backtest instead of being filled. The notebook
in `notebooks/03_sma_backtest.ipynb` walks through the experiment.

Tested metrics include CAGR, annualised Sharpe ratio, maximum drawdown,
annualised volatility, historical VaR, and beta versus the explicitly supplied
benchmark. Undefined Sharpe/beta values come with warnings. Metric conventions
and synthetic-return experiments are in `notebooks/04_performance_metrics.ipynb`.
Annualisation assumes the configured 252 periods per year; historical VaR is a
sample quantile, not a forecast. One SMA setting on SPY is a demonstration,
not evidence of an edge or out-of-sample validation.

## Stage 5: Streamlit playground

The sidebar lets you choose a strategy, asset or ETF portfolio, date range,
signal parameters, transaction costs, and slippage. Streamlit reruns the
research when an input changes; the local data cache prevents unnecessary
repeat downloads. Learning mode is enabled by default and provides
plain-English explanations, caveats, and a short glossary beside the results.
The dashboard reports data source, retrieval time, missing observations, and
any leading sessions excluded before the selected assets overlap.

Interactive controls make runs easier to inspect, but do not prove a strategy
is robust. The held-out period is deliberately short enough to make sample-size
limitations visible.

## Stage 6: momentum, mean reversion, and Markowitz

The playground now also compares long/flat momentum and mean-reversion rules.
Their lookbacks and thresholds are configured in `config/strategies.yaml`.
Parameters are held fixed rather than searched against the evaluation period.
The dashboard reserves the initial 70% of selected dates as signal warm-up or
estimation history and reports performance only over the final 30%, starting
the simulated portfolio in cash and charging entry and exit costs.

The Markowitz option uses a selected basket of the four configured ETFs. It
estimates expected daily returns and covariance from a rolling historical
window, rebalances at the configured interval, enforces long-only weights and
a maximum position, and passes weights through the same execution delay and
cost model. The SciPy optimiser is used only on past observations available at
each rebalance; estimation error and optimizer sensitivity remain serious
limitations. A future increase in the asset universe can make the maximum
weight infeasible; in that case, the optimizer fails explicitly rather than
silently changing the limit.

This is a single holdout, not nested walk-forward model selection. The fixed
signal thresholds have not been tuned, and changing them after seeing holdout
results would consume that holdout. The multi-strategy learning experiment is
in `notebooks/06_walk_forward_strategies.ipynb`.

## Stage 7: bias lab, predictions, and quizzes

Before running the backtest, record whether you expect the selected strategy to
beat its benchmark and your estimated maximum drawdown. The dashboard compares
those predictions with the held-out result; changing a research input requires
a new prediction.

The bias lab can deliberately remove costs, use tomorrow's signal or portfolio
weights today, or select SMA parameters using the full sample. These variants
are explicitly labelled invalid and are never reported as honest out-of-sample
results. The overfit demo reports the best full-sample setting on the same
observations used to choose it. The quiz tests concepts covered in the code.
See `notebooks/07_bias_lab.ipynb`.

## Stage 8: paper trading and trade journal

The optional simulator stores a local virtual account in
`data/paper_trading.sqlite3` (ignored by Git). It sends no orders and does not
connect to a brokerage. You manually enter a reference price; each simulated
trade requires a written rationale first and deducts the dashboard's current
transaction-cost and slippage assumptions. Cash limits, share availability,
ticker syntax, and numeric inputs are checked. Add a later review to each
trade. The initial account balance is configured in
`config/project.yaml`. See `notebooks/08_paper_trading_journal.ipynb`.

## Stage 9: validation, audit log, and threat model

Each evaluated daily signal is recorded with its run ID, date, target signal,
and available position. Paper-trade attempts and post-trade reviews are also
logged. The local `data/audit.jsonl` uses a SHA-256 hash chain; each append
checks the existing chain before writing. The log avoids copying free-text
trade rationales and reviews, retaining only their hashes.

The audit is tamper-evident, not tamper-proof: anyone able to rewrite the local
file can recalculate hashes or delete it. The log is not encrypted, signed,
remotely backed up, or a regulated record. Protect the device and keep the
SQLite journal and generated log out of Git. Read
[`docs/threat-model.md`](docs/threat-model.md) before extending data sources,
sharing the dashboard, or adding credentials or any brokerage connection.
The audit-log lesson is in `notebooks/09_audit_log.ipynb`.

## Status and intended use

Stages 1–10 are complete as a research platform and methods write-up. **No
empirical strategy results have been verified yet**, so the report does not
claim measured performance. Data downloads happen only when the caller invokes
the pipeline or opens the dashboard; the repository does not place real trades.
Everything built here is for education and paper research, not financial advice
or a claim of live or professional performance. Read
[`docs/research-writeup.md`](docs/research-writeup.md) for the research question,
method, reporting template, and next steps.
