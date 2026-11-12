import hashlib
import hmac
import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from opentelemetry import context
from opentelemetry.propagate import extract, inject
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from redis import Redis
from rq import Queue

from triage.agents import fallback
from triage.config import settings
from triage.corpus import chroma, fingerprint, index_info, manifest
from triage.guards import check_text
from triage.models import Dispute, Feedback
from triage.observability import RUNS, RUN_TIME, setup_tracing, span
from triage.storage import allow_client, cache_key, event, events, get_run, redis_client, save_run

HTTP_TIME = Histogram("triage_http_seconds", "API request latency", ["method", "route", "status"])
HTTP_COUNT = Counter("triage_http_requests_total", "API requests", ["method", "route", "status"])
REJECTS = Counter("triage_rejected_total", "Quarantined requests", ["reason"])
CACHE = Counter("triage_cache_total", "Whole-run cache", ["outcome"])
INDEX_CHUNKS = Gauge("triage_corpus_chunks", "Indexed chunks")
INDEX_BUILT = Gauge("triage_corpus_built_timestamp_seconds", "Index freshness")
INDEX_RATE = Gauge("triage_corpus_chunks_per_second", "Last ingestion throughput")
QUEUE_DEPTH = Gauge("triage_queue_depth", "Waiting jobs")
FEEDBACK = Gauge("triage_feedback_satisfactory_ratio", "Persisted satisfactory feedback ratio")
QUALITY = Gauge("triage_quality_proxy", "Latest sampled automated quality proxy", ["metric"])


@asynccontextmanager
async def lifespan(app):
    setup_tracing()
    yield


app = FastAPI(title="Electricity Dispute Triage", version="0.1.0", lifespan=lifespan,
              description="Advisory tariff positions only. Demo evidence is synthetic. No bills are modified.")


@app.middleware("http")
async def instrument(request: Request, call_next):
    if int(request.headers.get("content-length", "0") or 0) > 16384:
        return JSONResponse({"detail": "Request body too large"}, status_code=413)
    correlation = request.headers.get("x-correlation-id", "")
    try:
        correlation = str(uuid.UUID(correlation))
    except ValueError:
        correlation = str(uuid.uuid4())
    request.state.correlation_id = correlation
    token = context.attach(extract(dict(request.headers)))
    start = time.monotonic()
    try:
        with span("api.request", correlation, method=request.method, path=request.url.path):
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
            route = request.scope.get("route")
            name = route.path if route else "unmatched"
            HTTP_TIME.labels(request.method, name, str(response.status_code)).observe(time.monotonic() - start)
            HTTP_COUNT.labels(request.method, name, str(response.status_code)).inc()
            return response
    finally:
        context.detach(token)


def client_identity(request: Request, x_api_key: str = Header(default="")):
    configured = [k.strip() for k in settings().api_client_keys.split(",") if k.strip()]
    if configured and not any(hmac.compare_digest(x_api_key, k) for k in configured):
        raise HTTPException(401, "Valid X-API-Key required")
    identity = x_api_key if configured else (request.client.host if request.client else "demo")
    return hashlib.sha256(identity.encode()).hexdigest()


def quarantine(request, errors, reason):
    identifier = str(uuid.uuid4())
    redis_client().hset("quarantine:" + identifier, mapping={
        "record": json.dumps({"time": time.time(), "correlation_id": request.state.correlation_id,
                               "reason": reason, "errors": errors}, default=str)})
    REJECTS.labels(reason).inc()
    return identifier


@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    errors = [{"field": ".".join(map(str, e["loc"])), "type": e["type"], "message": e["msg"]}
              for e in exc.errors()]
    identifier = quarantine(request, errors, "validation")
    # Preserve rejected body in quarantine only; never dispatch it to the queue.
    redis_client().hset("quarantine:" + identifier, "body", json.dumps(exc.body, default=str))
    return JSONResponse({"detail": errors, "quarantine_id": identifier, "agent_started": False}, 422)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse("web/index.html")


@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse("web/app.js", media_type="application/javascript")


@app.get("/style.css", include_in_schema=False)
def css():
    return FileResponse("web/style.css", media_type="text/css")


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        redis_client().ping()
        chroma().heartbeat()
        active = index_info()
        if not active or active["fingerprint"] != fingerprint(manifest()):
            raise RuntimeError("Corpus not indexed")
        if settings().app_mode == "production" and active["status"] != "approved":
            raise RuntimeError("Official corpus not approved")
    except Exception as exc:
        raise HTTPException(503, "Dependencies or corpus not ready") from exc
    return {"status": "ready", "mode": settings().app_mode}


