# External data contracts

All JSON text is UTF-8. OpenAPI is published at `/openapi.json`; interactive documentation
is `/docs`. Machine-readable request/recommendation/verification schemas are versioned in
`docs/contracts/`. `triage contracts` regenerates them from the authoritative Pydantic models.
The public contract prefix is `/v1`; incompatible changes require another version.

## Submit: POST /v1/disputes

Content-Type `application/json`, body `Dispute.schema.json`. Extra fields are rejected.
State length 2..60, description 15..4000, activity 2..200. Connection is LT/HT/EHT;
category and premises-use values are closed enums. Loads must be finite and in (0,10000]
kW. Areas must be finite and in (0,100000] square metres. Business area requires total
area and cannot exceed it. Mixed premises require an activity. Future billing dates are
invalid. Exceeding sanctioned load is a valid dispute, not an ingestion rejection.
The supported corpus scope is checked after structural ingestion and escalated if absent.

Optional headers: `Idempotency-Key` up to 128 characters; `X-Correlation-ID` UUID;
`X-API-Key` when configured. Success HTTP 202:

```json
{"run_id":"UUID","status_url":"/v1/runs/UUID"}
```

The `Location` header points to the status resource. Validation or text-policy failure
returns 422 with `detail` as field/type/message records, a `quarantine_id` UUID and
`agent_started:false`. Raw rejected input and errors are persisted in Redis quarantine,
never enqueued. Invalid JSON is also quarantined. HTTP 401 means missing/invalid client
key, 409 idempotency/body conflict, 429 per-client rate limit with Retry-After, 503 unavailable
index/queue, and 413 oversized declared body. Transport-level rejections do not start agents.

## Poll: GET /v1/runs/{run_id}

Owned by the authenticated client (demo uses caller IP hash). Returns 404 for missing or
other-client runs. States: queued -> running -> completed/escalated/failed. A cached verified
run may move straight to completed or escalated. Fields include run_id, request, submitted_at,
prompt_version, corpus_version/fingerprint, mode and correlation_id. Terminal runs add
completed_at, result, elapsed_seconds, cost, currency, pricing_label and cache_hit.
Unix timestamps use seconds. Cost is configured currency; zero-priced fixture calls are
labelled synthetic. An overdue worker run is reconciled to failed on polling.

Verified result: the recommendation schema plus `verified:true, advisory_only:true`.
Every claim has supporting chunk IDs and every citation has document, clause, physical PDF
page (1-based), source URL, chunk ID and an exact quote. A supported recommendation can
still escalate when its evidence supports referral rather than a settled category.

Fallback result: route `site-inspection-required`, `tariff_position:null`, empty claims and
citations, escalation_required true, a reason, verified false and advisory_only true. The
inspection route is the public routing enum; an officer may choose document review rather
than an actual site visit when the reason is a provider failure or out-of-scope connection.

## Audit: GET /v1/runs/{run_id}/events

Returns run_id and time-ordered `events`. Each event has Unix time, run_id, agent, kind,
trace_id and kind-specific fields. Model events include prompt messages, prompt version/hash,
completion, actual reported usage, recorded unit prices/currency/cost and latency. Tool events
include tool, arguments, retrieved result and latency. Verification events include supported,
reasons and retry_query. Cached runs include source_run_id/source_events for the same client.
Audit data may contain complaint text; keep access controlled and define retention before
using real personal data. The local course service intentionally does not expose quarantine
contents through an unauthenticated public endpoint.

## Feedback: POST /v1/runs/{run_id}/feedback

Body `Feedback.schema.json`: satisfactory boolean, reason length 3..1000, no extra fields.
Text policy applies. Terminal owned runs only; pending returns 409, unknown returns 404.
HTTP 201 `{"saved":true}`. One current feedback record per run; resubmission replaces it.
`GET /v1/dashboard` returns aggregated feedback counts/ratio, queue depth and recent quality
samples. It never returns another client's complaint or reason text.

## Configuration, health and metrics

`GET /v1/config` describes mode, non-secret corpus metadata, prompt version, SLO, pricing
label and authentication requirement. `GET /health/live` is process liveness;
`GET /health/ready` checks Redis, Chroma and an active corpus (200 or 503). Prometheus
text exposition is `/metrics`. Static web assets are GET-only. No provider credentials,
client keys or internal token are returned by these endpoints.

## Internal contracts

Verifier POST `/verify` uses `VerifyRequest.schema.json` and returns
`Verification.schema.json`; `X-Internal-Token` and propagated trace context are required.
There is no public verifier port. Worker-verifier error/timeout always degrades safely.
`POST /internal/evaluate` is protected by the same token and selects prompt v1/v2 via
`X-Prompt-Version`; it accepts the normal dispute contract and returns a submission envelope,
while bypassing cache/public throttling for controlled reference experiments. Protect that
token: this endpoint is intentionally not a public cost-control bypass.

The demo model implements the OpenAI chat-completion JSON request/response subset and
reports explicitly estimated fixture token usage. Its fault endpoint is disabled unless
configured, token-protected and unexposed on host ports. Real provider interfaces are used
through a configured URL/key/model; the adapter requires usage in successful responses.
