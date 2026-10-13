from __future__ import annotations

import json
import re

from pydantic import ValidationError

from briefquote.llm import LLMClient
from briefquote.prompts import SYSTEM_PROMPT, build_user_prompt
from briefquote.schema import ScopeExtraction

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


class ExtractionError(RuntimeError):
    """Raised when the model never produced valid scope JSON."""

    def __init__(self, message: str, last_output: str = "") -> None:
        super().__init__(f"{message}\nLast raw output:\n{last_output}")
        self.last_output = last_output


def strip_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE.match(text)
    return m.group(1).strip() if m else text


def extract_scope(brief: str, client: LLMClient, max_attempts: int = 2) -> ScopeExtraction:
    schema = ScopeExtraction.json_schema_for_llm()
    base_prompt = build_user_prompt(brief)
    user = base_prompt
    raw = ""
    last_error = ""
    for _ in range(max_attempts):
        raw = client.complete_json(SYSTEM_PROMPT, user, schema)
        try:
            return ScopeExtraction.model_validate(json.loads(strip_fences(raw)))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            user = (
                f"{base_prompt}\n\nYour previous output was invalid: {last_error}\n"
                "Return only valid JSON."
            )
    raise ExtractionError(
        f"Could not get valid output after {max_attempts} attempts: {last_error}", raw
    )
