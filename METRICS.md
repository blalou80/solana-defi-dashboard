# Ground Truth — every metric the product displays

Phase 0 fix #7. Each value rendered by the CLI, daemon, or dashboard must
appear in this table. If a source cannot answer, the product shows an
explicit *unavailable* state — it never interpolates, seeds, or fabricates.

| Metric | Source | Refresh | Calculation | Unavailable state |
|---|---|---|---|---|
| Native SOL balance | Solana RPC `getBalance` (configured `rpc_endpoint`) | every daemon tick (`polling_interval_sec`, default 15s) | `value / 10^9` | fetch error → previous snapshot stands, error logged |
| SPL token balances (**all** tokens) | Solana RPC `getTokenAccountsByOwner` by programId (Token + Token-2022), jsonParsed | every tick | sum of `tokenAmount.uiAmount` grouped by mint; decimals taken from the account itself; zero/absent tokens omitted | same as above |
| Token symbol / name | Metaplex metadata PDA via RPC `getAccountInfo` (raw account bytes, V1 layout), cached in `token_meta` (TTL 30d) | on first sight of a mint, then cached | borsh string parse (name, symbol); SOL is a documented protocol constant | unresolvable → symbol NULL, UI renders mint prefix; never a guessed ticker |
| USD price per mint | Jupiter Price API v3 (`lite-api.jup.ag/price/v3`) | every tick, batched per snapshot | `usdPrice` field per mint | mint missing from response → `usd_price = NULL`, row excluded from totals |
| Total portfolio value (USD) | stored snapshot (`portfolio_snapshots.total_value_usd`) | per tick | Σ of `usd_value` over *priced* balances only | `0.0` with unpriced rows visible in `token_balances` |
| Token exposure breakdown | `token_balances` of latest snapshot | per tick | Σ `usd_value` grouped by symbol | rows with NULL price excluded |
| VaR (95%) | snapshot value history | per tick after ≥ 20 snapshots | historical simulation: 5th percentile of period returns × latest total value (`risk/metrics.calculate_var`) | `None` → dashboard shows "unavailable" + snapshot count |
| Sharpe ratio | snapshot value history | per tick after ≥ 5 snapshots | (mean − 0.02) / std of period returns (`calculate_sharpe_ratio`) | `None` → "unavailable" |
| Swap quote (expected price, price impact, slippage bps) | Jupiter Swap API v1 (`lite-api.jup.ag/swap/v1/quote`) | on demand (CLI `quote`, dashboard Trade page) | `outAmount/inAmount` adjusted for known decimals; `priceImpactPct × 100`; `slippageBps / 100` | API error → exception surfaced in UI; unknown decimals → price `"unavailable"` |
| Route table (per swap step) | same quote response `routePlan` | on demand | one row per step: AMM `label`, `percent` | empty `routePlan` → empty table, "No routes found." |
| `fill_probability`, `volatility_estimate`, `gas_estimate` | **no source exists** | — | never invented: `None` / `0.0` = "not measured" | always shown as not measured |
| Realized slippage | on-chain tx receipt vs recorded expectation | on demand, after a trade is recorded | `(expected − realized) / expected × 100` (`engines/slippage.realized_slippage`) | no realized amount → `None`, warning logged |
| Position range status | `positions` table — Orca v2 API (`/v2/solana/positions/list?provider=`) enriched with each pool's live `tickCurrentIndex` (`/v2/solana/pools/{addr}`); each row carries the polled `wallet` (S4) | per daemon tick | `tick_lower ≤ current_tick ≤ tick_upper` | positions lacking real ticks are dropped and logged, never stored with invented bounds; empty table → page states "no positions yet" |
| Realized slippage (from receipt) | Solana RPC `getTransaction` (jsonParsed) pre/postTokenBalances for the owner | on demand per tx signature | received mint delta vs quoted expectation: `(expected − received) / expected × 100` | mint absent from receipt → `None` + warning |
| Position IL (since first observation) | stored tick history (`positions` table, 7-day window) | per tick after ≥ 2 observations | entry proxy = 1.0001^first_tick, current = 1.0001^latest_tick, classic constant-product IL | `None` → "unavailable"; proxy is explicitly NOT the true on-chain entry |
| Time out of range | out-of-range observations × polling interval | per tick | count(is_in_range=0) × polling_interval_sec | approximate, captioned as such |
| Alerts (stop-loss) | Jupiter Price v3 live price; rules from `alert_rules` table (dashboard) ∪ `.config.yaml`; **wallet scope**: a scoped stop_loss only fires while that wallet's latest snapshot holds the symbol (S4) | per tick | fires when real price ≤ configured threshold; each rule carries its own cooldown_min, enforced per (type, target); scoped rules use target `stop_loss:<wallet8>:<symbol>` | price fetch failed → alert *skipped* and logged to `alerts_log` as `stop_loss_skipped` — never checked against a mock price; unknown symbol → skipped |
| Quote log | `quotes` table — every Jupiter swap/v1 quote shown in CLI or Trade page; optional wallet attribution (S4) | on demand | raw inAmount/outAmount/priceImpactPct/slippageBps/routePlan labels persisted verbatim | logging failure never blocks the quote; warning surfaced |
| Realized slippage check | on-chain receipt (`getTransaction`) via Trade page form | on demand | received out-mint delta for the wallet vs user-entered expected amount | mint not moved in receipt → "Unavailable" with reason; nothing estimated |
| Alert delivery | Telegram/Discord webhook HTTP status | on fire | `delivered=1` only on 2xx; target recorded for cooldown/audit | env var missing → error logged, `delivered=0` |

## Removed in Phase 0 (previously displayed, never real)

- VaR/Sharpe from `np.random.seed(42)` fixed mock returns — `risk/metrics.py`
- Stop-loss evaluated against hardcoded price `100` — `risk/alerts.py`
- Fabricated Raydium/Orca quotes (invented prices/slippage that always won
  "best route" sorting) — `services/dex_aggregator.py`
- Mock Orca/Raydium liquidity positions — `engines/liquidity.py`
- Random-walk "monitoring" of position ticks/fees — `services/cl_position_service.py`
- Simulated fee harvesting (×0.8 of local fields + invented gas) — `services/fee_harvester.py`
- Wall-clock-jittered "transaction simulation" — `services/transaction_simulator.py`

## Storage & data flow

`daemon (src/main.py) → Solana RPC + Jupiter APIs → SQLite (.data/dashboard.db) → dashboard (Streamlit) / alerts / metrics`.
The SQLite file is the single source of truth shared across processes;
in-process `state.py` remains only for same-session dashboard scratch data
and is explicitly documented as process-local.
