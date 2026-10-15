# Check on real client briefs

Date: 2026-10-15. Model: gemma3:4b through Ollama on CPU. Estimator: TabPFN over the bundled 30 synthetic jobs.

The three example briefs in this repo were written by an AI for the demo. This is a first check on briefs written by real clients. It is small (8 briefs) and judged by one person, so treat it as a sanity check, not a benchmark.

## Method

- Source: public Upwork job posts, read through a read-only job-search connector, all posted on 2026-10-14 or 2026-10-15.
- Selection: software, AI/automation, data or web build posts with at least 80 words of description, from clients outside a short list of excluded countries. 8 briefs across data scraping, data engineering, AI automation, an AI agent and two website builds, including one long brief (763 words) and one very short, vague one (95 words).
- Cleaning: client, company, product and people names, emails, phone numbers and URLs were replaced by `[removed]` before use. The cleaned texts were kept only in a scratch folder outside the repo and deleted afterwards. **The briefs are not republished here.** This file contains no quotes, job titles, client names or links.
- Run: `briefquote quote <file> --save-scope <scope.json>` per brief, with real Gemma extraction.
- Judging: I compared each extraction with its brief and tallied defects by severity (High: drops or misstates a large part of the scope; Medium: would mislead the quote or needs a real fix; Low: cosmetic, generic or arguable).

## Aggregate

| Measure | Result |
|---|---|
| Briefs run | 8 |
| Returned valid output | 8 of 8 |
| Valid on first attempt / after retry / failed | not separable (see note) / not separable / 0 |
| `error:` lines or HTTP 500 surfaced | 0 |
| Seconds per brief | 124, 74, 55, 97, 65, 59, 62, 59 |
| Median seconds | 63.5 (the 124 s run included a cold model load) |
| Invented deliverables or technologies | 0 clear cases, 1 mild (a tech list that includes options the client only listed as acceptable) |
| Invented or misread timeline or budget | 1 (a fill-in-the-blank template line read as a real 7-day timeline) |
| High defects | 2 |
| Medium defects | 13 |
| Low defects | 10 |
| Usable as a first draft without major edits | 3 of 8 |

Note on retries: the CLI retries silently (a second extraction attempt, and a second HTTP request after a 500) and does not log which path ran. Nothing failed and no error line appeared, but I cannot say how many of the 8 needed a retry.

## Per-brief summaries

1. Data scraping job on a JavaScript-rendered site, 288 words: type labelled `ai_automation` instead of `data`; invented a 7-day timeline from an unfilled template line; three generic "unknowns" asking things the freelancer is meant to propose (price, turnaround). Deliverables good. 48.9 h, $2,300. Defects: 2 Medium, 1 Low.
2. Data engineer hiring ad, 356 words: this is an ad for a person, not a scoped project, so the output is generic. Labelled `ai_automation`; five boilerplate unknowns; deliverables are three overlapping phrases; real-time feeds under-represented. 60.3 h, $2,900. Defects: 1 Medium, 3 Low.
3. Very short, vague data pipeline request, 95 words: sensible unknowns (authentication, volume) and a correct deliverable list, but labelled `ai_automation` instead of `data` and marked "clear requirements" despite a vague, phased brief. 32.6 h, $1,450. Defects: 1 Medium, 2 Low.
4. Long AI operations assistant brief, 763 words, six listed automations: kept only 3 deliverables and dropped carrier onboarding, document processing and record management; counted 3 integrations where the brief names about 5 systems; listed as unknown something the brief already answers (human approval); one risk flag is just a quoted sentence. 81.1 h, $3,900. Defects: 1 High, 3 Medium, 1 Low.
5. Event-monitoring workflow build in n8n, 341 words: three deliverables where the brief has about seven (registry scraping, newsroom scraping and error handling were folded away or dropped); stack lists every database the client said they had experience with; two risk flags are quoted sentences that are not risks. 71.7 h, $3,400. Defects: 1 High, 2 Medium, 1 Low.
6. Lightweight Python AI agent, 127 words: best result. Deliverables match the brief's own list, unknowns are sharp (which API, expected volume). One weak risk flag. The estimate of 60.6 h, $2,650 looks high for something described as lightweight. Defects: 1 Low.
7. Ecommerce store build on WooCommerce, 156 words: correct type and stack, but missed the catalog size, artwork uploads and the stated exclusions; asked "what is the size of the catalog" when the brief gives it; three risk flags are quoted sentences, one claiming an unrealistic timeline where none is stated; marked "unclear requirements" for a reasonably clear brief. 48 h, $2,150. Defects: 3 Medium, 1 Low.
8. Marketing agency website, 147 words: correct type, deliverables faithful and complete. Both risk flags are the client's proposal instructions copied as "risks". 73.7 h, $3,350. Defects: 1 Medium.

