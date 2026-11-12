import asyncio
import json
import time

from opentelemetry import context
from opentelemetry.propagate import extract
from prometheus_client import start_http_server
from redis import Redis
from rq import Queue, Worker

from triage.agents import fallback, investigate
from triage.config import settings
from triage.corpus import index_info
from triage.observability import RUNS, RUN_TIME, setup_tracing, span
from triage.storage import cache_key, event, events, get_run, redis_client, save_run


def execute(run_id, trace_headers=None):
    cfg = settings()
    record = get_run(run_id)
    if not record or record.get("status") in {"completed", "escalated", "failed"}:
        return
    token = context.attach(extract(trace_headers or {}))
    try:
        save_run(run_id, status="running", started_at=time.time())
        event(run_id, "orchestrator", "run_started")
        deadline = record["submitted_at"] + cfg.max_run_seconds
        if deadline <= time.time():
            result = fallback("Queue wait exhausted the end-to-end deadline; resubmit or contact an officer.")
        else:
            info = index_info()
            if not info or info["fingerprint"] != record["corpus_fingerprint"]:
                result = fallback("Corpus changed after submission; resubmit for a consistent evidence snapshot.")
            else:
                with span("run", run_id):
                    result = asyncio.run(investigate(run_id, record["request"], deadline, record["prompt_version"]))
        # Deadline remains authoritative even if a blocking tool completes late.
        if time.time() > deadline:
            result = fallback("Run exceeded deadline; no tariff position returned.")
        status = "escalated" if result["escalation_required"] else "completed"
        if result["verified"] and cfg.cache_enabled and record.get("cache_allowed", True):
            key = cache_key(record["request"], record["corpus_fingerprint"], record["prompt_version"], record["owner"])
            redis_client().setex(key, cfg.cache_ttl_seconds, json.dumps({"result": result, "source_run_id": run_id}))
    except Exception as exc:
        result = fallback("Execution or verification unavailable; refer to grievance officer.")
        status = "failed"
        event(run_id, "orchestrator", "run_failure", error=type(exc).__name__, detail=str(exc)[:300])
    audit = events(run_id)
    cost = sum(e.get("cost", 0) for e in audit)
    elapsed = time.time() - record["submitted_at"]
    save_run(run_id, status=status, result=result, completed_at=time.time(),
             elapsed_seconds=elapsed, cost=cost, currency=cfg.cost_currency,
             pricing_label=cfg.pricing_label, cache_hit=False)
    RUNS.labels(status).inc()
    RUN_TIME.labels(status).observe(elapsed)
    event(run_id, "orchestrator", "run_finished", status=status, cost=cost, elapsed_seconds=elapsed)
    context.detach(token)
    if cfg.quality_sample_every > 0 and int(redis_client().incr("quality:counter")) % cfg.quality_sample_every == 0:
        from triage.evaluation import audit_metrics
        metrics = audit_metrics(audit, result)
        redis_client().rpush("quality:samples", json.dumps({"run_id": run_id, "time": time.time(),
                                                            "metrics": metrics, "proxy": True}))


def main():
    cfg = settings()
    setup_tracing()
    from prometheus_client import CollectorRegistry, multiprocess
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    start_http_server(cfg.metrics_port, registry=registry)
    # RQ Worker forks a work horse on Linux, so each run is bounded independently.
    connection = Redis.from_url(cfg.redis_url, socket_connect_timeout=4, socket_timeout=5)
    worker = Worker([Queue("triage", connection=connection)], connection=connection)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
