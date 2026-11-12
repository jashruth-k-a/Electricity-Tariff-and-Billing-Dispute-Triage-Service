"""Chroma's stock HTTP client disables timeouts; enforce one for every request."""
from functools import wraps

from chromadb.api.fastapi import FastAPI

from triage.config import settings


def install_timeout():
    # Chroma 1.5.9 rejects custom HTTP API classes and offers no timeout setting.
    # Keep the supported class and narrowly wrap its request boundary, including init.
    if getattr(FastAPI._make_request, "_triage_bounded", False) is True:
        return
    original = FastAPI._make_request

    @wraps(original)
    def bounded(self, method, path, **kwargs):
        kwargs["timeout"] = settings().call_timeout_seconds
        return original(self, method, path, **kwargs)

    bounded._triage_bounded = True
    FastAPI._make_request = bounded
