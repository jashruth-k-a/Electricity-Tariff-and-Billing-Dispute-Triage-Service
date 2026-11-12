"""Check a configured provider without displaying credentials or raw HTTP failures."""
import argparse
import json
import os

import httpx
import truststore
from dotenv import dotenv_values

parser = argparse.ArgumentParser()
parser.add_argument("--env-file", default=".env.official")
parser.add_argument("--catalog-url")
parser.add_argument("--native", action="store_true", help="Check Gemini's native generateContent endpoint")
parser.add_argument("--model")
parser.add_argument("--base-url")
parser.add_argument("--key-name", default="LLM_API_KEY")
parser.add_argument("--scenario")
parser.add_argument("--prompt-version", default="v6")
parser.add_argument("--temperature", type=float, default=0)
parser.add_argument("--structured", action="store_true")
parser.add_argument("--evidence-from")
parser.add_argument("--timeout", type=float, default=30)
args = parser.parse_args()
cfg = {k.upper(): v for k, v in {**os.environ, **dotenv_values(args.env_file)}.items()}
key = cfg.get(args.key_name.upper(), "")
base_url = args.base_url or cfg["LLM_BASE_URL"]
if not key:
    raise SystemExit("Provider key is missing from the selected environment file")
truststore.inject_into_ssl()
try:
    with httpx.Client(timeout=args.timeout) as client:
        if args.catalog_url:
            response = client.get(args.catalog_url, headers={"x-goog-api-key": key})
        elif args.native:
            model = args.model or cfg["LLM_MODEL"]
            url = base_url.rstrip("/").removesuffix("/openai") + "/models/" + model + ":generateContent"
            response = client.post(url, headers={"x-goog-api-key": key}, json={
                "contents": [{"role": "user", "parts": [{"text": 'Return JSON only: {"ready":true}'}]}],
                "generationConfig": {"maxOutputTokens": 2048, "responseMimeType": "application/json"}})
        else:
            messages = [{"role": "user", "content": 'Return JSON only: {"ready":true}'}]
            if args.scenario:
                from pathlib import Path
                case = next(c for c in json.loads(Path(args.scenario).read_text(encoding="utf-8"))
                            if c["id"] == "tailoring-reference")
                payload = {"task": "investigate", "REQUEST": case["request"],
                           "PASSAGES": [], "HISTORY": [], "RETRY_QUERY": "", "step": 0}
                if args.evidence_from:
                    evidence_report = json.loads(Path(args.evidence_from).read_text(encoding="utf-8"))
                    audit = next(iter(evidence_report["variants"].values()))["cases"][0]["audit"]
                    passages = {p["chunk_id"]: p for e in audit if e["kind"] == "tool_call"
                                and isinstance(e.get("result"), list) for p in e["result"]}
                    payload["PASSAGES"] = list(passages.values())
                    payload["HISTORY"] = [{"tool": "corpus_search"}, {"tool": "clause_lookup"}]
                messages = [{"role": "system", "content": Path(
                    f"prompts/{args.prompt_version}/investigator.txt").read_text(encoding="utf-8")},
                    {"role": "user", "content": json.dumps(payload)}]
            response_format = {"type": "json_object"}
            if args.structured:
                if not args.scenario:
                    parser.error("--structured requires --scenario")
                from triage.structured import decision_schema
                response_format = {"type": "json_schema", "json_schema": {
                    "name": "agent_decision", "schema": decision_schema(payload)}}
            response = client.post(base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + key}, json={"model": args.model or cfg["LLM_MODEL"],
                "messages": messages, "temperature": args.temperature,
                "max_tokens": 2048, "response_format": response_format})
        if response.status_code != 200:
            try:
                failure = response.json()
                if isinstance(failure, list):
                    failure = failure[0] if failure else {}
                error = failure.get("error", {})
            except ValueError:
                error = {}
            print(json.dumps({"http_status": response.status_code, "success": False,
                "provider_status": error.get("status"),
                "message": str(error.get("message", "")).replace(key, "[redacted]")[:800],
                "quota_violations": [{k: v[k] for k in ["quotaMetric", "quotaId", "quotaValue"] if k in v}
                    for detail in error.get("details", []) for v in detail.get("violations", [])],
                "retry_delays": [d["retryDelay"] for d in error.get("details", []) if "retryDelay" in d]}))
            raise SystemExit(1)
        body = response.json()
        if args.catalog_url:
            print(json.dumps({"available_models": [m["name"] for m in body.get("models", [])
                              if "generateContent" in m.get("supportedGenerationMethods", [])]}, indent=2))
        elif args.native:
            print(json.dumps({"success": True, "model": body.get("modelVersion"),
                              "usage": body.get("usageMetadata"), "candidate_count": len(body.get("candidates", []))}, indent=2))
        else:
            print(json.dumps({"success": True, "model": body.get("model"), "usage": body.get("usage"),
                "content": body["choices"][0]["message"].get("content"),
                "finish_reason": body["choices"][0].get("finish_reason")}, indent=2))
except httpx.HTTPError as exc:
    print(json.dumps({"success": False, "transport_error": type(exc).__name__}))
    raise SystemExit(1) from None
