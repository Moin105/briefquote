from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from briefquote.quote import build_quote
from briefquote.schema import ScopeExtraction

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("build_replay", ROOT / "scripts" / "build_replay.py")
build_replay = importlib.util.module_from_spec(_spec)
sys.modules["build_replay"] = build_replay
_spec.loader.exec_module(build_replay)


@pytest.fixture(scope="module")
def data() -> dict:
    # Baseline path: needs neither Ollama nor TabPFN.
    return build_replay.build_data(prefer_tabpfn=False, today="2026-10-15")


@pytest.fixture(scope="module")
def html(data) -> str:
    return build_replay.build_html(data)


def test_three_samples_marked_baseline(data):
    assert len(data["samples"]) == 3
    assert {s["method"] for s in data["samples"]} == {"baseline"}
    assert data["models"]["estimator"].startswith("baseline")
    assert data["generated"] == "2026-10-15"


def test_price_ordering(data):
    for s in data["samples"]:
        q = s["quote"]
        assert q["price_floor"] <= q["recommended_price"] <= q["price_ceiling"]
        e = s["estimate"]
        assert e["hours_p10"] <= e["hours_p50"] <= e["hours_p90"]


def test_deterministic(data):
    again = build_replay.build_data(prefer_tabpfn=False, today="2026-10-15")
    assert json.dumps(again, sort_keys=True) == json.dumps(data, sort_keys=True)


def test_no_external_references(html):
    assert not re.search(r"<script[^>]+src\s*=", html, re.I)
    assert not re.search(r"<link[^>]+href\s*=", html, re.I)
    assert not re.search(r"<img[^>]+src\s*=", html, re.I)
    allowed = "https://github.com/Moin105/briefquote"
    assert not re.search(
        r"""(src|href)\s*=\s*["']\s*(?!""" + re.escape(allowed) + r"""["'])(https?:)?//""", html, re.I
    )
    assert not re.search(r"url\(\s*[\"']?(https?:)?//", html, re.I)
    assert "fetch(" not in html and "XMLHttpRequest" not in html


def test_required_content(html):
    assert "nothing here calls a model" in html
    assert 'href="https://github.com/Moin105/briefquote" id="source">GitHub repository</a>' in html
    assert "briefquote serve --open" in html
    assert "innerHTML" not in html


def test_python_mirror_of_rate_math(data):
    """The stored quote equals build_quote for the default rate (recomputed from stored numbers)."""
    from briefquote.estimate import Estimate

    for s in data["samples"]:
        scope = ScopeExtraction.model_validate(s["scope"])
        est = Estimate(**s["estimate"])
        q = build_quote(scope, est, 55.0)
        assert q.price_floor <= q.recommended_price <= q.price_ceiling
    s = data["samples"][0]
    scope = ScopeExtraction.model_validate(s["scope"])
    assert build_quote(scope, Estimate(**s["estimate"]), data["default_rate"]).recommended_price == s["quote"][
        "recommended_price"
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_js_rate_math_matches_build_quote(data, html, tmp_path):
    from briefquote.estimate import Estimate

    block = re.search(r"// <rate-math>.*?// </rate-math>", html, re.S).group(0)
    rates = [5, 17, 40, 40.5, 55, 62.5, 99, 150, 333, 500]
    expected = {}
    for s in data["samples"]:
        scope = ScopeExtraction.model_validate(s["scope"])
        est = Estimate(**s["estimate"])
        expected[s["id"]] = {
            str(r): [
                (q := build_quote(scope, est, float(r))).recommended_price,
                q.price_floor,
                q.price_ceiling,
            ]
            for r in rates
        }
    js = (
        block
        + "\nconst data = "
        + json.dumps(data)
        + ";\nconst rates = "
        + json.dumps(rates)
        + ";\nconst out = {};\n"
        "for (const s of data.samples) { out[s.id] = {}; for (const r of rates) {"
        " const q = recompute(s, r); out[s.id][String(r)] = [q.recommended_price, q.price_floor, q.price_ceiling]; } }\n"
        "console.log(JSON.stringify(out));\n"
    )
    f = tmp_path / "check.js"
    f.write_text(js, encoding="utf-8")
    res = subprocess.run(["node", str(f)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout) == expected


def test_replay_discloses_synthetic_history(data, html):
    assert all(s["estimate"]["history_is_bundled_example"] for s in data["samples"])
    assert "synthetic example data" in html
    assert "example history (synthetic)" in html
    assert all("synthetic demo data" in s["markdown"] for s in data["samples"])
