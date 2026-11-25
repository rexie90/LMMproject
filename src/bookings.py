from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_BOOKINGS_FILE = _DATA_DIR / "bookings.json"
_INSTRUCTORS_FILE = _DATA_DIR / "instructors.json"


def _load_bookings() -> list[dict]:
    if not _BOOKINGS_FILE.exists():
        return []
    with open(_BOOKINGS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _load_instructors() -> list[dict]:
    with open(_INSTRUCTORS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _minutes_to_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _office_hour_slots(instructor_name: str, day_name: str) -> list[str]:
    """Return all valid :00/:30 slot start times for an instructor on a given day."""
    slots: list[str] = []
    for inst in _load_instructors():
        if inst["name"].lower() != instructor_name.lower():
            continue
        for window in inst["office_hours"]:
            if window["day"] != day_name:
                continue
            start = _time_to_minutes(window["start"])
            end = _time_to_minutes(window["end"])
            current = start
            while current < end:
                slots.append(_minutes_to_time(current))
                current += 30
    return slots


def check_availability(instructor: str, date: str, time: str) -> dict:
    """
    Check if a slot is free.

    Returns:
      {"available": True}
      {"available": False, "nearest": ["HH:MM", ...]}  # up to 2 nearest free slots
    """
    from datetime import date as date_cls

    bookings = _load_bookings()
    taken = {
        b["time"]
        for b in bookings
        if b["instructor"].lower() == instructor.lower() and b["date"] == date
    }

    if time not in taken:
        return {"available": True}

    # Find up to 2 nearest free slots on the same day
    try:
        d = date_cls.fromisoformat(date)
    except ValueError:
        return {"available": False, "nearest": []}

    day_name = d.strftime("%A")
    all_slots = _office_hour_slots(instructor, day_name)
    free_slots = [s for s in all_slots if s not in taken]

    requested_minutes = _time_to_minutes(time)
    free_slots.sort(key=lambda s: abs(_time_to_minutes(s) - requested_minutes))
    nearest = free_slots[:2]

    return {"available": False, "nearest": nearest}


def save_booking(state: dict) -> str:
    """
    Persist a confirmed booking to data/bookings.json.
    Returns a booking ID string like "MWD-20261201-0002".
    """
    bookings = _load_bookings()

    # Generate next ID: count existing bookings for that date + 1
    date_compact = state["date"].replace("-", "")
    day_bookings = [
        b for b in bookings if b["date"] == state["date"]
    ]
    seq = len(day_bookings) + 1
    booking_id = f"MWD-{date_compact}-{seq:04d}"

    record = {
        "booking_id":   booking_id,
        "instructor":   state["instructor"],
        "date":         state["date"],
        "time":         state["time"],
        "topic":        state["topic"],
        "student_name": state["student_name"],
    }
    if state.get("course_code"):
        record["course_code"] = state["course_code"]

    bookings.append(record)
    with open(_BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, indent=2, ensure_ascii=False)

    return booking_id
