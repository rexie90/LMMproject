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
    Returns None if valid, or a bilingual error string if invalid.
    Language is taken from state.get("language", "EN").
    """
    AR = state.get("language") == "AR"

    if slot_name == "instructor":
        names = _instructor_names()
        if value not in names:
            listed = ", ".join(names)
            if AR:
                return f"الدكتور/ة '{value}' غير موجود/ة. المتاحون: {listed}."
            return f"Unknown instructor '{value}'. Available: {listed}."
        return None

    if slot_name == "date":
        try:
            d = date.fromisoformat(value)
        except ValueError:
            if AR:
                return f"التاريخ '{value}' غير صحيح (الصيغة المطلوبة: YYYY-MM-DD)."
            return f"Date '{value}' is not a valid date (expected YYYY-MM-DD)."

        # Use _today from state if provided (keeps tests deterministic);
        # fall back to the real system date in production.
        _today_str = state.get("_today") or str(date.today())
        _today_d = date.fromisoformat(_today_str)
        if d <= _today_d:
            if AR:
                return f"التاريخ {value} في الماضي. الرجاء اختيار تاريخ مستقبلي."
            return f"Date {value} is in the past. Please choose a future date."

        instructor_name = state.get("instructor")
        if instructor_name:
            inst = _get_instructor(instructor_name)
            if inst:
                allowed_days = {oh["day"] for oh in inst["office_hours"]}
                day_name = d.strftime("%A")
                if day_name not in allowed_days:
                    days_str = ", ".join(sorted(allowed_days))
                    if AR:
                        return (
                            f"لا توجد ساعات مكتبية لـ {instructor_name} يوم {day_name}. "
                            f"الأيام المتاحة: {days_str}."
                        )
                    return (
                        f"{instructor_name} has no office hours on {day_name}. "
                        f"Available days: {days_str}."
                    )
        return None

    if slot_name == "time":
        t = _parse_time(value)
        if t is None:
            if AR:
                return f"الوقت '{value}' غير صحيح (الصيغة المطلوبة: HH:MM)."
            return f"Time '{value}' is not valid (expected HH:MM)."
        if t.minute not in (0, 30):
            on_hour = value[:3] + "00"
            on_half = value[:3] + "30"
            if AR:
                return (
                    f"المواعيد تبدأ على الساعة أو النصف فقط. "
                    f"هل تقصد {on_hour} أو {on_half}؟"
                )
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
                if not windows:
                    # No office hours on this day — the date validator should have
                    # caught this, but handle defensively here too.
                    if AR:
                        return f"لا توجد ساعات مكتبية لـ {instructor_name} يوم {day_name}."
                    return f"{instructor_name} has no office hours on {day_name}."
                in_window = any(
                    _parse_time(w["start"]) <= t < _parse_time(w["end"])
                    for w in windows
                )
                if not in_window:
                    ranges = ", ".join(f"{w['start']}–{w['end']}" for w in windows)
                    if AR:
                        return (
                            f"{value} خارج ساعات مكتب {instructor_name} "
                            f"يوم {day_name} ({ranges})."
                        )
                    return (
                        f"{value} is outside {instructor_name}'s office hours "
                        f"on {day_name} ({ranges})."
                    )
        return None

    if slot_name == "topic":
        if len(value.strip()) < 5:
            if AR:
                return "الموضوع قصير جداً (5 أحرف كحد أدنى)."
            return "Topic is too short (minimum 5 characters)."
        if len(value) > 200:
            if AR:
                return "الموضوع طويل جداً (200 حرف كحد أقصى)."
            return "Topic is too long (maximum 200 characters)."
        return None

    if slot_name == "student_name":
        name = value.strip()
        if len(name) < 2:
            if AR:
                return "الاسم قصير جداً (حرفان كحد أدنى)."
            return "Name is too short (minimum 2 characters)."
        if len(name) > 60:
            if AR:
                return "الاسم طويل جداً (60 حرفاً كحد أقصى)."
            return "Name is too long (maximum 60 characters)."
        if re.search(r"\d", name):
            if AR:
                return "الاسم لا يجب أن يحتوي على أرقام."
            return "Name should not contain numbers."
        return None

    if slot_name == "course_code":
        if value and not COURSE_CODE_RE.match(value):
            if AR:
                return f"'{value}' ليس رمز مادة صحيحاً (مثال: CS101، IS4201)."
            return f"'{value}' is not a valid course code (e.g. CS101, IS4201)."
        return None

    return None
