# Feature Specification: Solana DeFi Analytics & Risk Management

**Feature Branch**: `001-defi-analytics-risk`

**Created**: 2026-09-09

**Status**: Draft

**Input**: User description: "Build a production-ready Python DeFi Analytics and Risk Management Tool designed for Solana liquidity venues (Jupiter Aggregator, Orca Whirlpools, Raydium). The application must include the following modules: 1. Real-Time Execution & Slippage Engine: Fetch live trade and route data via Jupiter REST APIs / RPC nodes. Calculate price impact, expected vs. realized slippage, and execution fill quality across different AMM routing pathways. Output structured comparison metrics using Pandas and NumPy. 2. Concentrated Liquidity & PnL Monitor: Track active concentrated liquidity positions (tick ranges) on Orca Whirlpools / Uniswap-style protocols. Calculate real-time impermanent loss (IL), earned trading fees, and net position yield. Implement boundary check triggers that flag when positions drift out-of-range. 3. Inventory & Risk Dashboard: Build an interactive Streamlit UI displaying real-time total portfolio value, token exposure metrics, and dynamic drawdown risk (Value at Risk / Sharpe ratio calculations). Integrate an automated webhook/alert system (Telegram or Discord API) for automated stop-loss and anomaly risk notifications."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real-Time Slippage Analysis (Priority: P1)

A DeFi trader wants to compare expected vs. actual execution quality across multiple Solana DEX routes before placing a trade. They input a token pair and trade size; the system fetches live quotes from Jupiter, computes price impact and estimated slippage, then monitors the actual fill once the trade executes, reporting the delta.

**Why this priority**: Slippage is the primary cost for any trade; accurate pre-trade estimates and post-trade analysis are essential for profitable trading. This is the core value proposition.

**Independent Test**: Can be tested by simulating a trade against Jupiter's quote API and verifying that the system correctly calculates price impact and compares it to the realized slippage from a mock transaction receipt.

**Acceptance Scenarios**:

1. **Given** a user specifies a token pair (e.g., SOL/USDC) and a trade size (e.g., 10 SOL), **When** they request a quote, **Then** the system returns the expected price impact, estimated slippage, and the best route(s) with their fill probabilities.
2. **Given** a trade is executed through Jupiter, **When** the system receives the transaction confirmation, **Then** it calculates the realized slippage and compares it to the pre‑trade estimate, highlighting any deviation.
3. **Given** multiple routes are available, **When** the user requests a comparison, **Then** the system presents a tabular comparison (using Pandas) showing each route's price impact, estimated slippage, and expected fill quality.

---

### User Story 2 - Concentrated Liquidity Position Monitoring (Priority: P2)

A liquidity provider (LP) who has deposited into Orca Whirlpools wants to monitor their positions in real time. They need to see current tick range, accumulated fees, impermanent loss, and net yield. They also want alerts when their position goes out of range.

**Why this priority**: CL positions require active management; missing the range can lead to significant IL and lost fee revenue. This feature helps LPs optimize their positions.

**Independent Test**: Can be tested by connecting to a known Orca Whirlpool position and verifying that the system correctly calculates IL and fee accrual based on historical price data.

**Acceptance Scenarios**:

1. **Given** a user provides their Orca Whirlpool position ID, **When** the system fetches current price and tick data, **Then** it displays the current tick range, distance to boundary, and accumulated fees.
2. **Given** price moves such that the position becomes out-of-range, **When** the system detects the change, **Then** it triggers a boundary alert (via the notification system) and updates the PnL metrics.
3. **Given** a position is in-range for a period, **When** the user requests yield metrics, **Then** the system calculates the net yield (fees earned minus IL) and displays it as an annualized percentage.

---

### User Story 3 - Inventory & Risk Dashboard with Alerts (Priority: P3)

A portfolio manager wants a single pane of glass showing total value, token exposure, and risk metrics (VaR, Sharpe). They also want to set stop‑loss levels and receive anomaly alerts via their preferred messaging app.

**Why this priority**: This integrates the analytics into an actionable UI and notification system, enabling proactive risk management. It builds on the data from the first two stories.

**Independent Test**: Can be tested by loading mock portfolio data and verifying that the Streamlit dashboard renders correctly and that alerts are sent to a configured webhook.

**Acceptance Scenarios**:

1. **Given** the system has portfolio data (positions and balances), **When** the user opens the Streamlit dashboard, **Then** they see a summary of total value, token breakdown, and a risk gauge (VaR at 95% confidence).
2. **Given** a user configures a stop‑loss threshold for a specific token, **When** the price drops below that threshold, **Then** the system sends an alert via the configured webhook (Telegram or Discord) with details of the position and the current price.
3. **Given** the portfolio’s Sharpe ratio falls below a user‑defined minimum, **When** the system calculates the ratio, **Then** it triggers a notification advising the user to review their strategy.

