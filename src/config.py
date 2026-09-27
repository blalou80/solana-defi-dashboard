"""Configuration management for the Solana DeFi Analytics Tool."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml
from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration."""
    rpc_endpoint: str
    polling_interval_sec: int
    risk_window_days: int
    portfolio_assets: List[str]
    alert_channels: Dict[str, bool]
    # Wallets the daemon polls for real balances (public keys, read-only).
    wallet_addresses: List[str] = field(default_factory=list)
    alert_cooldown_minutes: int = 30
    # Alert definitions, e.g. [{type: stop_loss, symbol: SOL, threshold: 100,
    # channel: telegram, enabled: true}].
    alerts: List[Dict] = field(default_factory=list)
    # SQLite file shared between daemon and dashboard.
    db_path: Optional[str] = None
    # Enhanced features configuration
    nlp_model: str = "en_core_web_sm"
    il_prediction_model: str = "random_forest"
    api_rate_limit_per_sec: float = 5.0
    cache_ttl_sec: int = 30
    simulation_enabled: bool = True
    ai_insights_enabled: bool = True


def load_config(config_path: str = ".config.yaml", env_path: str = ".env") -> Config:
    """Load configuration from YAML and environment variables."""
    # Load .env
    load_dotenv(env_path)

    # Load YAML
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)

    # Required fields
    rpc_endpoint = data.get('rpc_endpoint')
    if not rpc_endpoint:
        raise ValueError("rpc_endpoint is required in config")
    polling_interval_sec = data.get('polling_interval_sec', 15)
    risk_window_days = data.get('risk_window_days', 30)
    portfolio_assets = data.get('portfolio_assets', [])
    alert_channels = data.get('alert_channels', {})
    wallet_addresses = data.get('wallet_addresses', [])
    db_path = data.get('db_path')
    alerts = data.get('alerts', [])
    alert_cooldown_minutes = data.get('alert_cooldown_minutes', 30)

    # Enhanced features with defaults
    nlp_model = data.get('nlp_model', 'en_core_web_sm')
    il_prediction_model = data.get('il_prediction_model', 'random_forest')
    api_rate_limit_per_sec = data.get('api_rate_limit_per_sec', 5.0)
    cache_ttl_sec = data.get('cache_ttl_sec', 30)
    simulation_enabled = data.get('simulation_enabled', True)
    ai_insights_enabled = data.get('ai_insights_enabled', True)

    return Config(
        rpc_endpoint=rpc_endpoint,
        polling_interval_sec=polling_interval_sec,
        risk_window_days=risk_window_days,
        portfolio_assets=portfolio_assets,
        alert_channels=alert_channels,
        wallet_addresses=wallet_addresses,
        db_path=db_path,
        alerts=alerts,
        alert_cooldown_minutes=alert_cooldown_minutes,
        nlp_model=nlp_model,
        il_prediction_model=il_prediction_model,
        api_rate_limit_per_sec=api_rate_limit_per_sec,
        cache_ttl_sec=cache_ttl_sec,
        simulation_enabled=simulation_enabled,
        ai_insights_enabled=ai_insights_enabled
    )


def save_config(config: Config, config_path: str = ".config.yaml") -> None:
    """Save configuration to YAML file."""
    config_dict = {
        'rpc_endpoint': config.rpc_endpoint,
        'polling_interval_sec': config.polling_interval_sec,
        'risk_window_days': config.risk_window_days,
        'portfolio_assets': config.portfolio_assets,
        'alert_channels': config.alert_channels,
        'wallet_addresses': config.wallet_addresses,
        'db_path': config.db_path,
        'alerts': config.alerts,
        'alert_cooldown_minutes': config.alert_cooldown_minutes,
        'nlp_model': config.nlp_model,
        'il_prediction_model': config.il_prediction_model,
        'api_rate_limit_per_sec': config.api_rate_limit_per_sec,
        'cache_ttl_sec': config.cache_ttl_sec,
        'simulation_enabled': config.simulation_enabled,
        'ai_insights_enabled': config.ai_insights_enabled
    }

    with open(config_path, 'w') as f:
        yaml.dump(config_dict, f, default_flow_style=False)
