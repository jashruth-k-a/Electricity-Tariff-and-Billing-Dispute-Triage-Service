from triage.verification import deterministic_checks


def test_supported_quote(candidate, evidence, request_data):
    assert deterministic_checks(candidate, evidence, request_data) == []


def test_invented_quote_rejected(candidate, evidence, request_data):
    candidate["citations"][0]["quote"] = "An invented tariff exemption that never appears in the source."
    assert any("quote" in e for e in deterministic_checks(candidate, evidence, request_data))


def test_unretrieved_citation_rejected(candidate, evidence, request_data):
    assert "Citation was not retrieved" in deterministic_checks(candidate, [], request_data)


def test_changed_page_rejected(candidate, evidence, request_data):
    candidate["citations"][0]["page"] = 900
    assert "Citation metadata mismatch: page" in deterministic_checks(candidate, evidence, request_data)


def test_uncited_claim_rejected(candidate, evidence, request_data):
    candidate["claims"][0]["chunk_ids"] = ["missing"]
    assert "Claim lacks retrieved citations" in deterministic_checks(candidate, evidence, request_data)


def test_unverified_position_text_rejected(candidate, evidence, request_data):
    candidate["tariff_position"] += " The bill is hereby cancelled."
    errors = deterministic_checks(candidate, evidence, request_data)
    assert "Tariff position contains text outside verified claims" in errors
    assert "Output guardrail rejected candidate" in errors


def test_mixed_use_requires_modifier_and_human(candidate, evidence, request_data):
    request_data.update(premises_use="mixed", business_activity="tailoring")
    errors = deterministic_checks(candidate, evidence, request_data)
    assert "Mixed-use case lacks modifier evidence" in errors


def test_hidden_business_is_detected(candidate, evidence, request_data):
    request_data["description"] = "I run a tailoring shop in one room of my house."
    assert "Mixed-use case lacks modifier evidence" in deterministic_checks(candidate, evidence, request_data)
