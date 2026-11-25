"""
Gemini API wrapper for Mawid.

Per-request timeout: min(30 s, time remaining before 90 s deadline).
  HttpOptions.timeout is in milliseconds; a new client is created per attempt
  so the timeout is always tight against the deadline.
Retry policy: initial attempt + 2 retries on 503/429/transport errors, with
  1 s and 2 s backoffs. Real programming errors are never swallowed.
Fallback: switches to GEMINI_FALLBACK_MODEL if primary exhausts retries or
  returns 404.
Logging: failure reason is printed to the terminal (no secrets logged).
"""
from __future__ import annotations

import os
import time

from google import genai
from google.genai import errors
from google.genai import types

# ── transport exception types ────────────────────────────────────────────────
# The SDK uses httpx2 (confirmed from google.genai.errors exports).
# httpx2.TransportError is the base for TimeoutException and other network
# errors. We import it here so we can catch transport failures specifically
# instead of using a bare "except Exception".
_httpx2 = getattr(errors, "httpx2", None)
_httpx = getattr(errors, "httpx", None)

_transport_exc: list[type[Exception]] = []
for _mod in (_httpx2, _httpx):
    if _mod is not None:
        _cls = getattr(_mod, "TransportError", None)
        if _cls is not None:
            _transport_exc.append(_cls)

# TransportError covers TimeoutException (confirmed: TimeoutException is a
# subclass of TransportError in httpx2).
_TRANSPORT_ERRORS: tuple[type[Exception], ...] = tuple(_transport_exc)

# ── constants ────────────────────────────────────────────────────────────────
_TOTAL_DEADLINE_S = 90.0
_MIN_REMAINING_S = 5.0      # stop scheduling new attempts if less than this remains
_RETRYABLE_CODES = {429, 503}


class LLMError(Exception):
    """Raised when all Gemini calls fail. The message is safe to show to the user."""


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_client(timeout_s: int) -> genai.Client:
    """Create a Gemini client with the given per-request timeout (seconds)."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise LLMError("API key is missing. Add GOOGLE_API_KEY to your .env file.")
    # HttpOptions.timeout is in milliseconds (confirmed from SDK _api_client.py:
    #   "timeout_in_seconds = timeout / 1000.0")
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
    """One generate_content call. Raises errors.APIError or _TRANSPORT_ERRORS on failure."""
    config = types.GenerateContentConfig(system_instruction=system_prompt)
    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=config,
    )
    return (response.text or "").strip()


def _remaining(deadline: float) -> float:
    return deadline - time.monotonic()


# ── public API ────────────────────────────────────────────────────────────────

def call_llm(system_prompt: str, user_message: str, timeout_s: int = 30) -> str:
    """
    Send a prompt to Gemini with retry and fallback.

    Strategy
    --------
    1. Try primary (GEMINI_MODEL) up to 3 times on 503/429/transport errors,
       with 1 s and 2 s backoffs.
    2. Per-request timeout = min(timeout_s, time left before 90 s deadline).
       If less than 5 s remain, stop immediately.
    3. If primary returns 404, skip to fallback immediately.
    4. Try GEMINI_FALLBACK_MODEL once (same deadline check).
    5. Raise LLMError with a user-facing message if everything fails.

    Failure reasons are printed to the terminal for debugging (no secrets).

    Raises
    ------
    LLMError
        On auth errors, model-not-found, exhausted retries, or deadline.
    """
    primary = os.environ.get("GEMINI_MODEL", "").strip()
    fallback = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()

    if not primary:
        raise LLMError("GEMINI_MODEL is not set in your .env file.")

    deadline = time.monotonic() + _TOTAL_DEADLINE_S

    # ── primary model: initial attempt + 2 retries ───────────────────────────
    for attempt in range(3):
        rem = _remaining(deadline)
        if rem < _MIN_REMAINING_S:
            print(
                f"[Mawid LLM] Deadline reached before attempt {attempt + 1} "
                f"on '{primary}' — stopping."
            )
            break

        req_timeout = max(1, int(min(timeout_s, rem)))
        client = _get_client(req_timeout)

        try:
            return _call_once(client, primary, system_prompt, user_message)

        except errors.APIError as e:
            if e.code in (401, 403):
                raise LLMError(
                    "API key is not authorized. Check your GOOGLE_API_KEY in .env."
                )
            if e.code == 404:
                print(f"[Mawid LLM] Primary '{primary}' → 404, switching to fallback.")
                break
            if e.code not in _RETRYABLE_CODES:
                raise LLMError(
                    f"The AI model returned an unexpected error (HTTP {e.code}). "
                    "Please try again."
                )
            reason = "rate limit (429)" if e.code == 429 else "server overloaded (503)"
            will_retry = attempt < 2
            suffix = f"retrying in {2 ** attempt} s…" if will_retry else "trying fallback…"
            print(f"[Mawid LLM] Attempt {attempt + 1}/3 on '{primary}' failed: {reason} — {suffix}")

        except _TRANSPORT_ERRORS as e:
            # Timeout or network error — retryable. Real programming errors
            # (AttributeError, etc.) are NOT caught here and will propagate.
            will_retry = attempt < 2
            suffix = f"retrying…" if will_retry else "trying fallback…"
            print(f"[Mawid LLM] Attempt {attempt + 1}/3 on '{primary}' failed: {type(e).__name__} — {suffix}")

        if attempt < 2:
            rem = _remaining(deadline)
            if rem < _MIN_REMAINING_S:
                break
            time.sleep(min(2 ** attempt, rem - _MIN_REMAINING_S))

    # ── fallback model: single attempt ───────────────────────────────────────
    if fallback:
        rem = _remaining(deadline)
        if rem < _MIN_REMAINING_S:
            print(f"[Mawid LLM] No time left for fallback model '{fallback}'.")
        else:
            req_timeout = max(1, int(min(timeout_s, rem)))
            print(
                f"[Mawid LLM] Trying fallback '{fallback}' "
                f"(timeout {req_timeout} s, {rem:.0f} s left on deadline)…"
            )
            client = _get_client(req_timeout)
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
                print(f"[Mawid LLM] Fallback '{fallback}' failed: HTTP {e.code}")

            except _TRANSPORT_ERRORS as e:
                print(
                    f"[Mawid LLM] Fallback '{fallback}' failed: "
                    f"{type(e).__name__}"
                )

    raise LLMError(
        "Could not reach the AI model after multiple attempts. "
        "Please wait a moment and try again."
    )
