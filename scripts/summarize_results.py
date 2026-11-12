"""Publish compact measured evidence while keeping full complaint audits in ignored output/."""
import json
from pathlib import Path

directory = Path("evaluation/results")
directory.mkdir(parents=True, exist_ok=True)
for filename, published in [("evaluation.json", "prompt-comparison.json"),
                            ("official-evaluation.json", "official-comparison.json"),
                            ("official-probe.json", "official-probe-initial.json"),
                            ("official-probe-structured.json", "official-probe-constrained.json"),
                            ("official-probe-qwen.json", "official-probe-smaller-model.json"),
                            ("official-probe-v4.json", "official-probe-v4.json"),
                            ("official-probe-llama-v4.json", "official-probe-larger-model.json"),
                            ("official-probe-gemini.json", "official-probe-gemini.json"),
                            ("official-probe-gemini35.json", "official-probe-gemini35.json"),
                            ("official-probe-final.json", "official-reference-passed-gemini35.json"),
                            ("official-probe-lite.json", "official-reference-flash-lite.json"),
                            ("official-probe-groq.json", "official-reference-groq.json")]:
    evaluation_path = Path("output") / filename
    if not evaluation_path.exists():
        continue
    evaluation = json.loads(evaluation_path.read_text())
    for variant in evaluation["variants"].values():
        for case in variant["cases"]:
            responses = [e for e in case.get("audit", []) if e["kind"] == "model_response"]
            case["model_identities"] = [dict(zip(["backend", "model", "revision"], identity))
                for identity in sorted({(e.get("backend", "legacy"), e.get("model", "unknown"),
                                         e.get("model_revision", "")) for e in responses})]
            case["reported_tokens"] = {name: sum(e.get(name, 0) for e in responses)
                                       for name in ["prompt_tokens", "completion_tokens"]}
            case["prompt_hashes"] = sorted({e["prompt_sha256"] for e in responses if e.get("prompt_sha256")})
        variant["cases"] = [{k: v for k, v in case.items() if k not in {"audit", "result"}}
                            for case in variant["cases"]]
    (directory / published).write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
official_path = Path("output/official-evaluation.json")
if official_path.exists():
    official = json.loads(official_path.read_text(encoding="utf-8"))
    final = official.get("variants", {}).get("v6", {})
    if final.get("complete"):
        reference = next(c for c in final["cases"] if c["id"] == "tailoring-reference")
        example = {"case_id": reference["id"], "run_id": reference["run_id"],
                   "passed": reference["passed"], "elapsed_seconds": reference["elapsed_seconds"],
                   "result": reference["result"], "model_calls": reference["model_calls"],
                   "corpus_version": official["configuration"]["corpus"]["version"]}
        (directory / "official-reference-answer.json").write_text(json.dumps(example, indent=2), encoding="utf-8")
for source in Path("output/load").glob("*-summary.json"):
    (directory / source.name).write_text(source.read_text(), encoding="utf-8")
for name in ["smoke", "resilience", "rate-limit", "official-smoke"]:
    source = Path(f"output/{name}.json")
    if source.exists():
        data = json.loads(source.read_text())
        if name == "resilience":
            data = {key: {"run_id": value["record"]["run_id"], "status": value["record"]["status"],
                          "elapsed_seconds": value["record"]["elapsed_seconds"],
                          "verified": value["record"]["result"]["verified"],
                          "event_kinds": [e["kind"] for e in value["events"]]}
                    for key, value in data.items()}
        (directory / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
