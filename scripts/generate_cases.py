"""The fixed teaching benchmark. Official-reference cases need corpus review first."""
import json
from pathlib import Path

base = {"state": "Karnataka", "connection_type": "LT", "billed_category": "domestic",
        "premises_use": "residential", "description": "My dwelling is used exclusively as a home. Is domestic billing correct?",
        "connected_load_kw": 3, "sanctioned_load_kw": 5, "billing_date": "2026-10-01"}
specifications = [
    ("residential-correct", {}, "bill-stands-with-reason", False, True, ["D1"]),
    ("residential-wrong", {"billed_category": "commercial"}, "revision-recommended", False, True, ["D1"]),
    ("shop-correct", {"premises_use": "commercial", "billed_category": "commercial", "description": "My entire premises is a retail shop. Is commercial classification correct?"}, "bill-stands-with-reason", False, True, ["C1"]),
    ("shop-wrong", {"premises_use": "commercial", "description": "My entire premises is a retail shop. I dispute domestic classification."}, "revision-recommended", False, True, ["C1"]),
    ("factory-correct", {"premises_use": "industrial", "billed_category": "industrial", "description": "The whole premises is used for manufacturing goods. Is industrial classification appropriate?"}, "bill-stands-with-reason", False, True, ["I1"]),
    ("factory-wrong", {"premises_use": "industrial", "description": "The whole premises is used for manufacturing goods. Please check the category."}, "revision-recommended", False, True, ["I1"]),
    ("tailoring-reference", {"premises_use": "mixed", "business_activity": "tailoring", "description": "I have a domestic connection. I run a small tailoring shop from one room of the house. Which tariff category should I be billed under?"}, "site-inspection-required", True, True, ["D1", "M1"]),
    ("tailoring-small-area", {"premises_use": "mixed", "business_activity": "tailoring", "business_area_sqm": 8, "total_area_sqm": 100, "description": "I run a tailoring business from one room at home. Does the small area settle my category?"}, "site-inspection-required", True, True, ["D1", "M1"]),
    ("home-office", {"premises_use": "mixed", "business_activity": "office", "description": "Part of my house is an office serving business clients. Please review domestic classification."}, "site-inspection-required", True, True, ["D1", "M1"]),
    ("home-shop-separate-meter", {"premises_use": "mixed", "business_activity": "retail shop", "separate_meter": True, "description": "A shop operates in my house and has a separate meter. Please investigate which category applies."}, "site-inspection-required", True, True, ["D1", "M1"]),
    ("home-salon", {"premises_use": "mixed", "business_activity": "salon", "description": "I operate a salon in one room of my residential dwelling. Can the category stay domestic?"}, "site-inspection-required", True, True, ["D1", "M1"]),
    ("hidden-mixed-description", {"description": "I use one room of my house as a tailoring shop. The connection is domestic. Please check."}, "site-inspection-required", True, True, ["D1", "M1"]),
    ("changed-use", {"billed_category": "commercial", "description": "My premises is exclusively residential. I dispute re-categorisation and have no inspection record."}, "site-inspection-required", True, True, ["D1", "S1"]),
    ("fast-meter", {"description": "My meter seems fast and the recorded usage is unusually high. Please investigate accuracy."}, "site-inspection-required", True, True, ["S2"]),
    ("load-exceeds", {"connected_load_kw": 7, "description": "My connected load is seven kilowatts but only five is sanctioned. I dispute the load violation."}, "site-inspection-required", True, True, ["S3"]),
    ("arrears-dispute", {"description": "My bill contains old arrears that I believe I already paid. Please review the payment records."}, "site-inspection-required", True, True, ["S4"]),
    ("disconnection", {"description": "I dispute disconnection for an outstanding balance and have no notice record."}, "site-inspection-required", True, True, ["S4"]),
    ("out-of-state", {"state": "Kerala"}, "site-inspection-required", True, False, []),
    ("out-of-scope-ht", {"connection_type": "HT"}, "site-inspection-required", True, False, []),
    ("agricultural", {"premises_use": "agricultural", "billed_category": "agricultural", "description": "This connection serves an agricultural irrigation pump. Please check my category."}, "site-inspection-required", True, False, []),
    ("unknown-use", {"premises_use": "unknown", "description": "I am unable to establish what the premises is currently used for. Please investigate."}, "site-inspection-required", True, False, []),
    ("historical-bill", {"billing_date": "2018-01-01"}, "site-inspection-required", True, False, [])
]
cases = [{"id": name, "reference_kind": "synthetic-teaching-fixture", "request": {**base, **changes},
          "expected": {"route": route, "escalation_required": escalation, "verified": verified,
                       "clauses": clauses}} for name, changes, route, escalation, verified, clauses in specifications]
Path("evaluation").mkdir(exist_ok=True)
Path("evaluation/cases.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
