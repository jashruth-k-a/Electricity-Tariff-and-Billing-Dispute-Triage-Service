"""Record downloaded primary-source hashes and locations without approving legal currency."""
import hashlib
import json
from pathlib import Path

documents = [
    {"id": "KERC-TARIFF-2025", "title": "KERC Combined Tariff Order 2025, All ESCOMs, Annexure 9",
     "path": "data/raw/tariff.pdf", "source_url": "https://kerc.karnataka.gov.in/uploads/96731743148968.pdf",
     "version": "2025-order-fy2026-27-schedule-review-pending", "kind": "tariff",
     "effective_from": "2026-04-01", "effective_to": "2027-03-31",
     "pages": list(range(539, 571)),
     "clause_overrides": {"550": "Annexure-9 / LT-1", "555": "Annexure-9 / LT-5"}},
    {"id": "KERC-COS-2013", "title": "Conditions of Supply with first and second amendments (2013 compilation)",
     "path": "data/raw/supply.pdf",
     "source_url": "https://www.bescom.co.in/bescom/assets/pdfs/ConditionsofSupplyofElectricitywithIandIIAmendments.pdf",
     "version": "2013-compilation-current-amendments-unverified", "kind": "supply",
     "effective_from": "2006-06-17", "effective_to": "2013-06-09",
     "pages": [5, 6, 7, 8, 9, 10, 11, 12, 75, 76, 77, 78, 79, 80, 81, 87, 88, 89],
     "clause_overrides": {"79": "42.02(a)", "80": "42.02(b)-(c)", "87": "42.06(e) / 42.07"}}
]
for doc in documents:
    doc["sha256"] = hashlib.sha256(Path(doc["path"]).read_bytes()).hexdigest()
manifest = {"state": "Karnataka", "status": "pending-review", "version": "kerc-research-2026-11-06",
            "reviewed_by": "", "reviewed_on": "", "documents": documents,
            "review_notes": "Tariff source obtained from regulator. Supply compilation is historical; obtain and reconcile later amendments before approval. Faculty must confirm reference case. Selected pages define project scope, not the full state regulatory corpus."}
Path("corpus/official/research-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
