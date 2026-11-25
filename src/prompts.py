"""
Prompt templates for Mawid's extractor.
v1: simple baseline.  v2: improved (Role+Task+Format, instructor list, today's date,
    delimiters, few-shot, correction rules, null-on-ambiguity).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

_INSTRUCTORS_PATH = Path(__file__).parent.parent / "data" / "instructors.json"

_SLOT_KEYS = ("instructor", "date", "time", "topic", "student_name", "course_code")


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_instructor_text() -> str:
    with open(_INSTRUCTORS_PATH, encoding="utf-8") as f:
        instructors = json.load(f)
    lines = []
    for inst in instructors:
        hours = "; ".join(
            f"{h['day']} {h['start']}–{h['end']}" for h in inst["office_hours"]
        )
        lines.append(f"- {inst['name']} ({inst['department']}): {hours}")
    return "\n".join(lines)


def _state_summary(state: dict) -> str:
    filled = {k: v for k, v in state.items() if v and k in _SLOT_KEYS}
    if not filled:
        return "No slots filled yet."
    return "\n".join(f"  {k}: {v}" for k, v in filled.items())


def _next_weekday(today_str: str, weekday: int) -> str:
    """Return the next occurrence of weekday (0=Mon … 6=Sun) after today."""
    d = date.fromisoformat(today_str)
    days = (weekday - d.weekday() + 7) % 7
    if days == 0:
        days = 7
    return str(d + timedelta(days=days))


def _tomorrow(today_str: str) -> str:
    return str(date.fromisoformat(today_str) + timedelta(days=1))


# ── public entry point ────────────────────────────────────────────────────────

def build_system_prompt(version: str, today: str, state: dict) -> str:
    """Return the system prompt for the given version ("v1" or "v2")."""
    if version == "v1":
        return _v1(today)
    return _v2(today, state)


# ── v1: simple baseline ───────────────────────────────────────────────────────

def _v1(today: str) -> str:
    null_updates = json.dumps({k: None for k in _SLOT_KEYS}, ensure_ascii=False)
    skeleton = json.dumps(
        {"intent": "provide_info|correction|confirm|reject|cancel|off_topic",
         "updates": {k: None for k in _SLOT_KEYS}},
        ensure_ascii=False,
    )
    return (
        f"You are a booking assistant for university office-hours appointments.\n"
        f"Extract the user's intent and booking details from their message.\n"
        f"Return ONLY valid JSON — no markdown fences, no explanation:\n"
        f"{skeleton}\n\n"
        f"Today is {today}.\n"
        f"Convert dates to YYYY-MM-DD and times to HH:MM (24-hour).\n"
        f"Use null for any field not mentioned in the message."
    )


# ── v2: improved ──────────────────────────────────────────────────────────────

def _v2(today: str, state: dict) -> str:
    instructors = _load_instructor_text()
    state_text = _state_summary(state)
    next_sunday = _next_weekday(today, 6)   # weekday 6 = Sunday
    next_monday = _next_weekday(today, 0)   # weekday 0 = Monday
    tomorrow = _tomorrow(today)

    schema = json.dumps(
        {
            "intent": "provide_info | correction | confirm | reject | cancel | off_topic",
            "updates": {
                "instructor": "exact name from list or null",
                "date":       "YYYY-MM-DD or null",
                "time":       "HH:MM (24-hour) or null",
                "topic":      "string or null",
                "student_name": "string or null",
                "course_code":  "string or null",
            },
        },
        indent=2,
        ensure_ascii=False,
    )

    ex1 = json.dumps(
        {"intent": "provide_info",
         "updates": {"instructor": "Dr. Sara (sample)", "date": next_sunday,
                     "time": "10:00", "topic": None, "student_name": None, "course_code": None}},
        ensure_ascii=False,
    )
    ex2 = json.dumps(
        {"intent": "provide_info",
         "updates": {"instructor": "Dr. Khalid (sample)", "date": next_monday,
                     "time": "10:30", "topic": "my project", "student_name": None, "course_code": None}},
        ensure_ascii=False,
    )
    ex3 = json.dumps(
        {"intent": "correction",
         "updates": {"instructor": None, "date": None, "time": "10:30",
                     "topic": None, "student_name": None, "course_code": None}},
        ensure_ascii=False,
    )
    ex4 = json.dumps(
        {"intent": "confirm",
         "updates": {k: None for k in _SLOT_KEYS}},
        ensure_ascii=False,
    )

    return f"""\
## ROLE
You are an intent and slot extractor for Mawid, the office-hours booking chatbot at Umm Al-Qura University. You handle both Arabic and English messages.

## TASK
Analyze the student's message and return a structured JSON object containing:
1. Their intent (what they are trying to do).
2. Any booking slot values they provided or changed.

## CONTEXT
Today's date: {today}
Tomorrow: {tomorrow}

Available instructors and office hours:
{instructors}

Currently filled booking slots:
{state_text}

## OUTPUT FORMAT
Return ONLY valid JSON — no markdown fences, no preamble, no explanation:
{schema}

## RULES
1. RELATIVE DATES  — Convert to YYYY-MM-DD using today ({today}).
   "بكرة / tomorrow" → {tomorrow}.  "الأحد الجاي / next Sunday" → {next_sunday}.
   "الاثنين الجاي / next Monday" → {next_monday}.
2. RELATIVE TIMES  — "العاشرة" → 10:00.  "العاشرة ونص / 10:30" → 10:30.
   "2 ونص (afternoon context)" → 14:30.
3. AMBIGUITY       — If a time has no AM/PM context (e.g. bare "7"), return null for time.
4. CORRECTIONS     — Intent = "correction". Include ONLY the changed field(s); set all others null.
5. CONFIRMATION    — "نعم / yes / أكد / confirm" → intent = "confirm", all updates null.
6. REJECTION       — "لا / no" after a booking summary → intent = "reject", all updates null.
7. CANCEL          — User explicitly abandons the booking → intent = "cancel", all updates null.
8. OFF-TOPIC       — Unrelated to booking office hours → intent = "off_topic", all updates null.
9. INSTRUCTOR NAMES — Only use names exactly as listed above. Unrecognised names → null.
10. OPTIONAL FIELD  — course_code is optional; extract only if the user explicitly mentions it.

## EXAMPLES
Input: "أبغى أحجز مع د.سارة يوم الأحد الجاي الساعة 10"
Output: {ex1}

Input: "I want to book with Dr. Khalid on Monday at 10:30 about my project"
Output: {ex2}

Input: "غير الوقت إلى 10:30"
Output: {ex3}

Input: "نعم"
Output: {ex4}"""
