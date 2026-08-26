def calculate_fee(duration_seconds: int, gia_moi_gio: int, buoc_lam_tron: int, phi_toi_thieu: int) -> int:
    hours = max(1, (duration_seconds / 3600))
    raw_fee = hours * gia_moi_gio
    fee = int(round(raw_fee / buoc_lam_tron) * buoc_lam_tron)
    return max(fee, phi_toi_thieu)

def test_pricing():
    # Test base 1 hour minimum
    assert calculate_fee(10, 20000, 5000, 5000) == 20000
    
    # Test 1.5 hours -> 30000
    assert calculate_fee(5400, 20000, 5000, 5000) == 30000
    
    # Test exactly 1 hour -> 20000
    assert calculate_fee(3600, 20000, 5000, 5000) == 20000
    
    # Test rounding up
    # 1.1 hours = 3960s -> 22000 raw -> rounds to 20000 (nearest 5k)
    assert calculate_fee(3960, 20000, 5000, 5000) == 20000
    
    # 1.25 hours = 4500s -> 25000 raw -> 25000
    assert calculate_fee(4500, 20000, 5000, 5000) == 25000
    
    # Test minimum fee overrides
    # If gia_moi_gio is very low (e.g. 1000) but phi_toi_thieu is 5000
    assert calculate_fee(10, 1000, 1000, 5000) == 5000
