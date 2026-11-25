"""
Extracts intent and slot updates from a user message via the Gemini LLM.
"""
from __future__ import annotations

import json
import re

from src.llm_client import LLMError, call_llm
from src.prompts import build_system_prompt

_VALID_INTENTS = frozenset(
    {"provide_info", "correction", "confirm", "reject", "cancel", "off_topic"}
)
_SLOT_KEYS = ("instructor", "date", "time", "topic", "student_name", "course_code")


class ExtractionError(Exception):
    """Raised when the LLM response cannot be parsed as valid extractor JSON."""


def extract(
    message: str,
    state: dict,
    today: str,
    prompt_version: str = "v2",
) -> dict:
    """
    Call the LLM and return the extractor JSON.

    Returns:
        {"intent": str, "updates": {slot: str | None, ...}}

    Raises:
        LLMError: if the model could not be reached.
        ExtractionError: if the response cannot be parsed after a retry.
    """
    system_prompt = build_system_prompt(prompt_version, today, state)

    raw = call_llm(system_prompt, message)
    parsed = _parse_response(raw)

    if parsed is None:
        # Retry once: keep same system prompt, prepend a JSON reminder
        nudge = (
            "IMPORTANT: Respond with ONLY valid JSON exactly as specified — "
            "no markdown, no explanation.\n\n" + message
        )
        raw2 = call_llm(system_prompt, nudge)
        parsed = _parse_response(raw2)

    if parsed is None:
        raise ExtractionError(
            "The model did not return valid JSON after two attempts."
        )

    return parsed


def _parse_response(raw: str) -> dict | None:
    """Strip ```json fences and parse. Return None on any failure."""
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

    # Normalise: ensure all 6 keys exist (default missing ones to None)
    updates = {key: data["updates"].get(key) for key in _SLOT_KEYS}

    return {"intent": data["intent"], "updates": updates}
