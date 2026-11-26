# Mawid — موعد

**Mawid** (Arabic for "appointment") is a bilingual, multi-turn chatbot that books a university student an office-hours appointment with a faculty member and produces a structured booking record. Built for CS4509 – Special Topics I: LLM Applications at Umm Al-Qura University.

## Features

- **Bilingual (Arabic / English):** Detects the user's language turn by turn and replies in the same language. Arabic replies are rendered right-to-left.
- **Multi-turn slot filling:** Collects five required fields (instructor, date, time, topic, student name) and one optional field (course code) across any number of turns.
- **LLM-powered understanding:** Uses Gemini to interpret free-text input, resolve relative dates ("next Sunday", "بكرة"), and handle ambiguous expressions.
- **Code-side validation:** All business rules are enforced by Python, not the LLM — office-hour windows, day restrictions, :00/:30 slots, future dates, and duplicate-booking checks.
- **Conflict detection:** Checks availability before confirming. If a slot is taken, suggests the nearest free times.
- **Correction without restart:** Users can change any field after seeing the summary; only that field is re-validated.
- **Structured output:** Confirmation summary followed by a JSON booking record with a unique booking ID (MWD-YYYYMMDD-NNNN).
- **Graceful error handling:** Covers missing/invalid API key, 429 rate limit, 503 overload, timeout, 404 model, and malformed JSON — without crashing.

## Setup

### Prerequisites

- Python 3.11
- A free [Google AI Studio](https://aistudio.google.com/) account for a Gemini API key

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/rexie90/LMMproject.git
cd LMMproject

# 2. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate.bat     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Open .env and replace "your_api_key_here" with your real key
```

Your `.env` should look like:

```
GOOGLE_API_KEY=AIza...
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODEL_2=gemini-3.1-flash-lite
```

> **Note:** `gemini-2.5-flash` returns 404 for new API keys (Google limits it to accounts that previously used it). The app uses `gemini-3.8-flash` as primary. If that is unavailable or rate-limited, it automatically falls back to `gemini-3.5-flash-lite`, then `gemini-3.1-flash-lite`.

## Running the App

```bash
source .venv/bin/activate   # if not already active
streamlit run src/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser. The sidebar shows which booking slots are filled. Click **New booking** to start over.

## Running the Tests

```bash
# Unit tests (no API calls, deterministic)
python tests/test_phase2a.py     # 40 checks
python tests/test_app.py         # UI smoke test (5 checks)

# Official T1–T5 (real Gemini calls — requires API key)
python tests/run_tests.py        # writes evaluation/test_results.csv

# Prompt comparison (real Gemini calls)
python evaluation/run_prompt_comparison.py   # writes evaluation/prompt_comparison.md
```

## Project Structure

```
LLMproject/
├── src/
│   ├── app.py            # Streamlit UI: chat window + sidebar + "New booking"
│   ├── llm_client.py     # Gemini API wrapper: timeout, retry, fallback
│   ├── prompts.py        # System prompt builder: v1 (baseline) and v2 (improved)
│   ├── extractor.py      # Calls LLM and parses extractor JSON
│   ├── messages.py       # All user-facing reply strings (AR and EN)
│   ├── state.py          # Slot state struct + apply_updates (with cross-validation)
│   ├── validators.py     # Per-slot validation rules (instructor, date, time, etc.)
│   ├── bookings.py       # Availability check + save_booking → bookings_runtime.json
│   └── policy.py         # next_action: decides the next dialogue step and reply
├── data/
│   ├── instructors.json  # Three sample instructors with office-hour schedules
│   └── bookings.json     # Committed sample with one pre-booked slot (read-only)
├── tests/
│   ├── run_tests.py      # Official T1–T5 runner (real Gemini)
│   ├── test_phase2a.py   # Unit tests: validators, state, policy (40 checks)
│   ├── test_app.py       # Streamlit smoke test (5 checks)
│   └── test_plan.md      # T1–T5 test plan with expected behavior
├── evaluation/
│   ├── run_prompt_comparison.py  # v1 vs v2 comparison on real Gemini
│   ├── prompt_comparison.md      # Results of prompt comparison
│   ├── test_results.csv          # Official T1–T5 results
│   └── analysis.md               # Failure analysis + Responsible AI
├── report/
│   ├── technical_report.md       # Full technical report
│   └── architecture.md           # Architecture diagram (Mermaid)
├── presentation/
│   └── slides_outline.md         # 8–10 min slide deck + demo script
├── requirements.txt
├── .env.example
└── README.md
```

## Models

| Variable | Model | Role |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.8-flash` | Primary |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash-lite` | First fallback (if primary is 429/503/timeout) |
| `GEMINI_FALLBACK_MODEL_2` | `gemini-3.1-flash-lite` | Second fallback |

`gemini-2.5-flash` is **not** used: it returns HTTP 404 for new API keys (Google restricts access to accounts with prior usage). This is noted in the report.

## Known Limitations

- **Local only:** No deployment; requires the user to have Python 3.11 and a Gemini API key.
- **Rate limits:** The free Gemini tier limits requests per minute. The app handles this with an automatic 10-minute block on 429 and fallback to alternative models.
- **Sample instructors only:** The three instructors and their office hours are fictional samples for demonstration purposes.
- **No authentication:** The chatbot takes the student's name as input; it cannot verify identity.
- **English office-hour format in errors:** Office-hour day names in error messages are translated to Arabic, but time ranges use the HH:MM format in both languages.

## Course

CS4509 – Special Topics I: LLM Applications  
Umm Al-Qura University, Jamoum University College  
Group project — Track C (Task-Oriented Chatbot)
