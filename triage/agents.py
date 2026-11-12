import asyncio
import json
import time
from typing import TypedDict

import httpx
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph
from opentelemetry.propagate import inject
from pydantic import BaseModel, Field

from triage.config import settings
from triage.corpus import index_info, lookup, search
from triage.guards import check_text
from triage.models import Recommendation, Verification
from triage.observability import CALLS, LATENCY, RETRIES, STEPS, SUCCESS, TOOLS_PER_RUN, span
from triage.provider import Provider
from triage.storage import event


class SearchArgs(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    strategy: str = Field(default="hybrid", pattern="^(hybrid|vector)$")
    limit: int = Field(default=4, ge=1, le=5)


class LookupArgs(BaseModel):
    identifier: str = Field(min_length=1, max_length=120)


class FieldsArgs(BaseModel):
    fields: list[str] = Field(min_length=1, max_length=20)


class Investigation(TypedDict, total=False):
    run_id: str
    request: dict
    deadline: float
    prompt_version: str
    steps: int
    tool_calls: int
    passages: list[dict]
    history: list[dict]
    action: dict
    candidate: dict
    retry_query: str
    verifications: int
    result: dict


def fallback(reason):
    if not isinstance(reason, str):
        reason = "Insufficient verified evidence; human review required."
    reason = reason[:2000]
    return {"route": "site-inspection-required", "tariff_position": None, "claims": [], "citations": [],
            "escalation_required": True, "escalation_reason": reason,
            "verified": False, "advisory_only": True}


def budget(state, extra=1):
    cfg = settings()
    if time.time() >= state["deadline"]:
        return "Run deadline exceeded; refer to grievance officer."
    if state["steps"] + extra > cfg.max_steps or state["tool_calls"] >= cfg.max_tool_calls:
        return "Agent step/tool budget exhausted; refer to grievance officer."
    return None


async def decide(state):
    reason = budget(state)
    if reason:
        return {"result": fallback(reason)}
    provider = Provider("investigator", state["run_id"], state["deadline"], state["prompt_version"])
    action = await provider.complete({"task": "investigate", "REQUEST": state["request"],
              "PASSAGES": state["passages"], "HISTORY": [{k: v for k, v in item.items() if k != "result"}
                                                          for item in state["history"]],
              "RETRY_QUERY": state.get("retry_query", ""), "step": state["steps"]})
    event(state["run_id"], "investigator", "decision", action=action)
    if state["history"] and state["history"][-1].get("verification_rejected") and not (
            action.get("action") == "tool" and action.get("tool") == "corpus_search"):
        return {"result": fallback("The required evidence re-search was not performed; human review required.")}
    if action.get("action") not in {"tool", "answer", "escalate"}:
        return {"result": fallback("Invalid agent action; human review required.")}
    return {"action": action, "steps": state["steps"] + 1}


async def use_tool(state):
    cfg = settings()
    action = state["action"]
    request = state["request"]
    fields_tool = StructuredTool.from_function(
        func=lambda fields: {k: request[k] for k in fields if k in request},
        name="request_fields", description="Read supplied premises and load facts", args_schema=FieldsArgs)
    tools = {
        "corpus_search": StructuredTool.from_function(search, name="corpus_search",
            description="Search category definitions and modifying provisions", args_schema=SearchArgs),
        "clause_lookup": StructuredTool.from_function(lookup, name="clause_lookup",
            description="Read a specific retrieved clause or chunk identifier", args_schema=LookupArgs),
        "request_fields": fields_tool,
    }
    name = action.get("tool", "")
    args = action.get("arguments", {})
    if name not in tools or check_text(args):
        return {"result": fallback("Tool request rejected by policy.")}
    if any(item.get("tool") == name and item.get("arguments") == args for item in state["history"]):
        event(state["run_id"], "investigator", "duplicate_tool_rejected", tool=name, arguments=args)
        return {"tool_calls": state["tool_calls"] + 1, "history": state["history"] + [{
            "tool_rejected": name, "arguments": args,
            "reason": "Identical tool call already completed. Read PASSAGES; answer if sufficient or choose a different query."}]}
    start = time.monotonic()
    with span("tool." + name, state["run_id"], arguments=json.dumps(args)):
        for attempt in range(cfg.max_retries + 1):
            if state["tool_calls"] + attempt >= cfg.max_tool_calls:
                raise TimeoutError("Tool-call budget exhausted")
            try:
                result = await asyncio.wait_for(asyncio.to_thread(tools[name].invoke, args),
                         min(cfg.call_timeout_seconds, max(.01, state["deadline"] - time.time())))
                break
            except (TimeoutError, ConnectionError, httpx.TransportError) as exc:
                event(state["run_id"], "investigator", "tool_failure", tool=name,
                      attempt=attempt, error=type(exc).__name__)
                if attempt >= cfg.max_retries or time.time() >= state["deadline"]:
                    raise
                RETRIES.labels("investigator").inc()
                await asyncio.sleep(min(.25 * 2 ** attempt, max(.01, state["deadline"] - time.time())))
    if check_text(result):
        return {"result": fallback("Unsafe corpus content quarantined before reaching a model.")}
    passages = {p["chunk_id"]: p for p in state["passages"]}
    if name != "request_fields":
        billing_date = request["billing_date"]
        for passage in result:
            if passage["effective_from"] <= billing_date <= passage["effective_to"]:
                passages[passage["chunk_id"]] = passage
    elapsed = time.monotonic() - start
    CALLS.labels("investigator", name, "success").inc()
    LATENCY.labels("investigator", name).observe(elapsed)
    event(state["run_id"], "investigator", "tool_call", tool=name, arguments=args,
          result=result, latency_seconds=elapsed)
    return {"passages": list(passages.values()), "tool_calls": state["tool_calls"] + attempt + 1,
            "history": state["history"] + [{"tool": name, "arguments": args, "result": result}]}


async def verify(state):
    action = state["action"]
    if action["action"] == "escalate":
        # The model's reason remains in the decision audit. It has not passed the
        # semantic verifier and may itself contain an unsupported tariff position.
        return {"result": fallback("The investigator could not establish a supported tariff position; "
                                   "refer the supplied facts and retrieved evidence to a grievance officer.")}
    reason = budget(state, 2)
    if reason:
        return {"result": fallback(reason)}
    try:
        candidate = Recommendation.model_validate(action.get("recommendation", {})).model_dump()
    except ValueError:
        candidate = action.get("recommendation", {})
    cfg = settings()
    headers = {"X-Internal-Token": cfg.internal_token, "X-Correlation-ID": state["run_id"]}
    with span("handoff.verifier", state["run_id"]):
        inject(headers)
        async with httpx.AsyncClient(timeout=max(.01, state["deadline"] - time.time())) as client:
            response = await client.post(cfg.verifier_url.rstrip("/") + "/verify", headers=headers,
                json={"run_id": state["run_id"], "request": state["request"], "candidate": candidate,
                      "passages": state["passages"], "prompt_version": state["prompt_version"],
                      "deadline": state["deadline"], "steps_remaining": cfg.max_steps - state["steps"]})
            response.raise_for_status()
    result = Verification.model_validate(response.json())
    event(state["run_id"], "investigator", "handoff_result", candidate=candidate,
          verification=result.model_dump())
    if result.supported:
        return {"result": {**candidate, "verified": True, "advisory_only": True},
                "steps": state["steps"] + 2}
    if state["verifications"] >= 1:
        return {"result": fallback("Evidence verification failed twice: " + "; ".join(result.reasons))}
    return {"retry_query": result.retry_query or "mixed use supply conditions exceptions",
            "history": state["history"] + [{"verification_rejected": result.model_dump()}],
            "verifications": state["verifications"] + 1, "steps": state["steps"] + 2}


def next_decision(state):
    if state.get("result"):
        return END
    return "tool" if state["action"]["action"] == "tool" else "verify"


builder = StateGraph(Investigation)
builder.add_node("investigator", decide)
builder.add_node("tool", use_tool)
builder.add_node("verify", verify)
builder.add_edge(START, "investigator")
builder.add_conditional_edges("investigator", next_decision, {END: END, "tool": "tool", "verify": "verify"})
builder.add_conditional_edges("tool", lambda s: END if s.get("result") else "investigator")
builder.add_conditional_edges("verify", lambda s: END if s.get("result") else "investigator")
investigation_graph = builder.compile()


async def investigate(run_id, request, deadline, version):
    initial = {"run_id": run_id, "request": request, "deadline": deadline, "prompt_version": version,
               "steps": 0, "tool_calls": 0, "passages": [], "history": [], "verifications": 0}
    info = index_info()
    if not info:
        return fallback("Corpus unavailable; human review required.")
    if settings().app_mode == "production" and info["status"] != "approved":
        return fallback("Official corpus is not approved; human review required.")
    if request["state"].casefold() != info["state"].casefold() or request["connection_type"] != "LT":
        return fallback("State or connection type is outside the indexed LT corpus.")
    if request["billed_category"] == "agricultural" or request["premises_use"] == "agricultural":
        return fallback("Agricultural category is outside the selected project scope.")
    if request["premises_use"] == "unknown":
        return fallback("Actual premises use is unknown; a grievance officer must establish the facts.")
    if not all(d["effective_from"] <= request["billing_date"] <= d["effective_to"] for d in info["documents"]):
        return fallback("Billing date is outside the reviewed corpus effective period.")
    with span("agent.investigator", run_id):
        final = await asyncio.wait_for(investigation_graph.ainvoke(initial, {"recursion_limit": 50}),
                                       max(.01, deadline - time.time()))
    STEPS.labels("investigator").observe(final["steps"])
    TOOLS_PER_RUN.labels("investigator").observe(final["tool_calls"])
    SUCCESS.labels("investigator", "verified" if final["result"]["verified"] else "escalated").inc()
    event(run_id, "investigator", "agent_summary", steps=final["steps"], tool_calls=final["tool_calls"])
    return final["result"]
