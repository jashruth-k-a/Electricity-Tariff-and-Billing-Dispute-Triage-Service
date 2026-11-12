"""Constrain local-model actions; provenance metadata is materialised from retrieved evidence."""
from copy import deepcopy

from triage.models import Recommendation, Verification


def object_schema(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required, "additionalProperties": False}


def decision_schema(payload):
    if payload["task"] == "verify":
        return Verification.model_json_schema()
    passages = payload.get("PASSAGES", [])
    history = payload.get("HISTORY", [])
    ids = [p["chunk_id"] for p in passages]
    choices = []

    def tool(name, arguments):
        return object_schema({"action": {"const": "tool"}, "tool": {"const": name}, "arguments": arguments})

    choices.append(tool("corpus_search", object_schema({
        "query": {"type": "string", "minLength": 3, "maxLength": 250},
        "strategy": {"enum": ["hybrid", "vector"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 4}})))
    must_research = bool(history and history[-1].get("verification_rejected"))
    if not must_research and not any(item.get("tool") == "request_fields" for item in history):
        choices.append(tool("request_fields", object_schema({"fields": {
            "type": "array", "minItems": 1, "maxItems": 8,
            "items": {"enum": list(payload["REQUEST"])}}})))
    if passages and not must_research:
        identifiers = sorted(set(ids + [p["clause"] for p in passages]))
        choices.append(tool("clause_lookup", object_schema({"identifier": {"enum": identifiers}})))
    retrieval_count = sum(item.get("tool") in {"corpus_search", "clause_lookup"} for item in history)
    mixed = payload["REQUEST"]["premises_use"] == "mixed" or bool(payload["REQUEST"].get("business_activity"))
    can_answer = bool(passages) and not must_research and (not mixed or retrieval_count >= 2)
    definitions = {}
    if can_answer:
        recommendation = deepcopy(Recommendation.model_json_schema())
        definitions = recommendation.pop("$defs", {})
        recommendation["properties"].pop("tariff_position")
        recommendation["required"].remove("tariff_position")
        definitions["Claim"]["properties"]["chunk_ids"]["items"] = {"enum": ids}
        definitions["Claim"]["properties"]["statement"]["maxLength"] = 400
        definitions["Citation"] = object_schema({"chunk_id": {"enum": ids}})
        recommendation["properties"]["claims"]["maxItems"] = 3
        recommendation["properties"]["citations"]["maxItems"] = 4
        settled = deepcopy(recommendation)
        settled["properties"].update({"route": {"enum": ["bill-stands-with-reason", "revision-recommended"]},
                                      "escalation_required": {"const": False},
                                      "escalation_reason": {"const": ""}})
        referred = deepcopy(recommendation)
        referred["properties"].update({"route": {"const": "site-inspection-required"},
                                       "escalation_required": {"const": True},
                                       "escalation_reason": {"type": "string", "minLength": 5, "maxLength": 500}})
        choices.insert(0, object_schema({"action": {"const": "answer"},
                                         "recommendation": {"anyOf": [settled, referred]}}))
        choices.append(object_schema({"action": {"const": "escalate"},
                                      "reason": {"type": "string", "minLength": 5, "maxLength": 500}}))
    result = {"type": "object", "anyOf": choices}
    if definitions:
        result["$defs"] = definitions
    return result


def materialize(result, payload):
    if result.get("action") != "answer":
        return result
    result = deepcopy(result)
    evidence = {p["chunk_id"]: p for p in payload["PASSAGES"]}
    recommendation = result["recommendation"]
    recommendation["tariff_position"] = " ".join(c["statement"] for c in recommendation["claims"])
    for index, reference in enumerate(recommendation["citations"]):
        citation = {"chunk_id": reference} if isinstance(reference, str) else reference
        source = evidence[citation["chunk_id"]]
        citation.update({k: source[k] for k in ["document", "clause", "page", "source_url"]})
        citation["quote"] = source["text"]
        recommendation["citations"][index] = citation
    return result
