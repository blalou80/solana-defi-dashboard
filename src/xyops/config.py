"""Configuration loading for xyOps plugin."""
import os

from src.config import load_config as load_dashboard_config


def load_plugin_config():
    """Load plugin-specific configuration, falling back to dashboard config."""
    config = load_dashboard_config()
    # Override with environment variables if present
    config.solana_rpc_endpoint = os.environ.get("SOLANA_RPC_ENDPOINT", config.solana_rpc_endpoint)
    config.solana_owner = os.environ.get("SOLANA_OWNER", config.solana_owner)
    return config
