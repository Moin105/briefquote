from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request

import pytest

from briefquote.web.server import create_server


def _start(**kw):
    srv = create_server(0, prefer_tabpfn=False, **kw)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, t, f"http://127.0.0.1:{srv.server_address[1]}"


def _stop(srv, t):
    srv.shutdown()
    srv.server_close()
    t.join(timeout=5)


@pytest.fixture(scope="module")
def demo():
    srv, t, base = _start(demo=True)
    yield base
    _stop(srv, t)


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read().decode("utf-8")


def _post(url, body: bytes):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _quote(base, **over):
    payload = {"brief": "Build me a Shopify app", "hourly_rate": 40, "use_tabpfn": False}
    payload.update(over)
    return _post(base + "/api/quote", json.dumps(payload).encode())


def test_health_shape(demo):
    status, body = _get(demo + "/api/health")
    h = json.loads(body)
    assert status == 200
    assert h["demo"] is True
    assert h["method"] == "baseline"
    assert {"ollama", "model"} <= set(h)
    assert {"reachable", "models", "model_present"} <= set(h["ollama"])


def test_samples(demo):
    _, body = _get(demo + "/api/samples")
    samples = json.loads(body)["samples"]
    assert len(samples) == 3
    assert all(s["text"].strip() and s["id"] for s in samples)


def test_quote_happy_path(demo):
    status, d = _quote(demo)
    assert status == 200
    assert {"scope", "estimate", "quote", "markdown"} <= set(d)
    assert "## Price" in d["markdown"]
    assert d["estimate"]["method"] == "baseline"
    assert d["quote"]["recommended_price"] > 0


def test_empty_brief(demo):
    status, d = _quote(demo, brief="   ")
    assert status == 400 and "empty" in d["error"]


def test_long_brief(demo):
    status, d = _quote(demo, brief="x" * 20_001)
    assert status == 400


@pytest.mark.parametrize("rate", [0, 4, 501, "40", None])
def test_bad_rate(demo, rate):
    status, d = _quote(demo, hourly_rate=rate)
    assert status == 400 and "hourly_rate" in d["error"]


def test_invalid_json(demo):
    status, d = _post(demo + "/api/quote", b"not json")
    assert status == 400


def test_oversized_body(demo):
    status, d = _post(demo + "/api/quote", b'{"brief":"' + b"a" * 150_000 + b'"}')
    assert status == 413


def test_unknown_path(demo):
    with pytest.raises(urllib.error.HTTPError) as ei:
        urllib.request.urlopen(demo + "/nope", timeout=5)
    assert ei.value.code == 404


def test_no_cors_headers(demo):
    with urllib.request.urlopen(demo + "/api/health", timeout=5) as r:
        assert not any(k.lower().startswith("access-control") for k in r.headers)


def test_html_has_no_external_references(demo):
    status, html = _get(demo + "/")
    assert status == 200
    assert "briefquote" in html
    assert "Demo mode: canned extraction, no model running" in html
    assert not re.search(r"https?://", html)


def test_ollama_down_returns_503(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9")
    srv, t, base = _start(demo=False)
    try:
        status, d = _quote(base)
        assert status == 503
        assert "ollama pull" in d["error"]
        assert "Traceback" not in d["error"]
        _, body = _get(base + "/api/health")
        assert json.loads(body)["ollama"]["reachable"] is False
    finally:
        _stop(srv, t)
