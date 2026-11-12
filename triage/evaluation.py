"""Transparent, reproducible equivalent evaluator; metric limitations are documented."""
import asyncio
import json
import platform
import statistics
import time
from pathlib import Path

import httpx


def audit_metrics(audit, result, expected_clauses=None):
    handoffs = [e for e in audit if e["kind"] == "handoff_result"]
    candidates = [e["candidate"] for e in handoffs]
    claims = [(claim, candidate) for candidate in candidates for claim in candidate.get("claims", [])]
    passages = {p["chunk_id"]: p for e in audit if e["kind"] == "tool_call"
                and isinstance(e.get("result"), list) for p in e["result"] if "chunk_id" in p}
    resolvable = 0
    for claim, candidate in claims:
        citations = {c["chunk_id"]: c for c in candidate.get("citations", [])}
        if all(cid in passages and cid in citations and
               " ".join(citations[cid]["quote"].split()) in " ".join(passages[cid]["text"].split())
               for cid in claim.get("chunk_ids", [])) and claim.get("chunk_ids"):
            resolvable += 1
    supported_claims = sum(len(e["candidate"].get("claims", [])) for e in handoffs
                           if e["verification"]["supported"])
    denominator = max(1, len(claims))
    if expected_clauses is not None:
        relevant = sum(p["clause"] in expected_clauses for p in passages.values())
    else:
        cited_ids = {c["chunk_id"] for c in result.get("citations", [])}
        relevant = sum(cid in cited_ids for cid in passages)
    return {"groundedness": resolvable / denominator,
            "context_relevance": relevant / max(1, len(passages)),
            "faithfulness": supported_claims / denominator,
            "hallucination_rate": (len(claims) - supported_claims) / denominator}


def percentile(values, p):
    if not values:
        return 0
    values = sorted(values)
    return values[max(0, min(len(values) - 1, int((len(values) - 1) * p + .5)))]


async def evaluate(api_url, token, cases_path, versions, concurrency, api_key="", checkpoint=None):
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    gate = asyncio.Semaphore(concurrency)
    report = {"generated_at": time.time(), "machine": platform.platform(), "synthetic": True,
              "cases_file": cases_path, "metrics_definition": "docs/evaluation.md", "variants": {}}
    async with httpx.AsyncClient(base_url=api_url, timeout=15, headers={"X-API-Key": api_key}) as client:
        config = (await client.get("/v1/config")).json()
        report["synthetic"] = config["mode"] == "demo"
        report["configuration"] = config
        for version in versions:
            completed = []
            report["variants"][version] = {"complete": False, "cases": completed}
            async def one(case):
                async with gate:
                    started = time.monotonic()
                    response = await client.post("/internal/evaluate", json=case["request"],
                                  headers={"X-Internal-Token": token, "X-Prompt-Version": version})
                    response.raise_for_status()
                    run_id = response.json()["run_id"]
                    deadline = config.get("max_run_seconds", 90) + 45
                    while time.monotonic() - started < deadline:
                        status = await client.get("/v1/runs/" + run_id)
                        status.raise_for_status()
                        record = status.json()
                        if record["status"] not in {"queued", "running"}:
                            break
                        await asyncio.sleep(.25)
                    else:
                        raise TimeoutError("Evaluation poll deadline")
                    audit_response = await client.get("/v1/runs/" + run_id + "/events")
                    audit_response.raise_for_status()
                    audit = audit_response.json()["events"]
                    result = record["result"]
                    expected = case["expected"]
                    actual_clauses = {c["clause"] for c in result.get("citations", [])}
                    passed = (result["route"] == expected["route"] and
                              result["escalation_required"] == expected["escalation_required"] and
                              result["verified"] == expected["verified"] and
                              ("issue_type" not in expected or result.get("issue_type") == expected["issue_type"]) and
                              set(expected["clauses"]) <= actual_clauses)
                    outcome = {"id": case["id"], "run_id": run_id, "passed": passed, "expected": expected,
                            "result": result, "metrics": audit_metrics(audit, result, expected["clauses"]),
                            "cost": record.get("cost", 0), "elapsed_seconds": record.get("elapsed_seconds", 0),
                            "model_calls": sum(e["kind"] == "model_response" for e in audit),
                            "audit": audit}
                    completed.append(outcome)
                    if checkpoint:
                        print(json.dumps({"version": version, "case": case["id"], "passed": passed,
                                          "seconds": round(outcome["elapsed_seconds"], 2)}), flush=True)
                        destination = Path(checkpoint)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        temporary = destination.with_suffix(destination.suffix + ".tmp")
                        temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
                        temporary.replace(destination)
                    return outcome
            results = await asyncio.gather(*(one(case) for case in cases))
            metrics = {name: statistics.mean(r["metrics"][name] for r in results)
                       for name in ["groundedness", "context_relevance", "faithfulness", "hallucination_rate"]}
            costs = [r["cost"] for r in results]
            by_agent = {}
            for result in results:
                for entry in result["audit"]:
                    if entry["kind"] == "model_response" and "cost" in entry:
                        by_agent[entry["agent"]] = by_agent.get(entry["agent"], 0) + entry["cost"]
            report["variants"][version] = {"complete": True, "cases": results, "metrics": metrics,
                "pass_rate": sum(r["passed"] for r in results) / len(results),
                "p50_seconds": percentile([r["elapsed_seconds"] for r in results], .5),
                "p95_seconds": percentile([r["elapsed_seconds"] for r in results], .95),
                "cost_per_100_runs": statistics.mean(costs) * 100,
                "cost_by_agent": by_agent, "total_model_calls": sum(r["model_calls"] for r in results)}
    if len(versions) == 2:
        before, after = (report["variants"][v] for v in versions)
        report["change"] = (f"{versions[0]} -> {versions[1]}: compare the versioned investigator and verifier "
                            "prompt artifacts; backend, corpus, structured contract and cache bypass are shared")
        report["delta"] = {k: after["metrics"][k] - before["metrics"][k] for k in before["metrics"]}
        report["pass_rate_delta"] = after["pass_rate"] - before["pass_rate"]
    return report
