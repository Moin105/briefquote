# briefquote

Quote from a client brief without the brief leaving your laptop. Paste a client brief, and briefquote uses an open-weight model (Gemma, running locally through Ollama) to extract a structured scope as JSON: deliverables, tech stack, complexity, integrations, unknowns to ask the client, and risk flags.

## Why open-weight

- **Privacy:** client briefs often contain confidential business details. Nothing is sent to a third-party API.
- **Zero per-call cost:** quote as many briefs as you like.
- **Works offline:** once the model is pulled, no internet is needed.

## Status

- **Day 1:** brief-to-scope extraction (this release).
- **Day 2:** TabPFN-based hour and price estimator trained on your past jobs (`data/past_jobs.csv` is the seed dataset).
- **Day 3:** web UI.

## Setup

1. Install Ollama from <https://ollama.com>.
2. Pull the model: `ollama pull gemma3:4b`. On CPU-only machines `gemma3:1b` is faster (use `--model gemma3:1b` or set `BRIEFQUOTE_MODEL`).
3. Create a virtual environment and install:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Environment variables: `OLLAMA_HOST` (default `http://localhost:11434`), `BRIEFQUOTE_MODEL` (default `gemma3:4b`).

## Usage

```bash
briefquote doctor
briefquote extract examples/briefs/saas-dashboard.txt --pretty
cat brief.txt | briefquote extract - --pretty
```

`doctor` checks that Ollama is reachable and the model is installed, and prints the exact commands to fix it. Run the tests (no Ollama needed) with `pytest`.

## Example output

```json
{
  "summary": "Rebuild a B2B SaaS customer dashboard in Next.js from existing Figma designs, with Supabase auth/data and Stripe subscription billing.",
  "project_type": "web",
  "deliverables": [
    "Next.js (App Router, TypeScript, Tailwind) dashboard implementing 14 Figma screens",
    "Supabase authentication and data integration",
    "Stripe subscriptions with customer portal and webhooks",
    "Role-based access (owner, manager, viewer)",
    "CSV export on the projects table",
    "Profitability charts performant with a few thousand rows",
    "Vercel deployment"
  ],
  "tech_stack": ["Next.js", "TypeScript", "Tailwind", "Supabase", "Postgres", "Stripe", "Vercel", "Figma"],
  "complexity": 4,
  "integrations_count": 2,
  "has_design_provided": true,
  "has_clear_requirements": true,
  "unknowns": [
    "Which Stripe plans and prices exist, and how are plan limits enforced?",
    "What are the Supabase table schemas and are row-level security policies already defined?",
    "How many and which bugs are in the existing API, and is that in scope?",
    "Is dark mode in the Figma designs?",
    "Which charting requirements and interactions are expected?"
  ],
  "risk_flags": [
    "Unspecified API bug fixes could expand scope",
    "5-week deadline tied to a customer demo",
    "Dark mode described as nice-to-have but not defined",
    "Budget described as flexible, which may signal scope creep"
  ],
  "client_timeline_days": 35,
  "budget_mentioned_usd": 6000.0
}
```

## License

MIT

Started 2026-10-14 for the DEV Hacktoberfest Open-Source AI Challenge Week 2.
