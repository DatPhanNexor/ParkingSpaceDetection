from typing import Any, Callable
from adapters.slot_id_mapper import (
    get_slot_code as _get_slot_code,
    is_valid_slot as _is_valid_slot,
)

get_slot_code: Callable[[Any], str] = _get_slot_code
is_valid_slot: Callable[[Any], bool] = _is_valid_slot


def test_slot_mapper():
    # Valid slots
    assert get_slot_code(1) == "S01"
    assert get_slot_code("2") == "S02"
    assert get_slot_code("9") == "S09"
    assert is_valid_slot("S01") is True
    assert is_valid_slot("S09") is True

    # Invalid slots (including boolean subtype of int)
    assert get_slot_code(10) == "UNMAPPED"
    assert get_slot_code(0) == "UNMAPPED"
    assert get_slot_code("abc") == "UNMAPPED"
    assert get_slot_code(True) == "UNMAPPED"
    assert get_slot_code(False) == "UNMAPPED"
    assert is_valid_slot("S10") is False
    assert is_valid_slot(None) is False
