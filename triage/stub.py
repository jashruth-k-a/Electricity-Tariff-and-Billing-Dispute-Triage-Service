"""Delayed deterministic OpenAI-compatible fixture. Not an LLM or a legal reasoning benchmark."""
import asyncio
import hmac
import json

from fastapi import FastAPI, Header, HTTPException
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field

from triage.config import settings
from triage.observability import CALLS, LATENCY
from triage.storage import redis_client
from triage.verification import deterministic_checks

app = FastAPI(title="Deterministic model stub (synthetic demo and load tests only)")
app.mount("/metrics", make_asgi_app())


class Fault(BaseModel):
    mode: str = Field(pattern="^(normal|unavailable|timeout|unsupported)$")


@app.get("/health")
def health():
    return {"status": "ok", "model": "stub"}


@app.post("/admin/fault")
def fault(body: Fault, x_internal_token: str = Header(default="")):
    cfg = settings()
    if not cfg.stub_admin_enabled or not hmac.compare_digest(x_internal_token, cfg.internal_token):
        raise HTTPException(403, "Fault injection disabled or unauthorised")
    redis_client().setex("stub:fault", 300, body.mode)
    return {"mode": body.mode, "expires_in": 300}


def issue(request):
    text = request["description"].lower()
    if request["connected_load_kw"] > request["sanctioned_load_kw"] or "load violation" in text:
        return "load-violation", "load"
    if any(w in text for w in ["meter", "faulty", "accuracy"]):
        return "meter-accuracy", "meter"
    if "disconnect" in text:
        return "disconnection", "arrears"
    if any(w in text for w in ["arrear", "payment", "paid"]):
        return "arrears", "arrears"
    return "tariff-category", request["premises_use"]


def mixed(request):
    text = request["description"].lower()
    return request["premises_use"] == "mixed" or (request["premises_use"] == "residential" and
           (request.get("business_activity") or any(w in text for w in ["tailor", "shop", "business", "office", "salon"])))


def tool(name, **arguments):
    return {"action": "tool", "tool": name, "arguments": arguments}


