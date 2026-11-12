import json
import os
import random
import time
import uuid
from pathlib import Path

from locust import HttpUser, between, events, task

RESULTS = []


class Officer(HttpUser):
    wait_time = between(.1, .3)

    @task
    def dispute(self):
        request = {"state": "Karnataka", "connection_type": "LT", "billed_category": "domestic",
                   "premises_use": "residential", "description": "My home is used exclusively as a residential dwelling. Please check the domestic category.",
                   "connected_load_kw": 3, "sanctioned_load_kw": 5, "billing_date": "2026-10-01"}
        if os.getenv("LOAD_REPEATED", "false").lower() != "true":
            request["total_area_sqm"] = random.uniform(30, 500)
        started = time.monotonic()
        headers = {"X-API-Key": os.getenv("LOAD_API_KEY", ""), "Idempotency-Key": str(uuid.uuid4())}
        terminal, error, run_id = None, None, None
        try:
            response = self.client.post("/v1/disputes", json=request, headers=headers, name="submit")
            if response.status_code != 202:
                raise RuntimeError("Submission HTTP " + str(response.status_code))
            run_id = response.json()["run_id"]
            while time.monotonic() - started < 110:
                response = self.client.get("/v1/runs/" + run_id, headers=headers, name="poll")
                if response.status_code != 200:
                    raise RuntimeError("Polling HTTP " + str(response.status_code))
                record = response.json()
                if record["status"] not in {"queued", "running"}:
                    terminal = record
                    if not record.get("result", {}).get("verified"):
                        error = RuntimeError("Terminal result was not verified")
                    break
                time.sleep(.25)
            else:
                raise TimeoutError("Run polling deadline")
        except Exception as exc:
            error = exc
        elapsed = time.monotonic() - started
        events.request.fire(request_type="RUN", name="terminal", response_time=elapsed * 1000,
                            response_length=0, exception=error, context={})
        RESULTS.append({"run_id": run_id, "elapsed_seconds": elapsed, "verified": error is None,
                        "error": str(error) if error else None, "cache_hit": bool(terminal and terminal.get("cache_hit")),
                        "cost": terminal.get("cost", 0) if terminal else 0})


@events.quitting.add_listener
def save_results(environment, **kwargs):
    path = Path(os.environ["LOAD_RESULTS"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
