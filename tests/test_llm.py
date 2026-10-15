import pytest

from briefquote import llm
from briefquote.llm import ModelError, OllamaClient, OllamaUnavailable


class _Resp:
    def __init__(self, status, text="", body=None):
        self.status_code = status
        self.text = text
        self._body = body

    def json(self):
        return self._body


OK = _Resp(200, body={"message": {"content": "{}"}})


def _patch(monkeypatch, responses):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(json)
        return responses[len(calls) - 1]

    monkeypatch.setattr(llm.requests, "post", fake_post)
    return calls


def test_500_then_200_retries_with_new_options(monkeypatch):
    calls = _patch(monkeypatch, [_Resp(500, "prediction aborted"), OK])
    assert OllamaClient().complete_json("s", "u", {}) == "{}"
    assert calls[0]["options"] == {"temperature": 0.1}
    assert calls[1]["options"] == {"temperature": 0.3, "repeat_penalty": 1.2}


def test_500_twice_raises_model_error(monkeypatch):
    _patch(monkeypatch, [_Resp(500, "x" * 500), _Resp(500, "token repeat limit " + "y" * 400)])
    with pytest.raises(ModelError) as ei:
        OllamaClient().complete_json("s", "u", {})
    msg = str(ei.value)
    assert "aborted generation" in msg and "--model" in msg
    assert "token repeat limit" in msg and "y" * 400 not in msg


def test_other_status_becomes_model_error(monkeypatch):
    calls = _patch(monkeypatch, [_Resp(503, "busy")])
    with pytest.raises(ModelError, match="503"):
        OllamaClient().complete_json("s", "u", {})
    assert len(calls) == 1


def test_404_still_unavailable(monkeypatch):
    _patch(monkeypatch, [_Resp(404, "nope")])
    with pytest.raises(OllamaUnavailable):
        OllamaClient().complete_json("s", "u", {})
