# Mawid Test Plan — T1 to T5

**Author:** Taleen (Member 4)  
**Date written:** 2026-11-25 (before any test is run)  
**Purpose:** Define expected behaviour for each test so pass/fail is objective.  
**How to run:** `python tests/run_tests.py` (executes all 5 tests sequentially against real Gemini)

---

## Background

Today's date used in all tests: **2026-11-25** (Wednesday).

Pre-booked slot in `data/bookings.json`:
- Instructor: Dr. Sara (sample)
- Date: 2026-12-13 (Sunday)
- Time: 10:00
- Student: Nora Ahmed

Instructor office hours:
- **Dr. Sara (sample)** — Sun 09:00–12:00, Tue 13:00–15:00
- **Dr. Khalid (sample)** — Mon 10:00–12:00, Wed 09:00–11:00
- **Dr. Lama (sample)** — Sun 14:00–16:00, Thu 10:00–12:00

---

## T1 — Normal Multi-Turn (English)

**Purpose:** Verify that the bot collects required slots across separate turns and produces a confirmed booking.

| Turn | User input | Expected bot behaviour |
|------|-----------|------------------------|
| 1 | `I want to book with Dr. Khalid` | Ask for date |
| 2 | `Monday December 7` | Ask for time (2026-12-07 is a Monday ✓) |
| 3 | `10:30` | Ask for topic |
| 4 | `I need help with my final project` | Ask for student name |
| 5 | `Sara Mohammed` | Show confirmation summary with all 5 slots; step = confirm |
| 6 | `Yes` | Save booking; reply contains booking ID (MWD-…); step = booked |

**Expected slot state at turn 5:**
```
instructor:   Dr. Khalid (sample)
date:         2026-12-07
time:         10:30
topic:        I need help with my final project
student_name: Sara Mohammed
course_code:  None
```

**Expected final JSON keys:** `booking_id`, `instructor`, `date`, `time`, `topic`, `student_name`

---

## T2 — Single Message All Fields (Arabic)

**Purpose:** Verify that all 5 required slots can be extracted from one Arabic message and that the Arabic reply is in Arabic.

| Turn | User input | Expected bot behaviour |
|------|-----------|------------------------|
| 1 | `أبغى أحجز مع د.سارة يوم الأحد القادم الساعة 9 الموضوع مشروع التخرج واسمي ريم الشمري` | Extract all 5 slots; show confirmation summary in **Arabic** (RTL); step = confirm |
| 2 | `نعم` | Save booking; reply in Arabic contains booking ID; step = booked |

**Expected extraction from turn 1:**
- instructor: `Dr. Sara (sample)`
- date: `2026-11-29` (next Sunday from 2026-11-25)
- time: `09:00`
- topic: contains "مشروع التخرج"
- student_name: `ريم الشمري`

**Expected:** Reply language = AR in both turns.

---

## T3 — Challenging: Already-Booked Slot + Correction After Summary (English)

**Purpose:** Verify that (a) the bot correctly detects the pre-booked slot and suggests alternatives, (b) a correction after the summary changes only that slot without restarting.

| Turn | User input | Expected bot behaviour |
|------|-----------|------------------------|
| 1 | `Book Dr. Sara on Sunday December 13 at 10:00, topic is exam review, my name is Lina Nasser` | Slot unavailable reply; suggests 09:30 and 10:30 (or similar nearest free times) |
| 2 | `10:30` | All slots now filled and free; show confirmation summary; step = confirm |
| 3 | `Actually change my name to Lina Al-Nasser` | Update student_name only; re-show confirmation summary with new name; step = confirm |
| 4 | `Yes confirm` | Save booking; reply contains booking ID; step = booked |

**Key verifications:**
- After turn 1: `available=False`, nearest slots returned (09:30, 10:30)
- After turn 2: step = confirm, summary shows 10:30
- After turn 3: student_name updated to `Lina Al-Nasser`, date/time/instructor unchanged, step = confirm again
- After turn 4: `booking_id` present in reply

---

## T4 — Ambiguous / Incomplete (Arabic)

**Purpose:** Verify that ambiguous values produce null and trigger clarification, and that incomplete information is handled gracefully.

| Turn | User input | Expected bot behaviour |
|------|-----------|------------------------|
| 1 | `أبغى أحجز مع الدكتور` | instructor = null (no name given); bot asks which instructor |
| 2 | `د. سارة` | instructor = Dr. Sara (sample); bot asks for date |
| 3 | `الساعة 7` | time = null (ambiguous: 7 AM or PM); bot asks for clarification (AM/PM) |
| 4 | `الساعة 7 الصباح` | time = `07:00`; but 07:00 is before Dr. Sara's Sunday hours (09:00); validator rejects with "outside office hours" error; bot asks to pick a valid time |
| 5 | `الساعة 9 صباحاً يوم الأحد القادم` | date = 2026-11-29, time = 09:00; both valid; bot asks for topic |

**Key verifications:**
- Turn 1: intent = provide_info, instructor = null
- Turn 3: intent = provide_info, time = null (ambiguous hour)
- Turn 4: validation error; step = reask; reply in Arabic
- Turn 5: date and time accepted; conversation continues normally

---

## T5 — Invalid / Unsupported Inputs (English + Arabic mix)

**Purpose:** Verify that each error type is caught and explained without crashing.

| Sub-test | User input | Expected bot behaviour |
|----------|-----------|------------------------|
| T5a — unknown instructor | `Book with Dr. Mohammed` | instructor = null; bot says instructor not found / asks which instructor |
| T5b — past date | `Book Dr. Khalid on December 1 2020` | date validation error: "date must be in the future"; step = reask |
| T5c — outside office hours | `Book Dr. Sara on Tuesday at 10:00` | time = 10:00 on Tuesday; Dr. Sara's Tuesday hours are 13:00–15:00; validation error: "outside office hours"; step = reask |
| T5d — off-topic | `What is the weather today?` | intent = off_topic; step = redirect; bot says it only handles booking |
| T5e — Arabic cancel | `إلغاء` | intent = cancel; step = cancelled; reply in Arabic |

**Key verifications:**
- Each sub-test: app does not crash
- T5a: bot asks which instructor from the list (or indicates instructor not found)
- T5b: validation error message mentions "future" or similar
- T5c: validation error message mentions "outside" or "13:00"
- T5d: step = redirect, reply is concise
- T5e: step = cancelled, reply in Arabic

---

## Evaluation Criteria

| Test | Pass condition |
|------|----------------|
| T1 | booking_id present in final reply; all 6 slot states correct |
| T2 | Arabic reply; booking_id present; all 5 required slots extracted from single message |
| T3 | Nearest slots suggested; correction changes only the named slot; booking_id present |
| T4 | Ambiguous time yields null; validation error shown; conversation recovers |
| T5 | Each sub-test handled without crash; correct step (redirect/reask/cancelled) |

---

*Results will be recorded in `evaluation/test_results.csv` after running against real Gemini.*
