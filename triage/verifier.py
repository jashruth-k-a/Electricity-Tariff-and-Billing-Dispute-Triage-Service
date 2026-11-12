import asyncio
import hmac
import time
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import Depends, FastAPI, Header, HTTPException
from langgraph.graph import END, START, StateGraph
from opentelemetry import context
from opentelemetry.propagate import extract
from prometheus_client import make_asgi_app

from triage.config import settings
from triage.corpus import lookup
from triage.models import Verification, VerifyRequest
from triage.observability import STEPS, SUCCESS, TOOLS_PER_RUN, setup_tracing, span
from triage.provider import Provider
from triage.storage import event, redis_client
from triage.verification import deterministic_checks


class AuditState(TypedDict, total=False):
    body: VerifyRequest
    errors: list[str]
    result: dict


async def inspect(state):
    body = state["body"]
    errors = deterministic_checks(body.candidate, body.passages, body.request)
    # Independently resolve every supplied passage against the index: an investigator
    # cannot manufacture a passage and get approval by quoting it accurately.
    for passage in body.passages:
        remaining = body.deadline - time.time()
        if remaining <= 0:
            raise TimeoutError("verification-deadline")
        actual = await asyncio.wait_for(asyncio.to_thread(lookup, passage["chunk_id"]),
                                        min(remaining, settings().call_timeout_seconds))
        if not actual or actual[0] != passage:
            errors.append("Passage provenance failed independent index lookup")
    return {"errors": errors}


async def judge(state):
    body = state["body"]
    if state["errors"]:
        return {"result": Verification(supported=False, reasons=state["errors"],
                 retry_query="misuse electricity higher charges purpose changed use tariff category conditions of supply").model_dump()}
    provider = Provider("verifier", body.run_id, body.deadline, body.prompt_version)
    result = await provider.complete({"task": "verify", "REQUEST": body.request,
                                      "CANDIDATE": body.candidate, "PASSAGES": body.passages})
    return {"result": Verification.model_validate(result).model_dump()}


builder = StateGraph(AuditState)
builder.add_node("provenance_and_policy", inspect)
builder.add_node("semantic_entailment", judge)
builder.add_edge(START, "provenance_and_policy")
builder.add_edge("provenance_and_policy", "semantic_entailment")
builder.add_edge("semantic_entailment", END)
audit_graph = builder.compile()


@asynccontextmanager
async def lifespan(app):
    setup_tracing()
    yield


app = FastAPI(title="Independent evidence verifier", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


def authorised(x_internal_token: str = Header(default="")):
    if not hmac.compare_digest(x_internal_token, settings().internal_token):
        raise HTTPException(401, "Internal authentication required")


@app.get("/health")
def health():
    redis_client().ping()
    return {"status": "ok", "agent": "verifier"}


@app.post("/verify", response_model=Verification, dependencies=[Depends(authorised)])
async def verify(body: VerifyRequest, traceparent: str = Header(default="")):
    token = context.attach(extract({"traceparent": traceparent}))
    try:
        with span("agent.verifier", body.run_id):
            result = await asyncio.wait_for(audit_graph.ainvoke({"body": body}),
                                            max(.01, body.deadline - time.time()))
            event(body.run_id, "verifier", "verification", **result["result"])
            STEPS.labels("verifier").observe(2)
            TOOLS_PER_RUN.labels("verifier").observe(len(body.passages))
            SUCCESS.labels("verifier", "supported" if result["result"]["supported"] else "rejected").inc()
            return result["result"]
    except Exception as exc:
        event(body.run_id, "verifier", "verification_failure", error=type(exc).__name__)
        SUCCESS.labels("verifier", "failed").inc()
        raise HTTPException(503, "Verification unavailable; caller must escalate") from exc
    finally:
        context.detach(token)
