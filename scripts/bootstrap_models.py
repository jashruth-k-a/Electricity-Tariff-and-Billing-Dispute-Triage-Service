"""Populate the local Ollama service once; keep identifiers in runtime configuration."""
import json
import os

import httpx

base = os.environ["EMBEDDING_BASE_URL"].removesuffix("/v1").rstrip("/")
local_pairs = [("EMBEDDING_MODEL", "EMBEDDING_REVISION")]
if os.getenv("LLM_BACKEND") == "ollama":
    local_pairs.append(("LLM_MODEL", "LLM_REVISION"))
models = {os.environ[model_key] for model_key, _ in local_pairs}
with httpx.Client(timeout=1800) as client:
    response = client.get(base + "/api/tags")
    response.raise_for_status()
    installed = {m["name"] for m in response.json()["models"]}
    for model in models:
        canonical = model if ":" in model else model + ":latest"
        if canonical not in installed:
            response = client.post(base + "/api/pull", json={"name": model, "stream": False})
            response.raise_for_status()
        print(json.dumps({"model": model, "ready": True}))
    response = client.get(base + "/api/tags")
    response.raise_for_status()
    actual = {model["name"]: model["digest"] for model in response.json()["models"]}
    for model_key, revision_key in local_pairs:
        model = os.environ[model_key]
        canonical = model if ":" in model else model + ":latest"
        expected = os.getenv(revision_key, "")
        if expected and actual.get(canonical, "").removeprefix("sha256:") != expected.removeprefix("sha256:"):
            raise ValueError("Local model revision mismatch: " + model_key)
