import pytest
import pandas as pd
from src.engines.slippage import compute_slippage_metrics, natural_to_smallest

def test_natural_to_smallest():
    assert natural_to_smallest(1.0, "So11111111111111111111111111111111111111112") == 1000000000
    assert natural_to_smallest(0.5, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") == 500000

def test_compute_slippage_metrics_empty():
    df = compute_slippage_metrics({})
    assert df.empty
    df = compute_slippage_metrics({"routes": []})
    assert df.empty

def test_compute_slippage_metrics_sample():
    data = {
        "routes": [
            {
                "marketInfos": [{"amm": "Jupiter"}],
                "priceImpactPct": 0.5,
                "slippageBps": 10,
                "fillProbability": 0.95,
                "outAmount": "1000"
            }
        ]
    }
    df = compute_slippage_metrics(data)
    assert not df.empty
    assert df.iloc[0]['route'] == 'Jupiter'
    assert df.iloc[0]['price_impact_pct'] == 0.5
    assert df.iloc[0]['slippage_est'] == 0.1  # 10 bps = 0.1%
    assert df.iloc[0]['fill_probability'] == 0.95