from pathlib import Path

import pytest

from briefquote.schema import ScopeExtraction

ROOT = Path(__file__).parent.parent


@pytest.fixture
def sample_scope() -> ScopeExtraction:
    text = (ROOT / "examples" / "sample_extraction.json").read_text(encoding="utf-8")
    return ScopeExtraction.model_validate_json(text)


@pytest.fixture
def history_path() -> Path:
    return ROOT / "data" / "past_jobs.csv"
