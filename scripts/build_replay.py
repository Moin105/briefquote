"""Build the static replay demo: site/data.json and site/index.html.

Takes the committed real Gemma extractions in examples/outputs/, runs them through the
real estimator and quote code, and embeds the results in a single self-contained page.
The page chrome (CSS and result-card markup/rendering) is sliced out of the live app's
briefquote/web/static/index.html so the two stay visually identical.

Usage: python scripts/build_replay.py [--no-tabpfn] [--rate 40]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from briefquote.estimate import TabPFNEstimator, fit_estimator  # noqa: E402
from briefquote.features import load_history  # noqa: E402
from briefquote.quote import build_quote, render_markdown  # noqa: E402
from briefquote.schema import ScopeExtraction  # noqa: E402

LIVE_HTML = ROOT / "briefquote" / "web" / "static" / "index.html"
BRIEFS = ROOT / "examples" / "briefs"
OUTPUTS = ROOT / "examples" / "outputs"
HISTORY = ROOT / "data" / "past_jobs.csv"
SITE = ROOT / "site"
DEFAULT_RATE = 40.0
EXTRACTION_MODEL = "gemma3:4b"


def _version(pkg: str) -> str:
    try:
        from importlib.metadata import version

        return version(pkg)
    except Exception:
        return "unknown"


def _title(stem: str) -> str:
    return stem.replace("-", " ").capitalize().replace("Saas", "SaaS").replace("whatsapp", "WhatsApp")


def build_data(prefer_tabpfn: bool = True, rate: float = DEFAULT_RATE, today: str | None = None) -> dict:
    os.environ.setdefault("TABPFN_NO_BROWSER", "1")
    df = load_history(str(HISTORY))
    est = fit_estimator(df, prefer_tabpfn=prefer_tabpfn)
    samples = []
    for brief_path in sorted(BRIEFS.glob("*.txt")):
        out = OUTPUTS / (brief_path.stem + ".json")
        scope = ScopeExtraction.model_validate_json(out.read_text(encoding="utf-8"))
        estimate = est.predict(scope)
        quote = build_quote(scope, estimate, rate)
        samples.append(
            {
                "id": brief_path.stem,
                "title": _title(brief_path.stem),
                "brief": brief_path.read_text(encoding="utf-8"),
                "scope": scope.model_dump(),
                "estimate": dataclasses.asdict(estimate),
                "quote": dataclasses.asdict(quote),
                "markdown": render_markdown(scope, quote),
                "method": estimate.method,
                "n_history": estimate.n_history,
            }
        )
    return {
        "generated": today or date.today().isoformat(),
        "default_rate": rate,
        "models": {
            "extraction": EXTRACTION_MODEL,
            "extraction_runtime": "Ollama",
            "estimator": "TabPFN v3.5 (CPU)" if isinstance(est, TabPFNEstimator) else "baseline kNN (k=5)",
            "tabpfn_package": _version("tabpfn"),
            "briefquote": _version("briefquote"),
        },
        "estimator_class": type(est).__name__,
        "samples": samples,
    }


# --- page assembly ---------------------------------------------------------------------

def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


RATE_MATH_JS = r"""// <rate-math>
function round50(x) {
  const q = x / 50, f = Math.floor(q), d = q - f;
  const r = d < 0.5 ? f : d > 0.5 ? f + 1 : (f % 2 === 0 ? f : f + 1); // half to even, like Python round()
  return r * 50;
}
function money(x) { return "$" + Math.round(x).toLocaleString("en-US"); }
// Mirrors briefquote/quote.py build_quote: only the rate arithmetic, from stored hours and price quantiles.
function recompute(sample, rate) {
  const e = sample.estimate, pct = sample.quote.contingency_pct, mult = 1 + pct / 100;
  const blend = (price, hours) => round50((price + hours * rate * mult) / 2);
  return {
    hourly_rate: rate, contingency_pct: pct,
    recommended_price: blend(e.price_p50, e.hours_p50),
    price_floor: blend(e.price_p10, e.hours_p10),
    price_ceiling: blend(e.price_p90, e.hours_p90),
  };
}
function markdownFor(sample, q) {
  return sample.markdown
    .replace(/- Recommended: \*\*\$[\d,]+\*\*/, "- Recommended: **" + money(q.recommended_price) + "**")
    .replace(/- Floor: \$[\d,]+/, "- Floor: " + money(q.price_floor))
    .replace(/- Ceiling: \$[\d,]+/, "- Ceiling: " + money(q.price_ceiling))
    .replace(/at \$[\d,]+\/hour\./, "at " + money(q.hourly_rate) + "/hour.");
}
// </rate-math>
"""

EXTRA_CSS = """
.banner { font-weight: 600; }
pre.brief { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; font: inherit; background: var(--bg);
  border: 1px solid var(--border); border-radius: 8px; padding: 12px; max-height: 320px; overflow: auto; }
