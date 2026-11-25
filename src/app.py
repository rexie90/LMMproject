"""
Mawid — office-hours booking chatbot.
Streamlit UI: chat window + sidebar slot panel + "New booking" button.
"""
from __future__ import annotations

import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv

# Load .env before importing anything that reads GOOGLE_API_KEY
load_dotenv()

from src.extractor import ExtractionError, extract
from src.llm_client import LLMError
from src.messages import greeting, llm_error
from src.policy import detect_language, next_action
from src.state import apply_updates, new_state

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mawid — موعد",
    page_icon="📅",
    layout="wide",
)

# ── session state bootstrap ───────────────────────────────────────────────────
if "booking_state" not in st.session_state:
    st.session_state.booking_state = new_state()
if "messages" not in st.session_state:
    # Start with the greeting message in English (default)
    st.session_state.messages = [
        {"role": "assistant", "content": greeting("EN")}
    ]
if "done" not in st.session_state:
    st.session_state.done = False  # True once booking saved or cancelled

# ── constants ─────────────────────────────────────────────────────────────────
_MAX_INPUT_CHARS = 500
_SLOT_LABELS = {
    "instructor":   "Instructor",
    "date":         "Date",
    "time":         "Time",
    "topic":        "Topic",
    "student_name": "Name",
    "course_code":  "Course code (optional)",
}

# ── sidebar: slot state panel ─────────────────────────────────────────────────
with st.sidebar:
    st.header("Booking Slots")
    state = st.session_state.booking_state
    for slot, label in _SLOT_LABELS.items():
        value = state.get(slot)
        if value:
            st.success(f"**{label}:** {value}")
        else:
            st.info(f"**{label}:** —")

    st.divider()
    if st.button("🗑 New booking", use_container_width=True):
        st.session_state.booking_state = new_state()
        lang = "EN"
        st.session_state.messages = [
            {"role": "assistant", "content": greeting(lang)}
        ]
        st.session_state.done = False
        st.rerun()

# ── main: chat window ─────────────────────────────────────────────────────────
st.title("Mawid — موعد")
st.caption("Office-hours booking assistant · Umm Al-Qura University")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── input bar ─────────────────────────────────────────────────────────────────
if st.session_state.done:
    st.chat_input("Booking complete. Click 'New booking' to start again.", disabled=True)
else:
    user_input = st.chat_input("Type your message here…")
    if user_input is not None:
        user_input = user_input.strip()

        # --- input validation ---
        if not user_input:
            st.warning("Please type a message before sending.")
            st.stop()

        if len(user_input) > _MAX_INPUT_CHARS:
            st.warning(
                f"Your message is too long ({len(user_input)} characters). "
                f"Please keep it under {_MAX_INPUT_CHARS} characters."
            )
            st.stop()

        # --- show user message ---
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # --- detect language and update state ---
        lang = detect_language(user_input)
        st.session_state.booking_state["language"] = lang

        today = str(date.today())

        # --- call LLM + run dialogue logic ---
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    extraction = extract(
                        user_input,
                        st.session_state.booking_state,
                        today,
                        prompt_version="v2",
                    )
                    intent = extraction["intent"]
                    updates = extraction["updates"]

                    # apply slot updates (also runs validation)
                    new_booking_state, errors = apply_updates(
                        st.session_state.booking_state, updates
                    )
                    st.session_state.booking_state = new_booking_state

                    # decide next step
                    action = next_action(
                        st.session_state.booking_state, intent, errors
                    )

                    reply = action["reply"]
                    step = action["step"]

                    if step in ("booked", "cancelled"):
                        st.session_state.done = True

                except (LLMError, ExtractionError) as e:
                    reply = llm_error(lang)
                    print(f"[Mawid app] Error in dialogue: {type(e).__name__}: {e}")

            st.markdown(reply)

        st.session_state.messages.append({"role": "assistant", "content": reply})

        # --- refresh sidebar immediately ---
        st.rerun()
