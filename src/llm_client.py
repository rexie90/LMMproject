"""
Gemini API wrapper for Mawid.
Per-request timeout: 30 s (HttpOptions, converted to ms by the SDK).
Retry policy: initial attempt + 2 retries on 503/429/timeout, increasing backoff.
Fallback: switches to GEMINI_FALLBACK_MODEL if primary exhausts retries or returns 404.
Hard cap: total wall-clock time across all attempts is capped at 90 s.
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors
from google.genai import types

_TOTAL_DEADLINE_S = 90.0
_RETRYABLE_CODES = {429, 503}


class LLMError(Exception):
    """Raised when all Gemini calls fail. The message is safe to show to the user."""


def _get_client(timeout_s: int) -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise LLMError("API key is missing. Add GOOGLE_API_KEY to your .env file.")
    # HttpOptions.timeout is in milliseconds (confirmed from SDK source)
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=timeout_s * 1000),
    )


def _call_once(
    client: genai.Client,
    model: str,
    system_prompt: str,
    user_message: str,
) -> str:
    """Single generate_content call. Raises errors.APIError or Exception on failure."""
    config = types.GenerateContentConfig(system_instruction=system_prompt)
    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=config,
    )
    return (response.text or "").strip()


def call_llm(system_prompt: str, user_message: str, timeout_s: int = 30) -> str:
    """
    Send a prompt to Gemini with retry and fallback.

    Strategy:
      1. Try primary (GEMINI_MODEL) up to 3 times on 503/429/timeout,
         with 1 s and 2 s backoffs.
      2. If primary returns 404, skip to fallback immediately.
      3. Try GEMINI_FALLBACK_MODEL once.
      4. Total wall-clock time is capped at 90 s across all attempts.
      5. Raise LLMError with a user-facing message if everything fails.

    Timeouts from the HTTP layer surface as plain Exception (httpx.TimeoutException),
    not as errors.APIError, so both exception types are handled in the retry loop.

    Raises:
        LLMError: on auth errors, model-not-found, exhausted retries, or deadline.
    """
    primary = os.environ.get("GEMINI_MODEL", "").strip()
    fallback = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()

    if not primary:
        raise LLMError("GEMINI_MODEL is not set in your .env file.")

    client = _get_client(timeout_s)
    deadline = time.monotonic() + _TOTAL_DEADLINE_S

    # --- primary model: initial attempt + 2 retries ---
    for attempt in range(3):
        if time.monotonic() >= deadline:
            break
        try:
            return _call_once(client, primary, system_prompt, user_message)
        except errors.APIError as e:
            if e.code in (401, 403):
                raise LLMError(
                    "API key is not authorized. Check your GOOGLE_API_KEY in .env."
                )
            if e.code == 404:
                break  # model not available — go straight to fallback
            if e.code not in _RETRYABLE_CODES:
                raise LLMError(
                    f"The AI model returned an unexpected error (HTTP {e.code}). "
                    "Please try again."
                )
            # 429 / 503: fall through to backoff
        except Exception:
            # Timeout (httpx.TimeoutException) or network error — retryable
            pass

        if attempt < 2:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(2**attempt, remaining))  # 1 s, then 2 s

    # --- fallback model: single attempt ---
    if fallback and time.monotonic() < deadline:
        try:
            return _call_once(client, fallback, system_prompt, user_message)
        except errors.APIError as e:
            if e.code in (401, 403):
                raise LLMError(
                    "API key is not authorized. Check your GOOGLE_API_KEY in .env."
                )
            if e.code == 404:
                raise LLMError(
                    f"Fallback model '{fallback}' is not available to this key. "
                    "Update GEMINI_FALLBACK_MODEL in .env."
                )
        except Exception:
            pass  # timeout / network on fallback

    raise LLMError(
        "Could not reach the AI model after multiple attempts. "
        "Please wait a moment and try again."
    )
