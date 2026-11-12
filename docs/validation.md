# Measured validation

## Real-model validation status (2026-11-07)

The official profile indexes three primary PDFs, 14 annotations and 18 chunks with local
semantic embeddings. The selected tariff annex covers FY2026-27; the active review cutoff
is 2026-11-06, not a statutory expiry. Faculty confirmation is not claimed.

The alternate Groq/Qwen v6 tailoring reference passed in 32.46 seconds with both LT-1 and 42.02(a),
three real model responses and independent verification. Exact source text and metadata
are assembled from model-selected passage IDs; the semantic judge still checks entailment.
The completed 24-case v1/v6 comparison is in [official-evaluation.md](official-evaluation.md):
strict matches improved from 6/24 to 15/24, with no quota errors in the completed run.
The final public official-profile smoke passed nine checks, including a verified tailoring
run in 20.84 seconds, idempotency, cache reuse, quarantine, referral, audit and feedback.
A passing reference is not a general accuracy claim.

The completed measured profile uses Gemini 3.1 Flash-Lite. Its standalone reference passed
in 24.19 seconds, the fixed-set reference passed again, and the fresh public smoke passed
in 20.84 seconds. Both complete prompt variants had zero HTTP 429 cases. Eight of the nine
final strict misses returned unverified referrals; the remaining meter case used a verified
testing provision different from the reference's required clause.

Current regression suite: 51 tests passed in the Linux application container. An isolated
image startup with fresh Redis/Chroma volumes passed all nine public API smoke checks and
all 46 then-current tests. After the final breaker change, the isolated resilience drill
again passed unsupported-answer re-search, outage/open-circuit fallback and recovery.

Earlier CPU probes failed verification, repeated queries or reached a deadline. Gemini
eventually passed the reference but its 20-request daily quota interrupted a batch. A later
comparison exposed malformed model output incorrectly opening the shared outage breaker;
that run was excluded, the distinction was fixed and both variants were restarted.
The incident log and compact evidence preserve these failures. Browser automation timed
out again; screenshot-based visual QA remains unverified.

## Archived controlled synthetic experiments

The results below are infrastructure/fixture evidence only, not official model accuracy.

Recorded on 2026-11-06. The full runtime is Docker Desktop Linux/WSL2; Docker reports
16 CPUs and 7,975,665,664 bytes of available memory. The model is a deterministic synthetic
stub with 1.5 seconds delay per completion. Hash embeddings index nine synthetic passages.
All numbers below are measured fixture results, not claims about regulatory/model accuracy.

## Functional verification

- Container unit suite: 35 tests passed at the first completed regression run; the final
  verification command/output is recorded alongside delivery.
- Final image-only check used fresh Redis/Chroma volumes in an isolated Compose project:
  all smoke checks and all 35 tests passed. The temporary project was removed afterward.
- Normal public limit accepted 12 requests and returned HTTP 429 on the next request.
  Final readiness was HTTP 200; all nine configured Prometheus scrape targets were up.
  Compact delivery evidence is in `evaluation/results/delivery-check.json`.
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
| groundedness | 0.7727 | 0.7727 | +0.0000 |
| context_relevance | 0.3500 | 0.5152 | +0.1652 |
| faithfulness | 0.5000 | 0.7727 | +0.2727 |
| hallucination_rate | 0.2727 | 0.0000 | -0.2727 |

Expected-outcome pass rate: v1 68.18%, v2 100.00%.
The deliberate change is explicit modifier retrieval in the v2 investigator prompt.
The independent verifier remains enabled for both. Read the precise metric definitions in
evaluation.md: these are conservative citation/judge proxies, and no-answer cases have
zero answer-quality scores. A safely escalated case can still pass its expected outcome.

v2 made 90 stub completions for 22 scenarios. During the
recorded comparison the investigator made 73 and the verifier 17 completions; investigation
is the largest call-count driver. Total configured cost and cost per 100 runs are zero
because the local stub has zero prices. Monetary cache savings cannot be inferred from
that zero baseline. Real usage/pricing is recorded by the same adapter when configured.

## Performance experiments

Target declared in slo.md BEFORE measurement: p95 <= 60 seconds at three concurrent clients,
one worker and 1.5 seconds per completion, with at least 95% verified useful results.

| Experiment | Workers | Clients | Terminal runs | Terminal RPS | p50 s | p95 s | Verified | Target met |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| cache-off | 3 | 3 | 6 | 0.304 | 8.56 | 8.65 | 100% | yes |
| cache-on | 3 | 3 | 63 | 3.771 | 0.02 | 0.04 | 100% | yes |
| one-worker-c3 | 1 | 3 | 6 | 0.111 | 25.22 | 25.67 | 100% | yes |
| one-worker-c9 | 1 | 9 | 12 | 0.116 | 59.12 | 75.48 | 100% | no |
| three-workers-c3 | 3 | 3 | 12 | 0.310 | 8.58 | 9.28 | 100% | yes |
| three-workers-c9 | 3 | 9 | 18 | 0.339 | 25.02 | 25.70 | 100% | yes |

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
