"""Fixed source-labelled cases for the bounded official Karnataka corpus."""
import json
from pathlib import Path

base = {"state": "Karnataka", "connection_type": "LT", "billed_category": "domestic",
        "premises_use": "residential", "connected_load_kw": 3, "sanctioned_load_kw": 5,
        "billing_date": "2026-10-01"}
lt1, lt3, lt5 = "Annexure-9 / LT-1", "Annexure-9 / LT-3(a)", "Annexure-9 / LT-5"
misuse = "42.02(a)"
specs = [
    ("residential-correct", {}, "My connection serves only my residential dwelling and household appliances. Is domestic classification appropriate?", "bill-stands-with-reason", False, True, [lt1]),
    ("residential-misclassified", {"billed_category": "commercial"}, "The premises has always been exclusively my residential dwelling, with no business activity or change of use. It was recorded as commercial in error. Please recommend the applicable category for officer review.", "revision-recommended", False, True, [lt1]),
    ("tailoring-reference", {"premises_use": "mixed", "business_activity": "tailoring"}, "I have a domestic connection. I run a small tailoring shop from one room of the house which I occupy as my residence. Which tariff category should I be billed under?", "bill-stands-with-reason", False, True, [lt1, misuse]),
    ("tailoring-independent-shop", {"premises_use": "industrial", "business_activity": "tailoring shop"}, "This is a standalone tailoring shop used exclusively for tailoring, not an occupant's residence. It has been billed as domestic. Please recommend the applicable tariff position.", "revision-recommended", False, True, [lt5]),
    ("beauty-parlour-at-home", {"premises_use": "mixed", "business_activity": "beauty parlour"}, "I occupy this house as my residence and use one portion as my beauty parlour. My connection is domestic. Please check the residential applicability exception and any modifying provision.", "bill-stands-with-reason", False, True, [lt1, misuse]),
    ("beauty-parlour-independent", {"premises_use": "commercial", "billed_category": "commercial"}, "The entire independent premises is a beauty parlour, with no residential use. Is commercial classification appropriate?", "bill-stands-with-reason", False, True, [lt3]),
    ("legal-consultancy-at-home", {"premises_use": "mixed", "business_activity": "legal consultancy"}, "I live in this house and use one portion for my legal consultancy practice. It is not a separate office premises. Is the domestic category applicable to this listed home activity?", "bill-stands-with-reason", False, True, [lt1, misuse]),
    ("medical-consultancy-at-home", {"premises_use": "mixed", "business_activity": "medical consultancy"}, "I occupy the house as my home and use one portion for medical consultancy. There is no independent clinic establishment. Please review my domestic classification against the listed residential activities.", "bill-stands-with-reason", False, True, [lt1, misuse]),
    ("private-clinic-independent", {"premises_use": "commercial", "billed_category": "commercial"}, "This independent premises is exclusively a private clinic and diagnostic centre, with no dwelling. Please check its commercial classification.", "bill-stands-with-reason", False, True, [lt3]),
    ("job-typing-at-home", {"premises_use": "mixed", "business_activity": "job typing"}, "I live in my residential house and use a portion for job typing. Please check the domestic applicability and any modifying provision.", "bill-stands-with-reason", False, True, [lt1, misuse]),
    ("paying-guests-shared-home", {"premises_use": "mixed", "business_activity": "paying guests"}, "I occupy the house as my residence and host paying guests in a portion of the same house. It is not independent exclusive paying-guest accommodation. Please check domestic classification.", "bill-stands-with-reason", False, True, [lt1, misuse]),
    ("paying-guests-exclusive-premises", {"premises_use": "commercial", "billed_category": "commercial"}, "The independent exclusive premises is entirely paying-guest accommodation and is not occupied as the operator's home. Please check commercial applicability.", "bill-stands-with-reason", False, True, [lt3]),
    ("bakery-manufacturing", {"premises_use": "industrial", "billed_category": "industrial"}, "The independent premises is a bakery-product manufacturing unit, not a retail bakery shop or residence. Is industrial classification supported?", "bill-stands-with-reason", False, True, [lt5]),
    ("bakery-retail", {"premises_use": "commercial", "billed_category": "commercial"}, "This premises is exclusively a retail bakery shop. No manufacturing occurs here and there is no residential use. Please check commercial applicability.", "bill-stands-with-reason", False, True, [lt3]),
    ("load-discrepancy", {"connected_load_kw": 7}, "The utility alleges that connected load exceeds the sanctioned five kilowatts. I dispute the measured connected load and no physical inspection report is available. Can tariff text alone establish the physical load?", "site-inspection-required", True, True, ["Annexure-9 / General-17"]),
    ("meter-accuracy", {}, "I dispute the meter's accuracy because it seems to run fast. There is no meter test result. Please recommend the investigation route rather than assuming the meter is faulty.", "site-inspection-required", True, True, ["6(11)(vii)-(xi)"]),
    ("unsettled-mixed-workshop", {"premises_use": "mixed", "business_activity": "automobile repair workshop"}, "I live in one part of the premises and operate an automobile repair workshop in another part on the same connection. The separate business load and metering arrangements are unknown. Please investigate rather than assume this is a listed domestic exception.", "site-inspection-required", True, True, [lt1, misuse]),
    ("unknown-premises-facts", {"premises_use": "unknown"}, "I cannot establish what the premises is currently used for, and no inspection or occupation record is available. Please refer the tariff question for investigation.", "site-inspection-required", True, False, []),
    ("outside-state", {"state": "Kerala"}, "My exclusively residential dwelling has a domestic connection. Please check the category under this state's rules.", "site-inspection-required", True, False, []),
    ("outside-ht", {"connection_type": "HT"}, "Please investigate the category of this high-tension connection serving my premises.", "site-inspection-required", True, False, []),
    ("outside-agriculture", {"premises_use": "agricultural", "billed_category": "agricultural"}, "This connection is for an agricultural irrigation pump. Please investigate the agricultural tariff.", "site-inspection-required", True, False, []),
    ("outside-reviewed-period", {"billing_date": "2018-01-01"}, "Please determine the category for this historical residential bill from January 2018.", "site-inspection-required", True, False, []),
    ("arrears-documentary-dispute", {}, "I dispute arrears on my domestic account. The payment ledger and previous bills have not been reconciled. Please route this as an arrears complaint for officer review, without deciding the amount or liability from tariff text alone.", "site-inspection-required", True, True, ["7 / complaints-handling"]),
    ("disconnection-documentary-dispute", {}, "I dispute disconnection of my domestic connection. The notice, account ledger and service records are unavailable. Please route the disconnection grievance for officer review without declaring the disconnection lawful or unlawful.", "site-inspection-required", True, True, ["10 / grievance-redressal"]),
]
cases = [{"id": identifier, "reference_kind": "official-primary-source-technical-reference",
          "request": {**base, **changes, "description": description},
          "expected": {"route": route, "escalation_required": escalate, "verified": verified, "clauses": clauses},
          "reference_note": "Supporting passages are exact source-validated annotations in corpus/official/annotations. Faculty confirmation remains a presentation-stage deliverable."}
         for identifier, changes, description, route, escalate, verified, clauses in specs]
issue_types = {"meter-accuracy": "meter-accuracy", "load-discrepancy": "load-violation",
               "arrears-documentary-dispute": "arrears", "disconnection-documentary-dispute": "disconnection"}
for case in cases:
    if case["expected"]["verified"]:
        case["expected"]["issue_type"] = issue_types.get(case["id"], "tariff-category")
Path("evaluation/official-cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
print(f"Wrote {len(cases)} official-reference cases")
