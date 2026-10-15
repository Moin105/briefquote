# Real-model run notes (Day 3a)

Model: `gemma3:4b` (3.4 GB, CPU only, about 7 tokens/s) via Ollama 0.40.4, temperature 0.1, JSON-schema constrained output (`format`).
Date: 2026-10-15.

`briefquote doctor`: `[ok]` Ollama reachable, `[ok]` model present, exit code 0.

## Timings (final prompt)

| Brief | Seconds | Valid JSON |
|---|---|---|
| dental-whatsapp-bot | 57 | yes |
| saas-dashboard | 57 | yes |
| shopify-descriptions | 55 | yes |

## First run, original prompt (before tuning)

| Brief | Seconds | Valid JSON | Result |
|---|---|---|---|
| dental-whatsapp-bot | 57 | yes | quality defects below |
| saas-dashboard | 113 | no | two attempts both returned `complexity: 8`, rejected by the validator |
| shopify-descriptions | 41 | no | Ollama returned HTTP 500 `prediction aborted, token repeat limit reached` (reproducible) |

## Defects found

Original prompt:
- dental: `project_type: "mobile"` for a WhatsApp bot (should be ai_automation); `complexity: 1` for a GDPR-sensitive integration; risk flag "unrealistic timeline (before end of year)" is not backed by the brief ("no fixed deadline"); unknowns such as "GDPR compliance requirements" and "'simple' for new booking functionality" are vague or about a not-yet-requested feature.
- saas: `complexity: 8` (out of range; JSON schema does not carry the 1-5 bound because it is a validator, so constrained decoding does not enforce it); `client_timeline_days` and `budget_mentioned_usd` missing although "5 weeks" and "$6,000" are stated; unknowns contained field names (`"client_timeline_days"`, `"budget_mentioned_usd"`); risk flag "budget mentioned (flexible)" is not a risk; the API bug-fix request was not flagged.
- shopify: the model looped and Ollama aborted the request.

Iteration 1 (after prompt change) left: `tech_stack: ["unknown","unknown","unknown"]` and `["unknowns"]` placeholders on dental and shopify; the saas bug-fix request not flagged; the dental `deliverables` included "GDPR compliance" and "Integration with DentFlow" as separate items.

Remaining after iteration 2 (minor, not fixed):
- saas `deliverables` lists "Figma designs (14 screens)" although the client supplies them.
- saas risk flag calls dark mode "unclear acceptance criteria" (it is optional scope, wrong label).
- shopify `client_timeline_days` is null though "a couple of weeks" could be read as 14; arguably acceptable.
- shopify unknowns include padding ("client's experience with CSV files").
- dental risk flag "unrealistic timeline" still flags "the sooner the better, ideally before the end of the year", although the brief says there is no fixed deadline.
- `has_design_provided` correct on all three (true only for saas). `integrations_count` correct (dental 1, saas 2 Stripe+Supabase, shopify 1). Dental timeline and budget correctly null; saas 35 days and 6000 correct.

## What changed

`briefquote/prompts.py` (system prompt rules added, no structural change):
- project_type guidance (ai_automation for bots and LLM tools, mobile only for native apps).
- "eventually/later/maybe" features are scope-creep flags, not deliverables.
- complexity must be an integer 1-5.
- how to convert timeline and budget to numbers and when to use null.
- what counts as an integration; unknowns must be full questions; risk flags must be grounded in the text.
- lists capped at 8 short non-repeating items (this stopped the Shopify repetition abort).
- tech_stack empty list instead of placeholders; side requests like "fix a few bugs" go to risk_flags and deliverables.
- always emit every key.

`briefquote/schema.py`: complexity description now says "integer ... Must not exceed 5".

Before/after on the failing briefs: saas went from invalid (complexity 8) to valid with 35 days and 6000.0 captured; shopify went from HTTP 500 to valid. Dental went from `mobile`/complexity 1 to `ai_automation`/complexity 3, but it still flags the client's "sooner the better" phrasing as an unrealistic timeline, which is a remaining defect.

## Is 4B good enough?

Honestly, borderline but usable as a first draft. After tuning it produced valid JSON on 3 of 3 briefs, with correct hard facts (design provided, integrations, timeline, budget) and mostly grounded unknowns and risks. It is weak on judgement: complexity ratings are noisy (3 for everything), some unknowns are padding, risk labels are sometimes wrong, and results vary run to run, so three samples are not proof of reliability. It also fails in ways code must absorb: out-of-range numbers and Ollama aborting on repetition. About one minute per brief on CPU is acceptable. A human should review the extraction before quoting.

Suggestions outside my edit scope:
- Done in `d484f4d`: `briefquote/llm.py` retries a 500 once with temperature 0.3 and repeat_penalty 1.2 and then raises ModelError (exercised only by tests with mocked responses, not against a real Ollama 500).
- Done in `d484f4d`: `briefquote/cli.py` forces UTF-8 on stdout and stderr.
- Done in `d484f4d`: `briefquote/schema.py` now emits minimum 1 and maximum 5 for complexity, and real Ollama accepted it (a real run on the SaaS brief returned valid JSON, complexity 3, in 55 seconds).

## gemma3:1b

Not tested (not pulled). I would not offer it by default: a 4B model already needs prompt babysitting to produce sane complexity and project_type, and a 1B model will likely fail schema compliance and ground facts worse. It could be offered as an opt-in "fast draft" mode on slow machines, labelled experimental, only after running the three example briefs through it.