## Defect tally

| Defect type | Count | Severity |
|---|---|---|
| Missed explicit requirements or deliverables | 3 briefs (4, 5, 7) | 2 High, 1 Medium |
| Wrong `project_type` (data work labelled `ai_automation`) | 3 briefs (1, 2, 3) | Medium each, because the type feeds the estimator |
| Risk flags that are quoted brief sentences, not risks | 4 briefs (4, 5, 7, 8) | Medium |
| Padded or generic "unknowns" (including ones the brief answers) | 7 briefs | Low to Medium |
| Misstated timeline | 1 brief (1) | Medium |
| Integration count off | 1 brief (4) | Medium |
| Over-inclusive tech list | 1 brief (5) | Medium (mild hallucination) |
| `has_clear_requirements` wrong | 3 briefs (3, 5, 7) | Low |

The tool did not invent features or technologies outright. Its failures are omission, label mistakes and filler, not fabrication.

## Context window finding

Ollama's default context window is small and long inputs are cut silently. Measured with `prompt_eval_count` from the API, using the same system prompt, user prompt and schema as the tool:

| Input | Words | Rough estimate (words x 1.4 + about 1,200 prompt and schema tokens) | Actual `prompt_eval_count`, default | With `num_ctx` raised |
|---|---|---|---|---|
| Short vague brief | 95 | about 1,330 | 725 | not needed |
| Long real brief | 763 | about 2,270 | 1,663 | 1,663 at 8192 (same) |
| That brief repeated 3 times | 2,287 | about 4,400 | 3,771 | 3,771 at 8192 (same) |
| That brief repeated 5 times | 3,811 | about 6,500 | **2,051 (cut)** | 5,879 at 16384 |

Follow-up: the client now sets `num_ctx` automatically for long briefs (and raises a clear error when a brief is too long) instead of truncating silently. Measured on a synthetic 3,728-word brief (the saas-dashboard example repeated 16 times): the client chose `num_ctx` 16384 and the model read all 5,472 prompt tokens, not the roughly 2,051 it would have seen at the default; the direct API call took 52 s.

My rough estimate overstates real token use by about 25 percent, because Gemma's tokenizer is more efficient than words x 1.4. Briefs up to about 2,300 words fit in the default window untouched. Somewhere between 2,300 and 3,800 words the input is truncated: the 3,811-word case reached the model as only 2,051 tokens, so the extraction would be made from a partial brief with no warning. Setting `options.num_ctx` fixes it (the full 5,879 tokens were read at 16384). Cost in seconds: 76 s to 110 s at 8192 for the 763-word brief, and 107 s to 202 s at 16384 for the 3,811-word input, though part of each difference is a model reload. Almost no real freelance brief is this long, so the practical risk is low, but it is silent when it happens. The 3,811-word case was a synthetic repeat of one brief and the exact cut-off point was not pinned down.

## Estimates and prices

These come from 30 synthetic jobs, so they are illustration only. Against my own sense of the work: the lightweight agent (brief 6) looks about 2 to 3 times too high at 60 h; the multi-system Slack assistant (brief 4) looks low at 81 h for the full list of automations, though acceptable for its stated proof-of-concept-first scope; the website and store builds (briefs 7 and 8) are plausible. Prices cluster between $1,450 and $3,900 almost regardless of scope, which suggests the history is too small to separate cases well.

## Verdict

About 3 of 8 outputs (briefs 3, 6 and 8, after removing the bogus risk flags) could be used as a first draft without major edits. Three more (1, 2, 7) are usable after real edits to type, unknowns and risks. Two (4, 5) drop roughly half the scope and should not be trusted. The longer and more structured the brief, the more the 4B model compresses it. The extraction is useful as a rough checklist and a source of clarifying questions; it is not a substitute for reading the brief.

## Caveats

- 8 briefs, one judge, no second reader.
- Cleaning replaced names, which may have nudged a few "unknowns" (for example asking for a source that had been replaced by a placeholder).
- Run-to-run variation: a repeat extraction of the long brief with a different context setting returned 6 deliverables instead of 3, so single runs overstate how stable the output is.
- Any budget shown outside a post's description text was not given to the tool.
- Timing is from one CPU machine.