---

### Edge Cases

- What happens when the Jupiter API is rate‑limited or unavailable? The system should fall back to cached data or a backup RPC and log the error.
- How does the system handle very large trade sizes that may cause significant price impact? It should calculate impact and warn if it exceeds a configurable threshold.
- What if a concentrated liquidity position is in multiple pools? The system should aggregate metrics across all positions.
- How are fees and IL calculated when the position has been partially harvested? The system should track cumulative fees and adjust the net yield accordingly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST fetch real‑time swap quotes and route data from Jupiter’s REST API for any Solana token pair.
- **FR-002**: System MUST compute price impact and estimated slippage for each route, outputting structured data (DataFrame) with columns: route, expected_price, price_impact_pct, slippage_est, fill_probability.
- **FR-003**: System MUST support retrieving on‑chain transaction receipts to calculate realized slippage for executed trades.
- **FR-004**: System MUST connect to Solana RPC nodes (public or user‑provided) to fetch current price and tick data for Orca Whirlpools and Raydium CL pools.
- **FR-005**: System MUST track active LP positions, including tick ranges, current price, and distance to boundaries.
- **FR-006**: System MUST calculate impermanent loss (IL) and accrued fees for each CL position, and compute net yield.
- **FR-007**: System MUST emit boundary‑out‑of‑range alerts when the price moves outside the position’s tick range.
- **FR-008**: System MUST provide a Streamlit dashboard that displays:
  - Total portfolio value in USD
  - Token exposure (percentage per token)
  - Value at Risk (VaR) at configurable confidence levels
  - Sharpe ratio for the portfolio over a configurable window
- **FR-009**: System MUST support webhook notifications to both Telegram and Discord via webhook URLs read from environment variables (`TELEGRAM_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`), loaded from a `.env` file at runtime.
- **FR-010**: System MUST allow users to set stop‑loss thresholds per token and trigger alerts when breached.
- **FR-011**: System MUST persist configuration (RPC endpoints, alert channels, portfolio assets) in a local config file (e.g., YAML or JSON).
- **FR-012**: System MUST handle API failures gracefully with retries and logging; error states should be communicated to the user via the dashboard.

### Key Entities

- **Trade**: Represents a swap transaction, including token pair, size, route, expected price, realized price, slippage, and timestamp.
- **Liquidity Position**: Represents a concentrated liquidity position in a pool, including pool ID, tick lower, tick upper, current tick, liquidity amount, fees earned, and impermanent loss.
- **Portfolio**: Aggregates all positions and token balances; includes total value, exposure percentages, and risk metrics.
- **Alert**: Defines a notification rule (type: stop‑loss, boundary, anomaly) with a threshold, channel, and message template.
- **Config**: Stores user preferences: RPC endpoints, alert channels, update intervals, and risk parameters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can obtain a slippage estimate for a trade in under 2 seconds from the time the request is submitted.
- **SC-002**: The system processes and updates portfolio metrics (value, risk) within 5 seconds of receiving new on‑chain data (assuming normal RPC latency).
- **SC-003**: Boundary alerts are triggered within 10 seconds of the price crossing the threshold.
- **SC-004**: The Streamlit dashboard loads and displays the full portfolio summary within 3 seconds of page load.
- **SC-005**: 90% of trade execution comparisons show a realized slippage within 10% of the pre‑trade estimate.
- **SC-006**: The system can monitor at least 10 distinct LP positions simultaneously without performance degradation.

## Assumptions

- The user has a Solana wallet and can sign transactions; the tool does not manage private keys but can accept a keypair path for read‑only access.
- A default public RPC endpoint (Helius free tier) is used unless the user provides a custom one; rate limits are respected. Users can override via config or `.env`.
- Data polling interval defaults to 15 seconds and is configurable.
- The tool is intended for individual traders and small funds; horizontal scaling is not required for v1.
- All data is stored locally; no cloud database is used.
- The user has Python 3.11+ and a functional Streamlit environment.
- The tool will be open‑source and available under an MIT license.
- Time intervals for risk calculations (e.g., VaR) default to 30 days but are configurable.
- Configuration (RPC endpoints, alert channels, polling interval) is stored in a local config file (YAML/JSON) and a `.env` file for secrets (webhook URLs).

## Clarifications Resolved

- **Q1**: Alert system supports both Telegram and Discord via environment variables (`TELEGRAM_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`) loaded from a `.env` file. Users may configure one or both channels.
- **Q2**: Data polling interval defaults to 15 seconds and is configurable via the config file to balance timeliness with public RPC rate limits.
- **Q3**: RPC endpoint defaults to a public Helius/Solana Mainnet endpoint, with user override available via config or `.env`.