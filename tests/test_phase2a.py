"""
Phase 2a manual test — runs without Gemini.
Simulates a full booking conversation by feeding fake extractor output directly
into state.py + validators.py + bookings.py + policy.py.
"""
import sys
import os

# Add project root to path so imports work from any working directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state import new_state, apply_updates
from src.policy import next_action, detect_language
from src.bookings import check_availability

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label, condition):
    status = PASS if condition else FAIL
    results.append((label, status))
    print(f"  [{status}] {label}")


print("\n=== Phase 2a Tests ===\n")

# ── Test 1: language detection ──────────────────────────────────────────────
print("1. Language detection")
check("Arabic text detected as AR", detect_language("مرحبا") == "AR")
check("English text detected as EN", detect_language("Hello") == "EN")
check("Mixed text with Arabic detected as AR", detect_language("I want موعد please") == "AR")

# ── Test 2: new_state returns empty state ────────────────────────────────────
print("\n2. new_state()")
s = new_state()
check("All slots start as None", all(s[k] is None for k in ["instructor","date","time","topic","student_name","course_code"]))
check("confirmed starts False", s["confirmed"] is False)
check("step starts as 'greeting'", s["step"] == "greeting")

# ── Test 3: apply_updates — valid values ─────────────────────────────────────
print("\n3. apply_updates — valid values")
s = new_state()
s["_today"] = "2026-11-25"   # pin today so the date check is deterministic
updates = {
    "instructor":   "Dr. Sara (sample)",
    "date":         "2026-12-06",   # Sunday — Dr. Sara has Sunday hours
    "time":         "10:00",
    "topic":        "Assignment feedback",
    "student_name": "Hana Ali",
    "course_code":  "CS101",
}
s, errors = apply_updates(s, updates)
check("No validation errors", errors == [])
check("instructor saved", s["instructor"] == "Dr. Sara (sample)")
check("date saved", s["date"] == "2026-12-06")
check("time saved", s["time"] == "10:00")
check("course_code saved", s["course_code"] == "CS101")

# ── Test 4: apply_updates — None values not overwritten ──────────────────────
print("\n4. apply_updates — None does not overwrite existing slot")
s2, errors2 = apply_updates(s, {"instructor": None, "topic": "New topic"})
check("No errors", errors2 == [])
check("instructor unchanged (None in update)", s2["instructor"] == "Dr. Sara (sample)")
check("topic updated", s2["topic"] == "New topic")

# ── Test 5: validators — bad values ──────────────────────────────────────────
print("\n5. Validators — bad values")
from src.validators import validate_slot
base = {"instructor": "Dr. Sara (sample)", "date": "2026-12-06"}

check("Unknown instructor → error",
      validate_slot("instructor", "Dr. Nobody", {}) is not None)
check("Past date → error",
      validate_slot("date", "2020-01-01", {}) is not None)
check("Time not on :00/:30 → error",
      validate_slot("time", "10:15", base) is not None)
check("Time outside office hours → error",
      validate_slot("time", "13:00", base) is not None)  # Sara has no Sunday 13:00
check("Topic too short → error",
      validate_slot("topic", "hi", {}) is not None)
check("Name with digits → error",
      validate_slot("student_name", "Sara123", {}) is not None)
check("Invalid course code → error",
      validate_slot("course_code", "12XY", {}) is not None)
check("Valid course code → no error",
      validate_slot("course_code", "CS101", {}) is None)
check("Empty course code (optional) → no error",
      validate_slot("course_code", "", {}) is None)

# ── Test 6: check_availability ───────────────────────────────────────────────
print("\n6. check_availability")
result_free = check_availability("Dr. Sara (sample)", "2026-12-07", "09:00")
check("Free slot → available=True", result_free["available"] is True)

# 2026-12-13 10:00 is pre-booked in bookings.json (Sunday, within Dr. Sara's 09:00-12:00)
result_taken = check_availability("Dr. Sara (sample)", "2026-12-13", "10:00")
check("Pre-booked slot → available=False", result_taken["available"] is False)
check("Pre-booked slot → nearest slots returned", len(result_taken.get("nearest", [])) > 0)
print(f"       Nearest free slots: {result_taken.get('nearest')}")

# ── Test 7: policy — missing slot triggers ask ───────────────────────────────
print("\n7. policy.next_action — missing slot")
s = new_state()
s["language"] = "EN"
s["instructor"] = "Dr. Sara (sample)"
action = next_action(s, "provide_info", [])
check("Missing date → step is 'ask'", action["step"] == "ask")
check("Reply mentions date", "date" in action["reply"].lower())

# ── Test 8: policy — validation error triggers reask ─────────────────────────
print("\n8. policy.next_action — validation errors")
s = new_state()
s["language"] = "EN"
action = next_action(s, "provide_info", ["Unknown instructor 'Dr. X'."])
check("Errors present → step is 'reask'", action["step"] == "reask")

# ── Test 9: policy — full state → confirm step ───────────────────────────────
print("\n9. policy.next_action — all slots filled, free slot → confirm")
s = new_state()
s.update({
    "instructor": "Dr. Sara (sample)",
    "date":       "2026-12-06",
    "time":       "09:00",
    "topic":      "Project discussion",
    "student_name": "Lina Nasser",
    "language":   "EN",
})
action = next_action(s, "provide_info", [])
check("All slots filled + free → step is 'confirm'", action["step"] == "confirm")
check("Reply contains instructor name", "Dr. Sara" in action["reply"])

# ── Test 10: policy — off-topic → redirect ───────────────────────────────────
print("\n10. policy.next_action — off-topic")
s = new_state()
s["language"] = "EN"
action = next_action(s, "off_topic", [])
check("off_topic intent → step is 'redirect'", action["step"] == "redirect")

# ── Test 11: policy — cancel ─────────────────────────────────────────────────
print("\n11. policy.next_action — cancel")
s = new_state()
s["language"] = "EN"
action = next_action(s, "cancel", [])
check("cancel intent → step is 'cancelled'", action["step"] == "cancelled")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n=== Summary ===")
passed = sum(1 for _, r in results if r == PASS)
failed = sum(1 for _, r in results if r == FAIL)
print(f"  {passed} passed, {failed} failed out of {len(results)} checks\n")
if failed:
    print("FAILED checks:")
    for label, r in results:
        if r == FAIL:
            print(f"  - {label}")
    sys.exit(1)
