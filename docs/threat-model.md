# Threat model: Quant Models Explained

**Classification:** self-directed academic research and education. The
application is not a broker, investment adviser, live-trading service, or
regulated financial system.

## Assets and scope

Assets include source code, environment configuration, downloaded factor and
market data, daily SPY option-chain snapshots, derived results, and local
research logs. The threat model covers local development, tests, and the
Streamlit Community Cloud demo if it is later enabled.

The initial yfinance workflows do not require credentials. No brokerage
integration or real-money order path is in scope. `.env.example` is a
credential-free template; `.env` and generated data must remain local.

## Trust boundaries

- **Provider to loader:** yfinance and Kenneth French library data are external
  and may be stale, revised, incomplete, malformed, or unavailable. Validate
  schema, date alignment, units, missing-value sentinels, and numeric ranges.
- **Config and user interface to model code:** YAML and slider inputs are
  untrusted. Parse YAML safely, validate types and bounds, and reject
  impossible values rather than silently substituting defaults.
- **Application to local storage:** downloaded snapshots, caches, and logs
  remain local and are excluded from Git. They are not encrypted.
- **Application to public hosting:** Streamlit Community Cloud is not yet
  configured. Before deployment, re-review privacy, secrets, resource limits,
  dependency exposure, and public access.

## Threats and mitigations

| Threat | Mitigation | Residual risk |
| --- | --- | --- |
| Poisoned, malformed, or revised market/option data | Validate tickers, schema, dates, numeric fields, and hashes; retain source and retrieval metadata; fail explicitly | A valid-looking but incorrect provider quote can still distort results |
| Factor-unit/date alignment error | Explicit percent-to-decimal conversion, sentinel handling, exact date joins, and published-series checks | Provider/library revisions and methodological differences can remain |
| Secrets committed to public Git | `.env` and local secret files ignored; `detect-secrets` pre-commit scan; no current API keys | Scanner false negatives and deliberate force-adds remain possible |
| Vulnerable or compromised dependency | Pinned direct requirements, CI `pip-audit`, and release-time audit | Pinned packages can still contain vulnerabilities; transitive dependencies also matter |
| Model leakage or biased estimates | Causal/filtered probabilities for decisions, separate smoothed plots, simulation tests, and explicit model traps | Human-driven repeated tuning can still leak evaluation information |
| Snapshot overwrite or silent data loss | Per-day output folder, atomic write, content hash, and fail-if-destination-exists behavior | Local files can still be deleted or modified by a user or process |
| Raw market data exposed in public repository | Git ignores local snapshots and caches; review staged files before publish | Ignore rules do not prevent explicit force-add or copying data elsewhere |
| Unsafe public app exposure | Deployment is not yet enabled; use Streamlit secrets only if credentials become necessary | A public demo has no custom authentication or authorization by default |

## Snapshot integrity and data policy

Each successful option snapshot has a JSON manifest with retrieval time in
UTC, New York snapshot date, expiration coverage, call/put counts, and SHA-256
of the compressed CSV. This detects accidental file changes when checked
against the manifest; it is not a digital signature or trusted timestamp.
Anyone able to replace both files can recompute the hash.

Snapshots are local and Git-ignored. yfinance data is for personal and
educational use in this project; do not commit or publish raw option chains.
The source may omit, delay, revise, or rate-limit quotes. The recorded
retrieval time does not establish an exchange timestamp, complete NBBO, or
tradability.

The committed detect-secrets baseline contains only reviewed false positives:
random notebook cell identifiers flagged as high-entropy hex strings and a
test fixture that uses the literal key name `api_key` to verify rejection.
The baseline does not store secret values. Re-scan and inspect every new
finding instead of automatically baselining it.

## Safe operating rules

- Do not add credentials to source, YAML, notebooks, test fixtures, output,
  logs, or commit messages.
- Keep `.env`, downloaded snapshots, caches, and local results out of Git.
- Review the exact staged file list before committing.
- Do not treat factor alpha, regimes, option prices, or fitted Heston
  parameters as forecasts or evidence of trading skill.
- Before enabling public hosting or scheduled data collection, review the
  provider's data-use terms and the new deployment/storage boundary.

## Out of scope

There is no real-money trading, brokerage connection, multi-user access
control, encrypted local data store, signed audit service, or production
availability guarantee. Add a new threat-model review before introducing
credentials, public automated snapshots, cloud storage, broker APIs, or
shared user accounts.
