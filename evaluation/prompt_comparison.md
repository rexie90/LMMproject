# Mawid — Prompt v1 vs v2 Comparison

**Run date:** 2026-11-25  
**Model:** gemini-3.5-flash-lite (fallback; primary gemini-3.8-flash blocked by 429)  
**Prompt versions:** v1 = simple baseline; v2 = Role+Task+Format + instructor list + few-shot + Rule 11

**Pass criterion:** For C1 and C2, PASS means the extracted instructor name exactly matches an entry in `instructors.json` as required by `validators.validate_slot("instructor", ...)`. An unnormalized name (e.g., "Dr. Khalid" instead of "Dr. Khalid (sample)") is **not in the JSON file and fails validation** — the booking cannot proceed. For C3, PASS means intent=`provide_info` and topic is not null.

---

## Summary

| Input | Description | v1 | v2 |
|---|---|---|---|
| C1 | Arabic — all slots in one message | **FAIL** | PASS |
| C2 | English — instructor + date + time + topic | **FAIL** | PASS |
| C3 | Short answer after bot asked for topic (triple run) | 3/3 PASS | 3/3 PASS |

---

## C1: Arabic — all slots in one message

**Input message:** `أبغى أحجز مع د.سارة يوم الأحد القادم الساعة 9 الموضوع مشروع التخرج واسمي ريم الشمري`

### v1 Result
**Raw output:**
```
{"intent": "provide_info", "updates": {"instructor": "د.سارة", "date": "2026-11-29", "time": "09:00", "topic": "مشروع التخرج", "student_name": "ريم الشمري", "course_code": null}}
```
**Parsed:** intent=`provide_info`, updates=`{"instructor": "د.سارة", "date": "2026-11-29", "time": "09:00", "topic": "مشروع التخرج", "student_name": "ريم الشمري"}`  
**Pass:** **NO** — `"د.سارة"` is not in `instructors.json`; `validate_slot("instructor", "د.سارة", ...)` returns an error. The booking cannot proceed without an exact name match.

### v2 Result
**Raw output:**
```
{
  "intent": "provide_info",
  "updates": {
    "instructor": "Dr. Sara (sample)",
    "date": "2026-11-29",
    "time": "09:00",
    "topic": "مشروع التخرج",
    "student_name": "ريم الشمري",
    "course_code": null
  }
}
```
**Parsed:** intent=`provide_info`, updates=`{"instructor": "Dr. Sara (sample)", "date": "2026-11-29", "time": "09:00", "topic": "مشروع التخرج", "student_name": "ريم الشمري"}`  
**Pass:** YES

---

## C2: English — instructor + date + time + topic

**Input message:** `I want to book with Dr. Khalid on Monday at 10:30 to discuss my project`

### v1 Result
**Raw output:**
```
{"intent": "provide_info", "updates": {"instructor": "Dr. Khalid", "date": "2026-11-30", "time": "10:30", "topic": "project", "student_name": null, "course_code": null}}
```
**Parsed:** intent=`provide_info`, updates=`{"instructor": "Dr. Khalid", "date": "2026-11-30", "time": "10:30", "topic": "project"}`  
**Pass:** **NO** — `"Dr. Khalid"` is not in `instructors.json` (the stored name is `"Dr. Khalid (sample)"`); `validate_slot("instructor", "Dr. Khalid", ...)` returns an error.

### v2 Result
**Raw output:**
```
{
  "intent": "provide_info",
  "updates": {
    "instructor": "Dr. Khalid (sample)",
    "date": "2026-11-30",
    "time": "10:30",
    "topic": "discuss my project",
    "student_name": null,
    "course_code": null
  }
}
```
**Parsed:** intent=`provide_info`, updates=`{"instructor": "Dr. Khalid (sample)", "date": "2026-11-30", "time": "10:30", "topic": "discuss my project"}`  
**Pass:** YES

---

## C3: Short answer after bot asked for topic (triple run, key difference: Rule 11)

**Input message:** `I need help with my final project`  
**State context:** instructor="Dr. Sara (sample)", date="2026-11-29", time="09:00", asking_for="topic"

C3 was run three times for each version to test consistency (LLM non-determinism). v1 never receives the `[Bot just asked for: topic]` hint (not in its prompt); v2 receives it via Rule 11.

### v1 — 3 runs

| Run | intent | topic | Pass |
|---|---|---|---|
| 1 | provide_info | "final project" | YES |
| 2 | provide_info | "final project" | YES |
| 3 | provide_info | "final project" | YES |

**v1: 3/3 PASS on this model.** The sentence "I need help with my final project" was interpreted as providing the topic on all three runs with gemini-3.5-flash-lite.

### v2 — 3 runs

| Run | intent | topic | Pass |
|---|---|---|---|
| 1 | provide_info | "I need help with my final project" | YES |
| 2 | provide_info | "I need help with my final project" | YES |
| 3 | provide_info | "final project" | YES |

**v2: 3/3 PASS on this model.** Rule 11 fires consistently; v2 occasionally returns the full sentence as the topic value.

---

## Analysis

### C1 — Arabic all-slots

Both versions extracted intent and date/time/topic/name correctly. **Critical difference:** v1 returned `instructor="د.سارة"` (the user's Arabic shorthand) while v2 returned `instructor="Dr. Sara (sample)"` (the exact name from the instructor list). In production, v1's output would fail `validate_slot("instructor", ...)` because validation requires an exact match. v2 is reliable here because the instructor list is part of the prompt context and Rule 9 instructs: *"only use names exactly as listed"*.

### C2 — English multi-slot

Same instructor name normalization gap: v1 returned `instructor="Dr. Khalid"` (not in `instructors.json`) while v2 returned `instructor="Dr. Khalid (sample)"` (exact match). In a real conversation, v1 would trigger a validation error asking the user to pick from the instructor list; v2 proceeds directly to the next slot. v2 also returned a more complete topic ("discuss my project" vs v1's "project").

### C3 — Short answer after asking_for

Both v1 and v2 passed all three runs with gemini-3.5-flash-lite. This should be reported honestly: on this model, the sentence "I need help with my final project" is recognised as a topic value even by v1.

**Historical context:** during iterative development of v2, an earlier version of v2 (before Rule 11 was added) classified this message as `off_topic` in a T1 rehearsal run. The T1 test runner used `prompt_version="v2"` throughout; v2 was improved by adding the `asking_for` state field and Rule 11. The fix was applied within v2, not by switching from v1 to v2. Rule 11 makes the behaviour explicit and model-independent; without it, the correct response depends on the model's internal tendencies and may not hold for a different model or a future update.

### Overall Conclusion

v2 outperforms v1 in two measurable, reproducible ways:
1. **Instructor name normalization (C1, C2):** v2's instructor list and Rule 9 ensure the exact stored name is returned, which is required for `validate_slot("instructor", ...)` to pass. v1 returns the user's raw text ("Dr. Khalid", "د.سارة"), which fails validation — C1 and C2 FAIL under the correct pass criterion.
2. **Explicit short-answer classification (C3):** v2's Rule 11 makes the correct topic extraction explicit and rule-driven. On gemini-3.5-flash-lite, v1 also passed all three runs, so there is no measured unreliability on this model for C3. The historical failure was in v2 before Rule 11 was added.