"""The ONLY module that talks to the LLM. Every other stage must import get_llm_response
from here rather than calling an API directly, so swapping providers/models is a
one-file change."""

import json
import logging
import time

import requests

from core import config

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

JSON_ONLY_INSTRUCTION = (
    "\n\n[CRITICAL] You must respond with ONLY valid JSON that can be parsed by Python's "
    "json.loads(). No prose, no explanation, no markdown code fences, no extra text. "
    "Start with [ or { and end with ] or }. Every response must be parseable JSON."
)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def get_llm_response(prompt: str, *, json_mode: bool = False, max_retries: int = 4):
    """Calls OpenRouter's chat completions endpoint and returns the text response.

    If json_mode=True, instructs the model to return only JSON and parses it
    defensively, returning a fallback (None) rather than raising on bad output.
    """
    if not config.OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is not set — skipping LLM call.")
        return None if json_mode else ""

    full_prompt = prompt + (JSON_ONLY_INSTRUCTION if json_mode else "")

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": full_prompt}],
    }
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    delay = 1
    response_text = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
            # Don't retry on auth errors (401, 403) — they won't resolve with retries
            if resp.status_code in (401, 403):
                logger.error(
                    "OpenRouter auth error %s (attempt %d/%d): invalid API key or permissions",
                    resp.status_code, attempt, max_retries,
                )
                break
            if resp.status_code == 429 or resp.status_code >= 500:
                logger.warning(
                    "OpenRouter transient error %s (attempt %d/%d), retrying in %ds",
                    resp.status_code, attempt, max_retries, delay,
                )
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
            data = resp.json()
            response_text = data["choices"][0]["message"]["content"]
            break
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            if attempt < max_retries:
                logger.warning(
                    "OpenRouter call failed (attempt %d/%d): %s", attempt, max_retries, exc
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.warning(
                    "OpenRouter call failed (attempt %d/%d): %s", attempt, max_retries, exc
                )

    if response_text is None:
        logger.error("OpenRouter call failed after %d attempts.", max_retries)
        return None if json_mode else ""

    if not json_mode:
        return response_text

    try:
        return json.loads(_strip_code_fences(response_text))
    except (ValueError, TypeError) as exc:
        logger.error("Failed to parse LLM JSON response: %s\nRaw: %r", exc, response_text)
        return None
