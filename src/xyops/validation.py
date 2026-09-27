"""Validation for plugin manifest and configuration."""

import json
import os
import re


def validate_plugin_manifest(manifest_path):
    """Validate the plugin manifest structure."""
    try:
        with open(manifest_path) as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Failed to load manifest: {e}"
    # Check required fields
    if "name" not in data:
        return False, "Missing 'name' field"
    if "xyOps" not in data:
        return False, "Missing 'xyOps' field"
    xyops = data["xyOps"]
    if "defaultView" not in xyops:
        return False, "Missing 'defaultView' field"
    if "headerTitle" not in xyops:
        return False, "Missing 'headerTitle' field"
    if "scripts" not in xyops:
        return False, "Missing 'scripts' field"
    # Validate types
    if not isinstance(data["name"], str):
        return False, "'name' must be a string"
    if not isinstance(xyops["defaultView"], bool):
        return False, "'defaultView' must be a boolean"
    if not isinstance(xyops["headerTitle"], str):
        return False, "'headerTitle' must be a string"
    if not isinstance(xyops["scripts"], dict):
        return False, "'scripts' must be a dictionary"
    # Check that required scripts are present
    required_scripts = ["analytics", "trade"]
    for script in required_scripts:
        if script not in xyops["scripts"]:
            return False, f"Missing required script: {script}"
    return True, "Manifest is valid"


def validate_plugin_config(config):
    """Validate plugin configuration."""
    # This is a simple example; actual validation would be more comprehensive
    if not hasattr(config, "solana_rpc_endpoint") or not config.solana_rpc_endpoint:
        return False, "solana_rpc_endpoint is required"
    if not hasattr(config, "solana_owner") or not config.solana_owner:
        return False, "solana_owner is required"
    return True, "Configuration is valid"
