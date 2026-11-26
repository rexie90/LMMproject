# Mawid — Evaluation Analysis

## Test Run Summary

**Date:** 2026-11-25  
**TODAY pin:** 2026-11-25 (injected via `state["_today"]` for deterministic date validation)  
**Models used:** gemini-3.5-flash-lite (primary blocked by 429); gemini-3.1-flash-lite used for T5b and T5d when 3.5-flash-lite also hit 429.  
**Result: 18/18 PASS**

---

## T1–T5 Results

| ID | Name | Checks | Result |
|---|---|---|---|
| T1 | Normal multi-turn EN | 2 | PASS |
| T2 | Single message Arabic | 3 | PASS |
| T3 | Booked slot + correction after summary | 4 | PASS |
| T4 | Ambiguous / incomplete Arabic | 4 | PASS |
| T5 | Invalid / unsupported (5 sub-cases) | 5 | PASS |

---

## Failure Analysis

**No functional failures on this run.** All 18 checks passed.

### Observed issues (non-failure, logged during the run)

1. **Primary model rate-limited (429).** `gemini-3.8-flash` returned 429 immediately on the first call. The 10-minute block mechanism prevented repeated 429 retries, and the fallback chain (3.5-flash-lite → 3.1-flash-lite) handled all calls successfully. Total elapsed time: 67.8 seconds for 18 LLM calls.

2. **Second fallback invoked twice (T5b, T5d).** `gemini-3.5-flash-lite` itself returned 429 on two calls. The second fallback (`gemini-3.1-flash-lite`) succeeded in both cases. This demonstrates that the two-fallback design is valuable under sustained free-tier usage.

### Bugs found during development

The following bugs were found during the rehearsal run (`tests/run_tests.py`) and manual browser testing, and were fixed before the official evaluation run:

| # | Bug | Cause | Fix |
|---|---|---|---|
| B1 | LLM call hung for 16+ minutes, blocking the app | The google-genai SDK has no default timeout; a stalled request blocked indefinitely | Added `HttpOptions(timeout=30000)` (30 s, in ms) per request and a 90 s hard deadline in `src/llm_client.py` |
| B2 | Pre-booked slot was outside Dr. Sara's Tuesday office hours | Sample booking was set to 2026-12-01 10:00 (Tue); Sara's Tue hours are 13:00–15:00, so T3 could not reach `step=suggest` | Moved pre-booked slot to 2026-12-13 (Sunday) 10:00, within Sara's Sun 09:00–12:00 window (`data/bookings.json`) |
| B3 | `booking_id` was None after `step=booked` | `save_booking()` returned the ID but `next_action()` never stored it back in `state` | Added `state["booking_id"] = booking_id` in the `booked` branch of `src/policy.py:next_action()` |
| B4 | Booking allowed on a day with no office hours when date was given before instructor | Date was validated without a known instructor; once the instructor was provided, the existing date was not re-checked | Added dependent re-validation in `src/state.py:apply_updates()` (Phase 2 and 3 cross-validation); also added an office-hours window check to `src/bookings.py:check_availability()` |
| B5 | App crashed on startup with `ModuleNotFoundError: No module named 'src'` | `streamlit run src/app.py` from the project root did not add the root to `sys.path` | Added `sys.path.insert(0, project_root)` at the top of `src/app.py`; fixed `AppTest` path in `tests/test_app.py` to use an absolute path |
| B6 | A short topic answer ("I need help with my final project") was classified as `off_topic` during the T1 rehearsal run | An early version of v2 (before Rule 11) had no hint that the bot had just asked for the topic; the LLM treated the sentence as a general request | Added `state["asking_for"]` tracking in `src/policy.py` and Rule 11 to the v2 prompt in `src/prompts.py`; v2 was improved iteratively — this was not a failure of v1 |

All bugs were found by the rehearsal run and by manual browser testing before the official T1–T5 run.

---

## Identified Improvements

### Improvement 1: Instructor name normalization in v1 (prompt improvement)

**Observation (from prompt comparison):** v1 returns the instructor name as the user typed it ("Dr. Khalid", "د.سارة"), while v2 normalizes to the exact stored name ("Dr. Khalid (sample)", "Dr. Sara (sample)") because the instructor list is in the prompt context. In production, v1's raw name would fail `validate_slot("instructor", ...)` and require an extra turn to correct.

**Improvement:** Add the instructor list to v1 (or deploy only v2 in production, which is what the app does).

### Improvement 2: Better clarification for ambiguous time (T4 observation)

**Observation:** In T4 turn 3, when the user said "الساعة 7" (7 o'clock, no AM/PM), the system returned null for time and re-asked for the date (since date was also missing). The re-ask message was about the date, not the time — which could confuse a user who already gave partial time information.

**Improvement:** When `time=null` due to ambiguity (not simply missing), `policy.next_action` could detect this case via a separate "clarifying_time" step and ask specifically "Did you mean 7 AM (07:00) or 7 PM (19:00)?" This would be more helpful than the generic "What time?" question.

---

## Responsible AI

### Risk 1: Saving an incorrect or incomplete booking

**Description:** If the system saved a booking without user review, errors (wrong date, wrong instructor) could disrupt real office hours.

**Implemented mitigation:** An explicit confirmation step is required before any booking is saved. `policy.py:next_action()` only returns `step="booked"` after the user has seen the full summary and sent a `confirm` intent. The function returns `step="confirm"` on the first full-slot fill, and only proceeds to `save_booking()` on the subsequent turn when `intent="confirm"` and `state["confirmed"]=True`. The user can reject the summary at any time and change individual fields.

**Code reference:** `src/policy.py`, function `next_action()` — the `booked` branch is only reached via `confirmed=True` → `intent="confirm"` → `save_booking()`.

### Risk 2: Collecting unnecessary personal data

**Description:** A booking chatbot could inadvertently ask for a student ID, phone number, or other sensitive information that is not needed for scheduling.

**Implemented mitigation:** The extractor schema includes only: instructor name, date, time, topic, student name, and optional course code. The student ID and phone number fields are explicitly excluded from the slot design. `validators.py:validate_slot("student_name", ...)` additionally rejects any value containing digits (`re.search(r"\d", name)`) — this prevents student IDs (which always contain digits) from being stored as names, even if a user accidentally types one.

**Code reference:** `src/validators.py`, function `validate_slot()`, `student_name` branch (line ~180).

### Risk 3: LLM producing booking records with invalid data

**Description:** An LLM can hallucinate slot values (e.g., invent a date that is a past date, or return an instructor name not in the system).

**Implemented mitigation:** Every slot value returned by the LLM is validated by `state.apply_updates()` before being stored. `validate_slot` checks: instructor is in `instructors.json`; date is in the future and on a valid office-hour day; time is on :00/:30 and within office hours; topic and name meet length constraints. Only values that pass all checks are written to the state.

**Code reference:** `src/state.py`, function `apply_updates()` — calls `validate_slot` for every non-null update before `new[key] = value`.
