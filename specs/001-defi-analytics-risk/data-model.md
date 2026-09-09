# Data Model: Solana DeFi Analytics & Risk Management

**Date**: 2026-09-09  
**Entities**: Defined from feature specification.

## Trade

Represents a swap transaction.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str (UUID) | Unique identifier |
| `token_in` | str | Input token mint address |
| `token_out` | str | Output token mint address |
| `amount_in` | float | Amount of token_in (in natural units) |
| `amount_out_expected` | float | Expected output amount from quote |
| `amount_out_realized` | float | Actual output amount from on-chain receipt |
| `route` | str | Route description (e.g., "Jupiter") |
| `price_impact_pct` | float | Price impact percentage |
| `slippage_estimated` | float | Estimated slippage percentage |
| `slippage_realized` | float | Realized slippage percentage (computed) |
| `timestamp` | datetime | When trade was executed |

## LiquidityPosition

Represents a concentrated liquidity position in a pool (Orca Whirlpool or Raydium CL).

| Field | Type | Description |
|-------|------|-------------|
| `id` | str (UUID) | Unique identifier |
| `pool_id` | str | Pool address (Orca/Raydium program) |
| `owner` | str | Wallet address of the LP |
| `tick_lower` | int | Lower tick index |
| `tick_upper` | int | Upper tick index |
| `current_tick` | int | Current tick price |
| `liquidity` | float | Amount of liquidity deposited |
| `fees_earned` | float | Cumulative fees earned (in USD or token) |
| `impermanent_loss` | float | IL amount (in USD) |
| `net_yield` | float | Fees earned minus IL (annualized %) |
| `last_updated` | datetime | When metrics were computed |

## Portfolio

Aggregates all positions and token balances for a user.

| Field | Type | Description |
|-------|------|-------------|
| `total_value_usd` | float | Total portfolio value in USD |
| `token_exposures` | Dict[str, float] | Mapping token -> value (USD) |
| `var_95` | float | Value at Risk at 95% confidence |
| `sharpe_ratio` | float | Sharpe ratio over configured window |
| `positions` | List[LiquidityPosition] | List of active LP positions |
| `last_updated` | datetime | When metrics were computed |

## Alert

Defines a notification rule.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str (UUID) | Unique identifier |
| `type` | str | "stop_loss", "boundary", "anomaly" |
| `threshold` | float | Trigger value (price, IL, etc.) |
| `channel` | str | "telegram" or "discord" |
| `message_template` | str | Template for alert message |
| `enabled` | bool | Whether rule is active |

## Config

User preferences stored locally.

| Field | Type | Description |
|-------|------|-------------|
| `rpc_endpoint` | str | Solana RPC URL (default Helius) |
| `polling_interval_sec` | int | Data update interval (default 15) |
| `alert_channels` | Dict[str, bool] | Which channels are enabled |
| `risk_window_days` | int | Days for VaR/Sharpe (default 30) |
| `portfolio_assets` | List[str] | Token mints to track |

**Relationships**:
- A `Portfolio` contains multiple `LiquidityPosition`s.
- `Alert` rules reference a `type` and `threshold`.
- `Config` is a singleton; loaded at startup and can be reloaded.

All fields are concrete and derived from FRs. No external dependencies.