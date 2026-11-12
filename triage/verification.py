import re

from triage.guards import check_text
from triage.models import Recommendation


def normal(text):
    return " ".join(text.split())


def deterministic_checks(candidate, passages, request):
    errors = []
    try:
        result = Recommendation.model_validate(candidate)
    except ValueError:
        return ["Candidate violates recommendation schema"]
    if check_text(candidate, output=True):
        errors.append("Output guardrail rejected candidate")
    evidence = {p["chunk_id"]: p for p in passages}
    cited = set()
    for citation in result.citations:
        p = evidence.get(citation.chunk_id)
        if not p:
            errors.append("Citation was not retrieved")
            continue
        cited.add(citation.chunk_id)
        if normal(citation.quote) not in normal(p["text"]):
            errors.append("Citation quote does not resolve to retrieved text")
        for field in ["document", "clause", "page", "source_url"]:
            if getattr(citation, field) != p[field]:
                errors.append("Citation metadata mismatch: " + field)
    for claim in result.claims:
        if not set(claim.chunk_ids) <= cited:
            errors.append("Claim lacks retrieved citations")
    if result.tariff_position != " ".join(c.statement for c in result.claims):
        errors.append("Tariff position contains text outside verified claims")
    # Requests marked residential can still describe a business; never rely only on the enum.
    mixed = (request["premises_use"] == "mixed" or (request.get("business_activity") and
              request["premises_use"] == "residential") or
             bool(re.search(r"(tailor|shop|business|salon|office).{0,60}(home|house|room)|"
                            r"(home|house|room).{0,60}(tailor|shop|business|salon|office)",
                            request["description"], re.I)))
    if mixed:
        texts = [evidence[c]["text"].lower() for c in cited]
        if not any("domestic" in t or "residential" in t for t in texts):
            errors.append("Mixed-use case lacks category evidence")
        if not any(re.search(r"mixed.use|partly|partially|portion|changed.use|non.domestic", t) for t in texts):
            errors.append("Mixed-use case lacks modifier evidence")
        if any(p.get("corpus_status") == "approved" for p in passages):
            cited_kinds = {evidence[c].get("kind") for c in cited}
            if not {"tariff", "supply"} <= cited_kinds:
                errors.append("Official home-business case must cite both tariff applicability and a modifying supply provision")
        # The semantic verifier decides whether an explicit exception settles the case.
        # A business at home is not automatically ambiguous if the official order expressly covers it.
    if result.escalation_required and (result.route != "site-inspection-required" or
                                        len(result.escalation_reason.strip()) < 5):
        errors.append("Escalation requires inspection route and reason")
    if not result.escalation_required and result.escalation_reason:
        errors.append("Non-escalated answer contains an escalation reason")
    if re.search(r"(?:revised|new|corrected)\s+(?:bill|amount)\s*(?:is|:|=)\s*\d", result.tariff_position, re.I):
        errors.append("Service cannot recompute bills")
    return errors
