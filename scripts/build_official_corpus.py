"""Build source-validated annotations and a bounded, reviewed official corpus manifest.

This records a technical source review, not faculty sign-off or a binding legal opinion.
No reconstructed tables, superseded OLD VERSION blocks or draft regulations are indexed.
"""
import hashlib
import json
import shutil
from pathlib import Path

directory = Path("corpus/official/annotations")
directory.mkdir(parents=True, exist_ok=True)
source_directory = Path("corpus/official/sources")
source_directory.mkdir(exist_ok=True)
for name, source_path in [("tariff.pdf", "data/raw/tariff.pdf"),
                          ("conditions.pdf", "data/research/cos-02.pdf"),
                          ("consumer-rights.pdf", "data/research/consumer-rights-2022.pdf")]:
    shutil.copyfile(source_path, source_directory / name)


def pages(path):
    return {p["page"]: " ".join(p["text"].split()) for p in json.loads(Path(path).read_text(encoding="utf-8"))}


def passage(source, page, clause, start, end, topic):
    text = source[page]
    start_index = text.index(start)
    end_index = text.index(end, start_index + len(start)) if end else len(text)
    return {"page": page, "clause": clause, "topic": topic, "text": text[start_index:end_index].strip()}


tariff = pages("data/research/tariff-selected.pages.json")
conditions = pages("data/research/cos-02.pages.json")
rights = pages("data/research/consumer-rights-2022.pages.json")
annotations = {
    "tariff": [
        passage(tariff, 550, "Annexure-9 / LT-1", "Applicable to lighting/combined", "Also applicable", "domestic-mixed-use"),
        passage(tariff, 552, "Annexure-9 / LT-3(a)", "Applicable to Commercial", "TARIFF SCHEDULE LT-3(a) (Applicable", "commercial"),
        passage(tariff, 555, "Annexure-9 / LT-5", "Applicable to Heating", None, "industrial-tailoring"),
        passage(tariff, 543, "Annexure-9 / General-29", "29. Conditions of Supply", None, "precedence"),
        passage(tariff, 541, "Annexure-9 / General-17", "17. For the purpose of billing", "18. The bill amount", "load"),
        passage(tariff, 539, "Annexure-9 / General-9", "9. LT power supply", None, "connection-scope"),
    ],
    "conditions": [
        passage(conditions, 79, "42.02(a)", "42.02 MISUSE OF ELECTRICITY", "OLD VERSION", "mixed-changed-use"),
        passage(conditions, 80, "42.02(c)", "(c) If at any time", "42.03", "changed-use"),
        passage(conditions, 74, "39.01(a)-(b)", "39.00 CONVERSION", None, "changed-use-procedure"),
        passage(conditions, 57, "27.01 / accuracy-dispute", "27.00 CORRECTNESS OF METER", "Amended version", "meter-accuracy"),
    ],
    "rights": [
        passage(rights, 15, "7 / complaints-handling", "7. Procedure for Complaints Handling", "8. In the event", "complaints"),
        passage(rights, 16, "10 / grievance-redressal", "10. Grievance redressal mechanism", "11. General Provisions", "grievance"),
        passage(rights, 18, "11(9) / precedence", "(9) Any issue", "(10) Issue", "precedence"),
        passage(rights, 14, "6(11)(vii)-(xi)", "(vii) Meter complaints", "(xii) Payment", "meter-bill-complaints"),
    ],
}
for name, values in annotations.items():
    (directory / f"{name}.json").write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

definitions = [
    ("KERC-TARIFF-2025", "KERC Combined Tariff Order 2025 / Annexure 9 / FY2026-27", "corpus/official/sources/tariff.pdf",
     "https://kerc.karnataka.gov.in/uploads/96731743148968.pdf", "tariff", "tariff", "2026-04-01"),
    ("KERC-COS-CURRENT-CLAUSES", "KERC Conditions of Supply / selected current clauses, reconciled against amendments", "corpus/official/sources/conditions.pdf",
     "https://kerc.karnataka.gov.in/storage/pdf-files/Regulations/ConditionsofSupplyofElectricitywithIandIIAmendments.pdf", "supply", "conditions", "2010-07-22"),
    ("KERC-CONSUMER-RIGHTS-2022", "KERC Rights of Consumers, Standards of Performance and allied matters Regulations 2022", "corpus/official/sources/consumer-rights.pdf",
     "https://kerc.karnataka.gov.in/uploads/media_to_upload1720004194.pdf", "supply", "rights", "2022-10-14"),
]
documents = []
for identifier, title, path, url, kind, name, effective_from in definitions:
    documents.append({"id": identifier, "title": title, "path": path, "source_url": url,
        "kind": kind, "version": "source-reviewed-2026-11-06", "effective_from": effective_from,
        "effective_to": "2026-11-06", "coverage_note": "End date is the corpus review cutoff, not statutory expiry.",
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "annotations_path": f"corpus/official/annotations/{name}.json"})

manifest = {"state": "Karnataka", "status": "approved", "version": "kerc-lt-reviewed-2026-11-06-v2",
    "reviewed_by": "Codex technical review of primary sources; faculty sign-off not represented",
    "reviewed_on": "2026-11-06", "review_valid_through": "2026-11-06", "documents": documents,
    "scope": "LT residential, commercial and industrial category positions on stated facts; meter/load/bill disputes routed for human verification. No penalties, bill sums, transfer-of-ownership liability, bulk/multi-unit metering or HT/EHT adjudication.",
    "review_basis": {"current_index": "https://kerc.karnataka.gov.in/27/regulations/en",
        "current_index_sha256": hashlib.sha256(Path("data/research/regulations.html").read_bytes()).hexdigest(),
        "tariff_index": "https://kerc.karnataka.gov.in/96/tariff-order/en",
        "draft_index": "https://kerc.karnataka.gov.in/28/draft-regulations/en",
        "amendment_inventory": "corpus/official/amendment-review.json"}}
Path("corpus/official/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

inventory = json.loads(Path("data/research/cos-inventory.json").read_text())
review = []
for item in inventory:
    path = Path("data/research") / item["file"]
    values_path = path.with_suffix(".pages.json")
    values = json.loads(values_path.read_text()) if values_path.exists() else []
    text = " ".join(p["text"] for p in values)
    review.append({**item, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "indexed": item["file"] == "cos-02.pdf", "mentions_42_02": "42.02" in text,
        "mentions_27_01": "27.01" in text,
        "review_note": "2017 amendment repeats unchanged 39.01 opening and (a)-(b); other clauses in that amended table are not indexed." if item["file"] == "cos-08.pdf" else
                       "Scanned Supreme Court compliance direction visually inspected; contains no operative category rule. Ownership/arrears liability is out of scope." if item["file"] == "cos-14.pdf" else
                       "Source inspected for effects on selected clauses; unselected and old-version text is excluded from the active index."})
Path("corpus/official/amendment-review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"documents": len(documents), "exact_passages": sum(map(len, annotations.values())),
                  "manifest": "corpus/official/manifest.json", "faculty_confirmation": "not claimed"}))
