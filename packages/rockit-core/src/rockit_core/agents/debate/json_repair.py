"""
Robust JSON extraction and repair for LLM debate responses.

Handles common Qwen3.5 failure modes:
  1. Empty content (thinking exhausted token budget)
  2. Truncated JSON (max_tokens cut mid-string)
  3. Markdown fences around JSON
  4. Extra text before/after JSON object
  5. JSON embedded in reasoning field
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def extract_json(content: str, reasoning: str = "") -> dict | None:
    """Extract a JSON object from LLM output, trying multiple strategies.

    Args:
        content: The LLM content field.
        reasoning: The LLM reasoning/thinking field (fallback).

    Returns:
        Parsed dict, or None if all strategies fail.
    """
    # Strategy 1: Direct parse
    result = _try_parse(content)
    if result is not None:
        return result

    # Strategy 2: Strip markdown fences
    result = _try_parse(_strip_fences(content))
    if result is not None:
        return result

    # Strategy 3: Extract JSON object from mixed text
    result = _extract_json_object(content)
    if result is not None:
        return result

    # Strategy 4: Repair truncated JSON
    result = _repair_truncated(content)
    if result is not None:
        return result

    # Strategy 5: If content was empty, try reasoning field
    if not content.strip() and reasoning.strip():
        logger.debug("Content empty, trying reasoning field for JSON")
        result = _extract_json_object(reasoning)
        if result is not None:
            return result
        result = _repair_truncated(reasoning)
        if result is not None:
            return result

    return None


def _try_parse(text: str) -> dict | None:
    """Try direct JSON parse."""
    if not text or not text.strip():
        return None
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _strip_fences(text: str) -> str:
    """Remove markdown code fences."""
    if not text:
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove opening fence (```json or ```) and closing fence (```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned


def _extract_json_object(text: str) -> dict | None:
    """Find and extract the first {...} JSON object from text."""
    if not text:
        return None

    # Find the first '{' and try to match to closing '}'
    start = text.find("{")
    if start == -1:
        return None

    # Walk through finding balanced braces
    depth = 0
    in_string = False
    escape_next = False
    end = start

    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    candidate = text[start:end]
    return _try_parse(candidate)


def _repair_truncated(text: str) -> dict | None:
    """Try to repair truncated JSON by closing open structures.

    Common truncation patterns:
      - String cut mid-value: ...some text  → close the quote
      - Array/object not closed: [...  → close brackets
    """
    if not text:
        return None

    # Find start of JSON
    start = text.find("{")
    if start == -1:
        return None

    candidate = text[start:].rstrip()

    # Try progressively adding closing characters
    # Count unclosed braces/brackets
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False
    last_was_key = False

    for ch in candidate:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            open_braces += 1
        elif ch == "}":
            open_braces -= 1
        elif ch == "[":
            open_brackets += 1
        elif ch == "]":
            open_brackets -= 1

    if open_braces <= 0 and open_brackets <= 0:
        # Not actually truncated, or already balanced
        return None

    # If we're in the middle of a string, close it
    repaired = candidate
    if in_string:
        repaired += '"'

    # Check if we ended mid-value (e.g., after a colon or comma)
    stripped = repaired.rstrip()
    if stripped.endswith(","):
        # Remove trailing comma before closing
        repaired = stripped[:-1]
    elif stripped.endswith(":"):
        # Key with no value — add empty string
        repaired = stripped + '""'

    # Close any open brackets/braces
    repaired += "]" * max(0, open_brackets)
    repaired += "}" * max(0, open_braces)

    result = _try_parse(repaired)
    if result is not None:
        logger.debug("Repaired truncated JSON (added %d }, %d ])", open_braces, open_brackets)
    return result
