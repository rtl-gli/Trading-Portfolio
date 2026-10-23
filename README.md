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

Planned evaluation includes CAGR, Sharpe ratio, maximum drawdown, volatility,
VaR, and beta versus SPY. Those results are not implemented yet. A free
historical-data source can revise or omit observations; locally cached data is
not automatically point-in-time or survivorship-bias-free.

## Build roadmap

1. Repository setup, environment, folder structure, and secrets handling
   (**complete**)
2. Validated market-data ingestion and local caching (**complete**)
3. Notebook-first, cost-aware SMA backtest versus buy-and-hold (**complete**)
4. Tested performance and risk metrics (**complete**)
5. Streamlit strategy playground and learning mode
6. Additional strategies and out-of-sample testing
7. Bias lab, predict-then-run, and quiz
8. Paper-trading simulator and trade journal
9. Audit logging, input validation, and threat model
10. Results, limitations, and project write-up

Each stage is intended to add a small learning notebook before the corresponding
production module. Features are described as planned until implemented and
tested.

## Local setup (PowerShell)

Requires Python 3.11 or newer.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell blocks environment activation, use the environment's interpreter
directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run checks with:

```powershell
python -m pytest
python -m ruff check .
```

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

## Status and intended use

Stages 1–4 are complete. Data downloads happen only when the caller invokes the
pipeline; the repository does not place trades. Everything built here is for
education and paper research, not financial advice or a claim of live or
professional performance.
