# Mawid — Architecture

## Component Diagram

```mermaid
flowchart LR
    Student([Student\nAR or EN]) -->|types message| UI

    subgraph UI [Streamlit UI — app.py]
        direction TB
        A1[language detect]
        A2[input validation]
        A3[render reply\nRTL / LTR]
    end

    UI -->|message + state| EXT

    subgraph LLM_Layer [LLM Layer]
        direction TB
        EXT[extractor.py\nextract]
        PR[prompts.py\nbuild_system_prompt\nv1 or v2]
        LC[llm_client.py\ncall_llm\nprimary → fallback1 → fallback2]
        EXT --> PR
        PR -->|system prompt| LC
        LC -->|raw JSON| EXT
    end

    EXT -->|intent + slot updates| UI

    subgraph Dialogue [Dialogue Core]
        direction TB
        ST[state.py\napply_updates\ncross-validation]
        VAL[validators.py\nvalidate_slot\nper-slot rules]
        POL[policy.py\nnext_action\nstep decision]
        BK[bookings.py\ncheck_availability\nsave_booking]
        ST --> VAL
        VAL -->|errors| ST
        ST -->|state + errors| POL
        POL --> BK
        BK -->|booking_id| POL
    end

    UI --> Dialogue
    POL -->|step + reply| UI
    UI -->|reply| Student

    BK <-->|read / write| JSON[(bookings_runtime.json)]
    PR <-->|read| INST[(instructors.json)]
```

## Data Flow (one turn)

1. **User types a message** in the Streamlit chat input.
2. **`app.py`** detects the language (Arabic letters present → AR, else EN), validates input length, and sets `state["language"]` and `state["_today"]`.
3. **`extractor.extract()`** builds a system prompt (`prompts.build_system_prompt`, v2 in production) and calls **`llm_client.call_llm()`**.
4. **`llm_client`** tries the primary model (Gemini 3.8-flash) with retry logic. On 429 it immediately switches to the fallback chain (3.5-flash-lite → 3.1-flash-lite) and blocks the primary for 10 minutes. Returns the raw text response.
5. **`extractor`** strips JSON fences, parses the response, and returns `{"intent": ..., "updates": {...}}`.
6. **`state.apply_updates()`** validates each changed slot via **`validators.validate_slot()`**, then cross-validates dependent slots (instructor change → re-check date; date change → re-check time). Returns the new state and any error strings.
7. **`policy.next_action()`** decides the next dialogue step (ask, reask, suggest, confirm, booked, cancelled, redirect). For `confirm` intent with all slots filled, it calls **`bookings.check_availability()`**. For `booked` step, it calls **`bookings.save_booking()`** which writes to `bookings_runtime.json` and returns a booking ID.
8. **`app.py`** renders the reply with `_render_reply()`: AR messages go in an RTL HTML div with dates/times/IDs wrapped in `<span dir="ltr">` to prevent reversal; EN messages use standard `st.markdown`.

## Key Design Decision

**The model understands; the code decides.**  
The LLM's only job is to extract *intent* and *slot values* from free text — including resolving relative dates using today's date provided in the prompt. All validation, availability checking, state management, and next-step logic are handled by deterministic Python code. This prevents the LLM from making booking decisions or producing inconsistent states, and makes the system testable without LLM calls for the core logic (see `tests/test_phase2a.py`).