input[type=range] { padding: 0; }
.note { color: var(--muted); font-size: .9rem; margin: 8px 0 0; }
.card p, .card ol { margin: 0 0 8px; }
.card ol { padding-left: 22px; }
code { background: var(--accent-soft); padding: 1px 6px; border-radius: 4px; overflow-wrap: anywhere; }
a { color: var(--accent); }
"""

BODY = """<main>
  <header>
    <h1>briefquote <span class="badge">replay</span></h1>
    <p>Quote from a client brief without the brief leaving your laptop</p>
  </header>

  <div class="banner" role="note" id="banner"></div>
  <div class="pills" id="pills">
    <span class="pill"><span class="dot"></span><span id="pill-date"></span></span>
    <span class="pill"><span class="dot"></span><span id="pill-model"></span></span>
    <span class="pill" id="pill-method-wrap"><span class="dot"></span><span id="pill-method"></span></span>
  </div>

  <section class="card">
    <div class="row" style="margin-top:0">
      <div>
        <label for="sample">Sample brief</label>
        <select id="sample"></select>
      </div>
    </div>
    <div style="margin-top:14px">
      <label>Client brief (stored text, read only)</label>
      <pre class="brief" id="brief" tabindex="0"></pre>
    </div>
    <div class="row">
      <div class="narrow">
        <label for="rate">Hourly rate (USD)</label>
        <input id="rate" type="number" min="5" max="500" step="1" value="40">
      </div>
      <div>
        <label for="rate-slider">Rate slider</label>
        <input id="rate-slider" type="range" min="5" max="500" step="1" value="40">
      </div>
    </div>
    <p class="note">The scope, hours and model outputs are fixed: they were computed once on the author's laptop. Only the rate arithmetic (contingency and blend, the same formula as <code>quote.py</code>) is recomputed live in your browser when you change the rate.</p>
  </section>

  __RESULT__

  <section class="card">
    <h2>Honest caveats</h2>
    <ul>
      <li>Three sample briefs prove nothing about accuracy. This shows what the pipeline outputs, not that the numbers are right.</li>
      <li>A human must review every scope and quote before it goes to a client.</li>
      <li>The 30 jobs behind the estimates are synthetic example data, so the numbers show how the pipeline works, not what a real freelancer's history would say.</li>
      <li>With only 30 rows, estimates are a rough guide and the on-time figure is clamped to 5% to 95%.</li>
      <li>TabPFN model weights are licensed for non-commercial use only. Selling quotes built with them needs a commercial TabPFN license, or use the baseline estimator.</li>
      <li>Nothing on this page calls a model. Results are pre-computed and stored in the page.</li>
    </ul>
  </section>

  <section class="card">
    <h2>Run it yourself</h2>
    <ol>
      <li>Install Ollama from ollama.com, then run <code>ollama pull gemma3:4b</code></li>
      <li>Create a virtual environment, then run <code>pip install -e ".[dev,estimator]"</code></li>
      <li>Run <code>briefquote serve --open</code></li>
    </ol>
    <p class="note">Built for the DEV Hacktoberfest Open-Source AI Challenge, Week 2.</p>
    <p><a href="#" id="source">GitHub repository (link to be added)</a></p>
  </section>
