import pytest

from src.engines.slippage import (
    compute_slippage_metrics,
    natural_to_smallest,
    parse_quote_for_trade,
)


def test_natural_to_smallest():
    assert natural_to_smallest(1.0, "So11111111111111111111111111111111111111112") == 1000000000
    assert natural_to_smallest(0.5, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") == 500000

def test_compute_slippage_metrics_empty():
    df = compute_slippage_metrics({})
    assert df.empty
    df = compute_slippage_metrics({"routePlan": []})
    assert df.empty

# Fixture shaped like a real Jupiter swap/v1 quote (captured 2026-09-27).
V1_QUOTE = {
    "inputMint": "So11111111111111111111111111111111111111112",
    "inAmount": "1000000000",
    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "outAmount": "122846032",
    "slippageBps": 50,
    "priceImpactPct": "0.000006205573194606019244711",
    "routePlan": [
        {
            "swapInfo": {
                "ammKey": "58bW57Cgf4UEk3sD3BDnchqrxjNCAofBTBqCkFAN1HKN",
                "label": "Meteora DLMM",
                "inputMint": "So11111111111111111111111111111111111111112",
                "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            },
            "percent": 100,
        }
    ],
}

def test_compute_slippage_metrics_v1_quote():
    df = compute_slippage_metrics(V1_QUOTE)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["route"] == "Meteora DLMM"
    # priceImpactPct is a fraction in v1 -> reported in percent
    assert row["price_impact_pct"] == pytest.approx(0.0006205573, rel=1e-6)
    assert row["slippage_est"] == pytest.approx(0.5)  # 50 bps = 0.5%
    # expected price is computed from real amounts: 122.846032 USDC / 1 SOL
    assert row["expected_price"] == pytest.approx(122.846032, rel=1e-6)
    # never fabricated: fill probability is not provided by the API
    assert row["fill_probability"] is None

def test_compute_slippage_metrics_unknown_decimals_gives_unavailable():
    quote = dict(V1_QUOTE)
    quote["inputMint"] = "UnknownMint111111111111111111111111111111"
    df = compute_slippage_metrics(quote)
    assert df.iloc[0]["expected_price"] == "unavailable"

def test_parse_quote_for_trade_v1():
    impact, slip_pct, out_amount = parse_quote_for_trade(V1_QUOTE)
    assert impact == pytest.approx(0.0006205573, rel=1e-6)
    assert slip_pct == pytest.approx(0.5)
    assert out_amount == 122846032.0

def test_parse_quote_for_trade_empty():
    assert parse_quote_for_trade({}) == (0.0, 0.0, 0.0)
