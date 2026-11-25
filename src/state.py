from __future__ import annotations


def new_state() -> dict:
    """Return a fresh empty booking state for a new conversation."""
    return {
        "instructor":   None,
        "date":         None,
        "time":         None,
        "topic":        None,
        "student_name": None,
        "course_code":  None,
        "confirmed":    False,
        "booking_id":   None,
        "language":     "EN",
        "step":         "greeting",
    }


def apply_updates(state: dict, updates: dict) -> tuple[dict, list[str]]:
    """
    Merge extractor updates into state.

    - Only overwrites a slot when the new value is not None.
    - Calls validators.validate_slot on each changed slot.
    - Returns (new_state, list_of_error_strings).
      An empty error list means every updated slot passed validation.
    """
    from src.validators import validate_slot

    new = dict(state)
    errors: list[str] = []

    slot_keys = ["instructor", "date", "time", "topic", "student_name", "course_code"]

    for key in slot_keys:
        value = updates.get(key)
        if value is not None:
            error = validate_slot(key, value, new)
            if error:
                errors.append(error)
            else:
                new[key] = value

    return new, errors
