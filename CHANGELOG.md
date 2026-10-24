# Changelog

Notable project changes are recorded here.

## [Unreleased]

- Added a documented, fixed 30-stock universe across all 11 sectors and four ETFs.
- Added validated daily adjusted-price ingestion with compressed local caching.
- Added freshness and offline-cache reporting, data-quality diagnostics, and tests.
- Documented survivorship and provider-history limitations.
- Added a delayed, cost- and slippage-aware SMA versus buy-and-hold backtest.
- Added tested performance metrics and two stage-by-stage learning notebooks.
- Added a Streamlit SMA playground with learning mode, data diagnostics, and glossary.
- Added momentum, mean-reversion, capped long-only Markowitz, and chronological holdout evaluation.
- Applied execution delays and transaction costs consistently across strategies and added walk-forward tests.
- Added prediction-before-run, deliberately biased comparison variants, and a project-specific learning quiz.
- Added a validated local paper ledger with transaction costs, rationale-first entries, and post-trade reviews.
- Added a hash-chained local audit log, signal/trade event recording, input validation, and threat model.
- Added a research write-up that documents the methodology, limitations, and a results-reporting template without overstating evidence.
- Recorded one cost-aware SPY holdout result with source/cache provenance, the prior prediction, and explicit interpretation limits.
- Added an equal-weight ETF-basket benchmark alongside SPY buy-and-hold for Markowitz comparisons.

## [0.1.0] - Initial foundation

- Created the Python package, configuration, test, and notebook structure.
- Added local-secret, downloaded-data, and generated-output exclusions.
- Documented the project's research scope, staged roadmap, and known limitations.
