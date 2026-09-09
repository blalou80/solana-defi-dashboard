# Interface Contracts

This document defines the external interfaces that the system exposes to users or other systems.

## 1. Jupiter API Client

**Purpose**: Fetch swap quotes and route data.

**Contract**:
- **Method**: `async def get_quote(token_in: str, token_out: str, amount: float) -> QuoteResponse`
- **Input**: Token mint addresses, amount in natural units.
- **Output**: `QuoteResponse` containing routes, price impact, slippage estimate, fill probability.
- **Error Handling**: Raises `JupiterAPIError` on failure; retries up to 3 times with backoff.

**Endpoint**: `https://quote-api.jup.ag/v6/quote?inputMint={token_in}&outputMint={token_out}&amount={amount}`

## 2. Solana RPC Client

**Purpose**: Fetch on-chain account data and transaction receipts.

**Contract**:
- **Method**: `async def get_account_info(account: str) -> AccountInfo`
- **Method**: `async def get_transaction(tx_hash: str) -> TransactionReceipt`
- **Input**: Account address or transaction hash.
- **Output**: Parsed account data (e.g., Whirlpool position) or receipt details.
- **Error Handling**: Retry on timeout; fallback to backup RPC if configured.

## 3. Alert Webhook Client

**Purpose**: Send notifications to Telegram/Discord.

**Contract**:
- **Method**: `async def send_alert(message: str, channel: str) -> bool`
- **Input**: Alert message content, channel name ("telegram" or "discord").
- **Output**: Boolean indicating success.
- **Behavior**: Formats message per platform API; uses configured webhook URLs from `.env`.

**Endpoints**:
- Telegram: `https://api.telegram.org/bot<TOKEN>/sendMessage`
- Discord: webhook URL provided by user.

## 4. Configuration Loader

**Purpose**: Read and validate config files.

**Contract**:
- **Method**: `load_config() -> Config`
- **Input**: None (reads from `.config.yaml` and `.env`).
- **Output**: `Config` object with all fields populated.
- **Validation**: Ensures required fields (RPC endpoint, polling interval) are present and valid.

## 5. Streamlit Dashboard

**Purpose**: Provide UI for portfolio monitoring and risk metrics.

**Contract**:
- **Page**: `/dashboard` (default)
- **Data Sources**: Reads from in-memory state updated by background tasks.
- **Interactions**: Buttons to refresh, set alerts, configure settings.
- **Output**: Displays charts (token exposure, VaR gauge), tables (positions), and alert logs.

All contracts are technology-agnostic and define clear input/output behaviors.