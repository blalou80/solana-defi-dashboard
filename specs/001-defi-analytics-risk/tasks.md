# Tasks: Solana DeFi Analytics & Risk Management

**Input**: Design documents from `/specs/001-defi-analytics-risk/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/README.md

**Tests**: Not explicitly requested — test tasks are omitted. Manual validation via quickstart.md scenarios is expected.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Includes exact file paths

## Path Conventions

Following plan.md: single project at repository root with `src/` and `tests/` directories.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure per plan.md: `src/engines/`, `src/dashboard/`, `src/risk/`, `src/dashboard/pages/`, `tests/unit/`, `tests/integration/`, `tests/contract/`
- [x] T002 Initialize Python virtual environment and create `requirements.txt` with dependencies: aiohttp, solana, pandas, numpy, streamlit, python-dotenv, pyyaml, pytest, pytest-asyncio
- [x] T003 [P] Create `.gitignore` for Python, virtual environment, config files with secrets
- [x] T004 [P] Create `pyproject.toml` or `setup.py` for project metadata and entry points (optional but recommended)
- [x] T005 Create default configuration file template: `.config.yaml.example` with rpc_endpoint, polling_interval_sec, risk_window_days, portfolio_assets, alert_channels
- [x] T006 [P] Create `.env.example` with TELEGRAM_WEBHOOK_URL and DISCORD_WEBHOOK_URL placeholders

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

⚠️ **CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Implement configuration loader in `src/config.py` that reads `.config.yaml` and `.env`, validates required fields, and returns a Config object (dataclass)
- [x] T008 [P] Implement logging setup in `src/utils.py` with structured logs (JSON optional), log rotation, and stdout output
- [x] T009 [P] Implement retry decorator/utility with exponential backoff in `src/utils.py`
- [x] T010 Define data models (dataclasses or Pydantic) in `src/models.py`: Trade, LiquidityPosition, Portfolio, Alert, Config (as per data-model.md)
- [x] T011 Implement shared state container (e.g., a dict or custom class) for in-memory data that will be updated by background tasks and read by Streamlit

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Real-Time Slippage Analysis (Priority: P1) 🎯 MVP

**Goal**: Provide real-time swap quotes and route comparisons from Jupiter API, and compute expected vs. realized slippage for executed trades.

**Independent Test**: Can be tested by simulating a trade against Jupiter's quote API and verifying price impact, slippage estimates, and route comparison table.

### Implementation for User Story 1

- [x] T012 [P] [US1] Implement Jupiter API client in `src/engines/slippage.py` with async `get_quote(token_in, token_out, amount)` method using aiohttp; parse JSON into structured data
- [x] T013 [P] [US1] Implement slippage calculation function in `src/engines/slippage.py` that computes price impact and estimated slippage from quote data; output Pandas DataFrame
- [x] T014 [US1] Implement `compare_routes()` in `src/engines/slippage.py` that takes token pair and amount, calls Jupiter, and returns DataFrame with route, expected_price, price_impact_pct, slippage_est, fill_probability
- [x] T015 [US1] Implement `realized_slippage()` in `src/engines/slippage.py` that fetches on-chain transaction receipt (using solana-py) and computes realized slippage vs. expected
- [x] T016 [US1] Add error handling and retries for Jupiter API calls in `src/engines/slippage.py`; log errors
- [x] T017 [US1] Create CLI entry point in `src/cli.py` (or separate module) to call `compare_routes` and output results to console (for testing)
- [x] T018 [US1] Integrate slippage analysis into Streamlit dashboard: add a page (e.g., `src/dashboard/pages/trade.py`) with input fields and display route comparison table (using st.dataframe)
- [x] T019 [US1] Ensure SC-001: slippage estimate under 2 seconds — add timing instrumentation if needed

**Checkpoint**: User Story 1 complete; trader can get quotes and compare routes via CLI or dashboard.

---

## Phase 4: User Story 2 - Concentrated Liquidity Position Monitoring (Priority: P2)

**Goal**: Track Orca Whirlpool and Raydium CL positions, calculate impermanent loss, fees, net yield, and trigger boundary-out-of-range alerts.

**Independent Test**: Connect to a known Orca Whirlpool position and verify IL/fee calculations and alert triggering.

### Implementation for User Story 2

- [x] T020 [P] [US2] Implement Solana RPC client in `src/engines/liquidity.py` using solana-py with async support; methods: `get_account_info`, `get_transaction`
- [x] T021 [P] [US2] Implement function to fetch position data from Orca Whirlpool (or Raydium CL) given pool ID and owner address; parse tick range and liquidity
- [x] T022 [US2] Implement IL calculation in `src/engines/liquidity.py`: compute impermanent loss from current price vs. entry price using tick math
- [x] T023 [US2] Implement fee accrual calculation in `src/engines/liquidity.py`: track fees earned from position data (depends on pool specifics)
- [x] T024 [US2] Implement net yield calculation: fees earned minus IL, annualized
- [x] T025 [US2] Implement boundary detection: compare current tick to tick_lower/tick_upper; if out-of-range, trigger alert (store alert in state)
- [x] T026 [US2] Create background task (async loop) that polls RPC every `polling_interval_sec` seconds, updates in-memory positions, computes metrics, and checks boundaries
- [x] T027 [US2] Add integration with shared state to update portfolio data (total value, exposures) based on positions
- [x] T028 [US2] [P] Add boundary alert integration: when out-of-range, call alert system (to be implemented in US3) or store alert for later dispatch
- [x] T029 [US2] Ensure SC-002 and SC-006: portfolio metrics update within 5 seconds; supports at least 10 positions

**Checkpoint**: User Story 2 complete; LP positions are tracked with real-time metrics and boundary alerts.

---

## Phase 5: User Story 3 - Inventory & Risk Dashboard with Alerts (Priority: P3)

**Goal**: Provide Streamlit dashboard with total portfolio value, token exposure, VaR, Sharpe ratio, and configure/trigger alerts via Telegram/Discord.

**Independent Test**: Load mock portfolio data and verify dashboard renders correctly; send test alert to configured webhook.

### Implementation for User Story 3

- [x] T030 [P] [US3] Implement risk metrics in `src/risk/metrics.py`: VaR (historical simulation or parametric), Sharpe ratio; use NumPy
- [x] T031 [P] [US3] Implement alert system in `src/risk/alerts.py`: async function `send_alert(message, channel)` that uses aiohttp to POST to webhook URLs from .env; format for Telegram and Discord
- [x] T032 [US3] Build main Streamlit app in `src/dashboard/app.py`: setup layout with sidebar for config, main area for portfolio summary (total value, exposure pie chart, VaR gauge, Sharpe)
- [x] T033 [US3] Create dashboard page for positions: display list of tracked positions with tick range, IL, fees, yield (reuse data from US2)
- [x] T034 [US3] Create dashboard page for alerts configuration: allow user to set stop-loss thresholds per token, enable/disable alert channels, and view alert history
- [x] T035 [US3] Integrate risk metrics into dashboard: compute VaR and Sharpe from portfolio data (using historical price data from RPC or cache)
- [x] T036 [US3] Implement alert trigger logic: periodically check thresholds (stop-loss, boundary) and call `send_alert` when breached
- [x] T037 [US3] Ensure SC-003 and SC-004: alerts triggered within 10 seconds; dashboard loads within 3 seconds
- [x] T038 [US3] Add background task to update portfolio metrics (total value, exposures) from positions and token prices; update shared state

**Checkpoint**: All user stories functional; full dashboard with risk metrics and alerts.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T039 [P] Update project README.md with setup instructions, architecture overview, and usage examples (based on quickstart.md)
- [x] T040 [P] Validate quickstart.md scenarios: run through setup, slippage analysis, LP monitoring, alert trigger, portfolio risk metrics (ensure they work)
- [x] T041 [P] Add docstrings and type hints to all public functions and classes
- [x] T042 Review error handling and logging across all modules; ensure consistent
- [x] T043 [P] Add unit tests for critical logic (optional, but if included, place in `tests/unit/`)
- [x] T044 Perform performance tuning: check that SC-001, SC-002, SC-003, SC-004, SC-006 are met; adjust polling interval or caching if needed
- [x] T045 Update `.config.yaml.example` and `.env.example` with comments for all fields

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can proceed in priority order (US1 → US2 → US3) or in parallel if team capacity allows
  - US2 depends on US1? Not directly; they are independent, but US3 may consume data from both.
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) — May integrate with US1 for token prices, but should be independently testable (can use its own RPC data)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) — Depends on data from US1 (trade history, slippage) and US2 (positions) for full dashboard, but can work with mock data initially.

### Within Each User Story

- Models (T010) are done in Foundational, so story tasks start with client implementations
- Services/engines before integration into dashboard/CLI
- Alerts and dashboard integration at end of each story

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (T008, T009)
- Within US1: T012 and T013 can run in parallel; T017 and T018 can run in parallel after T014
- Within US2: T020 and T021 can run in parallel; T028 can be done alongside T027
- Within US3: T030 and T031 can run in parallel; T032, T033, T034 can be done in parallel after T030/T031
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch Jupiter client and slippage calculation together:
Task T012: "Implement Jupiter API client in src/engines/slippage.py"
Task T013: "Implement slippage calculation function in src/engines/slippage.py"

# After T014 is done, launch CLI and dashboard integration together:
Task T017: "Create CLI entry point in src/cli.py"
Task T018: "Integrate slippage analysis into Streamlit dashboard"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test slippage analysis via CLI and dashboard
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (LP monitoring added)
4. Add User Story 3 → Test independently → Deploy/Demo (full dashboard + alerts)
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3 (starting with risk metrics and dashboard scaffolding)
3. Stories complete and integrate independently (US3 may need to wait for US1/US2 data, but can mock initially)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- All paths relative to repository root; adjust if using different structure