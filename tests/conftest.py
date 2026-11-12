import json
from pathlib import Path

import pytest


@pytest.fixture
def request_data():
    return json.loads(Path("evaluation/cases.json").read_text())[0]["request"].copy()


@pytest.fixture
def evidence():
    values = json.loads(Path("corpus/demo/tariff.json").read_text())
    return [{"chunk_id": p["clause"], "document": "DEMO-TARIFF", "source_url": "", **p} for p in values]


@pytest.fixture
def candidate(evidence):
    passage = evidence[0]
    statement = "Exclusive residential use supports domestic classification."
    return {"route": "bill-stands-with-reason", "tariff_position": statement,
            "claims": [{"statement": statement, "chunk_ids": [passage["chunk_id"]]}],
            "citations": [{"chunk_id": passage["chunk_id"], "quote": passage["text"],
                           **{k: passage[k] for k in ["document", "clause", "page", "source_url"]}}],
            "escalation_required": False, "escalation_reason": "", "issue_type": "tariff-category"}