</main>"""

SCRIPT_TAIL = r"""
function showSample(i) {
  current = i;
  const s = DATA.samples[i];
  $("brief").textContent = s.brief;
  $("pill-method").textContent = "This sample: " + s.method + " estimator, " + (s.estimate.history_is_bundled_example ? "example history (synthetic)" : s.n_history + " past jobs");
  $("pill-method-wrap").className = "pill" + (s.method === "tabpfn" ? " ok" : "");
  update();
}
function update() {
  const s = DATA.samples[current];
  const rate = parseFloat($("rate").value);
  const ok = rate >= 5 && rate <= 500;
  const q = ok ? recompute(s, rate) : s.quote;
  render({ scope: s.scope, estimate: s.estimate, quote: q, markdown: ok ? markdownFor(s, q) : s.markdown });
}
$("banner").textContent = "Replay of real local runs (" + DATA.models.extraction + " via Ollama, TabPFN v3.5 on CPU) on the author's laptop. The real tool runs entirely on your machine; nothing here calls a model. The 30 jobs behind the estimates are synthetic example data, so the numbers show how the pipeline works, not what a real freelancer's history would say.";
$("pill-date").textContent = "Generated " + DATA.generated;
$("pill-model").textContent = "Extraction: " + DATA.models.extraction + " (Ollama), tabpfn package " + DATA.models.tabpfn_package;
DATA.samples.forEach((s, i) => {
  const o = document.createElement("option");
  o.value = String(i); o.textContent = s.title + " (" + s.method + ")"; $("sample").appendChild(o);
});
$("sample").addEventListener("change", (ev) => showSample(parseInt(ev.target.value, 10)));
$("rate").addEventListener("input", (ev) => { $("rate-slider").value = ev.target.value; update(); });
$("rate-slider").addEventListener("input", (ev) => { $("rate").value = ev.target.value; update(); });
"""


def build_html(data: dict) -> str:
    live = LIVE_HTML.read_text(encoding="utf-8")
    css = _between(live, "<style>", "</style>")[len("<style>"):]
    result_html = _between(live, '<div id="result" class="hidden">', "</main>").replace(
        '<div id="result" class="hidden">', '<div id="result">', 1
    )
    js_helpers = _between(live, "function fillList", "async function loadHealth")
    js_helpers = re.sub(r"function money\(x\)[^\n]*\n", "", js_helpers)  # money() is in RATE_MATH_JS
    js_helpers = re.sub(r"function (showError|clearError)[^\n]*\n", "", js_helpers)
    js_render = _between(live, "function render(d)", "async function generate")
    js_copy = _between(live, '$("copy").addEventListener', "loadHealth();")

    body = BODY.replace("__RESULT__", result_html)
    script = (
        '"use strict";\n'
        'const DATA = JSON.parse(document.getElementById("replay-data").textContent);\n'
        'const $ = (id) => document.getElementById(id);\n'
        "let markdown = \"\";\nlet current = 0;\n\n"
        + RATE_MATH_JS + "\n" + js_helpers + "\n" + js_render + "\n" + SCRIPT_TAIL + "\n" + js_copy
        + '\n$("rate").value = DATA.default_rate; $("rate-slider").value = DATA.default_rate;\nshowSample(0);\n'
    )
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>briefquote replay</title>\n<style>"
        + css
        + EXTRA_CSS
        + "</style>\n</head>\n<body>\n"
        + body
        + '\n<script id="replay-data" type="application/json">'
        + payload
        + "</script>\n<script>\n"
        + script
        + "</script>\n</body>\n</html>\n"
    )


def write_site(data: dict, out_dir: Path = SITE) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "index.html").write_text(build_html(data), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-tabpfn", action="store_true")
    p.add_argument("--rate", type=float, default=DEFAULT_RATE)
    args = p.parse_args(argv)
    data = build_data(prefer_tabpfn=not args.no_tabpfn, rate=args.rate)
    write_site(data)
    for s in data["samples"]:
        e, q = s["estimate"], s["quote"]
        print(
            f"{s['id']}: method={s['method']} n={s['n_history']} hours p10/p50/p90="
            f"{e['hours_p10']}/{e['hours_p50']}/{e['hours_p90']} rec={q['recommended_price']} "
            f"floor={q['price_floor']} ceil={q['price_ceiling']} on_time={e['on_time_probability']} "
            f"notes={e['notes']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
