# Changelog

## v0.3.0 — 2026-09-27 ("PROVE IT" sprint)

### Fixed
- **S1** custom `db_path` split-brain: single `conn_for(config)` entry point, static guard test
- **S2** whale-wallet price fetches exceeded the API URL limit (HTTP 414): requests chunked at 25 mints
- **S6** wallets with stored data but no watchlist entry were hidden from the summary

### Added
- **S2** SQLite WAL + busy_timeout; 1-writer × 4-reader concurrency test
- **S3** horizon-honest metrics: intraday vs daily VaR/Sharpe, `daily_values` rollup
- **S4** wallet-scoped alert rules, position ownership, quote attribution
- **S6** browser-verified dashboard (screenshots in `docs/screens/`), watchlist form interaction test
- **S9** `deploy/` systemd units + docker-compose; `defi-up` verified with clean SIGINT shutdown

### Changed
- Deterministic CI: offline suite gates merges; live network tests are a separate informational step (`@pytest.mark.live`)
- **S8** removed ~800 LOC of unwired legacy (dex_aggregator, nlp/il/simulator/harvester services, orphaned components, state.py, xyops layer)

### Known gaps (carried forward)
- **S5** Orca position ingestion still awaiting its first live position-holding wallet — the dashboard shows an explicit unverified banner until then (blocked on public-RPC rate limits; needs a keyed RPC or a known LP wallet)
- **S7** real Telegram/Discord delivery untested beyond a local webhook sink (needs user's bot token)

## v0.2.0 — 2026-09-27
Phases 0–4 honesty/functionality restoration + MIRROR W1–W6 (see specs/004).
