from adapters.legacy_billing_adapter import calculate_fee, BillingConfig

def test_pricing():
    config = BillingConfig(hourly_rate_vnd=20000, rounding_vnd=5000, minimum_fee_vnd=5000)
    
    # Test duration 10 seconds -> ceil(55.5 / 5000) * 5000 = 5000, min 5000
    assert calculate_fee(10, config) == 5000
    
    # Test 1.5 hours -> 30000
    assert calculate_fee(5400, config) == 30000
    
    # Test exactly 1 hour -> 20000
    assert calculate_fee(3600, config) == 20000
    
    # Test rounding up
    # 1.1 hours = 3960s -> 22000 raw -> ceil(22000 / 5000) = 5 -> 25000
    assert calculate_fee(3960, config) == 25000
    
    # 1.25 hours = 4500s -> 25000 raw -> ceil(25000 / 5000) = 5 -> 25000
    assert calculate_fee(4500, config) == 25000
    
    # Test minimum fee overrides
    # If gia_moi_gio is very low (e.g. 1000) but phi_toi_thieu is 5000
    config_min = BillingConfig(hourly_rate_vnd=1000, rounding_vnd=1000, minimum_fee_vnd=5000)
    assert calculate_fee(10, config_min) == 5000
