from __future__ import annotations

import dataclasses
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from briefquote.estimate import BaselineEstimator, TabPFNEstimator, fit_estimator
from briefquote.extract import ExtractionError, extract_scope
from briefquote.features import load_history
from briefquote.llm import FakeClient, OllamaClient, OllamaUnavailable
from briefquote.quote import build_quote, render_markdown

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_HISTORY = PROJECT_ROOT / "data" / "past_jobs.csv"
SAMPLES_DIR = PROJECT_ROOT / "examples" / "briefs"
SAMPLE_EXTRACTION = PROJECT_ROOT / "examples" / "sample_extraction.json"
INDEX_HTML = Path(__file__).resolve().parent / "static" / "index.html"

MAX_BODY = 100 * 1024
MAX_BRIEF_CHARS = 20_000
MIN_RATE, MAX_RATE = 5.0, 500.0
MAX_RAW_CHARS = 2000


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class AppState:
    """Everything fitted or configured once at server start."""

    def __init__(
        self,
        *,
        demo: bool = False,
        model: str | None = None,
        history: str | Path | None = None,
        prefer_tabpfn: bool = True,
    ) -> None:
        self.demo = demo
        if demo:
            self.client = FakeClient([])
            self.model = "demo"
        else:
            self.client = OllamaClient(model=model)
            self.model = self.client.model
        df = load_history(str(history or DEFAULT_HISTORY))
        self.primary = fit_estimator(df, prefer_tabpfn=prefer_tabpfn)
        self.baseline = (
            self.primary
            if isinstance(self.primary, BaselineEstimator)
            else BaselineEstimator(notes=["TabPFN disabled for this request"]).fit(df)
        )

    @property
    def method(self) -> str:
        return "tabpfn" if isinstance(self.primary, TabPFNEstimator) else "baseline"

    def samples(self) -> list[dict]:
        out = []
        if SAMPLES_DIR.is_dir():
            for p in sorted(SAMPLES_DIR.glob("*.txt")):
                out.append(
                    {
                        "id": p.stem,
                        "title": p.stem.replace("-", " ").capitalize().replace("Saas", "SaaS").replace("whatsapp", "WhatsApp"),
                        "text": p.read_text(encoding="utf-8"),
                    }
                )
        return out

    def health(self) -> dict:
        if self.demo:
            ollama = {"reachable": False, "models": [], "model_present": False}
        else:
            ollama = self.client.health()
        return {"ollama": ollama, "model": self.model, "demo": self.demo, "method": self.method}

    def make_quote(self, payload: object) -> dict:
        if not isinstance(payload, dict):
            raise ApiError(400, "Request body must be a JSON object.")
        brief = payload.get("brief")
        if not isinstance(brief, str) or not brief.strip():
            raise ApiError(400, "The brief is empty. Paste a client brief first.")
        if len(brief) > MAX_BRIEF_CHARS:
            raise ApiError(
                400, f"The brief is too long ({len(brief)} characters, limit {MAX_BRIEF_CHARS})."
            )
        rate = payload.get("hourly_rate")
        if (
            isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not (MIN_RATE <= rate <= MAX_RATE)
        ):
            raise ApiError(400, f"hourly_rate must be a number between {MIN_RATE:g} and {MAX_RATE:g}.")
        use_tabpfn = bool(payload.get("use_tabpfn", True))

        client = self.client
        if self.demo:
            client = FakeClient([SAMPLE_EXTRACTION.read_text(encoding="utf-8")])
        try:
            scope = extract_scope(brief, client)
        except OllamaUnavailable as exc:
            raise ApiError(503, str(exc)) from None
        except ExtractionError as exc:
            raw = (exc.last_output or "")[:MAX_RAW_CHARS]
            raise ApiError(
                502,
                "The model did not return valid scope JSON after retrying. "
                f"Last raw output (truncated):\n{raw}",
            ) from None

        est = self.primary if use_tabpfn else self.baseline
        try:
            estimate = est.predict(scope)
        except Exception as exc:  # estimator failure must not leak a trace
            raise ApiError(500, f"Estimator failed: {type(exc).__name__}") from None
        quote = build_quote(scope, estimate, float(rate))
        return {
            "scope": scope.model_dump(),
            "estimate": dataclasses.asdict(estimate),
            "quote": dataclasses.asdict(quote),
            "markdown": render_markdown(scope, quote),
        }


def _make_handler(state: AppState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "briefquote"
        sys_version = ""

        def log_message(self, fmt, *args):  # quiet by default
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, obj: object) -> None:
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

        def _error(self, status: int, message: str) -> None:
            self._json(status, {"error": message})

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            try:
                if path in ("/", "/index.html"):
                    self._send(200, INDEX_HTML.read_bytes(), "text/html; charset=utf-8")
                elif path == "/api/health":
                    self._json(200, state.health())
                elif path == "/api/samples":
                    self._json(200, {"samples": state.samples()})
                else:
                    self._error(404, "Not found.")
            except Exception:
                self._error(500, "Internal error.")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path != "/api/quote":
                return self._error(404, "Not found.")
            try:
                length = int(self.headers.get("Content-Length", ""))
                if length < 0:
                    raise ValueError
            except ValueError:
                return self._error(400, "A valid Content-Length header is required.")
            if length > MAX_BODY:
                remaining = min(length, 1024 * 1024)  # drain so the client can read our reply
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                self.close_connection = True
                return self._error(413, f"Request body too large (limit {MAX_BODY // 1024} KB).")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._error(400, "Request body must be valid JSON.")
            try:
                self._json(200, state.make_quote(payload))
            except ApiError as exc:
                self._error(exc.status, exc.message)
            except Exception:
                self._error(500, "Internal error.")

    return Handler


def create_server(
    port: int = 8765,
    *,
    demo: bool = False,
    model: str | None = None,
    history: str | Path | None = None,
    prefer_tabpfn: bool = True,
    host: str = "127.0.0.1",
) -> ThreadingHTTPServer:
    os.environ.setdefault("TABPFN_NO_BROWSER", "1")
    state = AppState(demo=demo, model=model, history=history, prefer_tabpfn=prefer_tabpfn)
    srv = ThreadingHTTPServer((host, port), _make_handler(state))
    srv.daemon_threads = True
    srv.state = state  # type: ignore[attr-defined]
    return srv
