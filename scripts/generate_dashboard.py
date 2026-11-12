import json
from pathlib import Path

queries = [
    ("End-to-end p50 / p95 (seconds)", [
        'histogram_quantile(0.50, sum(rate(triage_run_seconds_bucket[5m])) by (le))',
        'histogram_quantile(0.95, sum(rate(triage_run_seconds_bucket[5m])) by (le))']),
    ("Terminal throughput (runs/s)", ['sum(rate(triage_runs_total[5m])) by (status)']),
    ("HTTP error fraction", ['sum(rate(triage_http_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(triage_http_requests_total[5m])), 0.001)']),
    ("Service availability", ['up']),
    ("Agent outcomes", ['sum(rate(triage_agent_tasks_total[5m])) by (agent,outcome)']),
    ("Agent steps per run", ['sum(rate(triage_agent_steps_sum[5m])) by (agent) / clamp_min(sum(rate(triage_agent_steps_count[5m])) by (agent), 0.001)']),
    ("Agent tool calls per run", ['sum(rate(triage_agent_tool_calls_sum[5m])) by (agent) / clamp_min(sum(rate(triage_agent_tool_calls_count[5m])) by (agent), 0.001)']),
    ("Agent task success fraction", ['sum(rate(triage_agent_tasks_total{outcome=~"verified|supported"}[5m])) by (agent) / clamp_min(sum(rate(triage_agent_tasks_total[5m])) by (agent), 0.001)']),
    ("Tool calls / model calls", ['sum(rate(triage_calls_total[5m])) by (agent,kind,outcome)']),
    ("Step p95 latency", ['histogram_quantile(0.95, sum(rate(triage_step_seconds_bucket[5m])) by (le,agent,kind))']),
    ("Retry rate", ['sum(rate(triage_retries_total[5m])) by (agent)']),
    ("Worker process uptime (seconds)", ['time() - triage_started_timestamp_seconds']),
    ("Queue depth", ['triage_queue_depth']),
    ("Configured currency cost / second", ['sum(rate(triage_cost_total[5m])) by (agent)']),
    ("Container CPU cores", ['sum(rate(container_cpu_usage_seconds_total{image!=""}[5m])) by (name)']),
    ("Container memory (bytes)", ['sum(container_memory_working_set_bytes{image!=""}) by (name)']),
    ("Corpus freshness (seconds)", ['time() - triage_corpus_built_timestamp_seconds']),
    ("Corpus chunks / ingest chunks per second", ['triage_corpus_chunks', 'triage_corpus_chunks_per_second']),
    ("Sampled quality proxies", ['triage_quality_proxy']),
    ("Satisfactory feedback fraction", ['triage_feedback_satisfactory_ratio']),
    ("Cache hit/miss rate", ['sum(rate(triage_cache_total[5m])) by (outcome)']),
    ("Quarantined ingestion", ['sum(rate(triage_rejected_total[5m])) by (reason)'])
]
panels = []
for i, (title, expressions) in enumerate(queries):
    panels.append({"id": i + 1, "title": title, "type": "timeseries",
                   "datasource": {"type": "prometheus", "uid": "prometheus"},
                   "gridPos": {"x": (i % 2) * 12, "y": (i // 2) * 8, "w": 12, "h": 8},
                   "targets": [{"expr": expr, "refId": chr(65 + j), "legendFormat": "{{agent}} {{kind}} {{status}} {{outcome}} {{name}} {{job}} {{metric}}"}
                               for j, expr in enumerate(expressions)],
                   "fieldConfig": {"defaults": {}, "overrides": []}, "options": {"tooltip": {"mode": "multi"}}})
dashboard = {"uid": "electricity-triage", "title": "Electricity Triage / AgentOps", "schemaVersion": 40,
             "version": 1, "refresh": "5s", "time": {"from": "now-30m", "to": "now"}, "panels": panels}
directory = Path("monitoring/grafana/dashboards")
directory.mkdir(parents=True, exist_ok=True)
(directory / "triage.json").write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
