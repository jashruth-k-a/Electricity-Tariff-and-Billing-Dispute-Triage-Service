import asyncio
import time

from triage.agents import budget, fallback


def test_deadline_forces_fallback():
    assert budget({"deadline": time.time() - 1, "steps": 0, "tool_calls": 0})


def test_step_budget_is_bounded():
    assert budget({"deadline": time.time() + 60, "steps": 1000, "tool_calls": 0})


def test_failure_has_no_confident_tariff_position():
    result = fallback("Provider failed")
    assert result["tariff_position"] is None
    assert result["verified"] is False
    assert result["escalation_required"] is True
    assert result["citations"] == []


def test_duplicate_tool_does_not_repeat_retrieval(monkeypatch, request_data):
    import triage.agents as agents
    def unexpected_search(**kwargs):
        raise AssertionError("Repeated retrieval must not run")
    monkeypatch.setattr(agents, "search", unexpected_search)
    monkeypatch.setattr(agents, "event", lambda *args, **kwargs: None)
    arguments = {"query": "domestic category", "strategy": "hybrid", "limit": 3}
    state = {"run_id": "duplicate", "request": request_data, "tool_calls": 1,
             "history": [{"tool": "corpus_search", "arguments": arguments}],
             "action": {"tool": "corpus_search", "arguments": arguments}}
    result = asyncio.run(agents.use_tool(state))
    assert result["tool_calls"] == 2
    assert result["history"][-1]["tool_rejected"] == "corpus_search"


def test_unverified_escalation_cannot_leak_tariff_advice():
    from triage.agents import verify
    result = asyncio.run(verify({"action": {"action": "escalate",
        "reason": "The customer must be billed commercial under an invented rule."}}))["result"]
    assert "commercial" not in result["escalation_reason"]
    assert result["tariff_position"] is None
    assert result["verified"] is False


def test_rejected_candidate_requires_search_before_another_answer(monkeypatch, request_data):
    import triage.agents as agents
    class FakeProvider:
        def __init__(self, *args):
            pass
        async def complete(self, payload):
            return {"action": "answer", "recommendation": {}}
    monkeypatch.setattr(agents, "Provider", FakeProvider)
    monkeypatch.setattr(agents, "event", lambda *args, **kwargs: None)
    state = {"run_id": "re-search", "deadline": time.time() + 60, "steps": 0, "tool_calls": 1,
             "prompt_version": "v6", "request": request_data, "passages": [],
             "history": [{"verification_rejected": {"supported": False}}]}
    result = asyncio.run(agents.decide(state))["result"]
    assert result["verified"] is False
    assert "re-search was not performed" in result["escalation_reason"]
