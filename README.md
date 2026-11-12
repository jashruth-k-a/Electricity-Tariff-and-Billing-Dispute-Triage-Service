# Electricity Tariff and Billing Dispute Triage Service

Course: Machine Learning System Design & AgentOps · Mini Project 11 · Three-member team.

A FastAPI service queues an electricity billing dispute, lets a LangGraph investigator
choose retrieval tools, and sends its proposed position to an independently deployed
LangGraph verifier. Only verified, cited recommendations are returned. Unsettled cases and
failures go to a human grievance officer. The application never modifies or recalculates bills.

**Default mode is a fully local synthetic demonstration.** Its teaching provisions and model
stub are prominently labelled. They are not Karnataka regulations. The separate real local-model
profile includes three official PDFs, reviewed clause annotations and semantic embeddings.
Its completed real-model comparison improved strict reference matches from 6/24 to 15/24;
nine misses remain documented. The required tailoring case and the public workflow passed.
Synthetic results are separate infrastructure evidence and do not establish regulatory accuracy.
See [official corpus and startup](docs/official-corpus.md), including the LT-1 tailoring exception
and the technical review boundary.

## Start from a clean clone

Requirements: Docker Desktop with Linux containers, Compose v2, internet for first image
build, and enough disk/memory for Chroma and observability services (8 GB Docker memory
is a useful starting allocation). No host Python, Redis, Node or model account is required.

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

On Linux/macOS use `cp .env.example .env`. Do not overwrite an existing configured `.env`.
Everything runs in containers. The one-shot `corpus-init` service must exit successfully;
API and workers wait for dependencies and health checks. Initial dependency/image downloads
can take several minutes. Normal startup after a build uses `docker compose up -d`.

| Interface | Default local address |
|---|---|
| Officer application | http://localhost:8011 |
| OpenAPI / interactive contracts | http://localhost:8011/docs |
| Readiness | http://localhost:8011/health/ready |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Jaeger | http://localhost:16686 |

Ports and deployment configuration are injected through `.env`. Grafana credentials are
the values in that file. Example secrets are local-demo values; replace them when configuring
real providers or clients. Internal services have no host ports. Data and report outputs
persist in Docker volumes and ignored `data/`/`output/` directories. `docker compose stop`
stops services without deleting state. `docker compose down` removes containers/networks
but preserves named data volumes; avoid `down -v` unless deletion is intentional.

## Try a dispute

For the official-document workflow, follow [official profile setup](docs/official-corpus.md).
The measured Gemini preset is `.env.gemini.example`; copy it to `.env.official`, add your provider key
and start with the official Compose overlay. The base commands above run synthetic fixtures.
The Groq preset `.env.groq.example` is an alternate with a passing reference probe.

Open the web client and submit the prefilled home-tailoring case. It shows the route,
supporting exact quotes, human-referral basis, latency, prompt version and recorded cost.
Expand the audit trail to inspect agent/tool decisions. Submit officer feedback afterward.
Demo rules intentionally escalate unresolved mixed use; official rules must be reviewed
separately and may settle a listed home activity differently.

API example:

```powershell
$body = @{
  state = "Karnataka"
  connection_type = "LT"
  billed_category = "domestic"
  premises_use = "mixed"
  description = "I run a small tailoring shop from one room of my house. Please check my domestic category."
  connected_load_kw = 3
  sanctioned_load_kw = 5
  billing_date = "2026-10-01"
  business_activity = "tailoring"
} | ConvertTo-Json
$run = Invoke-RestMethod -Method Post -Uri http://localhost:8011/v1/disputes -ContentType application/json -Body $body
Invoke-RestMethod -Uri "http://localhost:8011/v1/runs/$($run.run_id)"
```

The first call returns HTTP 202 and a run ID immediately. Poll until `completed`, `escalated`
or `failed`. Do not interpret a pending/failed run as a recommendation. Supply `X-API-Key`
if client keys are configured. Optional `Idempotency-Key` deduplicates submission per client
for 24 hours; a different body with the same key returns 409. Whole-run cache hits reference
the original verified audit. All returned positions are advisory to the officer.

## Verify the implementation

```powershell
docker compose exec api python scripts/smoke.py
docker compose exec -e OTEL_EXPORTER_OTLP_ENDPOINT= api python -m pytest -q -p no:locust
docker compose run --rm tools evaluate
docker compose exec api python scripts/resilience_demo.py
docker compose exec api python scripts/rate_limit_demo.py
```

Smoke tests exercise the real queue, both agents, both required teaching passages,
quarantine, injection/toxicity handling, out-of-scope escalation, idempotency and feedback.
The unit suite covers validation, exact citation support, uncited claims, authority filtering,
loop limits, missing bearer tokens and Chroma call timeouts. The resilience script injects
unsupported answers, verifies additional search and eventual escalation, opens the circuit
with a provider outage, checks fast fallback, then waits for a successful recovery probe.
Run it separately from evaluation/load tests because its faults affect the shared stub.
The rate-limit demonstration requires the normal configuration, without the load overlay.

