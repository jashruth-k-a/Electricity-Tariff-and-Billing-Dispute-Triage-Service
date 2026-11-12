import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description="Corpus, evaluation and failure demonstration tools")
    commands = parser.add_subparsers(dest="command", required=True)
    ingestion = commands.add_parser("ingest", help="Idempotently parse, chunk, embed and upsert the selected corpus")
    ingestion.add_argument("--reembed", action="store_true")
    fetch = commands.add_parser("fetch", help="Download hash-pinned primary sources from a manifest")
    fetch.add_argument("--manifest", default="corpus/official/research-manifest.json")
    evaluation = commands.add_parser("evaluate", help="Run the fixed reference set against both prompt versions")
    evaluation.add_argument("--api-url", default=os.getenv("API_INTERNAL_URL"))
    evaluation.add_argument("--cases", default="evaluation/cases.json")
    evaluation.add_argument("--versions", nargs="+", default=["v1", "v2"], choices=["v1", "v2", "v3", "v4", "v5", "v6"])
    evaluation.add_argument("--concurrency", type=int, default=3)
    evaluation.add_argument("--output", default="output/evaluation.json")
    faults = commands.add_parser("fault", help="Inject a short-lived demo provider failure")
    faults.add_argument("mode", choices=["normal", "unavailable", "timeout", "unsupported"])
    contracts = commands.add_parser("contracts", help="Export machine-readable JSON schemas")
    contracts.add_argument("--output", default="docs/contracts")
    args = parser.parse_args()
    if args.command == "fetch":
        import hashlib
        source_manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        for document in source_manifest["documents"]:
            destination = Path(document["path"]).resolve()
            if not destination.is_relative_to(Path("data").resolve()):
                parser.error("Downloaded documents must remain inside data/")
            if not document["source_url"].startswith("https://"):
                parser.error("Primary-source downloads require HTTPS")
            destination.parent.mkdir(parents=True, exist_ok=True)
            response = httpx.get(document["source_url"], timeout=60, follow_redirects=True)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise ValueError("Downloaded content is not a PDF")
            digest = hashlib.sha256(response.content).hexdigest()
            if document.get("sha256") and digest != document["sha256"]:
                raise ValueError("Source changed: review the document and update the manifest hash")
            destination.write_bytes(response.content)
            print(json.dumps({"document": document["id"], "sha256": digest, "bytes": len(response.content)}))
        return
    if args.command == "contracts":
        from triage.models import Dispute, Feedback, Recommendation, Verification, VerifyRequest
        directory = Path(args.output)
        directory.mkdir(parents=True, exist_ok=True)
        for model in [Dispute, Feedback, Recommendation, Verification, VerifyRequest]:
            (directory / (model.__name__ + ".schema.json")).write_text(
                json.dumps(model.model_json_schema(), indent=2), encoding="utf-8")
        return
    from triage.config import settings
    cfg = settings()
    if args.command == "ingest":
        from triage.corpus import ingest
        print(json.dumps(ingest(args.reembed), indent=2))
    elif args.command == "evaluate":
        from triage.evaluation import evaluate
        if not args.api_url:
            parser.error("--api-url or API_INTERNAL_URL is required")
        if not 1 <= args.concurrency <= 10:
            parser.error("concurrency must be 1..10")
        result = asyncio.run(evaluate(args.api_url, cfg.internal_token, args.cases, args.versions,
                                     args.concurrency, cfg.api_client_keys.split(",")[0], args.output))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({v: {k: value for k, value in r.items() if k != "cases"}
                          for v, r in result["variants"].items()}, indent=2))
        print("Full audit saved to " + str(output))
    elif args.command == "fault":
        if cfg.app_mode != "demo":
            parser.error("Fault injection requires demo mode")
        url = cfg.llm_base_url.removesuffix("/v1") + "/admin/fault"
        response = httpx.post(url, json={"mode": args.mode},
                              headers={"X-Internal-Token": cfg.internal_token}, timeout=5)
        response.raise_for_status()
        print(response.text)


if __name__ == "__main__":
    main()
