"""Write a human-readable summary only from a completed real-provider comparison."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

source = Path("output/official-evaluation.json")
report = json.loads(source.read_text(encoding="utf-8"))
if report.get("synthetic"):
    raise SystemExit("Refusing to publish a synthetic run as official-model evidence")
before, after = (report["variants"][version] for version in ["v1", "v6"])
if not all(variant.get("complete") for variant in [before, after]):
    raise SystemExit("Comparison is incomplete; preserve checkpoints and finish the run first")
if [c["id"] for c in before["cases"]] != [c["id"] for c in after["cases"]]:
    raise SystemExit("Prompt variants must use the same ordered reference set")
count = len(after["cases"])
measured = datetime.fromtimestamp(report["generated_at"], ZoneInfo("Asia/Kolkata")).date().isoformat()
models = sorted({e.get("provider_model") or e["model"] for v in [before, after]
                 for c in v["cases"] for e in c["audit"] if e["kind"] == "model_response"})
metric_rows = "\n".join(f"| {name} | {before['metrics'][name]:.4f} | {after['metrics'][name]:.4f} | "
                        f"{after['metrics'][name] - before['metrics'][name]:+.4f} |"
                        for name in ["groundedness", "context_relevance", "faithfulness", "hallucination_rate"])
case_rows = []
for old, new in zip(before["cases"], after["cases"]):
    expected = new["expected"]
    actual = new["result"]
    missing = sorted(set(expected["clauses"]) - {c["clause"] for c in actual.get("citations", [])})
    notes = []
    if not new["passed"]:
        if missing:
            notes.append("missing reference support: " + ", ".join(missing))
        for key in ["route", "verified", "escalation_required", "issue_type"]:
            if key in expected and actual.get(key) != expected[key]:
                notes.append(key + " differs")
        if actual.get("escalation_reason"):
            notes.append(actual["escalation_reason"][:160].replace("|", "/").replace("\n", " "))
        failures = [e for e in new["audit"] if e["kind"] == "run_failure"]
        if failures:
            failure = failures[-1]
            notes.append((failure.get("error", "") + ": " + failure.get("detail", ""))[:180]
                         .replace("|", "/").replace("\n", " "))
    case_rows.append(f"| {new['id']} | {'pass' if old['passed'] else 'fail'} | "
                     f"{'pass' if new['passed'] else 'fail'} | {'; '.join(notes) or 'matches reference'} |")
driver = max(after["cost_by_agent"], key=after["cost_by_agent"].get) if after["cost_by_agent"] else "none"
tokens = {name: sum(e.get(name, 0) for c in after["cases"] for e in c["audit"]
                   if e["kind"] == "model_response") for name in ["prompt_tokens", "completion_tokens"]}
failed_transport = sum(not c["result"].get("verified") and any(
    e["kind"] == "model_failure" and e.get("http_status") in {429, 500, 502, 503, 504}
    for e in c["audit"]) for c in after["cases"])
text = f"""# Real-model official reference evaluation

Measured {measured}. Model identities returned by the provider: {', '.join(models)}.
Source: `output/official-evaluation.json`; compact evidence: `evaluation/results/official-comparison.json`.
Full prompts, completions, exact retrieval results, canonical citations, verification decisions,
usage and timing remain in the ignored full audit. Credentials are not included.

## Controlled comparison

The same {count} fixed official-reference cases were run sequentially with caching bypassed.
Both variants use the same provider/model, source corpus, citation assembly, request pacing,
validation and independently deployed verifier. v1 investigates the apparent category with a
short output specification. v6 explicitly separates applicability from misuse/changed-use
research, distinguishes household exceptions from independent shops, specifies the advisory
output shape and requires re-search after rejection. Prompt files and resolved hashes are audited.

Expected-outcome pass rate: **v1 {sum(c['passed'] for c in before['cases'])}/{count}
({before['pass_rate']:.2%}) -> v6 {sum(c['passed'] for c in after['cases'])}/{count}
({after['pass_rate']:.2%})**, a change of {(after['pass_rate'] - before['pass_rate']) * 100:+.2f} percentage points.
This strict result checks route, escalation, verification, required source clauses and the
issue type where labelled. It is not a claim of general regulatory accuracy.

| Metric, averaged over all cases | v1 | v6 | Change |
|---|---:|---:|---:|
{metric_rows}

These are the proxies defined in evaluation.md. No-answer cases have zero answer-quality
scores; an expected unsupported-case referral can still pass. Exact quotation/provenance
is constructed from retrieved IDs, so grounding can be high by construction. Semantic
faithfulness still depends on a fallible model judge. Malformed drafts rejected before
handoff are visible in failure events and pass rate, not counted as verified candidate claims.
Required-clause scoring can reject a different valid supporting provision; inspect failed
cases with faculty instead of changing labels merely to make the model pass.

## Timing, usage and estimated cost

| Measure | v1 | v6 |
|---|---:|---:|
| Final verified recommendations | {sum(c['result']['verified'] for c in before['cases'])}/{count} | {sum(c['result']['verified'] for c in after['cases'])}/{count} |
| Model responses | {before['total_model_calls']} | {after['total_model_calls']} |
| p50 end-to-end seconds | {before['p50_seconds']:.2f} | {after['p50_seconds']:.2f} |
| p95 end-to-end seconds | {before['p95_seconds']:.2f} | {after['p95_seconds']:.2f} |
| Configured-price estimate per 100 runs, USD | {before['cost_per_100_runs']:.4f} | {after['cost_per_100_runs']:.4f} |

Final-variant reported tokens: {tokens['prompt_tokens']} input and
{tokens['completion_tokens']} output, including reported reasoning. The largest agent cost
driver is **{driver}**. Repeated investigation and context-bearing model calls drive cost.
The rate label in the audit identifies the published pricing assumption; estimates are not
invoices, and free-tier usage can have zero actual API charges. Failed calls without usage
have unknown token/cost consumption rather than a proven zero charge.

Latency includes failed and safe-referral runs, so lower latency alone is not proof of useful
throughput. The batch uses one concurrent client and shared provider pacing. These observational real-model
latencies do not replace the predeclared controlled delayed-stub load experiments in validation.md.
Provider quotas are a bottleneck that extra worker replicas cannot remove.
Final cases with a failed outcome accompanied by HTTP quota/5xx errors: {failed_transport}.

## Per-case results

| Case | v1 | v6 | Final-reference observation |
|---|---|---|---|
{chr(10).join(case_rows)}

## Review boundary

The three primary PDFs and 14 annotations cover the selected Karnataka LT questions and
reviewed billing period. Technical source review and evaluation labels are not faculty
approval or a binding legal opinion. The service never recalculates bills. Faculty corpus
confirmation, the live demonstration/viva and the team's GitHub publication remain human steps.
"""
Path("docs/official-evaluation.md").write_text(text, encoding="utf-8")
print(json.dumps({"report": "docs/official-evaluation.md", "cases": count,
                  "before_pass_rate": before["pass_rate"], "after_pass_rate": after["pass_rate"]}))