Evaluation runs 22 fixed scenarios against v1 and v2, bypassing result caching. It writes
`output/evaluation.json`, including full audits and before/after metrics. Definitions and
limitations are in [evaluation.md](docs/evaluation.md). Stub metrics are engineering fixture
results, never a claim of real-model regulatory accuracy. A sampled live-run quality trend
and aggregated feedback are visible in the web dashboard/Grafana.

## Performance and scaling

The [SLO](docs/slo.md) was declared before measurement: p95 <= 60 seconds at three concurrent
clients with one worker and 1.5 seconds per stub model completion, plus >=95% verified results.
Timing includes queue wait and polling to the terminal result. Failed/deadline referrals
cannot masquerade as useful low-latency answers.

For controlled load tests, use the load overlay to raise only the demo rate limit and
explicitly set cache behaviour:

```powershell
$env:LOAD_CACHE_ENABLED = "false"
docker compose -f compose.yaml -f compose.load.yaml up -d --scale agent-worker=1
docker compose -f compose.yaml -f compose.load.yaml run --rm loadtest python scripts/load_test.py --users 3 --seconds 45 --workers 1 --label one-worker
docker compose -f compose.yaml -f compose.load.yaml up -d --scale agent-worker=3
docker compose -f compose.yaml -f compose.load.yaml run --rm loadtest python scripts/load_test.py --users 3 --seconds 45 --workers 3 --label three-workers
```

Repeat at increasing concurrency to locate failure of the declared target. For caching,
run a repeated workload using `--repeated` with cache false, then true; change
`$env:LOAD_CACHE_ENABLED = "true"`, recreate API/workers with the same overlay, and rerun.
Every test writes Locust CSV/HTML, per-run records and a JSON summary under `output/load/`.
The worker-count argument records the setup; the actual replica count must match it.

Restore ordinary cost-control limits after the experiment:

```powershell
Remove-Item Env:LOAD_CACHE_ENABLED -ErrorAction SilentlyContinue
docker compose up -d --scale agent-worker=1
```

## Corpus and real-provider mode

```powershell
docker compose run --rm tools fetch
docker compose run --rm tools ingest
docker compose run --rm tools ingest --reembed
```

`fetch` downloads the hash-pinned official research sources; it does not approve them.
`ingest` uses `CORPUS_MANIFEST` from `.env`, so default ingestion indexes the synthetic corpus.
The active official corpus packages three public PDFs, 14 annotations and 24 reference cases.
Follow [official-corpus.md](docs/official-corpus.md) for the bounded amendment review and
production setup. The official overlay uses local Ollama semantic embeddings and needs no
sentence-transformers extra. The optional sentence-transformers adapter uses
`INSTALL_SEMANTIC=true`. Production requires semantic embeddings, explicit model/provider
configuration, pricing and a technically reviewed manifest. Client keys can be enabled;
the provided course deployment binds its public ports to loopback.
Models/endpoints/credentials are runtime configuration. Never commit `.env`.

Changing the corpus, prompt or provider invalidates cached result identities. Indexing is
idempotent and records document hashes, versions, chunk count, build timestamp and throughput.
Unsupported dates, HT/EHT, other states and excluded agricultural categories escalate.
This initial project scope is LT residential/commercial/industrial tariff triage in one state;
it is not universal electricity grievance adjudication.

## Project guide

- [Architecture, deployment boundaries and rejected alternatives](docs/architecture.md)
- [Data contracts and endpoint behaviour](docs/data-contracts.md)
- [Requirement-to-code matrix](docs/requirements.md)
- [Three-member ownership and learning guide](docs/team-plan.md)
- [Project plan](docs/project-plan.md) and [faculty reference-case packet](docs/reference-case.md)
- [Demonstration checklist](docs/demo.md)
- [Runbook](docs/runbook.md) and [genuine incident log](docs/incident-log.md)
- [Project report](docs/report.md) and [measured validation results](docs/validation.md)
- [Official real-model comparison and failed-case analysis](docs/official-evaluation.md)
- [Recorded official tailoring answer](evaluation/results/official-reference-answer.json)
- [Token-cost assumptions](docs/pricing.md)

The checked-in requirements lock pins the tested base/dev dependency set. Semantic-model
dependencies are an optional extra and must be pinned in the final real-provider environment.
For source editing, `compose.dev.yaml` mounts current Python/web files; default Compose
uses built images. Rebuild images after edits when using default Compose. No Git commits
or pushes are performed by the application or setup commands.
