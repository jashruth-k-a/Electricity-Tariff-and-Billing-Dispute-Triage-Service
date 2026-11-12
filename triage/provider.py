import asyncio
import hashlib
import json
import random
import time
from pathlib import Path

import httpx
from jsonschema import ValidationError as SchemaValidationError
from opentelemetry.propagate import inject

from triage.config import settings
from triage.guards import check_text
from triage.observability import CALLS, COST, LATENCY, RETRIES, TOKENS, span
from triage.storage import event, redis_client


class ProviderUnavailable(RuntimeError):
    pass


class CircuitOpen(ProviderUnavailable):
    pass


def retry_after(response):
    delays = [1.]
    try:
        delays.append(float(response.headers.get("retry-after", "1")))
    except ValueError:
        pass
    try:
        body = response.json()
        if isinstance(body, list):
            body = body[0] if body else {}
        for detail in body.get("error", {}).get("details", []):
            if "retryDelay" in detail:
                delays.append(float(detail["retryDelay"].removesuffix("s")))
    except (ValueError, TypeError, AttributeError):
        pass
    return max(delays)


def prompt(agent, version):
    text = Path(f"prompts/{version}/{agent}.txt").read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode()).hexdigest()


class Provider:
    def __init__(self, agent, run_id, deadline, version):
        self.agent, self.run_id, self.deadline, self.version = agent, run_id, deadline, version
        cfg = settings()
        self.key = "provider:" + hashlib.sha256(cfg.llm_base_url.encode()).hexdigest()[:16]

    def remaining(self):
        remaining = self.deadline - time.time()
        if remaining <= 0:
            raise ProviderUnavailable("run-deadline-exceeded")
        return min(remaining, settings().call_timeout_seconds)

    async def complete(self, payload):
        cfg = settings()
        system, prompt_hash = prompt(self.agent, self.version)
        artifact_hash = prompt_hash
        # User fields and retrieved text are screened before reaching any model.
        # Candidate drafts use the output policy too.
        if check_text(payload):
            raise ProviderUnavailable("unsafe-content-blocked-before-model")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload, default=str)}]
        if cfg.app_mode == "production":
            contract = ("\nRESPONSE CONTRACT: corpus_search.strategy must be exactly hybrid or vector; "
                        "keyword is not supported. claims MUST be objects shaped "
                        "{statement:string,chunk_ids:[string]}, never plain strings. "
                        "For answer recommendations, citations are objects shaped {chunk_id:string}, "
                        "with IDs chosen from PASSAGES. Omit quote, document, clause, page, source_url "
                        "and tariff_position. The server copies the EXACT complete selected passage and its "
                        "metadata and joins your claim statements into tariff_position. You must still choose "
                        "the supporting passages and reason only from them. This contract overrides output "
                        "format instructions above; all investigation and verification requirements still apply.")
            if self.agent != "verifier":
                messages[0]["content"] += contract
            compact = {**payload, "PASSAGES": [
                {k: p[k] for k in ["chunk_id", "clause", "kind", "text"] if k in p}
                for p in payload.get("PASSAGES", [])]}
            if self.agent == "verifier" and "CANDIDATE" in compact:
                compact["CANDIDATE"] = {k: v for k, v in payload["CANDIDATE"].items()
                                        if k not in {"citations", "tariff_position"}}
                compact["CANDIDATE"]["citations"] = [{"chunk_id": c["chunk_id"]}
                                                        for c in payload["CANDIDATE"].get("citations", [])]
                messages[0]["content"] += ("\nThe server already checked canonical citation text/metadata and "
                    "tariff_position equals joined claims. Judge claim entailment and routing using the cited IDs and PASSAGES.")
            messages[1]["content"] = json.dumps(compact, default=str, separators=(",", ":"))
            prompt_hash = hashlib.sha256(messages[0]["content"].encode()).hexdigest()
        r = redis_client()
        if r.exists(self.key + ":open"):
            raise CircuitOpen("provider-circuit-open")
        # Only one probe is allowed after the cool-down of a previously open breaker.
        if r.exists(self.key + ":recovering"):
            if not r.set(self.key + ":probe", "1", nx=True, ex=cfg.breaker_reset_seconds):
                raise CircuitOpen("provider-half-open-probe-in-progress")
        last = None
        for attempt in range(cfg.max_retries + 1):
            start = time.monotonic()
            accounted = False
            try:
                if cfg.provider_min_interval_seconds:
                    slot = self.key + ":start-slot:" + hashlib.sha256(cfg.llm_model.encode()).hexdigest()[:12]
                    while not r.set(slot, "1", nx=True, px=int(cfg.provider_min_interval_seconds * 1000) or 1):
                        delay = max(.01, r.pttl(slot) / 1000)
                        if delay >= self.deadline - time.time():
                            raise ProviderUnavailable("provider-pacing-would-exceed-run-deadline")
                        await asyncio.sleep(delay)
                    waited = time.monotonic() - start
                    if waited > .05:
                        event(self.run_id, self.agent, "provider_pacing", wait_seconds=waited)
                headers = {"X-Correlation-ID": self.run_id}
                if cfg.llm_api_key:
                    headers["Authorization"] = "Bearer " + cfg.llm_api_key
                inject(headers)
                with span("model." + self.agent, self.run_id, prompt_version=self.version):
                    async with httpx.AsyncClient(timeout=self.remaining()) as client:
                        if cfg.llm_backend == "ollama":
                            from triage.structured import decision_schema
                            schema = decision_schema(payload)
                            contract = (
                                "\nLOCAL RESPONSE CONTRACT: Tool calls use the actions above. When answering, "
                                "omit tariff_position and citation document/clause/page/source_url: the server "
                                "fills them from your claims and retrieved chunk IDs, including the exact quote. "
                                "Before evidence exists only tools are allowed; clause lookup may use only "
                                "retrieved identifiers. After a verification rejection you must search again.")
                            if self.agent == "verifier":
                                contract = "\nReturn only the verification JSON object, with a boolean supported, reasons array and retry_query string."
                            messages[0]["content"] = system + contract
                            # Provenance is checked independently against the index and retained in
                            # tool audits. The local model needs the clause text and stable ID, not
                            # repeated hashes, URLs and version metadata in its limited context.
                            compact = {**payload, "PASSAGES": [
                                {k: p[k] for k in ["chunk_id", "clause", "text"]}
                                for p in payload.get("PASSAGES", [])]}
                            messages[1]["content"] = json.dumps(compact, default=str, separators=(",", ":"))
                            prompt_hash = hashlib.sha256(messages[0]["content"].encode()).hexdigest()
                            url = cfg.llm_base_url.removesuffix("/v1").rstrip("/") + "/api/chat"
                            response = await client.post(url, headers=headers, json={"model": cfg.llm_model,
                                "messages": messages, "stream": False, "format": schema,
                                **({"think": cfg.llm_thinking} if cfg.llm_thinking is not None else {}),
                                "options": {"temperature": 0, "num_predict": cfg.llm_max_output_tokens,
                                            "num_ctx": cfg.llm_context_tokens, "num_thread": cfg.llm_cpu_threads}})
                        else:
                            response = await client.post(cfg.llm_base_url.rstrip("/") + "/chat/completions",
                                                     headers=headers, json={"model": cfg.llm_model,
                                                     "messages": messages, "temperature": 0,
                                                     "max_tokens": cfg.llm_max_output_tokens,
                                                     "response_format": {"type": "json_object"}})
                    response.raise_for_status()
                    body = response.json()
                    if cfg.llm_backend == "ollama":
                        body = {**body, "usage": {"prompt_tokens": body["prompt_eval_count"],
                                                  "completion_tokens": body["eval_count"]},
                                "choices": [{"message": body["message"]}]}
                    usage = body.get("usage")
                    if not usage or "prompt_tokens" not in usage or "completion_tokens" not in usage:
                        raise ValueError("provider-must-report-token-usage")
                    provider_usage = dict(usage)
                    usage = dict(usage)
                    # Some compatibility endpoints exclude thinking from completion_tokens
                    # but include it in total_tokens. Account for all reported output tokens.
                    if isinstance(usage.get("total_tokens"), int):
                        usage["completion_tokens"] = max(usage["completion_tokens"],
                            usage["total_tokens"] - usage["prompt_tokens"])
                    cost = (usage["prompt_tokens"] * cfg.input_price_per_million +
                            usage["completion_tokens"] * cfg.output_price_per_million) / 1_000_000
                    TOKENS.labels(self.agent, "prompt").inc(usage["prompt_tokens"])
                    TOKENS.labels(self.agent, "completion").inc(usage["completion_tokens"])
                    COST.labels(self.agent).inc(cost)
                    content = body["choices"][0]["message"]["content"]
                    # Account even an invalid response before parsing it.
                    event(self.run_id, self.agent, "model_response", attempt=attempt,
                          model=cfg.llm_model, model_revision=cfg.llm_revision, backend=cfg.llm_backend,
                          provider_model=body.get("model"), provider_system_fingerprint=body.get("system_fingerprint"),
                          thinking=cfg.llm_thinking,
                          prompt_version=self.version, prompt_sha256=prompt_hash,
                          prompt_artifact_sha256=artifact_hash,
                          response_schema=schema if cfg.llm_backend == "ollama" else None,
                          prompt_messages=messages, completion=content,
                          prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"],
                          provider_usage=provider_usage,
                          cost=cost, currency=cfg.cost_currency, pricing_label=cfg.pricing_label,
                          input_price_per_million=cfg.input_price_per_million,
                          output_price_per_million=cfg.output_price_per_million,
                          latency_seconds=time.monotonic() - start)
                    accounted = True
                    if check_text(content, output=True):
                        raise ValueError("unsafe-model-output")
                    result = json.loads(content)
                    if not isinstance(result, dict):
                        raise ValueError("model-output-must-be-object")
                    if cfg.llm_backend == "ollama":
                        from jsonschema import validate
                        validate(result, schema)
                    if cfg.app_mode == "production" or cfg.llm_backend == "ollama":
                        from triage.structured import materialize
                        result = materialize(result, payload)
                r.delete(self.key + ":failures", self.key + ":recovering", self.key + ":probe")
                CALLS.labels(self.agent, "model", "success").inc()
                LATENCY.labels(self.agent, "model").observe(time.monotonic() - start)
                return result
            except (httpx.HTTPError, ValueError, KeyError, TypeError, SchemaValidationError, ProviderUnavailable) as exc:
                last = exc
                LATENCY.labels(self.agent, "model").observe(time.monotonic() - start)
                CALLS.labels(self.agent, "model", "failure").inc()
                event(self.run_id, self.agent, "model_failure", attempt=attempt,
                      error=type(exc).__name__, latency_seconds=time.monotonic() - start,
                      http_status=exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None,
                      prompt_version=self.version, prompt_sha256=prompt_hash)
                if accounted and not isinstance(exc, httpx.HTTPError):
                    # A completed, costed response with invalid model content is not an
                    # availability outage. Do not poison other runs/variants or repeat a
                    # deterministic malformed draft without corrective evidence.
                    r.delete(self.key + ":failures", self.key + ":recovering", self.key + ":probe")
                    raise ProviderUnavailable("model-response-invalid") from exc
                throttled = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429
                failures = 0 if throttled else r.incr(self.key + ":failures")
                if not throttled:
                    r.expire(self.key + ":failures", cfg.breaker_reset_seconds * 2)
                if not throttled and (failures >= cfg.breaker_threshold or r.exists(self.key + ":recovering")):
                    r.set(self.key + ":open", "1", ex=cfg.breaker_reset_seconds)
                    r.set(self.key + ":recovering", "1", ex=cfg.breaker_reset_seconds * 10)
                    event(self.run_id, self.agent, "circuit_opened", cooldown=cfg.breaker_reset_seconds)
                    raise CircuitOpen("provider-circuit-open") from exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 \
                        and exc.response.status_code != 429:
                    break
                if attempt < cfg.max_retries:
                    RETRIES.labels(self.agent).inc()
                    delay = .25 * 2 ** attempt + random.random() * .1
                    if throttled:
                        delay = max(delay, retry_after(exc.response))
                    if delay >= self.deadline - time.time():
                        raise ProviderUnavailable("retry-would-exceed-run-deadline") from exc
                    await asyncio.sleep(delay)
        raise ProviderUnavailable("provider-call-failed") from last
