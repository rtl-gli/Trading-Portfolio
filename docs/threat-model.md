# Threat model

**Project classification:** self-directed academic research project. The app is
not a broker, live-trading service, financial adviser, or regulated record
system.

## Scope and assets

This model covers the local Python package, Streamlit dashboard, configuration,
downloaded adjusted-price cache, SQLite paper ledger, and JSON Lines audit log.
Assets include source integrity, the user's private trade rationale, local
research data, and the integrity of recorded signals and simulated trades.

The application currently uses keyless `yfinance` access. It does not connect
to brokerage accounts, execute real orders, or require API credentials.

## Trust boundaries

- **External provider to application:** market data is downloaded from the
  configured provider. Ticker/date inputs and returned data are checked, but
  the project does not independently verify provider identity, point-in-time
  coverage, or corporate-action correctness.
- **Configuration and user inputs to calculation code:** YAML configuration
  is parsed with `safe_load`; numerical settings, symbols, prices, signals,
  weights, dates, and journal values are validated before use.
- **Application to local files:** caches, the SQLite journal, and the audit log
  are written beneath the project data directory. They are excluded from Git,
  but are not encrypted.
- **Dashboard to browser:** Streamlit is intended for local educational use.
  The project does not implement user accounts, authorization, CSRF controls,
  or a public deployment security boundary.

## Threats and controls

| Threat | Current control | Residual risk |
| --- | --- | --- |
| Malformed or unexpected ticker and price data | Ticker allow-list pattern, strict dates, numeric/positive-price validation, explicit gap reporting, and fail-closed backtests | A valid-looking bad or revised observation from the provider can still affect results |
| Malicious or malformed YAML | `yaml.safe_load` and explicit type/range checks | A user who edits the local configuration can still change research assumptions |
| Look-ahead or execution-timing errors | Trailing signals, delayed fills, holdout evaluation, and tests that change future prices | A bug or misuse in future extensions may introduce leakage; review every new strategy |
| Overstated performance | Costs/slippage, held-out evaluation, warnings, and explicitly labelled bias demonstrations | Survivorship bias, provider revisions, parameter search, and small samples remain |
| SQL injection in the local journal | Parameterized SQLite statements and constrained inputs | Local users can edit the database directly; the simulator is not a secure shared service |
| Audit-file modification | Each JSONL event is linked with a SHA-256 hash; appending verifies the existing chain | A local writer can delete the file or recompute hashes; there is no trusted remote copy or signature |
| Secrets appearing in audit events | Secret-like field names are rejected; free-text rationale and review are not copied to the audit log | An existing local journal remains plaintext; protect the device and avoid storing personal data |
| Accidental publication of local data | `.gitignore` excludes market caches, SQLite databases, JSONL logs, and secret files | Explicit force-adds, copies, or external backups can still disclose data |
| Dependency or provider compromise | Dependencies and data provider are declared and documented | No lockfile, package signing policy, formal vendor review, or independent data verification |

## Audit semantics

Every dashboard evaluation logs a run header and one event per signal date,
including its signal/target and the modeled position when available. Each
paper-trade attempt and post-trade review is logged in the same transaction
workflow as the local ledger update. Free-text rationale and review are kept in
SQLite, not duplicated to the audit log; the audit stores their SHA-256 digest.

The JSONL chain is **tamper-evident, not tamper-proof**. It has no encryption,
access control, trusted timestamp, digital signature, or remote immutability.
Do not rely on it for legal, regulated, or financial dispute resolution.

## Safe operation

- Run the dashboard locally and do not expose it to an untrusted network.
- Never add credentials or personally identifying information to source,
  configuration, audit events, or trade rationale.
- Keep local data, paper journals, and logs on a device protected by the
  operating system's user-account controls.
- Review `git status` and staged changes before publishing; `.gitignore` is
  defense in depth, not a guarantee that private files cannot be committed.
- Treat all returns as exploratory historical calculations, not expected or
  live performance.

## Out of scope and next review

There is no real-money execution path, authentication, multi-user isolation,
encrypted storage, remote audit service, or production deployment hardening.
Before adding any broker integration, cloud deployment, credentials, or shared
accounts, create a new threat model and have the design reviewed. Survivorship
bias and market-data quality are research-validity risks as well as technical
risks; they are not eliminated by the controls above.
