# Implementation Plan — MIRROR Milestone

**Repo:** `blalou80/solana-defi-dashboard` @ `e279c84` (CI green, 83 tests)
**Date:** 2026-09-27 · **Owner:** solo · **Status:** proposed
**Source:** POST-PHASE AUDIT §4 (priorities) and §10 (milestone)

> **MIRROR definition of done:** a stranger pastes their wallet address into the
> browser and within seconds sees *every* token they hold in USD, their Orca
> positions with 24h tick/fee history on a chart, one alert delivered to their
> phone, and realized-vs-quoted slippage on their most recent real swap.
> Every number traceable to chain/API per `METRICS.md`. No mock data anywhere.

---

## 0. Guiding constraints (non-negotiable, inherited from Phases 0–4)

1. **Honesty contract** — unavailable beats invented. New UI states must render explicit "unavailable (reason)".
2. **Daemon writes, UI reads, SQLite is the only shared truth.** No new cross-process globals.
3. **Every new module must pass the import smoke test** (`tests/test_imports.py`) and add at least one behavior test.
4. **Read-only product** — no signing, no custody, no execution. Anything touching keys is out of scope.
5. Live-network tests `pytest.skip` when endpoints are unreachable; CI never fakes green.

---

## 1. Workstream W1 — Wallet-in-browser onboarding (est. 1.5 days)

**Goal:** replace `.config.yaml` hand-editing with a dashboard input.

| # | Task | Files | Acceptance criteria |
|---|---|---|---|
| 1.1 | `watchlist` table (`wallet TEXT PRIMARY KEY, added_ts, label, source`) + CRUD helpers | `src/db.py` | migration-safe (`CREATE TABLE IF NOT EXISTS`); unit test roundtrip |
| 1.2 | Validation: `solders Pubkey.from_string` on input; reject non-mainnet-looking input with reason | new `src/validation.py` (or reuse `xyops/validation.py` if compatible) | invalid pubkey → UI error, nothing stored |
| 1.3 | Dashboard "Watch a wallet" form on `app.py`; list watched wallets with remove | `src/dashboard/app.py` | add → daemon picks it up on next tick without restart |
| 1.4 | Daemon tick source = `watchlist` table ∪ config `wallet_addresses` (config stays for headless use) | `src/main.py` | both sources polled; deduplicated |
| 1.5 | Test: form-add → one `tick()` → snapshot rows appear for that wallet | `tests/test_watchlist_e2e.py` | passes with live RPC or skips cleanly |

**Exit:** a user with zero terminal access can start monitoring (data still requires the daemon running — see W6).

## 2. Workstream W2 — Token registry (est. 1 day)

**Goal:** arbitrary SPL mints in balances/exposures/alerts, not just SOL/USDC/USDT.

| # | Task | Files | Acceptance criteria |
|---|---|---|---|
| 2.1 | `token_meta` cache table (mint, symbol, name, decimals, logo_uri, fetched_ts) | `src/db.py` | TTL 30d; refresh on demand |
| 2.2 | Resolver: try Jupiter price/v3 (`decimals` in response) + `getTokenAccountsByOwner` jsonParsed (gives decimals per account) + fallback RPC `getAccountInfo` on mint | `src/services/market_data.py` | no third-party token-list dependency (endpoint unreachable from test box — documented blocker) |
| 2.3 | Replace the three hardcoded maps: `KNOWN_TOKENS` becomes seed-only; balance scan switches to **one** `getTokenAccountsByOwner(programId=Tokenkeg…)` call, aggregate by mint | `market_data.py`, `dex_aggregator.py`, `nlp_parser.py` | wallet holding JUP/BONWJUP etc. shows them; single RPC call instead of per-mint |
| 2.4 | Exposures keyed by registry symbol with mint fallback `SYMBOL (mint[:4]…)` | `risk/metrics.py` | no more `pool_id[:8]`-style keys |
| 2.5 | Tests: resolver with fixture + one live mint (`JUP…`); aggregation test on multi-token wallet | `tests/test_registry.py` | passes/skips per rule 5 |

