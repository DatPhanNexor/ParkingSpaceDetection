from adapters.slot_id_mapper import get_slot_code

def test_slot_mapper():
    # Valid slots
    assert get_slot_code(1) == "S01"
    assert get_slot_code("2") == "S02"
    assert get_slot_code("9") == "S09"
    
    # Invalid slots
    assert get_slot_code(10) == "UNMAPPED"
    assert get_slot_code(0) == "UNMAPPED"
    assert get_slot_code("abc") == "UNMAPPED"
