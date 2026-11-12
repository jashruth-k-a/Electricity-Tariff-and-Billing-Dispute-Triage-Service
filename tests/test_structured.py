import pytest
from jsonschema import ValidationError, validate

from triage.structured import decision_schema, materialize


def payload(evidence):
    return {"task": "investigate", "REQUEST": {"premises_use": "residential", "business_activity": None},
            "PASSAGES": evidence, "HISTORY": []}


def test_cannot_answer_or_invent_clause_lookup_without_evidence():
    schema = decision_schema(payload([]))
    with pytest.raises(ValidationError):
        validate({"action": "answer", "recommendation": {}}, schema)
    with pytest.raises(ValidationError):
        validate({"action": "tool", "tool": "clause_lookup", "arguments": {"identifier": "invented"}}, schema)
    validate({"action": "tool", "tool": "corpus_search", "arguments": {
        "query": "domestic category", "strategy": "hybrid", "limit": 3}}, schema)


def test_rejection_forces_search_not_another_unverified_answer(evidence):
    data = payload(evidence)
    data["HISTORY"] = [{"verification_rejected": {"supported": False}}]
    schema = decision_schema(data)
    assert len(schema["anyOf"]) == 1
    assert schema["anyOf"][0]["properties"]["tool"]["const"] == "corpus_search"


def test_citation_metadata_and_position_are_built_from_evidence(candidate, evidence):
    candidate.pop("tariff_position")
    for citation in candidate["citations"]:
        citation.pop("quote")
        for key in ["document", "clause", "page", "source_url"]:
            citation.pop(key)
    decision = {"action": "answer", "recommendation": candidate}
    validate(decision, decision_schema(payload(evidence)))
    expanded = materialize(decision, payload(evidence))["recommendation"]
    assert expanded["tariff_position"] == expanded["claims"][0]["statement"]
    assert expanded["citations"][0]["document"] == evidence[0]["document"]
    assert expanded["citations"][0]["quote"] == evidence[0]["text"]
    decision["recommendation"]["escalation_required"] = True
    with pytest.raises(ValidationError):
        validate(decision, decision_schema(payload(evidence)))


def test_materialization_cannot_resolve_an_unretrieved_citation(candidate, evidence):
    candidate["citations"][0]["chunk_id"] = "not-retrieved"
    with pytest.raises(KeyError):
        materialize({"action": "answer", "recommendation": candidate}, payload(evidence))


def test_string_reference_uses_the_same_canonical_source(candidate, evidence):
    candidate["citations"] = [candidate["citations"][0]["chunk_id"]]
    expanded = materialize({"action": "answer", "recommendation": candidate}, payload(evidence))["recommendation"]
    assert expanded["citations"][0]["quote"] == evidence[0]["text"]
    assert expanded["citations"][0]["clause"] == evidence[0]["clause"]
    candidate["citations"] = ["not-retrieved"]
    with pytest.raises(KeyError):
        materialize({"action": "answer", "recommendation": candidate}, payload(evidence))
