# Solana DeFi Analytics & Risk Management Dashboard

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Streamlit](https://img.shields.io/badge/dashboard-streamlit-FF4B4B.svg)](https://streamlit.io/)

A production-ready Python toolkit for real-time DeFi analytics and risk management on Solana, featuring live slippage analysis, concentrated liquidity monitoring, and an interactive Streamlit dashboard.

## ✨ Features

- **Real-Time Slippage Engine**: Fetch live quotes from Jupiter Aggregator, compare swap routes, and compute expected vs. realized slippage with price impact analysis.
- **Concentrated Liquidity Monitor**: Track Orca Whirlpool and Raydium CL positions, calculate impermanent loss, trading fees, and net yield with out-of-range alerts.
- **Risk Dashboard**: Interactive UI showing portfolio value, token exposure, VaR, Sharpe ratio, and automated alerts via Telegram/Discord.
- **Async-First Architecture**: Built with `asyncio` and `aiohttp` for high-performance, non-blocking API calls.
- **Modular & Extensible**: Clean separation of concerns with well-defined interfaces between data engines, risk calculations, and presentation layer.
- **Offline Simulation Mode**: Includes deterministic mock data generators for development and testing without RPC dependencies.

## 📊 DeFi Calculation Capabilities

### Impermanent Loss (IL)
```python
def compute_impermanent_loss(price_current: float, price_entry: float) -> float:
    """Compute impermanent loss percentage."""
    if price_entry == 0:
        return 0.0
    ratio = price_current / price_entry
    il = 2 * math.sqrt(ratio) / (1 + ratio) - 1
    return abs(il) * 100  # as percentage
```

### Slippage Analysis
- Fetches route data from Jupiter API v6
- Computes price impact percentage and slippage basis points
- Compares multiple routes for optimal execution
- Tracks realized slippage from on-chain transaction receipts

### Yield Calculations
```python
def compute_net_yield(fees_earned: float, impermanent_loss: float, liquidity: float, time_days: float = 30) -> float:
    """Compute net yield annualized percentage."""
    if liquidity == 0 or time_days == 0:
        return 0.0
    net = fees_earned - impermanent_loss
    annualized = (net / liquidity) * (365 / time_days) * 100
    return annualized
```

## 🏗️ Architecture

```mermaid
graph TD
    A[Solana RPC] --> B[Engines Layer]
    C[Jupiter API] --> B
    D[Orca/Raydium Programs] --> B
    B --> E[Risk Metrics Engine]
    B --> F[Shared State (In-Memory)]
    E --> G[Alerting System]
    F --> H[Streamlit Dashboard]
    G --> H
```

### Layers
1. **Data Ingestion Layer** (`src/engines/`)
   - Jupiter API client for swap quotes and route analysis
   - Solana RPC clients for position and transaction data
   - Protocol-specific parsers for Orca Whirlpools and Raydium CLMM

2. **Core Logic Layer**
   - `src/engines/liquidity.py`: Position tracking, IL, fee calculations
   - `src/engines/slippage.py`: Route comparison and slippage metrics
   - `src/risk/metrics.py`: Portfolio risk (VaR, Sharpe, diversification)
   - `src/risk/alerts.py`: Notification dispatch (Telegram, Discord, email)

3. **State Management** (`src/state.py`)
   - Thread-safe in-memory store for positions, trades, and portfolio state
   - Singleton pattern with update functions from background tasks

4. **Presentation Layer** (`src/dashboard/`)
   - Main Streamlit application (`app.py`)
   - Modular pages for different views (Trades, Positions, Analytics)
   - Real-time charts with Plotly and native Streamlit components

5. **Configuration & Utilities**
   - `src/config.py`: YAML-based configuration with environment overrides
   - `src/utils.py`: Logging configuration, retry decorators, async helpers
   - `src/models.py`: Pydantic data models for type safety and validation

## 📈 Test Coverage

The project includes a comprehensive test suite:
- **Unit Tests**: Testing calculation functions in isolation (IL, slippage, yield)
- **Integration Tests**: Testing engine interactions with mocked external APIs
- **Contract Tests**: Validating API response schemas against real endpoints
- **End-to-End Tests**: Simulating full data flow from API to dashboard display

Run tests with:
```bash
pytest tests/ -v
```

Current coverage: ~85% (calculations and core logic fully tested)

## 🚀 Step-by-Step Setup Guide

### Prerequisites
- Python 3.11 or higher
- Git (for version control)
- Solana RPC endpoint (public endpoints work, but dedicated RPC like Helius or QuickNode recommended for production)
- (Optional) Telegram Bot token or Discord Webhook URL for alerts

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/solana-defi-dashboard.git
cd solana-defi-dashboard
```

### 2. Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure the Application
```bash
# Copy example configuration files
cp .config.yaml.example .config.yaml
cp .env.example .env

# Edit .config.yaml to set your RPC endpoint and preferred assets
# Edit .env to add alerting credentials (Telegram bot token, Discord webhook, etc.)
```

### 5. Launch the Application
#### Option A: Development Mode (Recommended for testing)
```bash
# Start the background data updater in one terminal
python -m src.main --daemon

# In another terminal, launch the Streamlit dashboard
streamlit run src/dashboard/app.py
```

#### Option B: Production Deployment
```bash
# Run both services with a process manager like systemd, supervisord, or Docker
# See DEPLOYMENT.md for detailed instructions
```

### 6. Access the Dashboard
Open your web browser and navigate to:
```
http://localhost:8501
```

## � kml Configuration Files

### `.config.yaml`
```yaml
rpc_endpoint: "https://api.mainnet-beta.solana.com"  # or your Helius/QuickNode endpoint
polling_interval_sec: 15                            # How often to update positions
risk_window_days: 30                                # Lookback period for risk metrics
portfolio_assets:                                   # Tokens to track in portfolio
  - "SOL"
  - "USDC"
  - "RAY"
  - "ORCA"
alert_channels:                                     # Enable/disable alert channels
  telegram: false
  email: false
  discord: false
```

### `.env`
```env
# Telegram Alerts (optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Discord Alerts (optional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Email Alerts (optional - requires SMTP configuration)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
ALERT_FROM=your_email@gmail.com
ALERT_TO=recipient@example.com
```

## 🐳 Docker Deployment

A Dockerfile is provided for containerized deployment:

```bash
# Build the image
docker build -t solana-defi-dashboard .

# Run with docker-compose (recommended)
docker-compose up -d

# Or run directly
docker run -p 8501:8501 --name defi-dashboard solana-defi-dashboard
```

See `Dockerfile` and `docker-compose.yml` for details.

## 📚 API Reference

Generated API documentation is available in the `docs/` directory or can be built with:
```bash
pip install -r docs/requirements.txt
mkdocs serve
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing-feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please make sure to update tests as appropriate and follow the existing code style.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Jupiter Aggregator](https://jup.ag/) for their powerful swap API
- [Orca](https://www.orca.so/) and [Raydium](https://raydium.io/) for concentrated liquidity protocols
- [Streamlit](https://streamlit.io/) for the incredible dashboard framework
- The Solana developer community for excellent documentation and tooling