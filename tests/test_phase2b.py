"""
Phase 2b smoke test — makes ONE real Gemini call to verify the LLM stack.
Run from the project root with the venv activated:
    python tests/test_phase2b.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from src.state import new_state
from src.extractor import extract
from src.llm_client import call_llm

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label, condition):
    status = PASS if condition else FAIL
    results.append((label, status))
    print(f"  [{status}] {label}")


print("\n=== Phase 2b Smoke Test ===\n")

# ── 1: call_llm returns a non-empty string ───────────────────────────────────
print("1. call_llm — basic round-trip")
try:
    reply = call_llm("Reply with exactly the word: OK", "ping", timeout_s=30)
    print(f"   Model replied: {reply[:80]!r}")
    check("call_llm returns non-empty string", bool(reply))
    check("Reply contains 'OK'", "OK" in reply)
except Exception as e:
    print(f"   ERROR: {e}")
    check("call_llm returned without crashing", False)
    check("Reply contains 'OK'", False)

# ── 2: extract — English message, all required fields ───────────────────────
print("\n2. extract — full English message")
state = new_state()
state["language"] = "EN"
today = "2026-11-25"
msg = (
    "I want to book with Dr. Sara on Sunday 2026-11-29 at 10:00 "
    "about my project. My name is Hana Ali."
)
try:
    result = extract(msg, state, today, prompt_version="v2")
    print(f"   intent  : {result['intent']}")
    print(f"   updates : {result['updates']}")
    check("intent = provide_info", result["intent"] == "provide_info")
    check("instructor extracted", "Sara" in (result["updates"].get("instructor") or ""))
    check("date extracted", result["updates"].get("date") is not None)
    check("time extracted", result["updates"].get("time") == "10:00")
    check("student_name extracted", result["updates"].get("student_name") is not None)
except Exception as e:
    print(f"   ERROR: {e}")
    for label in ("intent = provide_info", "instructor extracted",
                  "date extracted", "time extracted", "student_name extracted"):
        check(label, False)

# ── 3: extract — Arabic confirmation ────────────────────────────────────────
print("\n3. extract — Arabic 'yes'")
try:
    r = extract("نعم", new_state(), today, prompt_version="v2")
    print(f"   intent: {r['intent']}")
    check("Arabic 'نعم' → intent = confirm", r["intent"] == "confirm")
    check("All updates are None", all(v is None for v in r["updates"].values()))
except Exception as e:
    print(f"   ERROR: {e}")
    check("Arabic 'نعم' → intent = confirm", False)
    check("All updates are None", False)

# ── 4: extract — off-topic ───────────────────────────────────────────────────
print("\n4. extract — off-topic message")
try:
    r = extract("What is the capital of France?", new_state(), today, prompt_version="v2")
    print(f"   intent: {r['intent']}")
    check("Off-topic → intent = off_topic", r["intent"] == "off_topic")
except Exception as e:
    print(f"   ERROR: {e}")
    check("Off-topic → intent = off_topic", False)

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
