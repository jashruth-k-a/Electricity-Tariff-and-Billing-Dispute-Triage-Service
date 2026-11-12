# Mini Project 11 - Electricity Tariff and Billing Dispute Triage Service

Course: Machine Learning System Design & AgentOps. Team size: three. Implementation snapshot:
2026-11-07. This report covers the implemented system, controlled synthetic engineering
experiments and completed official-document real-model evaluation. The final prompt matched
15/24 strict references, compared with 6/24 for the baseline. The required tailoring case
passed. Model limitations and nine reference misses remain explicit; faculty sign-off is
not represented.

## Problem, objective and scope

An electricity grievance officer needs a justified tariff position for a disputed bill.
Category definitions may be modified by mixed/changed-use provisions elsewhere in the order
or supply code. The service must find those provisions, cite them and know when to refer
the case to a human. It never revises a bill or computes a binding liability.

The initial scope is Karnataka LT residential/commercial/industrial premises. Meter, load,
arrears and disconnection disputes are classified and routed for human/physical investigation
when tariff evidence alone cannot settle them. Other states, HT/EHT, agriculture, unsupported
dates, missing evidence and conflicting provisions are referred rather than guessed.

The default base profile is explicitly synthetic. The separate official profile indexes
selected LT-1 residential, LT-3 commercial and LT-5 industrial applicability alongside
selected supply and consumer-rights provisions. It includes the home-tailoring exception
and a bounded review of listed amendments. Faculty confirmation of the demonstration's
reference answer remains outstanding (official-corpus.md).

## Agent design and architecture

The FastAPI ingestion boundary validates types/ranges/categories/cross-field relationships,
screens text and quarantines rejects. Valid requests enter Redis RQ and return a run ID.
Polling is suitable for an officer waiting interactively and avoids callback delivery secrets.
The web client displays the advisory recommendation, evidence, escalation, audit and feedback.

The investigator is a LangGraph agent with its own state and chosen search/clause/request
tools. It can inspect passages and reformulate queries, rather than follow a fixed retrieval
pipeline. A separately deployed LangGraph verifier re-resolves passage provenance, checks
citations/policy and judges semantic support. Rejection triggers a different search or human
referral. At most two candidate verification attempts occur; configured step/tool/wall-time
limits and individual call timeouts bound work. Provider retries use exponential backoff and
a shared circuit breaker. Incomplete runs return no confident tariff position.

See architecture.md for the Mermaid architecture diagram with deployment boundaries,
failure behaviour, chunking/embedding design and cache identity. API, workers, verifier,
Redis and Chroma have independent scaling/failure/resource profiles. A batch initializer,
delayed provider stub, Prometheus/Grafana, Jaeger, Redis exporter and cAdvisor complete the
local Compose deployment. Dependencies and health checks gate startup.

## Engineering choices and rejected alternatives

LangGraph gives explicit, inspectable loops and handoffs; LangChain tools/Runnable and
Chroma implement chosen hybrid retrieval. Local embeddings avoid embedding API cost.
Page/clause metadata, hashes, versions and effective periods keep evidence auditable.
Idempotent ingestion skips unchanged chunk identities; re-embedding does not delete unrelated
collections. Only verified whole-run answers are cached, keyed by client/facts/corpus/prompt/
model identity; per-client throttling limits repeated multi-step provider expenditure.

Rejected alternatives include a single embedding pass, a blocking long HTTP submission,
two prompts masquerading as independently deployed agents, and automatic bill recalculation.
Regex screening is a documented baseline, combined with tool restrictions, untrusted-data
prompts, output filtering and verification; it is not asserted to stop every injection.

## Evaluation, reliability, latency and cost

The fixed 22-case CLI benchmark compares v1/v2 on identical cases, preserving every tool,
query, passage, prompt version/hash, usage/cost and verification result. A custom equivalent
evaluator computes four explicitly defined metrics; evaluation.md documents their limits.
Feedback is persisted/aggregated, and every fifth live run produces a charted quality proxy.
Measured before/after metrics, SLO, throughput, p50/p95, scaling and cache experiments are
reported in validation.md and the machine-readable evaluation/results/ summaries.

The separate official comparison ran 24 fixed cases on Gemini 3.1 Flash-Lite, with the same
provider, corpus, citation assembly and pacing for v1 and v6. Strict matches improved from
25.00% to 62.50%. Groundedness changed 0.7500 -> 0.5000, context relevance 0.2333 -> 0.2639,
faithfulness 0.0417 -> 0.4583, and the unsupported-claim proxy 0.7083 -> 0.0833. No-answer
cases score zero, so lower average grounding does not itself mean worse source quotation.
The metric definitions and per-case failures are in official-evaluation.md.

Observed serial-batch p95 changed from 128.91 to 42.38 seconds. Configured list-rate cost
per 100 runs changed from USD 0.1586 to 0.0812; these are estimates, not invoices. The
investigator was the largest cost driver. These observations include provider pacing and
do not replace the predeclared delayed-stub concurrency SLO/load experiments.

All 51 final unit tests and all nine official public API smoke checks passed. The public
tailoring run completed with both required provisions in 20.84 seconds; the verified-result
cache, idempotency/conflict, quarantine, out-of-scope referral, audit and feedback were checked.

Fault drills demonstrate self-verification, another search, outage retries/circuit breaking,
safe fallback and recovery. Structured logs share run IDs and W3C tracing crosses API,
worker and verifier. Grafana exposes run/step latency, outcomes, calls, retries, uptime,
resource usage and quality. Chroma application-query metrics are a documented remaining
improvement; container/resource health and ingestion measurements are present.

## What did not work and practical limits

Development uncovered a rejected custom Chroma client, an invalid empty bearer header,
stale worker import paths, an occupied API port and a host Windows test-client stall. These
were diagnosed using real tracebacks/audits and fixed; incident-log.md records operational
failures and runbook.md gives confirmation/recovery for provider and corpus/worker outages.

The desktop browser preview timed out, so screenshot-based visual QA is not claimed.
Three official PDFs and 14 source-validated annotations are now packaged, with a bounded
amendment review and a separate 24-case reference set. This is a technical review, not faculty
confirmation. The final reference set had nine strict misses: eight unverified human
referrals and one verified meter-testing referral using a different source clause from
the reference. Model formatting, tool-argument reliability and strict clause selection
remain limitations. The full schema-union follow-up was rejected by the provider's
compatibility endpoint and was not enabled in the runtime; hosted generation uses JSON
object mode with local validation and deterministic citation assembly. Initial failed
probes and interrupted comparisons are preserved, not counted as successful accuracy runs.
Stub completions and regex guardrails are not substitutes for regulatory human review.
Local Ollama needs no paid
API key; its zero API pricing does not account for electricity or hardware. The project
runs locally; cloud deployment/model training are outside scope.

## Teamwork and deliverables

Jashruth owns agent design and verification. Harshitha owns corpus, retrieval, and evaluation.
Hamsa owns the API, deployment, and operations. All members review shared contracts
and the official reference case. team-plan.md maps responsibilities to files and viva topics.
The README provides clean startup and repeatable test commands; demo.md maps the ten live
demonstration items. Runtime secrets and raw/output data are ignored. Git history is left
for the team to create and review.
