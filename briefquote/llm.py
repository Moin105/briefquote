from __future__ import annotations

import os
from typing import Protocol

import requests

INSTALL_HINT = (
    "Could not reach Ollama. Install it from https://ollama.com, start it, "
    "then run: ollama pull gemma3:4b"
)


class OllamaUnavailable(RuntimeError):
    """Raised when the local Ollama server cannot be reached."""


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
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "options": {"temperature": 0.1},
        }
        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise OllamaUnavailable(f"{INSTALL_HINT}\n(details: {exc})") from exc
        if resp.status_code == 404:
            raise OllamaUnavailable(
                f"Model '{self.model}' not found. Run: ollama pull {self.model}"
            )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

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
