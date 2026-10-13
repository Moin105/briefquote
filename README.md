# briefquote

Quote from a client brief without the brief leaving your laptop. Paste a client brief, and briefquote uses an open-weight model (Gemma, running locally through Ollama) to extract a structured scope as JSON: deliverables, tech stack, complexity, integrations, unknowns to ask the client, and risk flags.

## Why open-weight

- **Privacy:** client briefs often contain confidential business details. Nothing is sent to a third-party API.
- **Zero per-call cost:** quote as many briefs as you like.
- **Works offline:** once the model is pulled, no internet is needed.

## Status

- **Day 1:** brief-to-scope extraction. Done.
- **Day 2:** TabPFN-based hour and price estimator trained on your past jobs (`data/past_jobs.csv` is the seed dataset), plus a client-ready Markdown quote. Done.
- **Day 3:** web UI.

## Setup

1. Install Ollama from <https://ollama.com>.
2. Pull the model: `ollama pull gemma3:4b`. On CPU-only machines `gemma3:1b` is faster (use `--model gemma3:1b` or set `BRIEFQUOTE_MODEL`).
3. Create a virtual environment and install:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,estimator]"   # estimator extra installs TabPFN (pulls PyTorch)
```

Environment variables: `OLLAMA_HOST` (default `http://localhost:11434`), `BRIEFQUOTE_MODEL` (default `gemma3:4b`).

## Usage

```bash
briefquote doctor
briefquote extract examples/briefs/saas-dashboard.txt --pretty
cat brief.txt | briefquote extract - --pretty
```

`doctor` checks that Ollama is reachable and the model is installed, and prints the exact commands to fix it. Run the tests (no Ollama needed) with `pytest`; the real-TabPFN test is marked `slow` and skips itself if the model weights are unavailable.

```bash
# Estimate from a saved scope (no Ollama needed)
briefquote estimate examples/sample_extraction.json --rate 40
briefquote estimate examples/sample_extraction.json --json
briefquote estimate examples/sample_extraction.json --no-tabpfn   # baseline only

# Full pipeline: brief -> scope (Ollama) -> estimate -> quote
briefquote quote examples/briefs/saas-dashboard.txt --rate 50 --save-scope scope.json
```

## How the estimate works

[TabPFN](https://github.com/PriorLabs/TabPFN) is a pretrained transformer for small tabular datasets, so it works with 20 to 30 past jobs instead of thousands. briefquote fits it on your history (project type, complexity, deliverables, integrations, design provided, requirements clarity) to predict hours, price and the chance of delivering on time. Quantiles (p10, p50, p90) give a range rather than a single number. If TabPFN is not installed or its weights cannot be loaded, a nearest-neighbour baseline (k=5, no ML dependencies) is used and the quote says so.

The recommended price is the average of the history-predicted price and `hours_p50 x rate x (1 + contingency)`, rounded to the nearest 50. Contingency is 10%, plus 10% when requirements are unclear, plus 5% per risk flag, capped at 35%.

TabPFN weights are gated: the first run needs a one-time license acceptance with Prior Labs (a browser login, or set the `TABPFN_TOKEN` environment variable from <https://ux.priorlabs.ai>). Set `TABPFN_NO_BROWSER=1` to fail fast instead of opening a browser.

## Sample quote (trimmed)

```markdown
# Project quote

## Summary
Rebuild a B2B SaaS customer dashboard in Next.js from existing Figma designs...

## Deliverables
- Supabase authentication and data integration
- Stripe subscriptions with customer portal and webhooks
- ...

## Estimate
Expected effort is about 95 hours, with a likely range of 48.8 to 112 hours.
Based on comparable past work, there is roughly a 60% chance of delivering on time.
_Method: baseline, based on 30 past jobs._

## Price
- Recommended: **$4,350**
- Floor: $1,800
- Ceiling: $4,650

Includes a 30% contingency (10% base, +10% if requirements are unclear, +5% per risk flag, capped at 35%)...
```

## Use your own history

Replace `data/past_jobs.csv` (or pass `--history your.csv`). One row per finished job, with these columns:

| column | meaning |
| --- | --- |
| `project_type` | one of `web, mobile, data, ai_automation, design, writing, devops, other` |
| `complexity` | 1 to 5 |
| `deliverables_count` | number of deliverables |
| `integrations_count` | third-party systems integrated |
| `has_design_provided` | `true` / `false` |
| `has_clear_requirements` | `true` / `false` |
| `hours_actual` | hours you really spent |
| `price_usd` | what you charged |
| `outcome` | `delivered`, `delivered_late` or `cancelled` |

Cancelled jobs are ignored for hours and price but count toward the on-time probability. 20 or more rows work well.

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
