# Research write-up

**Project type:** self-directed academic research. This is an educational
software project, not investment advice, professional client work, or a claim
of live or real-money performance.

## Question and objective

Can simple, long-only daily rules and a rolling mean-variance allocation be
implemented and evaluated in a way that makes timing assumptions, execution
friction, data limitations, and failed results visible?

The objective is to test a research process, not to select a profitable
strategy. A strategy that loses, fails to outperform its benchmark, or cannot
be evaluated on the available data is a valid outcome and must be reported.

## Scope

The configured universe contains 30 large-cap US companies assigned to the
project's 11 sector categories, plus SPY, QQQ, TLT, and GLD. The companies were
selected from today's familiar constituents. This creates survivorship bias:
historical data for firms that failed, were acquired, shrank, or left an index
is not represented. ETF histories are also not a point-in-time record of all
historical constituents.

Adjusted daily closing prices are requested from `yfinance` and cached locally.
The source is convenient for education, but it is not guaranteed to be
immutable, point-in-time, complete, or suitable for execution. The pipeline
validates dates, symbols, prices, and missing observations; it does not fill
gaps or independently verify the provider's corporate-action adjustments.

## Methods

- **SMA crossover:** long/flat exposure based on configured fast and slow
  trailing averages.
- **Momentum:** long/flat exposure after a configured trailing return crosses
  a fixed threshold.
- **Mean reversion:** long/flat exposure based on a trailing price z-score with
  configured entry and exit thresholds.
- **Markowitz:** long-only ETF weights estimated from trailing sample means
  and covariance, subject to a maximum asset weight and configured rebalance
  interval.
- **Benchmarks:** buy-and-hold for the selected stock/ETF, and SPY
  buy-and-hold plus a periodically rebalanced equal-weight version of the
  selected ETFs for the Markowitz portfolio.

Signals use only information available at their signal close. The configured
execution delay and the following return interval prevent a signal from
earning a return before its assumed fill. Transaction costs and slippage are
charged per side on turnover; the terminal holdings are liquidated. The
current configured default for each is 5 basis points per side.

The dashboard reserves the first 70% of selected dates for signal warm-up or
rolling estimates, reports only the final 30%, and begins the evaluated
portfolio in cash. Fixed strategy thresholds are not tuned against this
holdout. Markowitz weights are re-estimated from past data during the
evaluation. This is one chronological holdout, not nested walk-forward
validation; repeatedly inspecting the holdout can still cause human-in-the-loop
overfitting.

## Metrics

The implemented metrics are CAGR, annualised Sharpe ratio, maximum drawdown,
annualised volatility, historical value at risk, and beta versus SPY. They are
descriptive statistics of the selected historical sample. Annualisation uses
the configured 252 sessions per year; the risk-free rate defaults to zero;
historical VaR is not a worst-case loss or a forecast. No metric demonstrates
future performance.

## Results

One exploratory, reproducible-in-method run was calculated from the locally
cached SPY history on 2026-10-24. The loader reported cache retrieval time
2026-10-23 22:07:39 UTC, 5,283 observations from 2005-01-03 through
2025-12-31, and zero missing SPY observations. This was a cache read, not a
fresh provider download. The configured date range ended 2026-01-01
(exclusive); the initial 70% of observations supplied signal history and the
final 30% formed the holdout, from 2019-09-12 through 2025-12-31 (1,585
sessions). The portfolio started the holdout in cash.

The evaluated rule used a 50-session / 200-session SMA, a one-session
execution delay plus the following return interval, 5 bps per-side transaction
cost, and 5 bps per-side slippage. The benchmark was SPY buy-and-hold over the
same holdout, with matching cost assumptions. Metrics are rounded:

| Metric | SMA crossover | SPY buy-and-hold |
| --- | ---: | ---: |
| CAGR | 9.36% | 15.56% |
| Sharpe ratio | 0.61 | 0.82 |
| Maximum drawdown | -33.72% | -33.72% |
| Annualised volatility | 17.00% | 20.33% |
| Historical VaR (95%) | 1.44% | 1.77% |
| Beta versus SPY | 0.70 | 1.00 |

The SMA lagged the benchmark by 6.21 percentage points of annualised CAGR.
Both drawdowns ran from 2020-02-19 to 2020-03-23, when both portfolios were
fully invested; the equal drawdown is a property of this sample, not proof that
the strategy protects against large losses. The user predicted that the SMA
would beat its benchmark; it did not. At the user's direction, a 20% working
drawdown guess was recorded as the assistant's estimate, not represented as
the user's forecast; the realized drawdown was 13.72 percentage points deeper.

This one run is not a fresh market-data retrieval, a statistical test, or
evidence of a repeatable edge. It is a single asset, one fixed rule, and one
holdout with known survivorship and provider-history limitations. The local
cache is excluded from Git, so a clone cannot reproduce the exact price series
unless the provider returns identical history. Do not generalize these results
or treat the cached data as immutable. Re-run with verified data and save the
exact cache/provider timestamp and commit before using the figures elsewhere.

For each reproducible run, record the following:

| Item | Value to record |
| --- | --- |
| Git commit and software test result | Fill from the exact tested revision |
| Data source, cache state, retrieval time | Use the dashboard diagnostics |
| Requested and observed dates | Record the actual evaluation period |
| Asset(s) and benchmark | Include ticker symbols |
| Strategy and all parameters | Include windows, thresholds, and rebalance settings |
| Per-side transaction cost and slippage | Record basis points for each |
| CAGR, Sharpe, drawdown, volatility, VaR, beta | Include both strategy and benchmark |
| Failed or unavailable runs | State the error or reason; do not omit silently |
| Interpretation and limitations | Explain uncertainty and alternative explanations |

Never compare a full-sample, cost-free, or future-signal result as though it
were an honest out-of-sample result. The bias lab intentionally demonstrates
these invalid variants and labels them accordingly.

## Engineering and validation

The application separates configuration, market-data validation, strategies,
backtesting, metrics, and dashboard code. Unit tests cover price and signal
validation, execution delay, turnover and costs, portfolio weight drift,
chronological splits, strategy causality, Markowitz constraints, metric
calculations, paper-ledger limits, audit-log integrity, and dashboard
rendering. Passing software tests establishes tested behavior on those cases;
it does not establish economic validity or profitable performance.

The paper-trading area is a local manual-price simulation. It places no orders,
uses no broker API, and deducts modeled costs. Trade rationale is recorded
before a simulated order, then can be reviewed later.

## Limitations and next research steps

1. Replace the present-day universe with survivorship-free, point-in-time
   membership and delisted-security data.
2. Independently verify adjusted data and account for provider revisions,
   missing observations, delistings, corporate actions, and trading calendars.
3. Add repeated walk-forward or nested validation with parameters frozen
   before each evaluation period.
4. Investigate whether the simple per-side cost assumptions reflect plausible
   execution; this model omits market impact, spread dynamics, taxes, and
   capacity.
5. Evaluate parameter and universe sensitivity, multiple-testing effects,
   regime dependence, and uncertainty intervals.
6. Consider a point-in-time risk-free rate and carefully document benchmark
   choices and overlapping ETF exposures.

The project's differentiator is transparent measurement and secure-by-design
habits, not a claim that a rule predicts markets.
