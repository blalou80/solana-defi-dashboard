from src.risk.metrics import calculate_sharpe_ratio, calculate_var


def test_calculate_var():
    returns = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03, 0.04, -0.05, 0.01, -0.02]
    var_95 = calculate_var(returns, 0.95)
    # The 5th percentile of sorted returns (index 0? Actually index = int(0.05*10)=0 -> return -0.05)
    assert var_95 == -0.05

def test_sharpe_ratio():
    returns = [0.01, 0.02, 0.015, 0.03, 0.005]
    sr = calculate_sharpe_ratio(returns, 0.02)
    # Manual calculation: avg=0.016, std=~0.00935, sr=(0.016-0.02)/0.00935 ~ -0.428
    assert sr < 0

def test_sharpe_zero_std():
    returns = [0.01, 0.01, 0.01]
    sr = calculate_sharpe_ratio(returns, 0.02)
    assert sr == 0.0
