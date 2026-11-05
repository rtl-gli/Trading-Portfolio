# Fama-French factor regressions

Stage 3 fits FF3 and FF5 regressions to monthly returns for a configurable
long-only stock portfolio. The app asks for a prediction about alpha before it
requests market data or displays estimates.

## Model and units

For portfolio return \(R_{p,t}\), risk-free return \(R_{f,t}\), and factor
returns \(F_{j,t}\), the model is

\[
R_{p,t} - R_{f,t} = \alpha + \sum_j \beta_j F_{j,t} + \epsilon_t.
\]

- **FF3:** `Mkt-RF`, `SMB`, and `HML`.
- **FF5:** FF3 plus `RMW` and `CMA`.
- `RF` is subtracted from the portfolio return. The French library's factor
  and risk-free series are published in percent; the loader divides by 100
  before alignment and regression.
- The intercept is a monthly excess-return residual after the selected factors.
  The coefficient table reports Newey-West/HAC standard errors, t-statistics,
  p-values, and confidence intervals.

The app's default portfolio uses the present-day 30-stock list. Selected
stocks can be assigned custom long-only weights that sum to one. The portfolio
is rebalanced to those weights monthly; its input returns are gross of
transaction costs and should not be presented as a backtest or investable
performance. The current stock list introduces survivorship bias.

## Data pipeline

- **Prices:** validated daily adjusted closes from yfinance, using the existing
  local cache. Missing prices are not filled; an incomplete selected universe
  fails clearly. Monthly returns use month-end closes and start no earlier
  than the configured date.
- **Factors:** monthly FF3/FF5 ZIP files from the
  [Ken French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
  Archives are read in memory and never extracted. A local ZIP and JSON
  manifest are cached under the ignored `data/cache/factors/` directory. The
  manifest records the source URL, retrieval time, model, and SHA-256 digest.
- **Missing values:** documented numeric sentinel values such as `-99.99` are
  converted to missing data. Inner date alignment is exact by calendar month;
  incomplete and unmatched months are counted, never filled, and shown in the
  app.

The digest detects changes to a cached file when its manifest is unchanged; it
is not a digital signature or proof that the provider authored the file.
Ken French datasets can be revised as source data are updated. The saved
retrieval time and digest provide local provenance, not a point-in-time archive
guarantee.

## Newey-West inference

The regression uses an OLS coefficient estimate with a heteroskedasticity- and
autocorrelation-consistent covariance estimate (HAC/Newey-West). The default
lag count is configured in `config/factors.yaml`; the app allows it to be
changed. Standard errors affect inference, not coefficient estimates.

A confidence interval excluding zero, or a small p-value, is not the
probability that a strategy has skill. It does not repair survivorship bias,
factor misspecification, data revisions, omitted risks, multiple testing, or
the uncertainty in the chosen portfolio.

## Validation and references

Tests use deterministic synthetic factor data, a known alpha, missing-value
sentinels, and local mocked ZIP archives. They do not download data or claim
empirical results.

- Fama, E. F. and French, K. R. (1993), “Common Risk Factors in the Returns on
  Stocks and Bonds,” *Journal of Financial Economics*, 33(1), 3–56.
  <https://doi.org/10.1016/0304-405X(93)90023-5>
- Fama, E. F. and French, K. R. (2015), “A Five-Factor Asset Pricing Model,”
  *Journal of Financial Economics*, 116(1), 1–22.
  <https://doi.org/10.1016/j.jfineco.2014.10.010>
