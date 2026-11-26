"""
Streamlit UI smoke test using AppTest.
Verifies the app starts without exceptions and renders the bilingual greeting.

Run from the project root:
    python tests/test_app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

from streamlit.testing.v1 import AppTest

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str]] = []


def check(label: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    results.append((label, status))
    print(f"  [{status}] {label}")


print("\n=== App Smoke Test ===\n")

_app_path = str(Path(__file__).resolve().parent.parent / "src" / "app.py")
at = AppTest.from_file(_app_path, default_timeout=30)
at.run(timeout=30)

check("App starts without exception", not at.exception)
if at.exception:
    print(f"    Exception: {at.exception}")

# Session state should have the initial assistant message
messages = None
try:
    messages = at.session_state["messages"]
except (KeyError, TypeError, AttributeError):
    pass

check("Session state has messages list", messages is not None and len(messages) > 0)

if messages:
    first = messages[0]
    check("First message role is assistant", first.get("role") == "assistant")
    content = first.get("content", "")
    check("Greeting contains English text ('Hello')", "Hello" in content)
    check("Greeting contains Arabic text ('مرحباً')", "مرحباً" in content)

# Summary
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
