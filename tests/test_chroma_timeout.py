from unittest.mock import MagicMock

from triage.chroma_http import install_timeout


def test_sdk_timeout_covers_initialization_and_queries(monkeypatch):
    from chromadb.api.fastapi import FastAPI
    original = MagicMock(return_value={"ok": True})
    monkeypatch.setattr(FastAPI, "_make_request", original)
    install_timeout()
    wrapped = FastAPI._make_request
    install_timeout()
    assert FastAPI._make_request is wrapped
    wrapped(object(), "get", "/heartbeat")
    assert original.call_args.kwargs["timeout"] > 0
