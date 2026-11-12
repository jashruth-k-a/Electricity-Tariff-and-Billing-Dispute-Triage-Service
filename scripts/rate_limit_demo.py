"""Verify the normal public rate limit using a repeated, cacheable supported request."""
import json
import os
import time
from pathlib import Path

import httpx

from triage.config import settings

cfg = settings()
if cfg.app_mode != "demo" or cfg.rate_limit_per_minute > 100:
    raise RuntimeError("Run only in normal demo configuration, without the load-test overlay")
client = httpx.Client(base_url=os.environ["API_INTERNAL_URL"], timeout=10,
                      headers={"X-API-Key": cfg.api_client_keys.split(",")[0]})
request = {"state": "Karnataka", "connection_type": "LT", "billed_category": "domestic",
           "premises_use": "residential", "description": "My home is used exclusively as a residential dwelling. Please check the domestic category.",
           "connected_load_kw": 3, "sanctioned_load_kw": 5, "billing_date": "2026-10-01"}
response = client.post("/v1/disputes", json=request)
accepted = 0
if response.status_code == 202:
    accepted += 1
    run_id = response.json()["run_id"]
    for _ in range(400):
        record = client.get("/v1/runs/" + run_id).json()
        if record["status"] not in {"queued", "running"}:
            assert record["result"]["verified"], record
            break
        time.sleep(.25)
    else:
        raise TimeoutError("Cache priming run did not complete")
elif response.status_code != 429:
    response.raise_for_status()
for _ in range(cfg.rate_limit_per_minute + 1):
    response = client.post("/v1/disputes", json=request)
    if response.status_code == 429:
        break
    assert response.status_code == 202, response.text
    accepted += 1
else:
    raise AssertionError("Rate limit did not reject the repeated client")
assert response.headers.get("Retry-After") == "60"
result = {"configured_per_minute": cfg.rate_limit_per_minute, "accepted_in_this_probe": accepted,
          "rejected_status": response.status_code, "retry_after": response.headers["Retry-After"],
          "note": "Earlier requests in the same minute can reduce the accepted count."}
Path("output/rate-limit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
