import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from briefquote.schema import ScopeExtraction

SAMPLE = Path(__file__).parent.parent / "examples" / "sample_extraction.json"


def _sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_sample_loads():
    s = ScopeExtraction.model_validate(_sample())
    assert s.project_type == "web"
    assert s.complexity == 4
    assert s.budget_mentioned_usd == 6000.0


def test_complexity_out_of_range_fails():
    data = _sample() | {"complexity": 6}
    with pytest.raises(ValidationError):
        ScopeExtraction.model_validate(data)


def test_bad_project_type_fails():
    data = _sample() | {"project_type": "blockchain"}
    with pytest.raises(ValidationError):
        ScopeExtraction.model_validate(data)


def test_negative_integrations_fails():
    with pytest.raises(ValidationError):
        ScopeExtraction.model_validate(_sample() | {"integrations_count": -1})


def test_json_schema_for_llm_has_properties():
    schema = ScopeExtraction.json_schema_for_llm()
    assert "complexity" in schema["properties"]


def test_json_schema_carries_complexity_bounds():
    props = ScopeExtraction.json_schema_for_llm()["properties"]
    assert props["complexity"]["minimum"] == 1
    assert props["complexity"]["maximum"] == 5
    assert props["integrations_count"]["minimum"] == 0
