import hashlib
import json
import time
from functools import lru_cache

from redis import Redis

from triage.config import settings
from triage.observability import log


@lru_cache
def redis_client():
    return Redis.from_url(settings().redis_url, decode_responses=True, socket_timeout=4,
                          socket_connect_timeout=4, health_check_interval=20)


def save_run(identifier, **values):
    redis_client().hset(f"run:{identifier}", mapping={k: json.dumps(v, default=str) for k, v in values.items()})


def get_run(run_id):
    raw = redis_client().hgetall(f"run:{run_id}")
    return {k: json.loads(v) for k, v in raw.items()} if raw else None


def event(run_id, agent, kind, **details):
    from opentelemetry import trace
    context = trace.get_current_span().get_span_context()
    record = {"time": time.time(), "run_id": run_id, "agent": agent, "kind": kind,
              "trace_id": format(context.trace_id, "032x"), **details}
    redis_client().rpush(f"events:{run_id}", json.dumps(record, default=str))
    log(kind, run_id=run_id, agent=agent, **details)


def events(run_id):
    return [json.loads(v) for v in redis_client().lrange(f"events:{run_id}", 0, -1)]


def cache_key(request, corpus_version, prompt_version, owner=""):
    cfg = settings()
    value = json.dumps([request, corpus_version, prompt_version, owner, cfg.app_mode,
                        cfg.llm_backend, cfg.llm_model, cfg.llm_revision,
                        cfg.embedding_backend, cfg.embedding_model], sort_keys=True)
    return "result-cache:" + hashlib.sha256(value.encode()).hexdigest()


RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


def allow_client(client):
    digest = hashlib.sha256(client.encode()).hexdigest()
    count = redis_client().eval(RATE_SCRIPT, 1, f"rate:{digest}:{int(time.time() // 60)}", 61)
    return int(count) <= settings().rate_limit_per_minute
