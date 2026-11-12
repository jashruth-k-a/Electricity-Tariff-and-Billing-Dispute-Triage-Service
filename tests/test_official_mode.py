import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from triage.config import Settings
from triage.corpus import OllamaEmbeddings
from triage.verification import deterministic_checks


def configuration(**overrides):
    return Settings(_env_file=None, redis_url="", chroma_host="", verifier_url="", llm_base_url="",
                    llm_model="fixture", internal_token="test-only-internal-token", **overrides)


def test_local_real_model_does_not_require_a_paid_provider_key():
    cfg = configuration(app_mode="production", llm_backend="ollama", llm_api_key="",
                        embedding_backend="ollama", embedding_base_url="local", embedding_model="fixture",
                        pricing_label="local-zero-api-charge")
    assert cfg.app_mode == "production"


def test_hosted_provider_still_requires_key():
    with pytest.raises(ValidationError, match="Hosted provider"):
        configuration(app_mode="production", llm_backend="openai-compatible", llm_api_key="",
                      embedding_backend="sentence-transformers", embedding_model="fixture",
                      pricing_label="priced")


def test_ollama_embeddings_preserve_order_and_distinguish_query_prefix(monkeypatch):
    import triage.corpus as module
    cfg = configuration(embedding_backend="ollama", embedding_model="fixture", embedding_base_url="local",
                        embedding_document_prefix="document:", embedding_query_prefix="query:")
    monkeypatch.setattr(module, "settings", lambda: cfg)
    response = MagicMock()
    response.json.return_value = {"data": [{"index": 1, "embedding": [0., 1.]},
                                           {"index": 0, "embedding": [1., 0.]}]}
    post = MagicMock(return_value=response)
    monkeypatch.setattr("httpx.post", post)
    embeddings = OllamaEmbeddings()
    assert embeddings.embed_documents(["first", "second"]) == [[1., 0.], [0., 1.]]
    assert post.call_args.kwargs["json"]["input"] == ["document: first", "document: second"]
    embeddings.embed_query("question")
    assert post.call_args.kwargs["json"]["input"] == ["query: question"]


def test_express_domestic_exception_can_settle_home_business(request_data):
    annotation = json.loads(Path("corpus/official/annotations/tariff.json").read_text(encoding="utf-8"))[0]
    passage = {**annotation, "chunk_id": "source", "document": "official", "source_url": ""}
    request_data.update(premises_use="mixed", business_activity="tailoring",
                        description="I occupy the house and run tailoring from a portion of it.")
    statement = "On the stated facts the express residential applicability includes home tailoring."
    result = {"route": "bill-stands-with-reason", "tariff_position": statement,
              "claims": [{"statement": statement, "chunk_ids": ["source"]}],
              "citations": [{"chunk_id": "source", "quote": annotation["text"],
                             "document": "official", "source_url": "", "page": annotation["page"],
                             "clause": annotation["clause"]}],
              "escalation_required": False, "escalation_reason": "", "issue_type": "tariff-category"}
    assert deterministic_checks(result, [passage], request_data) == []
    # Real approved corpus records must also demonstrate the separate supply modifier.
    passage.update(kind="tariff", corpus_status="approved")
    assert any("both tariff applicability" in error for error in
               deterministic_checks(result, [passage], request_data))
