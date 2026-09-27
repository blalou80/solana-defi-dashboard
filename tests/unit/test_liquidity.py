from src.engines.liquidity import (
    check_boundary,
    compute_impermanent_loss,
    compute_net_yield,
    price_to_tick,
    tick_to_price,
)


def test_tick_price_conversion():
    assert tick_to_price(0) == 1.0
    assert abs(tick_to_price(100) - 1.01005) < 0.0001
    assert price_to_tick(1.0) == 0

def test_compute_impermanent_loss():
    # No change -> 0 loss
    assert compute_impermanent_loss(1.0, 1.0) == 0.0
    # Price doubles -> IL ~5.72%
    il = compute_impermanent_loss(2.0, 1.0)
    assert il > 5.7 and il < 5.8

def test_compute_net_yield():
    fees = 10.0
    il = 2.0
    liquidity = 1000.0
    days = 30
    yield_pct = compute_net_yield(fees, il, liquidity, days)
    # (10-2)/1000 * 365/30 * 100 = 8/1000 * 12.1667 * 100 = 9.7333
    assert abs(yield_pct - 9.7333) < 0.001

def test_check_boundary():
    assert check_boundary(0, -100, 100) is False
    assert check_boundary(-150, -100, 100) is True
    assert check_boundary(150, -100, 100) is True
