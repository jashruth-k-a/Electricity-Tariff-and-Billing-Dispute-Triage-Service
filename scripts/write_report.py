"""Generate the concise course report from saved, measured experiment summaries."""
import json
from pathlib import Path

source = Path("evaluation/results")
comparison = json.loads((source / "prompt-comparison.json").read_text())
variants = comparison["variants"]
loads = [json.loads(p.read_text()) for p in sorted(source.glob("*-summary.json"))]
metric_rows = []
for metric in ["groundedness", "context_relevance", "faithfulness", "hallucination_rate"]:
    before, after = (variants[v]["metrics"][metric] for v in ["v1", "v2"])
    metric_rows.append(f"| {metric} | {before:.4f} | {after:.4f} | {after-before:+.4f} |")
load_rows = [f"| {r['label']} | {r['worker_count']} | {r['users']} | {r['completed_runs']} | {r['terminal_rps']:.3f} | {r['p50_seconds']:.2f} | {r['p95_seconds']:.2f} | {r['verified_fraction']:.0%} | {'yes' if r['slo_met'] else 'no'} |" for r in loads]
validation = """# Measured validation

Recorded on 2026-11-06. The full runtime is Docker Desktop Linux/WSL2; Docker reports
16 CPUs and 7,975,665,664 bytes of available memory. The model is a deterministic synthetic
stub with 1.5 seconds delay per completion. Hash embeddings index nine synthetic passages.
All numbers below are measured fixture results, not claims about regulatory/model accuracy.

## Functional verification

- Container unit suite: 35 tests passed at the first completed regression run; the final
  verification command/output is recorded alongside delivery.
- Public API smoke checks: tailoring retrieval, full audit, range/cross-field quarantine,
  injection/toxicity rejection, out-of-corpus escalation, idempotency/conflict and feedback.
- Resilience drill: fabricated quote rejected -> another search -> escalation; provider
  outage -> retries -> open circuit; subsequent call fast-falls back; cooldown probe recovers.
- Prometheus targets for API, workers, verifier, stub, Redis, containers and Prometheus were
  all up. Grafana returned healthy. Jaeger listed API, investigator-worker and verifier traces.
- Native browser preview timed out in the desktop automation environment; no visual
  screenshot-based browser QA is claimed. Static assets/API and frontend contract were checked.

## Prompt comparison: same 22 cases

| Metric | v1 | v2 | Change |
|---|---:|---:|---:|
""" + "\n".join(metric_rows) + f"""

Expected-outcome pass rate: v1 {variants['v1']['pass_rate']:.2%}, v2 {variants['v2']['pass_rate']:.2%}.
The deliberate change is explicit modifier retrieval in the v2 investigator prompt.
The independent verifier remains enabled for both. Read the precise metric definitions in
evaluation.md: these are conservative citation/judge proxies, and no-answer cases have
zero answer-quality scores. A safely escalated case can still pass its expected outcome.

v2 made {variants['v2']['total_model_calls']} stub completions for 22 scenarios. During the
recorded comparison the investigator made 73 and the verifier 17 completions; investigation
is the largest call-count driver. Total configured cost and cost per 100 runs are zero
because the local stub has zero prices. Monetary cache savings cannot be inferred from
that zero baseline. Real usage/pricing is recorded by the same adapter when configured.

## Performance experiments

Target declared in slo.md BEFORE measurement: p95 <= 60 seconds at three concurrent clients,
one worker and 1.5 seconds per completion, with at least 95% verified useful results.

| Experiment | Workers | Clients | Terminal runs | Terminal RPS | p50 s | p95 s | Verified | Target met |
|---|---:|---:|---:|---:|---:|---:|---:|---|
""" + "\n".join(load_rows) + """

Locust records a separate RUN/terminal sample spanning submission, queue wait, execution and
polling to the final result. RPS above divides completed runs by wall time including drain;
it is deliberately different from HTTP polling RPS. Short runs and small sample counts
limit tail-percentile precision. These are local engineering experiments, not a sustained
capacity certification. The first one-worker experiments ran while an image build was
finishing in the background; this is a noise source for precise cross-experiment comparisons.
Raw per-run records and Locust HTML/CSV remain under ignored output/load/; compact summaries
are checked in under evaluation/results/.

The one-worker grid tested three and nine clients: three met the target, nine exceeded it.
This identifies an observed failing concurrency of nine, not the exact smallest integer
boundary. The bottleneck is serial per-worker investigation while waiting on several
delayed model calls; queue wait grows approximately with queued runs. Scaling competing
workers improves throughput and queue latency until another component or provider quota
dominates. The stub has no provider rate limit and its delay uses asynchronous sleep.

Caching experiments use the same repeated request with cache off/on. Only verified complete
results enter the cache; a cache hit avoids repeated agent/model calls and retains its source
audit. Report p95 and call avoidance, but do not claim a positive monetary saving from the
zero-priced stub. Public rate limiting is restored after controlled tests.

## Remaining evidence gates

The official 2025 tariff PDF and historical supply compilation were downloaded and hashed.
Current supply amendments and faculty reference confirmation are still pending. Production
mode is fail-closed until an approved corpus, local semantic embeddings, provider/client
credentials and explicit prices are supplied. No paid/free-tier real model was called, no
official-reference accuracy is claimed, and no Git commit/push was made.
"""
Path("docs/synthetic-validation.md").write_text(validation, encoding="utf-8")
report = """# Mini Project 11 - Electricity Tariff and Billing Dispute Triage Service

Course: Machine Learning System Design & AgentOps. Team size: three. Implementation snapshot:
2026-11-06. This report describes the delivered implementation and its measured synthetic
demonstration; regulatory corpus confirmation remains a separate deliverable.

## Problem, objective and scope

An electricity grievance officer needs a justified tariff position for a disputed bill.
Category definitions may be modified by mixed/changed-use provisions elsewhere in the order
or supply code. The service must find those provisions, cite them and know when to refer
the case to a human. It never revises a bill or computes a binding liability.

The initial scope is Karnataka LT residential/commercial/industrial premises. Meter, load,
arrears and disconnection disputes are classified and routed for human/physical investigation
when tariff evidence alone cannot settle them. Other states, HT/EHT, agriculture, unsupported
dates, missing evidence and conflicting provisions are referred rather than guessed.

The default runnable corpus is explicitly synthetic. Official-source research found the
2025 order's LT-1 home-tailoring applicability and LT-5 tailoring-shop applicability; the
downloaded supply compilation is historical. Current amendments and the faculty reference
answer must be confirmed before presenting official results (official-corpus.md).

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
Actual provider accuracy, current official supply-code coverage, human reference labels and
faculty corpus confirmation remain unverified. Stub completions and regex guardrails are
not substitutes for a real-model adversarial/regulatory benchmark. A real provider's
spending limit and explicit token prices must be configured before that work. The project
runs locally; cloud deployment/model training are outside scope.

## Teamwork and deliverables

Member 1 owns corpus/retrieval/reference labels; member 2 owns agents/verification/evaluation;
member 3 owns API/platform/observability/performance. All members review shared contracts
and the official reference case. team-plan.md maps responsibilities to files and viva topics.
The README provides clean startup and repeatable test commands; demo.md maps the ten live
demonstration items. Runtime secrets and raw/output data are ignored. Git history is left
for the team to create and review.
"""
Path("docs/synthetic-report.md").write_text(report, encoding="utf-8")
print("Updated archived synthetic-validation.md and synthetic-report.md; current delivery reports preserved")