**Exit:** portfolio completeness no longer capped at 3 tokens. This kills the last silent-partial-data risk (audit §7).

## 3. Workstream W3 — Position history & charts (est. 1.5 days)

**Goal:** the analytics story becomes visual; enables per-position IL and PnL.

| # | Task | Files | Acceptance criteria |
|---|---|---|---|
| 3.1 | `position_history` table — every tick appends (position_id, ts, current_tick, liquidity, fees_a, fees_b, is_in_range); prune > 7d | `src/db.py`, `main.py` | 15s cadence → ~5.7k rows/position/day, bounded |
| 3.2 | Positions page charts: fee accrual (area) + tick vs range band (line with lower/upper) via `st.line_chart` / altair | `src/dashboard/pages/positions.py` | renders from stored history only; <2 samples → "collecting history" note |
| 3.3 | Entry-price basis: first observed snapshot's implied price = entry proxy (label it "since first observation" — never claim true entry) | `risk/metrics.py` | IL computed with `compute_impermanent_loss` against proxy; UI caption states the proxy honestly |
| 3.4 | Out-of-range duration stat (count ticks where `is_in_range=0` × interval) | positions page | shown per position |
| 3.5 | Tests: history append/prune, IL proxy math | `tests/test_position_history.py` | green |

**Exit:** "24h tick/fee history chart" from the MIRROR demo line.

## 4. Workstream W4 — Durable alerts + realized slippage surface (est. 1.5 days)

**Goal:** retire session-only alerts; expose the receipt parser in the product.

| # | Task | Files | Acceptance criteria |
|---|---|---|---|
| 4.1 | `alert_rules` table (id, wallet, type, symbol/mint, threshold, channel, enabled, cooldown_min) + CRUD; daemon reads table ∪ config | `src/db.py`, `risk/alerts.py`, alerts page | add/edit/delete in UI survives restart; cooldown per rule |
| 4.2 | Alerts page: rules CRUD + `alerts_log` history view (delivered column) | `src/dashboard/pages/alerts.py` | no writes to in-process `state.alerts` anymore |
| 4.3 | `quotes` table: on `compare_routes`/CLI quote, persist (ts, mints, amount, quoted_out, price_impact, route labels) | `engines/slippage.py` or service wrapper | every quote auditable |
| 4.4 | Trade page: "Check a swap I made" — input tx signature + wallet → `realized_slippage_from_tx` vs nearest stored quote for same pair (or manual expected amount) | `src/dashboard/pages/trade.py` | real signature → realized % displayed with receipt provenance; no matching quote → ask for expected amount explicitly |
| 4.5 | Tests: rules CRUD, quote persistence, slippage-from-fixture-tx path in UI service layer | `tests/test_alert_rules.py`, `tests/test_quote_log.py` | green; webhook sink reused from `test_alerts_e2e.py` |

**Exit:** alert + slippage pillars of MIRROR; the "Add Alert (this session)" honesty wart is gone.

## 5. Workstream W5 — Second venue: Raydium CLMM **or** scope-cut — **DECIDED: CUT (2026-09-27)**

**Gate probe result:** `api-v3.raydium.io` is reachable and `/pools/info/mint` returns real
concentrated-pool data, but **no position-by-owner endpoint exists** on the public API
(`position/clmm/*`, `position/list`, `position?owners=` → 404; the OpenAPI spec is a
Swagger-UI HTML shell with no discoverable paths). Without an owner→positions source,
Raydium CLMM monitoring cannot be implemented fully, and per §0 the half-states are
forbidden. **Action taken:** every Raydium monitoring claim removed from README
(architecture diagram, layer list, acknowledgements); `RaydiumApiClient` stays as an
honest metadata-only client. Re-open only if Raydium ships a positions API or a
keyed-indexer (Helius) plan is adopted.

