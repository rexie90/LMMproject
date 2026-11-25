from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_instructors() -> list[dict]:
    with open(_DATA_DIR / "instructors.json", encoding="utf-8") as f:
        return json.load(f)


def _instructor_names() -> list[str]:
    return [i["name"] for i in _load_instructors()]


def _get_instructor(name: str) -> dict | None:
    for inst in _load_instructors():
        if inst["name"].lower() == name.lower():
            return inst
    return None


def _parse_time(t: str) -> datetime | None:
    try:
        return datetime.strptime(t, "%H:%M")
    except ValueError:
        return None


COURSE_CODE_RE = re.compile(r"^[A-Za-z]{2,4}\d{3,4}$")


def validate_slot(slot_name: str, value: str, state: dict) -> str | None:
    """
    Validate one slot value against booking rules.
    Returns None if valid, or an error string if invalid.
    """
    if slot_name == "instructor":
        names = _instructor_names()
        if value not in names:
            listed = ", ".join(names)
            return f"Unknown instructor '{value}'. Available: {listed}."
        return None

    if slot_name == "date":
        try:
            d = date.fromisoformat(value)
        except ValueError:
            return f"Date '{value}' is not a valid date (expected YYYY-MM-DD)."
        # Use _today from state if provided (keeps tests deterministic);
        # fall back to the real system date in production.
        _today_str = state.get("_today") or str(date.today())
        _today = date.fromisoformat(_today_str)
        if d <= _today:
            return f"Date {value} is in the past. Please choose a future date."
        instructor_name = state.get("instructor")
        if instructor_name:
            inst = _get_instructor(instructor_name)
            if inst:
                allowed_days = {oh["day"] for oh in inst["office_hours"]}
                day_name = d.strftime("%A")
                if day_name not in allowed_days:
                    days_str = ", ".join(sorted(allowed_days))
                    return (
                        f"{instructor_name} has no office hours on {day_name}. "
                        f"Available days: {days_str}."
                    )
        return None

    if slot_name == "time":
        t = _parse_time(value)
        if t is None:
            return f"Time '{value}' is not valid (expected HH:MM)."
        if t.minute not in (0, 30):
            on_hour = value[:3] + "00"
            on_half = value[:3] + "30"
            return (
                f"Appointments start on the hour or half-hour only. "
                f"Did you mean {on_hour} or {on_half}?"
            )
        instructor_name = state.get("instructor")
        booked_date = state.get("date")
        if instructor_name:
            inst = _get_instructor(instructor_name)
            if inst and booked_date:
                try:
                    d = date.fromisoformat(booked_date)
                except ValueError:
                    return None
                day_name = d.strftime("%A")
                windows = [oh for oh in inst["office_hours"] if oh["day"] == day_name]
                if windows:
                    in_window = any(
                        _parse_time(w["start"]) <= t < _parse_time(w["end"])
                        for w in windows
                    )
                    if not in_window:
                        ranges = ", ".join(
                            f"{w['start']}–{w['end']}" for w in windows
                        )
                        return (
                            f"{value} is outside {instructor_name}'s office hours "
                            f"on {day_name} ({ranges})."
                        )
        return None

    if slot_name == "topic":
        if len(value.strip()) < 5:
            return "Topic is too short (minimum 5 characters)."
        if len(value) > 200:
            return "Topic is too long (maximum 200 characters)."
        return None

    if slot_name == "student_name":
        name = value.strip()
        if len(name) < 2:
            return "Name is too short (minimum 2 characters)."
        if len(name) > 60:
            return "Name is too long (maximum 60 characters)."
        if re.search(r"\d", name):
            return "Name should not contain numbers."
        return None

    if slot_name == "course_code":
        if value and not COURSE_CODE_RE.match(value):
            return f"'{value}' is not a valid course code (e.g. CS101, IS4201)."
        return None

    return None
