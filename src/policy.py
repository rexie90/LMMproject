from __future__ import annotations

import re

from src import messages
from src.bookings import check_availability, save_booking
from src.messages import ask_what_to_change

_REQUIRED_SLOTS = ["instructor", "date", "time", "topic", "student_name"]


def detect_language(text: str) -> str:
    """Return 'AR' if the text contains Arabic characters, else 'EN'."""
    return "AR" if re.search(r"[؀-ۿ]", text) else "EN"


def next_action(state: dict, intent: str, errors: list[str]) -> dict:
    """
    Decide the next dialogue step and build the reply text.
    Sets state["asking_for"] to the slot name when asking for a specific slot,
    so the extractor can use it as a hint on the next turn.

    Returns:
      {
        "step":  "ask | reask | suggest | confirm | booked | cancelled | redirect",
        "reply": "<string>"
      }
    """
    lang = state.get("language", "EN")

    # --- off-topic or cancel first ---
    if intent == "off_topic":
        state["asking_for"] = None
        return {"step": "redirect", "reply": messages.off_topic(lang)}

    if intent == "cancel":
        state["asking_for"] = None
        return {"step": "cancelled", "reply": messages.booking_cancelled(lang)}

    # --- validation errors: ask the user to fix the bad slot ---
    if errors:
        combined = "\n".join(errors)
        state["asking_for"] = None
        return {"step": "reask", "reply": messages.validation_error(combined, lang)}

    # --- user is confirming the summary ---
    if intent == "confirm" and state.get("confirmed"):
        booking_id = save_booking(state)
        state["booking_id"] = booking_id
        state["asking_for"] = None
        return {
            "step":  "booked",
            "reply": messages.booking_confirmed(booking_id, state, lang),
        }

    # --- user is rejecting after summary (wants to change something) ---
    if intent == "reject" and state.get("confirmed"):
        state["confirmed"] = False
        state["asking_for"] = None   # we don't know which slot yet
        return {"step": "ask", "reply": ask_what_to_change(lang)}

    # --- check if any required slot is still missing ---
    missing = _first_missing(state)
    if missing:
        state["asking_for"] = missing   # hint for the extractor next turn
        return {"step": "ask", "reply": messages.ask_slot(missing, lang)}

    # --- all slots filled: check availability ---
    avail = check_availability(state["instructor"], state["date"], state["time"])
    if not avail["available"]:
        nearest = avail.get("nearest", [])
        state["asking_for"] = None
        return {
            "step":  "suggest",
            "reply": messages.slot_unavailable(nearest, lang),
        }

    # --- slot is free: show summary and ask for confirmation ---
    state["confirmed"] = True
    state["asking_for"] = None
    return {
        "step":  "confirm",
        "reply": messages.confirmation_summary(state, lang),
    }


def _first_missing(state: dict) -> str | None:
    """Return the name of the first required slot that has no value yet."""
    for slot in _REQUIRED_SLOTS:
        if not state.get(slot):
            return slot
    return None
