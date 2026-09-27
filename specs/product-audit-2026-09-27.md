# Product Audit — Solana DeFi Dashboard (codebase, not website)

Date: 2026-09-27 · Scope: `/home/dred/Documents` (repo `blalou80/solana-defi-dashboard`), 3,004 LOC Python across 33 modules. Every claim below was verified by reading the file or running a command on this machine.

---

## 1. Current capabilities (verified)

**What genuinely works:**
- `src/engines/liquidity.py` — correct constant-product IL math, annualized net-yield, tick↔price conversion, in/out-of-range boundary check. Unit-tested.
- `src/engines/slippage.py` — quote parsing → route DataFrame, bps→pct conversions, realized-slippage formula. Unit-tested.
- `src/risk/metrics.py` — historical VaR and Sharpe implementations are mathematically sound (inputs are fake, see §4).
- `src/risk/alerts.py` — real Telegram/Discord webhook dispatch (payload shapes correct, env-var driven).
- `src/config.py` — YAML + `.env` loading with sane defaults; no secrets committed (only `*.example` files tracked).
- Streamlit shell (`src/dashboard/app.py` + 3 pages) imports and renders from in-process state.
- Test suite runs: 10 passed in 1.0s (3 unit files, 77 LOC).

**What is claimed but not real:**
- "Real-Time Slippage Engine … live quotes from Jupiter" — `quote-api.jup.ag/v6` is **dead** (curl from this machine: connection failure; Jupiter deprecated v6). The flagship feature cannot fetch a quote.
- "Track Orca Whirlpool and Raydium CL positions" — `fetch_all_positions()` returns **hardcoded mock positions**; `fetch_orca_whirlpool_position()` is a documented stub.
- "VaR, Sharpe ratio" — computed from `np.random.seed(42); np.random.normal(...)` — a fixed random mock, not the portfolio.
- "Realized slippage from on-chain transaction receipts" — the receipt fetcher exists but nothing ever populates `amount_out_realized`; `realized_slippage()` just compares two fields.
- "Automated alerts via Telegram/Discord" — dispatch works, but `state.alerts` is never populated by any code path, and the stop-loss check compares against a literal `100` ("mock price").

## 2. Structural breakage (the biggest finding)

**9 of 11 "enhanced" services (≈1,450 LOC, ~half the codebase) cannot be imported at all.** Verified with a per-module import matrix:

```
src.services.dex_api_client        => No module named 'src.services.utils'
src.services.solana_rpc_client     => No module named 'src.services.utils'
src.services.dex_aggregator        => No module named 'src.services.utils'
src.services.cl_position_service   => 'src.models' is not a package
src.services.slippage_analytics    => 'src.models' is not a package
src.services.il_predictor          => 'src.models' is not a package
src.services.transaction_simulator => 'src.models' is not a package
src.services.fee_harvester         => 'src.models' is not a package
src.services.trade_template_manager=> 'src.models' is not a package
src.utils.error_handling           => 'src.utils' is not a package
```

Three root causes, all one-line-class fixes:
1. `src/services/utils.py` **does not exist** (imported by 2+ modules).
2. `src/models.py` (legacy module) shadows the `src/models/` directory because the directory has **no `__init__.py`** (a plain module beats a namespace package). Same pattern: `src/utils.py` shadows `src/utils/error_handling.py`.
3. Nobody ever ran these modules — there is no CI, no import smoke test, and the two empty `tests/integration/` and `tests/contract/` directories suggest tests were planned but never written.

`src/dashboard/components/` (`cl_monitor.py`, `trade_analyzer.py`) is **orphaned**: no page imports it, and its relative imports (`from ..models.cl_position`) resolve to `src.dashboard.models` — wrong depth. It would crash if wired up.

## 3. Architecture weaknesses