def investigate_fixture(payload, v2):
    request, history, passages = payload["REQUEST"], payload["HISTORY"], payload["PASSAGES"]
    used = [x.get("tool") for x in history]
    issue_type, topic = issue(request)
    if not used:
        return tool("request_fields", fields=["premises_use", "business_activity", "connected_load_kw",
                    "sanctioned_load_kw", "billed_category", "business_area_sqm", "total_area_sqm", "separate_meter"])
    if "corpus_search" not in used:
        query = {"residential": "D1 domestic residential dwelling lighting household appliances",
                 "mixed": "D1 domestic residential dwelling lighting household appliances",
                 "commercial": "C1 wholly commercial shop office retail services",
                 "industrial": "I1 industrial manufacturing production workshop",
                 "meter": "S2 meter accuracy faulty testing",
                 "load": "S3 load violation connected sanctioned equipment",
                 "arrears": "S4 arrears disconnection payment history notices"}.get(topic, "S5 scope unknown")
        return tool("corpus_search", query=query, strategy="vector", limit=2)
    by_clause = {p["clause"]: p for p in passages}
    is_mixed = mixed(request)
    changed = any(w in request["description"].lower() for w in ["re-categor", "recategor", "changed use", "change of use"])
    if v2 and is_mixed and "M1" not in by_clause:
        if len([t for t in used if t == "corpus_search"]) < 2:
            return tool("corpus_search", query="M1 mixed-use modifier partly tailoring house business area separate meter",
                        strategy="hybrid", limit=3)
        return tool("clause_lookup", identifier="M1")
    if v2 and changed and "S1" not in by_clause:
        return tool("clause_lookup", identifier="S1")
    if "clause_lookup" not in used:
        identifier = "D1" if topic in {"residential", "mixed"} else {
            "commercial": "C1", "industrial": "I1", "meter": "S2", "load": "S3", "arrears": "S4"}.get(topic, "S5")
        return tool("clause_lookup", identifier=identifier)
    if payload.get("RETRY_QUERY") and history[-1].get("verification_rejected"):
        return tool("corpus_search", query=payload["RETRY_QUERY"], strategy="hybrid", limit=4)
    if not passages:
        return {"action": "escalate", "reason": "No applicable passages were retrieved."}
    clauses = []
    escalate = False
    route = "bill-stands-with-reason"
    reason = ""
    if v2 and is_mixed:
        clauses = ["D1", "M1"]
        text = "The domestic category definition and mixed-use modifier require human review of the business operated from the dwelling. A site inspection is recommended; the tariff category remains unresolved."
        escalate = True
        reason = "Mixed residential and business use requires the officer to establish actual use, area, load and metering."
    elif v2 and changed:
        clauses = ["D1" if topic == "residential" else "C1", "S1"]
        text = "The category definition must be checked with the change-of-use process and inspection record before accepting re-categorisation. Human review and site inspection are recommended."
        escalate = True
        reason = "Change-of-use notice and inspection record require officer review."
    elif topic in {"meter", "load", "arrears"}:
        clauses = [{"meter": "S2", "load": "S3", "arrears": "S4"}[topic]]
        text = {"meter": "Meter accuracy cannot be settled from tariff definitions; meter testing or site inspection and human review are recommended.",
                "load": "Connected load exceeds sanctioned load; verification of equipment and load records by site inspection is recommended.",
                "arrears": "The contested arrears or disconnection require payment history and notice records; human investigation is recommended."}[topic]
        escalate = True
        reason = "The required physical test or supporting records need a grievance officer."
    elif topic in {"residential", "mixed"}:
        clauses = ["D1"]
        text = "Exclusive residential dwelling use supports the domestic category."
        if request["billed_category"] != "domestic":
            route = "revision-recommended"
            text += " Review of the billed category is recommended."
    elif topic == "commercial":
        clauses = ["C1"]
        text = "Exclusive commercial shop or office use supports the commercial category."
        if request["billed_category"] != "commercial":
            route = "revision-recommended"
            text += " Review of the billed category is recommended."
    elif topic == "industrial":
        clauses = ["I1"]
        text = "Exclusive manufacturing use supports the industrial category, subject to verified activity and load."
        if request["billed_category"] != "industrial":
            route = "revision-recommended"
            text += " Review of the billed category is recommended."
    else:
        return {"action": "escalate", "reason": "Unknown premises use is not settled by the indexed evidence."}
    if any(c not in by_clause for c in clauses):
        return tool("clause_lookup", identifier=next(c for c in clauses if c not in by_clause))
    chosen = [by_clause[c] for c in clauses]
    citations = [{"chunk_id": p["chunk_id"], "quote": p["text"], **{k: p[k] for k in
                 ["document", "clause", "page", "source_url"]}} for p in chosen]
    return {"action": "answer", "recommendation": {"route": "site-inspection-required" if escalate else route,
        "tariff_position": text, "claims": [{"statement": text, "chunk_ids": [p["chunk_id"] for p in chosen]}],
        "citations": citations, "escalation_required": escalate, "escalation_reason": reason, "issue_type": issue_type}}


@app.post("/v1/chat/completions")
async def complete(body: dict):
    import time
    started = time.monotonic()
    mode = redis_client().get("stub:fault") or "normal"
    if mode == "unavailable":
        raise HTTPException(503, "Injected provider outage")
    await asyncio.sleep(settings().call_timeout_seconds + 5 if mode == "timeout" else settings().stub_delay_seconds)
    payload = json.loads(body["messages"][-1]["content"])
    if payload["task"] == "verify":
        errors = deterministic_checks(payload["CANDIDATE"], payload["PASSAGES"], payload["REQUEST"])
        # Extra fixture-specific semantic checks. This does not substitute for a real model judge.
        candidate = payload["CANDIDATE"]
        if mixed(payload["REQUEST"]) and not candidate.get("escalation_required"):
            errors.append("Fixture semantics: mixed premises cannot be described as exclusively residential")
        result = {"supported": not errors, "reasons": errors,
                  "retry_query": "mixed use residential premises tailoring business supply conditions" if errors else ""}
    else:
        v2 = "THEN explicitly" in body["messages"][0]["content"]
        result = investigate_fixture(payload, v2)
        if mode == "unsupported" and result.get("action") == "answer":
            result["recommendation"]["citations"][0]["quote"] = "This fabricated text does not occur in the corpus."
    content = json.dumps(result)
    CALLS.labels("stub", "completion", "success").inc()
    LATENCY.labels("stub", "completion").observe(time.monotonic() - started)
    return {"choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": max(1, len(json.dumps(body["messages"])) // 4),
                      "completion_tokens": max(1, len(content) // 4)}, "fixture": True}