@app.get("/v1/config")
def public_config():
    cfg = settings()
    info = index_info()
    return {"mode": cfg.app_mode, "corpus": info, "prompt_version": cfg.prompt_version,
            "max_run_seconds": cfg.max_run_seconds,
            "slo_p95_seconds": cfg.slo_p95_seconds, "advisory_only": True,
            "authentication_required": bool(cfg.api_client_keys), "pricing_label": cfg.pricing_label}


@app.post("/internal/evaluate", status_code=202, include_in_schema=False)
def evaluation_submit(body: Dispute, request: Request,
                      x_internal_token: str = Header(default=""),
                      x_prompt_version: str = Header(default="v2")):
    if not hmac.compare_digest(x_internal_token, settings().internal_token):
        raise HTTPException(401, "Internal authentication required")
    if x_prompt_version not in {"v1", "v2", "v3", "v4", "v5", "v6"}:
        raise HTTPException(422, "Unknown prompt version")
    if check_text(body.model_dump(mode="json")):
        raise HTTPException(422, "Evaluation input rejected by guardrail")
    info = index_info()
    if not info:
        raise HTTPException(503, "Corpus not ready")
    # Evaluations deliberately bypass whole-run caching and per-client public limits.
    cfg = settings().model_copy(update={"prompt_version": x_prompt_version, "cache_enabled": False})
    client = client_identity(request, request.headers.get("x-api-key", ""))
    run_id = _create_run(body.model_dump(mode="json"), client, info, cfg, request)
    return {"run_id": run_id, "status_url": "/v1/runs/" + run_id}


@app.post("/v1/disputes", status_code=202)
def submit(body: Dispute, request: Request, response: Response,
           client=Depends(client_identity), idempotency_key: str | None = Header(default=None)):
    if not allow_client(client):
        raise HTTPException(429, "Client rate limit exceeded", headers={"Retry-After": "60"})
    payload = body.model_dump(mode="json")
    problem = check_text(payload)
    if problem:
        errors = [{"field": "free-text", "message": problem}]
        identifier = quarantine(request, errors, problem)
        redis_client().hset("quarantine:" + identifier, "body", json.dumps(payload))
        return JSONResponse({"detail": errors, "quarantine_id": identifier, "agent_started": False}, 422)
    info = index_info()
    if not info:
        raise HTTPException(503, "Corpus not ready")
    cfg = settings()
    r = redis_client()
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    idem = None
    if idempotency_key:
        if len(idempotency_key) > 128:
            raise HTTPException(422, "Idempotency-Key exceeds 128 characters")
        idem = "idempotency:" + client + ":" + hashlib.sha256(idempotency_key.encode()).hexdigest()
        with r.lock(idem + ":lock", timeout=10, blocking_timeout=2):
            old = r.get(idem)
            if old:
                old = json.loads(old)
                if old["digest"] != digest:
                    raise HTTPException(409, "Idempotency key reused with a different request")
                return {"run_id": old["run_id"], "status_url": "/v1/runs/" + old["run_id"]}
            run_id = _create_run(payload, client, info, cfg, request)
            r.setex(idem, 86400, json.dumps({"run_id": run_id, "digest": digest}))
    else:
        run_id = _create_run(payload, client, info, cfg, request)
    response.headers["Location"] = "/v1/runs/" + run_id
    return {"run_id": run_id, "status_url": "/v1/runs/" + run_id}


