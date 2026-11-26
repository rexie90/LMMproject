# Mawid — Presentation Outline
## 8–10 Minutes | Week 15 Live Demo

---

## Slide 1: Title (30 s — Retaj)

**Mawid — موعد**  
Office-Hours Appointment Booking Chatbot

CS4509 – Special Topics I: LLM Applications  
Group [XX] | Umm Al-Qura University

Members: Retaj · Lina · Raghad · Taleen

---

## Slide 2: Problem & Motivation (~1 min — Retaj)

**The problem:**
- Students must manually check schedules, call or email faculty, and confirm appointments.
- Fully in free-form Arabic or English — hard to automate with rule-based systems.
- Relative date expressions ("الأحد الجاي", "next Monday") require language understanding.

**Why an LLM?**
- Free-text understanding in both Arabic and English.
- Relative date and time resolution from natural language.
- One model handles both languages without switching.

**Target users:** UQU students booking office-hours appointments.

---

## Slide 3: Design and Architecture (~2 min — Lina)

**Core principle:** The model understands; the code decides.

**Slots collected:** instructor · date · time · topic · student name (+ optional course code)

**Architecture (Mermaid diagram):**

```
Student → Streamlit UI → Extractor (Gemini) → State + Validators → Policy → Bookings JSON
```

**Dialogue steps:** greeting → slot filling → validation → availability check → confirmation → save

**Key design decisions:**
- JSON extractor contract between LLM and code
- All validation and availability logic is in Python (testable without LLM)
- Bilingual: language detected per turn; replies match input language

---

## Slide 4: Live Demo (~3 min — Raghad)

> **Follow the demo script below exactly.**

### Demo Script

**Scenario:** Student books Dr. Sara on a Sunday, discovers the slot is taken, corrects to a free slot, then corrects her name before confirming.

---

**[Bot shows bilingual greeting — point to it, note the RTL Arabic block and LTR English block]**

**Turn 1 — give instructor only (English):**
```
I want to book with Dr. Sara
```
*Expected: bot asks for date. Sidebar shows Instructor filled.*

**Turn 2 — give date and time (all in one message):**
```
Sunday December 13 at 10:00
```
*Expected: bot says slot is taken (MWD-20261213-0001 is pre-booked at 10:00), suggests 09:30 or 10:30.*

**Turn 3 — pick a free slot:**
```
10:30
```
*Expected: bot asks for topic.*

**Turn 4 — give topic:**
```
I need help with my project proposal
```
*Expected: bot asks for name.*

**Turn 5 — give name:**
```
Sara Mohammed
```
*Expected: bot shows confirmation summary with all fields on separate lines.*

**[Point to the sidebar — all 5 required slots are green.]**

**Turn 6 — make a correction:**
```
No, change my name to Sara Al-Mohammed
```
*Expected: bot shows updated summary with corrected name.*

**Turn 7 — confirm:**
```
Yes
```
*Expected: bot shows "Booking confirmed!" with booking ID and JSON record.*

**[Point to the booking ID (MWD-YYYYMMDD-NNNN) and the JSON structure.]**

---

### Backup Plan (if API fails during demo)

1. If Gemini returns a 429 during the demo, the app automatically falls back to `gemini-3.5-flash-lite` or `gemini-3.1-flash-lite` — the demo continues without interruption.
2. If all three models are unavailable: show the browser-recorded video (`presentation/demo_recording.mp4`).
3. Walk through `evaluation/test_results.csv` and explain the test flow verbally.

---

## Slide 5: Prompt Engineering (~1 min — Retaj)

**v1 (baseline):** task description only, no examples, no instructor list, no context.

**v2 (improved):**
- Role + Task + Format structure (Wk4 slide 18)
- Instructor list with office hours in context
- Today's date + pre-computed relative dates
- Section delimiters (##) separating role / context / rules / examples (Wk4 slides 21–23)
- 4 few-shot examples (Wk3 slides 21–31)
- Null-on-ambiguity rule (Rule 3)
- `asking_for` hint (Rule 11): when bot asked for a specific slot, short plain answers are classified as that slot's value, not off_topic

**Key improvement:** v1 misclassifies "I need help with my final project" as `off_topic` when bot asked for the topic. v2 correctly extracts it as the topic value.

**[Show comparison table from evaluation/prompt_comparison.md]**

---

## Slide 6: Evaluation Results (~1 min — Taleen)

**[Show evaluation/test_results.csv results]**

| Test | Scenario | Result |
|---|---|---|
| T1 | Normal multi-turn EN | [result] |
| T2 | Single message Arabic | [result] |
| T3 | Booked slot + correction | [result] |
| T4 | Ambiguous/incomplete | [result] |
| T5 | Invalid/unsupported | [result] |

**Key observations:** [from analysis.md]

---

## Slide 7: Responsible AI (~30 s — Taleen)

**Risks and mitigations:**

1. **Saving incorrect data** → Explicit confirmation before `save_booking()` (policy.py)
2. **Collecting unnecessary personal data** → No student ID or phone number; name only (validators.py)
3. **LLM producing invalid bookings** → All slot values re-validated in Python before saving (state.py)

---

## Slide 8: Limitations and Conclusion (~1 min — Taleen)

**Limitations:**
- Local deployment only — no hosting or authentication
- Free-tier rate limits (handled via fallback chain)
- Sample instructors only (not a real faculty directory)
- LLM non-determinism: occasional misclassification despite v2 improvements

**Conclusion:**
Mawid shows that an LLM can be used as a natural-language front-end while keeping booking logic deterministic and testable in Python. The bilingual, multi-turn design handles Arabic and English in a single conversation with no language switching.

---

## Slide 9: Q&A

**Thank you!**

Questions?

---

## Member Q&A Prep (brief)

Each member should be ready to explain her files, the relevant course slide, and how her code connects to the others. See `.claude_work/member_guides.md` for the full preparation guide.
