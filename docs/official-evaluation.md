# Real-model official reference evaluation

Measured 2026-11-07. Model identities returned by the provider: gemini-3.1-flash-lite.
Source: `output/official-evaluation.json`; compact evidence: `evaluation/results/official-comparison.json`.
Full prompts, completions, exact retrieval results, canonical citations, verification decisions,
usage and timing remain in the ignored full audit. Credentials are not included.

## Controlled comparison

The same 24 fixed official-reference cases were run sequentially with caching bypassed.
Both variants use the same provider/model, source corpus, citation assembly, request pacing,
validation and independently deployed verifier. v1 investigates the apparent category with a
short output specification. v6 explicitly separates applicability from misuse/changed-use
research, distinguishes household exceptions from independent shops, specifies the advisory
output shape and requires re-search after rejection. Prompt files and resolved hashes are audited.

Expected-outcome pass rate: **v1 6/24
(25.00%) -> v6 15/24
(62.50%)**, a change of +37.50 percentage points.
This strict result checks route, escalation, verification, required source clauses and the
issue type where labelled. It is not a claim of general regulatory accuracy.

| Metric, averaged over all cases | v1 | v6 | Change |
|---|---:|---:|---:|
| groundedness | 0.7500 | 0.5000 | -0.2500 |
| context_relevance | 0.2333 | 0.2639 | +0.0306 |
| faithfulness | 0.0417 | 0.4583 | +0.4167 |
| hallucination_rate | 0.7083 | 0.0833 | -0.6250 |

These are the proxies defined in evaluation.md. No-answer cases have zero answer-quality
scores; an expected unsupported-case referral can still pass. Exact quotation/provenance
is constructed from retrieved IDs, so grounding can be high by construction. Semantic
faithfulness still depends on a fallible model judge. Malformed drafts rejected before
handoff are visible in failure events and pass rate, not counted as verified candidate claims.
Required-clause scoring can reject a different valid supporting provision; inspect failed
cases with faculty instead of changing labels merely to make the model pass.

## Timing, usage and estimated cost

| Measure | v1 | v6 |
|---|---:|---:|
| Final verified recommendations | 1/24 | 11/24 |
| Model responses | 56 | 44 |
| p50 end-to-end seconds | 16.29 | 13.04 |
| p95 end-to-end seconds | 128.91 | 42.38 |
| Configured-price estimate per 100 runs, USD | 0.1586 | 0.0812 |

Final-variant reported tokens: 49587 input and
4722 output, including reported reasoning. The largest agent cost
driver is **investigator**. Repeated investigation and context-bearing model calls drive cost.
The rate label in the audit identifies the published pricing assumption; estimates are not
invoices, and free-tier usage can have zero actual API charges. Failed calls without usage
have unknown token/cost consumption rather than a proven zero charge.

Latency includes failed and safe-referral runs, so lower latency alone is not proof of useful
throughput. The batch uses one concurrent client and shared provider pacing. These observational real-model
latencies do not replace the predeclared controlled delayed-stub load experiments in validation.md.
Provider quotas are a bottleneck that extra worker replicas cannot remove.
Final cases with a failed outcome accompanied by HTTP quota/5xx errors: 0.

## Per-case results

| Case | v1 | v6 | Final-reference observation |
|---|---|---|---|
| residential-correct | fail | pass | matches reference |
| residential-misclassified | fail | fail | missing reference support: Annexure-9 / LT-1; route differs; verified differs; escalation_required differs; issue_type differs; Invalid agent action; human review required. |
| tailoring-reference | fail | pass | matches reference |
| tailoring-independent-shop | fail | fail | missing reference support: Annexure-9 / LT-5; route differs; verified differs; escalation_required differs; issue_type differs; Invalid agent action; human review required. |
| beauty-parlour-at-home | fail | pass | matches reference |
| beauty-parlour-independent | fail | fail | missing reference support: Annexure-9 / LT-3(a); route differs; verified differs; escalation_required differs; issue_type differs; Invalid agent action; human review required. |
| legal-consultancy-at-home | fail | pass | matches reference |
| medical-consultancy-at-home | fail | pass | matches reference |
| private-clinic-independent | fail | fail | missing reference support: Annexure-9 / LT-3(a); route differs; verified differs; escalation_required differs; issue_type differs; Invalid agent action; human review required. |
| job-typing-at-home | fail | pass | matches reference |
| paying-guests-shared-home | fail | fail | missing reference support: 42.02(a), Annexure-9 / LT-1; route differs; verified differs; escalation_required differs; issue_type differs; The required evidence re-search was not performed; human review required. |
| paying-guests-exclusive-premises | fail | pass | matches reference |
| bakery-manufacturing | fail | fail | missing reference support: Annexure-9 / LT-5; route differs; verified differs; escalation_required differs; issue_type differs; Invalid agent action; human review required. |
| bakery-retail | fail | pass | matches reference |
| load-discrepancy | fail | pass | matches reference |
| meter-accuracy | fail | fail | missing reference support: 6(11)(vii)-(xi); The consumer disputes the accuracy of the meter, and the procedure requires a formal inspection and testing by a Third Party Agency as per clause 27.01. |
| unsettled-mixed-workshop | pass | pass | matches reference |
| unknown-premises-facts | pass | pass | matches reference |
| outside-state | pass | pass | matches reference |
| outside-ht | pass | pass | matches reference |
| outside-agriculture | pass | pass | matches reference |
| outside-reviewed-period | pass | pass | matches reference |
| arrears-documentary-dispute | fail | fail | missing reference support: 7 / complaints-handling; verified differs; issue_type differs; The required evidence re-search was not performed; human review required. |
| disconnection-documentary-dispute | fail | fail | missing reference support: 10 / grievance-redressal; verified differs; issue_type differs; Invalid agent action; human review required. |

## Review boundary

The three primary PDFs and 14 annotations cover the selected Karnataka LT questions and
reviewed billing period. Technical source review and evaluation labels are not faculty
approval or a binding legal opinion. The service never recalculates bills. Faculty corpus
confirmation, the live demonstration/viva and the team's GitHub publication remain human steps.
