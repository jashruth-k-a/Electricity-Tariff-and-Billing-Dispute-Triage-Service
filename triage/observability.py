import json
import logging
import os
import time
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram

from triage.config import settings

CALLS = Counter("triage_calls_total", "Agent and tool calls", ["agent", "kind", "outcome"])
LATENCY = Histogram("triage_step_seconds", "Step latency", ["agent", "kind"],
                    buckets=(.1, .5, 1, 2, 5, 10, 20, 40, 60, 90))
RUN_TIME = Histogram("triage_run_seconds", "Submission to terminal result", ["status"],
                     buckets=(1, 2, 5, 10, 20, 30, 45, 60, 90, 120))
RUNS = Counter("triage_runs_total", "Terminal runs", ["status"])
RETRIES = Counter("triage_retries_total", "Retried calls", ["agent"])
COST = Counter("triage_cost_total", "Configured currency model cost", ["agent"])
TOKENS = Counter("triage_tokens_total", "Provider reported tokens", ["agent", "kind"])
STEPS = Histogram("triage_agent_steps", "Steps per agent per run", ["agent"], buckets=(1, 2, 3, 4, 6, 8, 12, 20))
TOOLS_PER_RUN = Histogram("triage_agent_tool_calls", "Tool calls per agent per run", ["agent"], buckets=(0, 1, 2, 3, 4, 6, 8, 12))
SUCCESS = Counter("triage_agent_tasks_total", "Agent handoff outcomes", ["agent", "outcome"])
UPTIME = Gauge("triage_started_timestamp_seconds", "Process start timestamp")
UPTIME.set(time.time())
logging.basicConfig(level=logging.INFO, format="%(message)s")


def setup_tracing():
    cfg = settings()
    provider = TracerProvider(resource=Resource.create({"service.name": cfg.service_name,
                                                       "service.instance.id": os.getenv("HOSTNAME", "local")}))
    if cfg.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
            endpoint=cfg.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces", timeout=3)))
    trace.set_tracer_provider(provider)


@contextmanager
def span(name, run_id="", **attributes):
    with trace.get_tracer("electricity-triage").start_as_current_span(name) as current:
        current.set_attribute("run.id", run_id)
        for key, value in attributes.items():
            current.set_attribute(key, str(value))
        yield current


def log(event, **fields):
    logging.info(json.dumps({"event": event, "time": time.time(), **fields}, default=str))
