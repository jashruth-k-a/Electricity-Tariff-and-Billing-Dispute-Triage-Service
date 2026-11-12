# Evaluation definitions and limits

`evaluation/cases.json` contains 22 fixed synthetic scenarios. Each lists expected routing,
escalation, verification and supporting clauses; the passages are in `corpus/demo/*.json`.
The tailoring case is included. These are engineering reference answers, not regulatory
ground truth. The separate `evaluation/official-cases.json` contains 24 source-labelled official
cases. Faculty confirmation remains a human academic action. The official profile uses real
generation and local semantic embeddings; report its results separately from the synthetic set.

Long evaluations checkpoint each completed case to the configured output file. A variant
with `complete: false` is a partial run, not a completed benchmark. Version v4 uses shorter
instructions and a response contract matched to constrained local generation; v1 remains the
baseline. Both use the same backend, evidence, constraints and independent verifier in a run.
Version v5 explicitly requires a separate modifier search and both tariff and supply citations
for a home business. It was the earlier hosted-model candidate; v1 is the comparison baseline.
Version v6 keeps that investigation policy and selects passage IDs instead of retyping
quotations. Both baseline and final production variants use the same deterministic citation
assembly and input compaction. Groundedness may therefore be high by construction; it
does not prove that the cited passage entails a claim. Read faithfulness, strict reference
coverage and the independent judge's limitations alongside it.

Malformed completed model output fails its current run without opening the shared provider
availability breaker. HTTP/network outages retain retries and circuit protection. This keeps
a weak prompt's schema mistakes from suppressing later cases or another prompt variant.
Official cases additionally check the issue type on supported in-scope recommendations.
The set includes arrears and disconnection referrals as well as category, meter and load cases.

Run `docker compose run --rm tools evaluate`. This runs both prompt versions against the
same cases with whole-run caching bypassed. Version v1 investigates the apparent category;
v2 explicitly searches mixed/changed-use modifiers. Both still use the same verifier.
The deliberate change is the investigator prompt only. Results preserve every audit event.

Four reproducible metrics, averaged over cases:

| Metric | Computation |
|---|---|
| Groundedness | Candidate claims whose supporting citations all resolve to retrieved exact text / all candidate claims. This is citation grounding, not semantic entailment. |
| Context relevance | Unique retrieved chunks whose clause is in the case's reference support set / all unique retrieved chunks. A precision proxy; extra useful passages may be penalised. |
| Faithfulness | Candidate claims in recommendations accepted by the independent verifier / all candidate claims. A rejected multi-claim answer counts all its claims as unfaithful. |
| Hallucination rate | Candidate claims in rejected recommendations / all candidate claims. Conservative unsupported-answer proxy; includes policy/format failures. |

If there are no candidate claims, all four metrics are zero; the separate route/verification
pass rate must be read alongside them. A safe unsupported-case escalation can pass its
reference case while having no answer-quality score. Candidate metrics include failed
drafts even when the final service safely escalates. Also report final expected-outcome
pass rate, latency, model calls and cost. Do not call demo fixture scores real-model quality.

The verifier combines deterministic schema, citation and provenance checks with a semantic
model judge in provider mode. Demo mode replaces that judge with explicit fixture rules.
This is an equivalent custom evaluator, rather than a claim of using TruLens. A model judge
is fallible; official-reference validation should include a human-labelled sample.

Every fifth live run is scored automatically using the same audit logic, but without an
expected support set: context relevance then means cited chunks / retrieved chunks.
The dashboard and Prometheus label these as proxies and chart them over time.

Token counts are recorded when a successful provider response is received, before JSON
parsing or verification. Failed requests without usage information are logged as unknown,
not asserted to have zero provider cost. Stub token counts are character/4 estimates;
stub monetary cost is explicitly zero. Set provider input/output prices and pricing date
label at runtime for meaningful real-model cost per 100 runs.

Some compatibility endpoints report thinking in `total_tokens` while omitting it from
`completion_tokens`. The adapter retains raw provider usage and accounts for the larger
of reported completion tokens and total minus prompt tokens. Cost estimates therefore
include reported reasoning output. Published-rate estimates are not actual invoices or a
claim that a free-tier account was charged. Unknown usage on failed requests stays unknown.
