import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from triage.evaluation import percentile

parser = argparse.ArgumentParser()
parser.add_argument("--users", type=int, default=3)
parser.add_argument("--seconds", type=int, default=45)
parser.add_argument("--workers", type=int, default=1)
parser.add_argument("--label", default="baseline")
parser.add_argument("--repeated", action="store_true")
args = parser.parse_args()
if not 1 <= args.users <= 100 or not 10 <= args.seconds <= 600:
    parser.error("users must be 1..100; seconds must be 10..600")
directory = Path("output/load")
directory.mkdir(parents=True, exist_ok=True)
if not args.label.replace("-", "").replace("_", "").isalnum():
    parser.error("label may contain letters, numbers, hyphens and underscores")
prefix = directory / args.label
environment = {**os.environ, "LOAD_RESULTS": str(prefix) + "-runs.json",
               "LOAD_REPEATED": str(args.repeated).lower()}
started = time.monotonic()
process = subprocess.run([sys.executable, "-m", "locust", "-f", "loadtests/locustfile.py",
    "--headless", "--only-summary", "--host", os.environ["API_INTERNAL_URL"], "--users", str(args.users),
    "--spawn-rate", str(args.users), "--run-time", str(args.seconds) + "s",
    "--stop-timeout", "110", "--csv", str(prefix), "--html", str(prefix) + ".html"], env=environment)
elapsed = time.monotonic() - started
results_path = Path(str(prefix) + "-runs.json")
results = json.loads(results_path.read_text()) if results_path.exists() else []
latencies = [r["elapsed_seconds"] for r in results]
verified = [r for r in results if r["verified"]]
summary = {"label": args.label, "generated_at": time.time(), "machine": platform.platform(),
    "users": args.users, "worker_count": args.workers, "wall_seconds": elapsed,
    "stub_delay_seconds": float(os.environ["STUB_DELAY_SECONDS"]), "repeated_workload": args.repeated,
    "cache_enabled": os.getenv("CACHE_ENABLED", "false"),
    "completed_runs": len(results), "verified_runs": len(verified),
    "verified_fraction": len(verified) / max(1, len(results)),
    "terminal_rps": len(results) / elapsed, "verified_rps": len(verified) / elapsed,
    "p50_seconds": percentile(latencies, .5), "p95_seconds": percentile(latencies, .95),
    "slo_p95_seconds": int(os.environ["SLO_P95_SECONDS"]),
    "cost_per_run": sum(r["cost"] for r in results) / max(1, len(results)),
    "cache_hits": sum(r["cache_hit"] for r in results), "locust_exit_code": process.returncode}
summary["slo_met"] = bool(results) and summary["p95_seconds"] <= summary["slo_p95_seconds"] and summary["verified_fraction"] >= .95
Path(str(prefix) + "-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