def _create_run(payload, client, info, cfg, request):
    run_id = str(uuid.uuid4())
    now = time.time()
    save_run(run_id, run_id=run_id, owner=client, status="queued", request=payload, submitted_at=now,
             prompt_version=cfg.prompt_version, corpus_fingerprint=info["fingerprint"],
             corpus_version=info["version"], mode=cfg.app_mode, correlation_id=request.state.correlation_id)
    save_run(run_id, cache_allowed=cfg.cache_enabled)
    cached = redis_client().get(cache_key(payload, info["fingerprint"], cfg.prompt_version, client)) if cfg.cache_enabled else None
    if cached:
        value = json.loads(cached)
        result = value["result"]
        # Only previously verified complete recommendations enter this cache.
        if result.get("verified"):
            elapsed = time.time() - now
            save_run(run_id, status="escalated" if result["escalation_required"] else "completed",
                     result=result, cache_hit=True, source_run_id=value["source_run_id"], cost=0,
                     currency=cfg.cost_currency, pricing_label=cfg.pricing_label,
                     completed_at=time.time(), elapsed_seconds=elapsed)
            event(run_id, "api", "cache_hit", source_run_id=value["source_run_id"])
            CACHE.labels("hit").inc()
            RUN_TIME.labels("cached").observe(elapsed)
            RUNS.labels("cached").inc()
            return run_id
    CACHE.labels("miss").inc()
    trace_headers = {}
    inject(trace_headers)
    try:
        Queue("triage", connection=Redis.from_url(cfg.redis_url)).enqueue(
            "triage.worker.execute", run_id, trace_headers, job_id=run_id,
            job_timeout=cfg.max_run_seconds + 15, result_ttl=86400, failure_ttl=86400)
    except Exception:
        save_run(run_id, status="failed", result=fallback("Queue unavailable; no agent run started."),
                 completed_at=time.time())
        raise HTTPException(503, "Queue unavailable")
    event(run_id, "api", "submitted", prompt_version=cfg.prompt_version)
    return run_id


def owned(run_id, client):
    try:
        uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(404, "Run not found")
    record = get_run(run_id)
    if not record or record.get("owner") != client:
        raise HTTPException(404, "Run not found")
    if record["status"] in {"queued", "running"} and time.time() - record["submitted_at"] > settings().max_run_seconds + 15:
        # Covers a killed worker or RQ hard timeout; incomplete runs never look successful.
        save_run(run_id, status="failed", completed_at=time.time(),
                 result=fallback("Worker lost or run deadline exceeded; human review required."))
        event(run_id, "api", "orphaned_run_detected")
        record = get_run(run_id)
    return record


@app.get("/v1/runs/{run_id}")
def status(run_id: str, client=Depends(client_identity)):
    record = owned(run_id, client)
    return {k: v for k, v in record.items() if k != "owner"}


@app.get("/v1/runs/{run_id}/events")
def audit(run_id: str, client=Depends(client_identity)):
    record = owned(run_id, client)
    result = {"run_id": run_id, "events": events(run_id)}
    if record.get("source_run_id"):
        source = owned(record["source_run_id"], client)
        result["source_run_id"] = source["run_id"]
        result["source_events"] = events(source["run_id"])
    return result


@app.post("/v1/runs/{run_id}/feedback", status_code=201)
def feedback(run_id: str, body: Feedback, client=Depends(client_identity)):
    record = owned(run_id, client)
    if record["status"] in {"queued", "running"}:
        raise HTTPException(409, "Run is not complete")
    if check_text(body.model_dump()):
        raise HTTPException(422, "Feedback rejected by text policy")
    redis_client().hset("feedback", run_id, json.dumps({**body.model_dump(), "time": time.time()}))
    return {"saved": True}


@app.get("/v1/dashboard")
def dashboard(client=Depends(client_identity)):
    # Aggregate metrics contain no request text or client identifiers.
    feedbacks = [json.loads(v) for v in redis_client().hvals("feedback")]
    return {"queue_depth": redis_client().llen("rq:queue:triage"), "feedback_count": len(feedbacks),
            "satisfactory_ratio": sum(x["satisfactory"] for x in feedbacks) / max(1, len(feedbacks)),
            "quality_samples": [json.loads(x) for x in redis_client().lrange("quality:samples", -30, -1)]}


@app.get("/metrics", include_in_schema=False)
def metrics():
    info = index_info()
    if info:
        INDEX_CHUNKS.set(info["chunks"])
        INDEX_BUILT.set(info["built_at"])
        INDEX_RATE.set(info["chunks_per_second"])
    QUEUE_DEPTH.set(redis_client().llen("rq:queue:triage"))
    feedbacks = [json.loads(v) for v in redis_client().hvals("feedback")]
    FEEDBACK.set(sum(x["satisfactory"] for x in feedbacks) / max(1, len(feedbacks)))
    latest = redis_client().lindex("quality:samples", -1)
    if latest:
        for name, value in json.loads(latest)["metrics"].items():
            QUALITY.labels(name).set(value)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
