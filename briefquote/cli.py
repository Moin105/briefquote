from __future__ import annotations

import argparse
import sys

from briefquote.extract import ExtractionError, extract_scope
from briefquote.llm import OllamaClient, OllamaUnavailable


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
    d = sub.add_parser("doctor", help="Check that Ollama and the model are ready")
    d.add_argument("--model", help="Ollama model to check")
    d.set_defaults(func=_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
