"""Exercise rejection/retrieval retry and the provider outage circuit breaker."""
import json
import os
import time
from pathlib import Path

import httpx

from triage.config import settings

cfg = settings()
if cfg.app_mode != "demo":
    raise RuntimeError("Fault demonstrations are available only in demo mode")
client = httpx.Client(timeout=15)
api = os.environ["API_INTERNAL_URL"]
stub = cfg.llm_base_url.removesuffix("/v1")
headers = {"X-Internal-Token": cfg.internal_token, "X-Prompt-Version": "v2",
           "X-API-Key": cfg.api_client_keys.split(",")[0]}
request = json.loads(Path("evaluation/cases.json").read_text())[0]["request"]


def fault(mode):
    response = client.post(stub + "/admin/fault", headers=headers, json={"mode": mode})
    response.raise_for_status()


def run():
    response = client.post(api + "/internal/evaluate", headers=headers, json=request)
    response.raise_for_status()
    run_id = response.json()["run_id"]
    started = time.monotonic()
    while time.monotonic() - started < 115:
        record = client.get(api + "/v1/runs/" + run_id, headers=headers).json()
        if record["status"] not in {"queued", "running"}:
            audit = client.get(api + "/v1/runs/" + run_id + "/events", headers=headers).json()["events"]
            return {"record": record, "events": audit}
        time.sleep(.25)
    raise TimeoutError("Fault run did not terminate")


results = {}
try:
    fault("unsupported")
    unsupported = run()
    assert unsupported["record"]["result"]["verified"] is False
    assert any(e["kind"] == "verification" and not e["supported"] for e in unsupported["events"])
    assert sum(e["kind"] == "tool_call" and e.get("tool") == "corpus_search" for e in unsupported["events"]) >= 2
    results["unsupported_answer_caught_and_researched"] = unsupported
    fault("unavailable")
    outage = run()
    assert outage["record"]["result"]["tariff_position"] is None
    assert any(e["kind"] == "circuit_opened" for e in outage["events"])
    results["provider_outage_opens_circuit"] = outage
    fast = run()
    assert fast["record"]["result"]["tariff_position"] is None
    assert fast["record"]["elapsed_seconds"] < 5
    results["open_circuit_degrades_without_provider_call"] = fast
finally:
    fault("normal")
    time.sleep(cfg.breaker_reset_seconds + 1)
recovered = run()
assert recovered["record"]["result"]["verified"] is True
results["half_open_probe_recovers"] = recovered
Path("output/resilience.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps({name: {"run_id": item["record"]["run_id"], "status": item["record"]["status"],
                         "elapsed_seconds": item["record"]["elapsed_seconds"]}
                  for name, item in results.items()}, indent=2))
