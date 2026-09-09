import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from dotenv import load_dotenv

@dataclass
class Config:
    rpc_endpoint: str
    polling_interval_sec: int
    risk_window_days: int
    portfolio_assets: List[str]
    alert_channels: Dict[str, bool]

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

    return Config(
        rpc_endpoint=rpc_endpoint,
        polling_interval_sec=polling_interval_sec,
        risk_window_days=risk_window_days,
        portfolio_assets=portfolio_assets,
        alert_channels=alert_channels
    )