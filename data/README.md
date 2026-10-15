# data/past_jobs.csv

`past_jobs.csv` is **synthetic example data**. It was written for the briefquote demo and is **not real client work**. Nobody delivered these 30 jobs.

Its rows encode simple assumptions: more complexity, more deliverables and more integrations mean more hours and a higher price, and jobs with unclear requirements tend to run late or get cancelled. An estimator fitted on this file mostly learns those planted rules back. That shows the pipeline works. It says nothing about how long real work takes or how accurate briefquote is.

**Estimates are only meaningful after you replace this file with your own history.** Either overwrite `data/past_jobs.csv` or pass `--history your_jobs.csv` to `briefquote estimate`, `quote` or `serve`. While the bundled file is in use, briefquote prints a warning to stderr, and the quote footnote, web UI and replay say the history is a synthetic example.

## Columns

| column | meaning |
| --- | --- |
| `project_type` | one of `web, mobile, data, ai_automation, design, writing, devops, other` |
| `complexity` | 1 to 5 |
| `deliverables_count` | number of deliverables |
| `integrations_count` | third-party systems integrated |
| `has_design_provided` | `true` / `false` |
| `has_clear_requirements` | `true` / `false` |
| `hours_actual` | hours actually spent |
| `price_usd` | what was charged |
| `outcome` | `delivered`, `delivered_late` or `cancelled` |

Cancelled jobs are ignored for hours and price but count toward the on-time probability.

## License note

TabPFN model weights are licensed for non-commercial use only. Selling quotes built on briefquote needs a commercial TabPFN license from Prior Labs, or the `--no-tabpfn` baseline estimator. The CSV itself is example data released with the MIT-licensed briefquote code.
