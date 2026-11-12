import asyncio
import time
from unittest.mock import MagicMock

import httpx
import pytest

from triage.config import settings
from triage.provider import Provider


def test_keyless_demo_provider_omits_invalid_empty_bearer(monkeypatch):
    import triage.provider as module
    original_client = httpx.AsyncClient
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "choices": [{"message": {"content": '{"action":"escalate","reason":"No evidence"}'}}]})

    monkeypatch.setattr(module, "settings", lambda: settings().model_copy(
        update={"llm_api_key": "", "llm_backend": "openai-compatible"}))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler), **kwargs))
    redis = MagicMock()
    redis.exists.return_value = False
    monkeypatch.setattr(module, "redis_client", lambda: redis)
    monkeypatch.setattr(module, "event", MagicMock())
    result = asyncio.run(Provider("investigator", "test", time.time() + 20, "v2").complete({"facts": "home"}))
    assert result["action"] == "escalate"
    assert "authorization" not in seen[0].headers


@pytest.mark.parametrize("headers,body", [({"retry-after": "3"}, {}),
    ({}, [{"error": {"details": [{"retryDelay": "3s"}]}}])])
def test_rate_limit_honours_retry_after_without_opening_breaker(monkeypatch, headers, body):
    import triage.provider as module
    original_client = httpx.AsyncClient
    attempts, delays = [], []

    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            return httpx.Response(429, headers=headers, json=body)
        return httpx.Response(200, json={"usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [{"message": {"content": '{"action":"escalate","reason":"No evidence"}'}}]})

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(module, "settings", lambda: settings().model_copy(
        update={"llm_backend": "openai-compatible", "max_retries": 1}))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler), **kwargs))
    redis = MagicMock()
    redis.exists.return_value = False
    monkeypatch.setattr(module, "redis_client", lambda: redis)
    monkeypatch.setattr(module, "event", MagicMock())
    monkeypatch.setattr(module.asyncio, "sleep", sleep)
    result = asyncio.run(Provider("investigator", "rate-test", time.time() + 20, "v2").complete({"facts": "home"}))
    assert result["action"] == "escalate"
    assert delays == [3.]
    assert len(attempts) == 2
    redis.incr.assert_not_called()


def test_reasoning_tokens_in_provider_total_are_costed(monkeypatch):
    import triage.provider as module
    original_client = httpx.AsyncClient
    raw_usage = {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 100}
    def handler(request):
        return httpx.Response(200, json={"usage": raw_usage,
            "choices": [{"message": {"content": '{"action":"escalate","reason":"No evidence"}'}}]})
    monkeypatch.setattr(module, "settings", lambda: settings().model_copy(update={
        "llm_backend": "openai-compatible", "input_price_per_million": 1., "output_price_per_million": 2.}))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler), **kwargs))
    redis = MagicMock()
    redis.exists.return_value = False
    audit = MagicMock()
    monkeypatch.setattr(module, "redis_client", lambda: redis)
    monkeypatch.setattr(module, "event", audit)
    asyncio.run(Provider("investigator", "usage-test", time.time() + 20, "v2").complete({"facts": "home"}))
    record = audit.call_args.kwargs
    assert record["completion_tokens"] == 90
    assert record["provider_usage"] == raw_usage
    assert record["cost"] == 0.00019


def test_malformed_model_does_not_trip_shared_availability_breaker(monkeypatch):
    import triage.provider as module
    original_client = httpx.AsyncClient
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [{"message": {"content": "not JSON"}}]})
    monkeypatch.setattr(module, "settings", lambda: settings().model_copy(update={
        "llm_backend": "openai-compatible", "max_retries": 3, "provider_min_interval_seconds": 0}))
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=httpx.MockTransport(handler), **kwargs))
    redis = MagicMock()
    redis.exists.return_value = False
    monkeypatch.setattr(module, "redis_client", lambda: redis)
    audit = MagicMock()
    monkeypatch.setattr(module, "event", audit)
    with pytest.raises(module.ProviderUnavailable, match="model-response-invalid"):
        asyncio.run(Provider("investigator", "invalid", time.time() + 20, "v2").complete({"facts": "home"}))
    assert len(requests) == 1
    redis.incr.assert_not_called()
    redis.set.assert_not_called()
    assert any(call.args[2] == "model_response" for call in audit.call_args_list)
