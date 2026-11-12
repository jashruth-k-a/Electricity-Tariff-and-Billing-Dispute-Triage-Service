# Runbook

## Provider unavailable or slow

**Symptom:** new runs refer to an officer without a tariff position; model-failure or
circuit-opened events appear; retry count and end-to-end latency rise.

**Confirm:** inspect the run's `/v1/runs/{id}/events`, inspect `docker compose logs
agent-worker verifier`, and find the run in Jaeger. Distinguish HTTP 429, timeout and 5xx.
Check configured provider identity, quota and runtime secrets without printing credentials.

Gemini can return retry timing in `error.details[].retryDelay`, including a list-wrapped
error, rather than an HTTP Retry-After header. The adapter honours both. A retry beyond
the run deadline fails safely instead of sleeping for hours. Distinguish daily quota
exhaustion from a temporary per-minute limit: a new key in the same provider project does
not necessarily increase the project quota. Configure `PROVIDER_MIN_INTERVAL_SECONDS`
for a shared minimum spacing between model calls across all workers. Demo defaults to zero.

**Recover:** restore provider access or change the configured provider/model; restart only
API/worker/verifier services if configuration changes. Wait the breaker cooldown, then
submit one probe. Do not clear run state or mark failed runs completed. Resubmit affected
cases only after inspecting their audit records. In demo mode reset an injected fault with
`docker compose run --rm tools fault normal`; injected faults expire after five minutes.

## Corpus/index or queue/worker unavailable

**Symptom:** readiness returns 503, submissions fail, queue depth grows, or polling reports
an overdue/failed run. No confident tariff answer should appear.

**Confirm:** `docker compose ps`, `docker compose logs corpus-init chroma redis agent-worker`,
`docker compose exec redis redis-cli LLEN rq:queue:triage`. Check index freshness in Grafana.
If corpus manifest/fingerprint changed, require reindexing instead of mixing evidence versions.

**Recover:** restore Redis/Chroma/worker health, rerun `docker compose run --rm corpus-init`,
then `docker compose up -d`. RQ waiting jobs remain in Redis AOF. An abruptly killed run is
not silently replayed: once its end-to-end deadline passes, status polling returns a safe
failed/referral envelope. Inspect the original run and explicitly resubmit. Do not use
`docker compose down -v` unless intentionally deleting all state.

## Startup port conflict

If Docker says a host port is already allocated, change only the affected port in `.env`
and run `docker compose up -d`. The checked local configuration uses API port 8011. Do not
stop unrelated applications to free their ports. Grafana/Prometheus/Jaeger ports are also
runtime-configurable.
