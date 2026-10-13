from pathlib import Path

import pytest

from briefquote.extract import ExtractionError, extract_scope
from briefquote.llm import FakeClient

SAMPLE_TEXT = (Path(__file__).parent.parent / "examples" / "sample_extraction.json").read_text(
    encoding="utf-8"
)


def test_valid_json():
    s = extract_scope("brief", FakeClient([SAMPLE_TEXT]))
    assert s.integrations_count == 2
    assert s.has_design_provided is True


def test_fenced_json():
    s = extract_scope("brief", FakeClient([f"```json\n{SAMPLE_TEXT}\n```"]))
    assert s.project_type == "web"


def test_retry_after_garbage():
    client = FakeClient(["this is not json", SAMPLE_TEXT])
    s = extract_scope("brief", client)
    assert s.complexity == 4
    assert len(client.calls) == 2
    assert "Your previous output was invalid" in client.calls[1]["user"]
    assert "Expecting value" in client.calls[1]["user"]


def test_garbage_twice_raises():
    with pytest.raises(ExtractionError) as ei:
        extract_scope("brief", FakeClient(["nope", "still nope"]))
    assert "still nope" in str(ei.value)
    assert ei.value.last_output == "still nope"
