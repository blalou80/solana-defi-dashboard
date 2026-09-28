# Changelog

## v0.3.0 — 2026-09-27

### Fixed
- custom `db_path` split-brain: single `conn_for(config)` entry point, static guard test
- whale-wallet price fetches exceeded the API URL limit (HTTP 414): requests chunked at 25 mints
- wallets with stored data but no watchlist entry were hidden from the summary

### Added
- SQLite WAL + busy_timeout; 1-writer × 4-reader concurrency test
- horizon-honest metrics: intraday vs daily VaR/Sharpe, `daily_values` rollup
- wallet-scoped alert rules, position ownership, quote attribution
- browser-verified dashboard (screenshots in `docs/screens/`), watchlist form interaction test
- `deploy/` systemd units + docker-compose; `defi-up` verified with clean SIGINT shutdown

### Changed
- Deterministic CI: offline suite gates merges; live network tests are a separate informational step (`@pytest.mark.live`)
- removed ~800 LOC of unwired legacy (dex_aggregator, nlp/il/simulator/harvester services, orphaned components, state.py, xyops layer)

### Known gaps (carried forward)
- Orca position ingestion awaits its first live position-holding wallet; the dashboard shows an explicit pending notice until then (a keyed RPC endpoint unblocks this)
- Telegram/Discord delivery is verified against a local webhook sink; delivery to a live bot endpoint awaits configuration of `TELEGRAM_WEBHOOK_URL`

## v0.2.0 — 2026-09-27
Restored a working, honest baseline (real data end to end, fabricated sources removed) and added wallet onboarding, token registry, position history, durable alerts, and packaging.
