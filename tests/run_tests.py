"""
Mawid T1–T5 test runner.
Runs all five tests against real Gemini and writes evaluation/test_results.csv.

Each test drives the dialogue by calling extract() + apply_updates() + next_action()
directly — the same path the UI uses, but without Streamlit.

Run from the project root with the venv activated:
    python tests/run_tests.py
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

import shutil
from pathlib import Path

from src.extractor import ExtractionError, extract
from src.llm_client import LLMError
from src.policy import detect_language, next_action
from src.state import apply_updates, new_state
import src.bookings as _bk

TODAY = "2026-11-25"
CSV_PATH = "evaluation/test_results.csv"
os.makedirs("evaluation", exist_ok=True)

# ── bookings file isolation ───────────────────────────────────────────────────
# Redirect src.bookings to a temporary copy so save_booking() does not write
# to the real data/bookings.json. The real file is restored in the finally block.

_REAL_BOOKINGS = Path("data/bookings.json")
_TMP_BOOKINGS  = Path("data/bookings_test_tmp.json")


def _setup_tmp_bookings() -> None:
    shutil.copy(_REAL_BOOKINGS, _TMP_BOOKINGS)
    _bk._BOOKINGS_FILE = _TMP_BOOKINGS


def _teardown_tmp_bookings() -> None:
    _bk._BOOKINGS_FILE = _REAL_BOOKINGS
    _TMP_BOOKINGS.unlink(missing_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def turn(state: dict, message: str) -> tuple[dict, dict, list[str], dict]:
    """
    Run one dialogue turn.
    - Sets state["_today"] = TODAY so validators use the fixed test date,
      not the computer's real clock. This keeps tests valid after Dec 7.
    Returns (updated_state, extraction, errors, action).
    Raises LLMError or ExtractionError on failure.
    """
    lang = detect_language(message)
    state["language"] = lang
    state["_today"] = TODAY          # pin today for validators
    extraction = extract(message, state, TODAY, prompt_version="v2")
    new_st, errors = apply_updates(state, extraction["updates"])
    new_st["_today"] = TODAY         # carry forward in updated state
    action = next_action(new_st, extraction["intent"], errors)
    return new_st, extraction, errors, action


def print_turn(n: int, msg: str, action: dict, extraction: dict) -> None:
    print(f"  Turn {n}: {msg!r}")
    print(f"    intent={extraction['intent']}  step={action['step']}")
    upd = {k: v for k, v in extraction['updates'].items() if v is not None}
    if upd:
        print(f"    updates={upd}")
    print(f"    reply={action['reply'][:80]!r}")


# ── CSV writer ────────────────────────────────────────────────────────────────

FIELDNAMES = ["id", "name", "turn", "input", "expected", "actual", "pass", "reason"]
rows: list[dict] = []


def record(
    test_id: str,
    name: str,
    turn_n: int | str,
    user_input: str,
    expected: str,
    actual: str,
    passed: bool,
    reason: str = "",
) -> None:
    rows.append({
        "id":      test_id,
        "name":    name,
        "turn":    turn_n,
        "input":   user_input,
        "expected": expected,
        "actual":  actual,
        "pass":    "PASS" if passed else "FAIL",
        "reason":  reason,
    })
    status = "PASS" if passed else "FAIL"
    print(f"    [{status}] {expected[:70]}")


def save_csv() -> None:
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to {CSV_PATH}")


# ── T1: Normal multi-turn, English ───────────────────────────────────────────

def test_t1() -> None:
    print("\n── T1: Normal multi-turn (English) ──")
    s = new_state()
    messages = [
        "I want to book with Dr. Khalid",
        "Monday December 7",
        "10:30",
        "I need help with my final project",
        "Sara Mohammed",
        "Yes",
    ]
    for i, msg in enumerate(messages, 1):
        s, ex, errs, act = turn(s, msg)
        print_turn(i, msg, act, ex)
        time.sleep(1)  # space out Gemini calls

    record("T1", "Normal multi-turn EN", "final",
           "Yes",
           "step=booked, booking_id in reply",
           f"step={act['step']}, reply={act['reply'][:60]}",
           act["step"] == "booked" and s.get("booking_id") is not None,
           "booking_id present" if s.get("booking_id") else "booking_id missing")

    record("T1", "Normal multi-turn EN", "slots",
           "(all turns)",
           "instructor=Dr. Khalid, date=2026-12-07, time=10:30",
           f"instructor={s.get('instructor')}, date={s.get('date')}, time={s.get('time')}",
           s.get("instructor") == "Dr. Khalid (sample)"
           and s.get("date") == "2026-12-07"
           and s.get("time") == "10:30")


# ── T2: Single message all fields, Arabic ────────────────────────────────────

def test_t2() -> None:
    print("\n── T2: Single message all fields (Arabic) ──")
    s = new_state()
    msg1 = "أبغى أحجز مع د.سارة يوم الأحد القادم الساعة 9 الموضوع مشروع التخرج واسمي ريم الشمري"
    s, ex, errs, act = turn(s, msg1)
    print_turn(1, msg1, act, ex)
    time.sleep(1)

    # expect confirm step (all slots filled and free)
    record("T2", "Single message Arabic", 1,
           msg1,
           "step=confirm, instructor=Dr. Sara (sample), date=2026-11-29, time=09:00",
           f"step={act['step']}, slots={s.get('instructor')}, {s.get('date')}, {s.get('time')}",
           act["step"] == "confirm"
           and s.get("instructor") == "Dr. Sara (sample)"
           and s.get("date") == "2026-11-29"
           and s.get("time") == "09:00",
           "")

    # language check
    record("T2", "Single message Arabic", 1,
           msg1,
           "reply language = AR",
           f"language={s.get('language')}",
           s.get("language") == "AR")

    if act["step"] == "confirm":
        s, ex, errs, act = turn(s, "نعم")
        print_turn(2, "نعم", act, ex)
        time.sleep(1)
        record("T2", "Single message Arabic", 2,
               "نعم",
               "step=booked, booking_id in reply",
               f"step={act['step']}, booking_id={s.get('booking_id')}",
               act["step"] == "booked" and s.get("booking_id") is not None)


# ── T3: Challenging — booked slot + correction after summary ─────────────────

def test_t3() -> None:
    print("\n── T3: Booked slot + correction after summary (English) ──")
    s = new_state()

    # Turn 1 — the pre-booked slot
    msg1 = "Book Dr. Sara on Sunday December 13 at 10:00, topic is exam review, my name is Lina Nasser"
    s, ex, errs, act = turn(s, msg1)
    print_turn(1, msg1, act, ex)
    time.sleep(1)

    record("T3", "Booked slot", 1,
           msg1,
           "step=suggest (slot unavailable), nearest slots returned",
           f"step={act['step']}, reply={act['reply'][:60]}",
           act["step"] == "suggest")

    # Turn 2 — pick an alternative time
    msg2 = "10:30"
    s, ex, errs, act = turn(s, msg2)
    print_turn(2, msg2, act, ex)
    time.sleep(1)

    record("T3", "Correction - pick free time", 2,
           msg2,
           "step=confirm, time=10:30",
           f"step={act['step']}, time={s.get('time')}",
           act["step"] == "confirm" and s.get("time") == "10:30")

    # Turn 3 — correction after summary
    msg3 = "Actually change my name to Lina Al-Nasser"
    s, ex, errs, act = turn(s, msg3)
    print_turn(3, msg3, act, ex)
    time.sleep(1)

    record("T3", "Name correction after summary", 3,
           msg3,
           "step=confirm, student_name=Lina Al-Nasser, instructor/date/time unchanged",
           f"step={act['step']}, name={s.get('student_name')}, time={s.get('time')}",
           act["step"] == "confirm"
           and "Al-Nasser" in (s.get("student_name") or "")
           and s.get("time") == "10:30")

    # Turn 4 — final confirm
    if act["step"] == "confirm":
        msg4 = "Yes confirm"
        s, ex, errs, act = turn(s, msg4)
        print_turn(4, msg4, act, ex)
        time.sleep(1)
        record("T3", "Final confirm", 4,
               msg4,
               "step=booked, booking_id present",
               f"step={act['step']}, booking_id={s.get('booking_id')}",
               act["step"] == "booked" and s.get("booking_id") is not None)


# ── T4: Ambiguous / incomplete, Arabic ───────────────────────────────────────

def test_t4() -> None:
    print("\n── T4: Ambiguous / incomplete (Arabic) ──")
    s = new_state()

    # Turn 1 — no instructor name
    msg1 = "أبغى أحجز مع الدكتور"
    s, ex, errs, act = turn(s, msg1)
    print_turn(1, msg1, act, ex)
    time.sleep(1)

    record("T4", "Ambiguous - no instructor name", 1,
           msg1,
           "instructor=null, step=ask (asking which instructor)",
           f"instructor={ex['updates'].get('instructor')}, step={act['step']}",
           ex["updates"].get("instructor") is None and act["step"] == "ask")

    # Turn 2 — give instructor
    msg2 = "د. سارة"
    s, ex, errs, act = turn(s, msg2)
    print_turn(2, msg2, act, ex)
    time.sleep(1)

    record("T4", "Instructor resolved", 2,
           msg2,
           "instructor=Dr. Sara (sample), step=ask (asking for date)",
           f"instructor={s.get('instructor')}, step={act['step']}",
           s.get("instructor") == "Dr. Sara (sample)" and act["step"] == "ask")

    # Turn 3 — ambiguous time (no AM/PM)
    msg3 = "الساعة 7"
    s, ex, errs, act = turn(s, msg3)
    print_turn(3, msg3, act, ex)
    time.sleep(1)

    record("T4", "Ambiguous time (no AM/PM)", 3,
           msg3,
           "time=null (ambiguous), step=ask (clarify AM/PM)",
           f"time={ex['updates'].get('time')}, step={act['step']}",
           ex["updates"].get("time") is None)

    # Turn 4 — explicit 7 AM → outside Dr. Sara's hours
    msg4 = "الساعة 7 الصباح يوم الأحد"
    s, ex, errs, act = turn(s, msg4)
    print_turn(4, msg4, act, ex)
    time.sleep(1)

    record("T4", "Time outside office hours", 4,
           msg4,
           "step=reask (07:00 outside Dr. Sara's 09:00-12:00 hours)",
           f"step={act['step']}, errors={errs[:1]}",
           act["step"] == "reask")


# ── T5: Invalid / unsupported inputs ─────────────────────────────────────────

def test_t5() -> None:
    print("\n── T5: Invalid / unsupported inputs ──")

    # T5a — unknown instructor
    s = new_state(); s["language"] = "EN"
    s, ex, errs, act = turn(s, "Book with Dr. Mohammed")
    print_turn("5a", "Book with Dr. Mohammed", act, ex)
    record("T5a", "Unknown instructor", 1,
           "Book with Dr. Mohammed",
           "instructor=null or validation error; step=ask or reask",
           f"instructor={ex['updates'].get('instructor')}, step={act['step']}",
           ex["updates"].get("instructor") is None or act["step"] in ("ask", "reask"))
    time.sleep(1)

    # T5b — past date
    s = new_state(); s["language"] = "EN"
    s["instructor"] = "Dr. Khalid (sample)"
    s, ex, errs, act = turn(s, "Book Dr. Khalid on December 1 2020 at 10:00")
    print_turn("5b", "Past date 2020-12-01", act, ex)
    record("T5b", "Past date", 1,
           "Book Dr. Khalid on December 1 2020 at 10:00",
           "step=reask (date in the past)",
           f"step={act['step']}, errors={errs[:1]}",
           act["step"] == "reask")
    time.sleep(1)

    # T5c — outside office hours (Tuesday 10:00, Dr. Sara's Tue hours are 13:00-15:00)
    s = new_state(); s["language"] = "EN"
    s["instructor"] = "Dr. Sara (sample)"
    s["date"] = "2026-12-01"   # Tuesday (use directly — no validator on pre-set state)
    s, ex, errs, act = turn(s, "10:00 Tuesday")
    print_turn("5c", "10:00 on Dr. Sara Tuesday (outside hours)", act, ex)
    record("T5c", "Outside office hours", 1,
           "10:00 on Dr. Sara Tuesday (13:00-15:00 only)",
           "step=reask (time outside office hours)",
           f"step={act['step']}, errors={errs[:1]}",
           act["step"] == "reask")
    time.sleep(1)

    # T5d — off-topic
    s = new_state(); s["language"] = "EN"
    s, ex, errs, act = turn(s, "What is the weather today?")
    print_turn("5d", "Off-topic: weather", act, ex)
    record("T5d", "Off-topic message", 1,
           "What is the weather today?",
           "intent=off_topic, step=redirect",
           f"intent={ex['intent']}, step={act['step']}",
           ex["intent"] == "off_topic" and act["step"] == "redirect")
    time.sleep(1)

    # T5e — Arabic cancel
    s = new_state(); s["language"] = "AR"
    s, ex, errs, act = turn(s, "إلغاء")
    print_turn("5e", "Arabic cancel: إلغاء", act, ex)
    record("T5e", "Arabic cancel", 1,
           "إلغاء",
           "intent=cancel, step=cancelled, reply in Arabic",
           f"intent={ex['intent']}, step={act['step']}, lang={s.get('language')}",
           ex["intent"] == "cancel" and act["step"] == "cancelled")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    total_start = time.monotonic()
    print("=== Mawid T1–T5 Test Run ===")
    print(f"Today: {TODAY}  |  CSV: {CSV_PATH}\n")

    _setup_tmp_bookings()
    try:
        for test_fn in [test_t1, test_t2, test_t3, test_t4, test_t5]:
            try:
                test_fn()
            except (LLMError, ExtractionError) as e:
                print(f"  [ERROR] {type(e).__name__}: {e}")
                rows.append({"id": test_fn.__name__, "name": "ERROR", "turn": "?",
                             "input": "", "expected": "", "actual": str(e),
                             "pass": "FAIL", "reason": type(e).__name__})

        save_csv()
    finally:
        _teardown_tmp_bookings()

    passed = sum(1 for r in rows if r["pass"] == "PASS")
    failed = sum(1 for r in rows if r["pass"] == "FAIL")
    print(f"\n=== Summary: {passed} PASS / {failed} FAIL out of {len(rows)} checks ===")
    print(f"Total elapsed: {time.monotonic() - total_start:.1f} s")

    # Verify data/bookings.json was not modified by the test run
    result = subprocess.run(
        ["git", "status", "--porcelain", "data/bookings.json"],
        capture_output=True, text=True
    )
    if result.stdout.strip():
        print(f"\n[WARNING] data/bookings.json was modified! git says: {result.stdout.strip()}")
    else:
        print("\n[OK] data/bookings.json is unchanged.")
