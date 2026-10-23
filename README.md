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
   (**current stage**)
2. Validated market-data ingestion and local caching
3. Notebook-first, cost-aware SMA backtest versus buy-and-hold
4. Tested performance and risk metrics
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

## Status and intended use

This repository currently contains project scaffolding only. It does not
download data, generate signals, backtest strategies, or place trades.
Everything built here is for education and paper research, not financial advice
or a claim of live or professional performance.