1. **The daemon↔UI contract is impossible as designed.** `src/state.py` is an in-process global singleton. `main.py` (daemon) writes it; `streamlit run` is a *different process* that reads its own empty copy. The README mermaid diagram shows shared state between them — that can never work. The dashboard therefore always shows "No portfolio data available."
2. **Fake routes poison real ones.** `dex_aggregator` returns fabricated Raydium/Orca `RouteComparison`s with invented prices/slippage; results are sorted by `slippage_estimate`, so the fake placeholders (0.005) always beat the one real Jupiter quote (0.5) and get flagged `is_best_route`.
3. **Sync `@retry` decorating `async def`** in `dex_api_client.py` and `solana_rpc_client.py` — the wrapper returns the coroutine un-awaited, so retries never fire and exceptions escape on first failure.
4. **Hardcoded token universe** — 3-mint maps duplicated in `engines/slippage.py`, `dex_aggregator.py`, `nlp_parser.py` (with a visibly fake BONK mint `Bonk1E9P…`). No metadata service.
5. **No persistence.** Everything is memory-only; nothing survives a restart, which is why VaR/Sharpe/slippage history can't be real.
6. **Config lies** — `nlp_model: en_core_web_sm` and `il_prediction_model: random_forest` exist in config, but `nlp_parser` is regex-only (no spaCy) and `il_predictor` is a closed-form formula (no sklearn). Dead knobs.
7. **Jupiter v6 everywhere** — both the engine and the new client point at the retired endpoint; current API is `lite-api.jup.ag/swap/v1` (free tier) or `api.jup.ag/swap/v1` (keyed).
8. **Product lives in a home directory** — the repo's working tree is `~/Documents` alongside 15+ unrelated folders (`COmfyui`, `bLinder`, `Cline`, `مهمcai `…). `git status` shows 29 dirty entries; any contributor cloning gets a repo whose root is someone's desktop.

## 4. Technical debt inventory

| Item | Where | Severity |
|---|---|---|
| Un-importable services layer (~1,450 LOC dead on arrival) | `src/services/`, `src/models/`, `src/utils/` | **Critical** |
| Dead Jupiter v6 endpoint | `engines/slippage.py:38`, `dex_api_client.py:61` | **Critical** |
| Per-process "shared" state | `state.py` + `main.py` + `dashboard/` | **Critical** |
| Mock data indistinguishable from real in UI | `metrics.py` seed-42 VaR, `alerts.py` price=100, `fetch_all_positions` | High (also an honesty violation vs. your own no-fake-metrics rule) |
| Sync retry on async fns | `dex_api_client.py:42`, `solana_rpc_client.py:35,41,60` | High |
| Orphaned dashboard components w/ wrong relative imports | `dashboard/components/*` | Medium |
| `import asyncio` / `from datetime import datetime` at bottom of file | `utils.py:66`, `state.py:49` | Low (works, but signals LLM-generated-then-never-reviewed code) |
| `models.py` re-exporting `Config`; two model systems (dataclass vs BaseModel w/ uuid) | `models.py`, `models/base.py` | Medium |
| Empty integration/contract test dirs, no CI, no lint config, unpinned deps, pytest in runtime deps | repo root | Medium |
| Hardcoded owner/pools in daemon | `main.py:23-24` | Medium |
| xyops plugin layer targeting a tool absent from this machine | `src/xyops/` | Low (candidate for removal or separate repo) |
| `asyncio.get_event_loop()` in cache (deprecated pattern) | `solana_rpc_client.py:88` | Low |
| `asyncio.run()` inside Streamlit page | `pages/trade.py:29` | Low |

## 5. Easiest wins (ordered by hours-per-impact)

1. **Fix the three import breaks** — add `src/models/__init__.py`, `src/utils/__init__.py`, create `src/services/utils.py` re-exporting `retry/async_retry` from `src.utils`. ~1h. Revives half the codebase.
2. **Add an import-all smoke test** (`test_imports.py` walking `pkgutil.walk_packages`) so this class of failure can never recur silently. ~30min.
3. **Move Jupiter to swap/v1** (`https://lite-api.jup.ag/swap/v1/quote`) — same params, one URL ×2. ~30min + live test. Restores the flagship quote feature.
4. **Swap sync `@retry` → `@async_retry`** on the three async methods. ~15min.
5. **Delete fabricated Raydium/Orca placeholder quotes** — return `None` until real; keep `is_best_route` honest. ~30min.
6. **Honesty pass on README + UI labels** — mark VaR/Sharpe/positions as simulation until real data exists (matches the rule you enforced on the website). ~1h.
7. **Config-driven watchlist** replacing `main.py` hardcoded owner/pools. ~1h.