## 5b. Workstream W2 — status: DONE (`fbe7c6f`, CI green)

Token registry live: Metaplex PDA byte-parsing (fixture = real USDC metadata from
mainnet), `token_meta` 30-day cache, case-insensitive reverse lookup with ambiguity
logging, and the balance scan now covers **every** mint via two program-scoped RPC
calls (Token + Token-2022) — the 3-mint allowlist is gone from the data path.

**Decision gate (do this first):** probe `api-v3.raydium.io` CLMM endpoints from this network.
- **If reachable:** implement `raydium_client.py` mirroring `orca_client.py` (positions by owner, live tick), `source="raydium-api-v3"`, tests incl. one live check.
- **If not:** remove every "Raydium" claim from README/features (landing page is frozen and already says "protocol coverage" — acceptable) and record the cut here. **No half-implementations.**

## 6. Workstream W6 — Packaging, deploy, repo hygiene (est. 1 day)

| # | Task | Acceptance criteria |
|---|---|---|
| 6.1 | Entry points in `pyproject.toml`: `defi-daemon = src.main:main`, `defi-quote = src.cli:main`; `pip install -e .` works | fresh venv → install → commands run |
| 6.2 | One-command dev: `defi up` = daemon thread + streamlit (or document two terminals — pick simplest that works) | README quickstart ≤ 4 commands |
| 6.3 | Move repo to `~/solana-defi-dashboard/` (clean `git clone`, keep `~/Documents` history pointer) | `git status` in new home shows only real changes |
| 6.4 | Deploy daemon+UI to one small VPS or Fly.io volume (SQLite needs a disk — **not** serverless); basic log rotation | public demo URL with the user's consent on their wallet only |
| 6.5 | Delete or implement dead config knobs (W-final sweep): `nlp_model`, `il_prediction_model`, `simulation_enabled`, `ai_insights_enabled` | config matches reality |
| 6.6 | LICENSE check + version `0.2.0` tag + GitHub release | tag triggers nothing, documents the milestone |

## 7. Sequencing & dependencies

```
W1 ───→ W2 ─→ W3 ──→ W4 ──→ W6 (deploy last, needs everything)
     │
W5 (decision gate, can run parallel with W2/W3)
```

Total: **~6.5–7 focused dev-days** (matches audit §8 estimate; W5-cut saves 0.75d).
Recommended order: W1 → W2 → W5-gate → W3 → W4 → W6, committing + keeping CI green per workstream.

## 8. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Public RPC rate limits under multi-wallet polling | stale data | batch `getTokenAccountsByOwner` (W2.3 cuts calls ~10×); recommend Helius key in README; backoff already real |
| lite-api.jup.ag free-tier limits (quotes+prices) | unavailable states | acceptable degradation (UI honest); document upgrade path to keyed api.jup.ag |
| Orca positions API shape drift | parse breakage | drop-don't-fabricate parser + live integration test self-flags |
| Chart + history row growth on 15s cadence | DB bloat | 7-day prune (W3.1); interval configurable |
| Solo-founder scope creep (execution, AI features) | milestone slips | §0 constraint 4; anything else goes to backlog |

## 9. Success metrics for the milestone

- MIRROR demo recorded end-to-end in < 3 min with a stranger's wallet.
- Portfolio completeness: 100% of tokens shown for 5 test wallets holding ≥5 distinct mints each.
- ≥ 1 alert delivered to a real Telegram webhook (not sink) with `delivered=1`.
- Test count ≥ ~110, CI green on every workstream merge; zero new hardcoded token maps.
- `METRICS.md` updated with every new row — one line per new metric, no exceptions.

## 10. Explicitly deferred (post-MIRROR backlog)

Multi-user auth/accounts and billing (needs W6.4 + a product decision on paid tier), Raydium (if cut), NLP trade parsing, IL prediction models, fee-harvest automation (custody decision), xyops plugin revival, cross-chain, portfolio export/reports.
