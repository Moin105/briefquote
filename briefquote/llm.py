from __future__ import annotations

import json
import os
from typing import Protocol

import requests

INSTALL_HINT = (
    "Could not reach Ollama. Install it from https://ollama.com, start it, "
    "then run: ollama pull gemma3:4b"
)


class OllamaUnavailable(RuntimeError):
    """Raised when the local Ollama server cannot be reached."""


class ModelError(RuntimeError):
    """Raised when the model server answers with an error (e.g. aborted generation)."""


CTX_SIZES = (4096, 8192, 16384, 32768)
OUTPUT_RESERVE_TOKENS = 1500
NUM_CTX_THRESHOLD = 3000


def estimate_prompt_tokens(system: str, user: str, schema: dict) -> int:
    """Conservative token estimate: characters / 3.0 (overstates real use)."""
    chars = len(system) + len(user) + len(json.dumps(schema))
    return int(chars / 3.0)


def choose_num_ctx(system: str, user: str, schema: dict) -> int | None:
    """Return the num_ctx to send, or None to keep Ollama's default.

    BRIEFQUOTE_NUM_CTX (integer) forces a value. Otherwise num_ctx is set only
    when the estimate exceeds 3,000 tokens, to the smallest size that fits the
    prompt plus a 1,500-token output reserve. Raises ModelError when even 32768
    is not enough, so a long brief is never silently truncated.
    """
    override = os.environ.get("BRIEFQUOTE_NUM_CTX", "").strip()
    if override:
        try:
            return int(override)
        except ValueError:
            raise ModelError(
                f"BRIEFQUOTE_NUM_CTX must be an integer, got '{override}'."
            ) from None
    est = estimate_prompt_tokens(system, user, schema)
    if est <= NUM_CTX_THRESHOLD:
        return None
    needed = est + OUTPUT_RESERVE_TOKENS
    for size in CTX_SIZES:
        if needed <= size:
            return size
    raise ModelError(
        f"The brief is about {est} tokens, too long to process reliably "
        f"(the largest supported context is {CTX_SIZES[-1]}). "
        "Shorten it or split it into parts."
    )


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict) -> str: ...


class OllamaClient(LLMClient):
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 300,
    ) -> None:
        url = base_url or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        self.base_url = url.rstrip("/")
        self.model = model or os.environ.get("BRIEFQUOTE_MODEL") or "gemma3:4b"
        self.timeout = timeout

    def complete_json(self, system: str, user: str, schema: dict) -> str:
        options: dict = {"temperature": 0.1}
        num_ctx = choose_num_ctx(system, user, schema)
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "options": options,
        }
        resp = self._post(payload)
        if resp.status_code == 500:
            retry = dict(payload)
            retry["options"] = {"temperature": 0.3, "repeat_penalty": 1.2}
            if num_ctx is not None:
                retry["options"]["num_ctx"] = num_ctx
            resp = self._post(retry)
        if resp.status_code == 404:
            raise OllamaUnavailable(
                f"Model '{self.model}' not found. Run: ollama pull {self.model}"
            )
        if not 200 <= resp.status_code < 300:
            body = (getattr(resp, "text", "") or "")[:300]
            if resp.status_code == 500:
                raise ModelError(
                    "The model aborted generation (Ollama HTTP 500). Try again, or use a "
                    f"different --model. Response: {body}"
                )
            raise ModelError(f"Ollama returned HTTP {resp.status_code}. Response: {body}")
        return resp.json()["message"]["content"]

    def _post(self, payload: dict):
        try:
            return requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise OllamaUnavailable(f"{INSTALL_HINT}\n(details: {exc})") from exc

    def health(self) -> dict:
        result = {"reachable": False, "models": [], "model_present": False}
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            names = [m.get("name", "") for m in resp.json().get("models", [])]
        except Exception:
            return result
        result["reachable"] = True
        result["models"] = names
        wanted = self.model if ":" in self.model else self.model + ":latest"
        result["model_present"] = wanted in names
        return result


class FakeClient(LLMClient):
    """Returns canned responses in order; records calls for assertions."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def complete_json(self, system: str, user: str, schema: dict) -> str:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if not self.responses:
            raise RuntimeError("FakeClient has no more responses")
        return self.responses.pop(0)
