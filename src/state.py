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
        "asking_for":   None,
    }


def apply_updates(state: dict, updates: dict) -> tuple[dict, list[str]]:
    """
    Merge extractor updates into state.

    - Only overwrites a slot when the new value is not None.
    - Calls validators.validate_slot on each changed slot.
    - Cross-validates dependent slots after individual updates:
        * If instructor changes, re-validates existing date; if that fails,
          clears date and time and adds an error.
        * If instructor or date changes, re-validates existing time; if that
          fails, clears time and adds an error.
    - Returns (new_state, list_of_error_strings).
    """
    from src.validators import validate_slot

    new = dict(state)
    errors: list[str] = []

    slot_keys = ["instructor", "date", "time", "topic", "student_name", "course_code"]
    changed: set[str] = set()

    # Phase 1: validate and apply each individual update
    for key in slot_keys:
        value = updates.get(key)
        if value is not None:
            error = validate_slot(key, value, new)
            if error:
                errors.append(error)
            else:
                new[key] = value
                changed.add(key)

    # Phase 2: re-validate pre-existing date if instructor just changed
    if "instructor" in changed and new.get("date") and "date" not in changed:
        err = validate_slot("date", new["date"], new)
        if err:
            errors.append(err)
            new["date"] = None
            new["time"] = None   # time depends on date

    # Phase 3: re-validate pre-existing time if instructor or date just changed
    if (
        ("instructor" in changed or "date" in changed)
        and new.get("time")
        and "time" not in changed
        and new.get("date")
    ):
        err = validate_slot("time", new["time"], new)
        if err:
            errors.append(err)
            new["time"] = None

    return new, errors
