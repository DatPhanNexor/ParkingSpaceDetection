def get_slot_code(legacy_id: str) -> str:
    """
    Maps legacy slot IDs (1-9) to the new domain standard (S01-S09).
    If the legacy ID is outside this range, returns 'UNMAPPED'.
    """
    try:
        id_num = int(legacy_id)
        if 1 <= id_num <= 9:
            return f"S0{id_num}"
    except (ValueError, TypeError):
        pass
    
    return "UNMAPPED"

def is_valid_slot(slot_code: str) -> bool:
    """
    Checks if a slot code is in the valid range S01 to S09.
    """
    return slot_code in [f"S0{i}" for i in range(1, 10)]
