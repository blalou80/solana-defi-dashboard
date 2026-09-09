# Research: Solana DeFi Analytics & Risk Management

**Date**: 2026-09-09  
**Context**: Technical decisions for building a production-ready tool on Solana with Jupiter, Orca, Raydium, and Streamlit.

## 1. Async HTTP Client

**Decision**: Use `aiohttp` for all HTTP requests (Jupiter API, webhook delivery, RPC fallbacks).  
**Rationale**: Native async support, well-maintained, widely adopted in async Python ecosystem.  
**Alternatives**: `httpx` with async support; both are viable but `aiohttp` is more common in Solana tooling (e.g., `solana-py` uses it internally). We'll use `aiohttp.ClientSession` with connection pooling and retry logic.

## 2. Solana RPC Client

**Decision**: Use `solana-py` (official Python SDK) with async support, backed by `aiohttp`.  
**Rationale**: Provides high-level APIs for fetching account data, transaction receipts, and subscribing to logs. It supports custom RPC endpoints (Helius, QuickNode, etc.).  
**Alternatives**: `solders` (low-level bindings) or direct HTTP requests to RPC; `solana-py` offers a good balance of abstraction and control. We'll also use `anchorpy` if interacting with Orca/Raydium program IDs.

## 3. Jupiter API Integration

**Decision**: Use the Jupiter v6 REST API endpoints for quote and swap.  
**Rationale**: Official, well-documented, returns route data including price impact and slippage estimates. We'll use `aiohttp` to fetch quotes asynchronously.  
**Pattern**: Request quote, parse JSON into Pandas DataFrame for comparison. Cache quotes briefly to avoid duplicate calls.

## 4. Data Processing

**Decision**: Use Pandas for tabular data (route comparison, portfolio summaries) and NumPy for risk calculations (VaR, Sharpe).  
**Rationale**: Standard tools for data analysis; efficient vectorized operations. Pandas DataFrames can be directly displayed in Streamlit.  
**Alternatives**: Polars (faster) but Pandas is more familiar and sufficient for v1.

## 5. Configuration & Secrets

**Decision**: Use YAML for config (`.config.yaml`) and `.env` for secrets (webhook URLs).  
**Rationale**: YAML is human-readable and supports nested structures (RPC endpoints, alert channels, polling intervals). `.env` is standard for secrets and can be loaded with `python-dotenv`.  
**Alternatives**: JSON (less readable), TOML (less common). We'll keep both files in the project root; user can override via environment variables.

## 6. Alert System

**Decision**: Implement webhook delivery using `aiohttp` to both Telegram and Discord as configured.  
**Rationale**: Both platforms support webhook URLs; we'll format messages according to their APIs (Telegram: `sendMessage`, Discord: `send`).  
**Rate Limiting**: Respect platform rate limits; implement exponential backoff on failure.

## 7. Dashboard Framework

**Decision**: Use Streamlit for the interactive UI.  
**Rationale**: Rapid development, built-in reactivity, easy to integrate Pandas and Matplotlib.  
**Alternatives**: Dash, Flask+React. Streamlit is lighter and aligns with the tool's scope.

## 8. Polling Strategy

**Decision**: Poll RPC every 15 seconds (configurable) via an asyncio task that updates a shared state.  
**Rationale**: Balances timeliness with public RPC rate limits (Helius free tier allows ~1 req/s). 15 seconds is acceptable for LP monitoring and risk metrics.  
**Implementation**: Use `asyncio.create_task` with `asyncio.sleep(interval)` loop; update shared data structures; Streamlit will read from them.

## 9. Testing

**Decision**: Use `pytest` with `pytest-asyncio` for async tests.  
**Rationale**: Industry standard; supports async fixtures and test isolation.  
**Strategy**: Unit tests for logic (e.g., slippage calculation, risk metrics), integration tests against mock APIs (using `pytest-aiohttp` or `responses`), contract tests to ensure API compatibility.

## 10. Logging

**Decision**: Use Python `logging` with structured logs (JSON format optionally) and output to stdout.  
**Rationale**: Standard library; easy to capture errors and debug. Add log rotation for long-running instances.

## 11. Error Handling

**Decision**: Implement retries with exponential backoff for transient failures (API timeouts, rate limits). For permanent failures, log and notify user via dashboard.  
**Rationale**: Production readiness; prevents cascading failures.

All decisions are documented; no unknowns remain.