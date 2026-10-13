from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from briefquote.extract import ExtractionError, extract_scope
from briefquote.estimate import fit_estimator
from briefquote.features import load_history
from briefquote.llm import OllamaClient, OllamaUnavailable
from briefquote.quote import build_quote, render_markdown
from briefquote.schema import ScopeExtraction

DEFAULT_HISTORY = Path(__file__).resolve().parent.parent / "data" / "past_jobs.csv"


def _doctor(args: argparse.Namespace) -> int:
    client = OllamaClient(model=getattr(args, "model", None))
    h = client.health()
    if not h["reachable"]:
        print(f"[x] Ollama is not reachable at {client.base_url}")
        print("    Fix: install Ollama from https://ollama.com, start it, then run:")
        print(f"         ollama pull {client.model}")
        return 1
    print(f"[ok] Ollama is reachable at {client.base_url}")
    print(f"     Installed models: {', '.join(h['models']) or '(none)'}")
    if not h["model_present"]:
        print(f"[x] Model '{client.model}' is not installed.")
        print(f"    Fix: ollama pull {client.model}")
        return 1
    print(f"[ok] Model '{client.model}' is present. You are ready to go.")
    return 0


def _extract(args: argparse.Namespace) -> int:
    try:
        if args.path == "-":
            brief = sys.stdin.read()
        else:
            with open(args.path, encoding="utf-8") as f:
                brief = f.read()
    except OSError as exc:
        print(f"error: cannot read brief: {exc}", file=sys.stderr)
        return 1
    if not brief.strip():
        print("error: brief is empty", file=sys.stderr)
        return 1
    client = OllamaClient(model=args.model)
    try:
        scope = extract_scope(brief, client)
    except (OllamaUnavailable, ExtractionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(scope.model_dump_json(indent=2 if args.pretty else None))
    return 0


def _estimate_and_print(scope: ScopeExtraction, args: argparse.Namespace) -> int:
    try:
        history = load_history(args.history)
        est = fit_estimator(history, prefer_tabpfn=not args.no_tabpfn)
        estimate = est.predict(scope)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    quote = build_quote(scope, estimate, args.rate)
    if args.json:
        print(json.dumps(dataclasses.asdict(quote), indent=2))
    else:
        print(render_markdown(scope, quote))
    return 0


def _estimate(args: argparse.Namespace) -> int:
    try:
        with open(args.path, encoding="utf-8") as f:
            scope = ScopeExtraction.model_validate_json(f.read())
    except (OSError, ValueError) as exc:
        print(f"error: cannot load scope JSON: {exc}", file=sys.stderr)
        return 1
    return _estimate_and_print(scope, args)


def _quote(args: argparse.Namespace) -> int:
    try:
        with open(args.path, encoding="utf-8") as f:
            brief = f.read()
    except OSError as exc:
        print(f"error: cannot read brief: {exc}", file=sys.stderr)
        return 1
    if not brief.strip():
        print("error: brief is empty", file=sys.stderr)
        return 1
    client = OllamaClient(model=args.model)
    try:
        scope = extract_scope(brief, client)
    except (OllamaUnavailable, ExtractionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.save_scope:
        Path(args.save_scope).write_text(scope.model_dump_json(indent=2), encoding="utf-8")
    return _estimate_and_print(scope, args)


def _add_estimate_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--history", default=str(DEFAULT_HISTORY), help="Past jobs CSV (default: data/past_jobs.csv)")
    p.add_argument("--rate", type=float, default=40.0, help="Hourly rate in USD (default 40)")
    p.add_argument("--no-tabpfn", action="store_true", help="Use the baseline estimator instead of TabPFN")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="Print JSON")
    fmt.add_argument("--markdown", action="store_true", help="Print Markdown (default)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="briefquote", description="Local scope extraction from client briefs."
    )
    sub = p.add_subparsers(dest="command", required=True)
    e = sub.add_parser("extract", help="Extract structured scope from a brief")
    e.add_argument("path", help="Path to brief text file, or - for stdin")
    e.add_argument("--model", help="Ollama model (default: $BRIEFQUOTE_MODEL or gemma3:4b)")
    e.add_argument("--pretty", action="store_true", help="Indent JSON output")
    e.set_defaults(func=_extract)
    es = sub.add_parser("estimate", help="Estimate hours and price from a saved scope JSON (no Ollama needed)")
    es.add_argument("path", help="Path to a ScopeExtraction JSON file")
    _add_estimate_flags(es)
    es.set_defaults(func=_estimate)
    q = sub.add_parser("quote", help="Extract scope from a brief (Ollama), then estimate and quote")
    q.add_argument("path", help="Path to brief text file")
    q.add_argument("--model", help="Ollama model")
    q.add_argument("--save-scope", metavar="PATH", help="Save the extracted scope JSON here")
    _add_estimate_flags(q)
    q.set_defaults(func=_quote)
    d = sub.add_parser("doctor", help="Check that Ollama and the model are ready")
    d.add_argument("--model", help="Ollama model to check")
    d.set_defaults(func=_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
