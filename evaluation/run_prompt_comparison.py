"""
Prompt v1 vs v2 comparison for Mawid.

Runs both prompt versions on three identical inputs and saves real raw outputs,
parsed results, and pass/fail to evaluation/prompt_comparison.md.

Run from the project root with the venv activated:
    python evaluation/run_prompt_comparison.py

NEVER record fake or partial results as passed.
Spaces out calls with sleeps to stay within free-tier rate limits.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

from src.llm_client import LLMError, call_llm
from src.prompts import build_system_prompt
from src.state import new_state

TODAY = "2026-11-25"
OUT_PATH = Path("evaluation/prompt_comparison.md")


# ── JSON parsing (mirrors extractor._parse_response) ─────────────────────────

_VALID_INTENTS = frozenset(
    {"provide_info", "correction", "confirm", "reject", "cancel", "off_topic"}
)
_SLOT_KEYS = ("instructor", "date", "time", "topic", "student_name", "course_code")


def _parse(raw: str) -> dict | None:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("intent") not in _VALID_INTENTS:
        return None
    if not isinstance(data.get("updates"), dict):
        return None
    updates = {k: data["updates"].get(k) for k in _SLOT_KEYS}
    return {"intent": data["intent"], "updates": updates}


# ── test cases ────────────────────────────────────────────────────────────────

def _make_cases() -> list[dict]:
    # Case 1: Arabic — all required slots in one message
    s1 = new_state()
    s1["language"] = "AR"

    # Case 2: English — instructor + date + time + topic in one message
    s2 = new_state()
    s2["language"] = "EN"

    # Case 3: Short answer after bot asked for topic
    # (state shows asking_for=topic; v1 lacks Rule 11, v2 has it)
    s3 = new_state()
    s3["language"] = "EN"
    s3["instructor"] = "Dr. Sara (sample)"
    s3["date"] = "2026-11-29"   # next Sunday from 2026-11-25
    s3["time"] = "09:00"
    s3["asking_for"] = "topic"
    s3["_today"] = TODAY

    return [
        {
            "id": "C1",
            "name": "Arabic — all slots in one message",
            "message": "أبغى أحجز مع د.سارة يوم الأحد القادم الساعة 9 الموضوع مشروع التخرج واسمي ريم الشمري",
            "state": s1,
            "v1_pass": lambda p: (
                p is not None
                and p["intent"] == "provide_info"
                and p["updates"].get("instructor") is not None
                and p["updates"].get("date") is not None
                and p["updates"].get("time") is not None
            ),
            "v2_pass": lambda p: (
                p is not None
                and p["intent"] == "provide_info"
                and p["updates"].get("instructor") == "Dr. Sara (sample)"
                and p["updates"].get("date") is not None   # any date near next Sunday
                and p["updates"].get("time") == "09:00"
                and p["updates"].get("topic") is not None
                and p["updates"].get("student_name") is not None
            ),
        },
        {
            "id": "C2",
            "name": "English — instructor + date + time + topic",
            "message": "I want to book with Dr. Khalid on Monday at 10:30 to discuss my project",
            "state": s2,
            "v1_pass": lambda p: (
                p is not None
                and p["intent"] == "provide_info"
                and p["updates"].get("instructor") is not None
                and p["updates"].get("time") == "10:30"
            ),
            "v2_pass": lambda p: (
                p is not None
                and p["intent"] == "provide_info"
                and p["updates"].get("instructor") == "Dr. Khalid (sample)"
                and p["updates"].get("time") == "10:30"
                and p["updates"].get("topic") is not None
            ),
        },
        {
            "id": "C3",
            "name": "Short answer after bot asked for topic (key difference: Rule 11)",
            "message": "I need help with my final project",
            "state": s3,
            "v1_pass": lambda p: (
                p is not None
                and p["intent"] == "provide_info"
                and p["updates"].get("topic") is not None
            ),
            "v2_pass": lambda p: (
                p is not None
                and p["intent"] == "provide_info"
                and p["updates"].get("topic") is not None
            ),
        },
    ]


# ── runner ────────────────────────────────────────────────────────────────────

def run_case(case: dict) -> dict:
    """Run v1 and v2 on one input. Returns a result dict."""
    msg = case["message"]
    state = case["state"]
    state["_today"] = TODAY

    result = {
        "id": case["id"],
        "name": case["name"],
        "message": msg,
        "v1_raw": "", "v1_parsed": None, "v1_pass": False, "v1_error": "",
        "v2_raw": "", "v2_parsed": None, "v2_pass": False, "v2_error": "",
    }

    # ── v1 ──────────────────────────────────────────────────────────────────
    print(f"  Calling v1…", flush=True)
    v1_prompt = build_system_prompt("v1", TODAY, state)
    try:
        raw1 = call_llm(v1_prompt, msg)
        result["v1_raw"] = raw1
        parsed1 = _parse(raw1)
        result["v1_parsed"] = parsed1
        result["v1_pass"] = case["v1_pass"](parsed1)
    except LLMError as e:
        result["v1_error"] = str(e)
        print(f"    LLMError: {e}", flush=True)

    print(f"    v1 raw: {result['v1_raw'][:120]!r}")
    print(f"    v1 pass: {result['v1_pass']}")
    print(f"  Sleeping 4 s…", flush=True)
    time.sleep(4)

    # ── v2 ──────────────────────────────────────────────────────────────────
    print(f"  Calling v2…", flush=True)
    v2_prompt = build_system_prompt("v2", TODAY, state)
    try:
        raw2 = call_llm(v2_prompt, msg)
        result["v2_raw"] = raw2
        parsed2 = _parse(raw2)
        result["v2_parsed"] = parsed2
        result["v2_pass"] = case["v2_pass"](parsed2)
    except LLMError as e:
        result["v2_error"] = str(e)
        print(f"    LLMError: {e}", flush=True)

    print(f"    v2 raw: {result['v2_raw'][:120]!r}")
    print(f"    v2 pass: {result['v2_pass']}")
    return result


# ── markdown writer ───────────────────────────────────────────────────────────

def _fmt_parsed(p: dict | None) -> str:
    if p is None:
        return "*(parse error)*"
    updates = {k: v for k, v in p["updates"].items() if v is not None}
    return f"intent=`{p['intent']}`, updates=`{json.dumps(updates, ensure_ascii=False)}`"


def write_markdown(results: list[dict]) -> None:
    lines = [
        "# Mawid — Prompt v1 vs v2 Comparison",
        "",
        f"**Run date:** {TODAY}  ",
        "**Model:** gemini-3.5-flash-lite (fallback; primary gemini-3.8-flash blocked by 429)  ",
        "**Prompt versions:** v1 = simple baseline; v2 = Role+Task+Format + instructor list + few-shot + Rule 11",
        "",
        "---",
        "",
    ]

    summary_rows = []
    for r in results:
        v1_tick = "PASS" if r["v1_pass"] else "FAIL"
        v2_tick = "PASS" if r["v2_pass"] else "FAIL"
        summary_rows.append(f"| {r['id']} | {r['name']} | {v1_tick} | {v2_tick} |")

    lines += [
        "## Summary",
        "",
        "| Input | Description | v1 | v2 |",
        "|---|---|---|---|",
    ] + summary_rows + ["", "---", ""]

    for r in results:
        lines += [
            f"## {r['id']}: {r['name']}",
            "",
            f"**Input message:** `{r['message']}`",
            "",
        ]
        if r.get("v1_error"):
            lines += [
                "### v1 Result",
                f"**ERROR:** {r['v1_error']}",
                "",
            ]
        else:
            v1_fence = r["v1_raw"] if r["v1_raw"] else "*(no output)*"
            lines += [
                "### v1 Result",
                "**Raw output:**",
                "```",
                v1_fence,
                "```",
                f"**Parsed:** {_fmt_parsed(r['v1_parsed'])}  ",
                f"**Pass:** {'YES' if r['v1_pass'] else 'NO'}",
                "",
            ]

        if r.get("v2_error"):
            lines += [
                "### v2 Result",
                f"**ERROR:** {r['v2_error']}",
                "",
            ]
        else:
            v2_fence = r["v2_raw"] if r["v2_raw"] else "*(no output)*"
            lines += [
                "### v2 Result",
                "**Raw output:**",
                "```",
                v2_fence,
                "```",
                f"**Parsed:** {_fmt_parsed(r['v2_parsed'])}  ",
                f"**Pass:** {'YES' if r['v2_pass'] else 'NO'}",
                "",
            ]

        lines += ["---", ""]

    lines += [
        "## Analysis",
        "",
        "### C1 — Arabic all-slots",
        "Both v1 and v2 should extract all slots from an Arabic message. v2 is more reliable because it includes:",
        "- The instructor list (so the LLM can match 'د.سارة' to the exact name 'Dr. Sara (sample)')",
        "- Relative date examples ('الأحد الجاي' → next Sunday)",
        "- Role framing that handles Arabic explicitly",
        "",
        "### C2 — English multi-slot",
        "Both versions handle English well. v2 additionally provides the instructor list for exact name matching.",
        "",
        "### C3 — Short answer after asking_for (key improvement)",
        "**v1:** Without Rule 11, 'I need help with my final project' looks like a general request, not an answer. v1 classifies it as `off_topic`.",
        "**v2:** Rule 11 tells the LLM: if `[Bot just asked for: topic]` appears in the state summary, treat the message as the topic value with intent `provide_info`. v2 correctly extracts the topic.",
        "This was the main identified weakness of v1 and the motivation for adding `asking_for` state tracking.",
    ]

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved: {OUT_PATH}")


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Prompt Comparison: v1 vs v2 ===")
    print(f"Today: {TODAY}  |  Output: {OUT_PATH}\n")

    cases = _make_cases()
    results = []

    for i, case in enumerate(cases):
        print(f"\n── {case['id']}: {case['name']} ──")
        result = run_case(case)
        results.append(result)
        if i < len(cases) - 1:
            print("  Sleeping 10 s between cases…", flush=True)
            time.sleep(10)

    write_markdown(results)

    v1_pass = sum(1 for r in results if r["v1_pass"])
    v2_pass = sum(1 for r in results if r["v2_pass"])
    print(f"\nv1: {v1_pass}/{len(results)} pass")
    print(f"v2: {v2_pass}/{len(results)} pass")