## 6. Highest-impact improvements

1. **Real position ingestion** — Orca Whirlpool API (`api.orca.so/v2/pools/positions?whirlpoolAddr=` or RPC account parsing) + Raydium CLMM; normalize into `CLPosition`. This single change makes the product *true* rather than demo.
2. **Persistence (SQLite)** — positions, quotes, portfolio snapshots, alert log. Enables real historical VaR/Sharpe, realized-vs-expected slippage tracking, alert dedup, and dashboard history charts.
3. **One data path** — collapse daemon+UI into either (a) a single Streamlit process with a background refresh thread, or (b) daemon writes SQLite, UI reads SQLite. Option (b) also fixes the impossible shared-state design.
4. **Real price feed** — Jupiter Price API v2 or CoinGecko for USD values; kills the last mock in `compute_portfolio_metrics`.
5. **Token metadata registry** — fetch once, cache in SQLite; removes the three hardcoded mint maps.

## 7. Roadmap: today → usable MVP

**MVP definition:** paste a wallet address → see your *real* Orca/Raydium CL positions (live ticks, fees, IL, range status) → risk metrics computed from *stored history* → out-of-range and slippage alerts actually delivered to your webhook → one real Jupiter quote with measured price impact. Every number on screen traceable to chain or API.

**Phase 0 — Stop the bleeding (1 day)**
Items 1–5 of §5. Exit: `pytest` green incl. import smoke test; CLI `quote` returns a live Jupiter route table.

**Phase 1 — Real data in (2–3 days)**
Jupiter swap/v1 + price/v2 clients; Orca Whirlpool position fetcher (owner → positions via `getSignaturesForAddress`/Whirlpool API); SQLite schema (`positions`, `snapshots`, `quotes`, `alerts`); config watchlist with real wallet. Exit: daemon stores live position + price snapshots every poll.

**Phase 2 — Real analytics (2–3 days)**
VaR/Sharpe from stored snapshot returns (delete seed-42); boundary checks from live pool ticks; realized slippage from tx receipts (parse `meta.postTokenBalances`); token exposures by mint with metadata names. Exit: dashboard metrics page shows numbers that change with the market and match DB queries.

**Phase 3 — Alerts that fire (2 days)**
Rules engine over real state (out-of-range, IL > threshold, slippage anomaly); alert log + cooldowns in SQLite; Telegram/Discord dispatch verified end-to-end; alerts page reads the log. Exit: moving a test position out of range produces one (and only one) webhook message.

**Phase 4 — UI on truth + guardrails (2–3 days)**
Streamlit pages read SQLite (fixes §3.1); positions page with real PnL/IL/range bars; trade analyzer on real quotes only; ruff + GitHub Actions CI (lint, type-check optional, pytest, import smoke); pinned `requirements.txt`; move working tree out of `~/Documents` root into a dedicated checkout. Exit: CI green on push; a stranger can `git clone`, `pip install -r`, set one env var, and see their own wallet.

**Deferred (post-MVP):** NLP trade parsing, IL prediction models, fee auto-harvest (signing = custody risk — keep read-only until you decide), xyops plugin, Raydium direct quotes, multi-chain.

---

### Honest bottom line
The repo today is a **working math core wrapped in a non-importing service layer and fed by mock data**. The good news: the hard parts (formulas, webhook dispatch, async plumbing, dashboard skeleton) are already correct in isolation, the codebase is small enough to fix in days not months, and Phase 0 alone converts ~1,450 LOC of dead code into living code.
