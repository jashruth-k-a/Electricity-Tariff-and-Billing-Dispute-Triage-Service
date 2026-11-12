from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_mode: str = "demo"
    redis_url: str
    chroma_host: str
    chroma_port: int = 8000
    verifier_url: str
    llm_base_url: str
    llm_model: str
    llm_api_key: str = ""
    llm_backend: Literal["openai-compatible", "ollama"] = "openai-compatible"
    llm_revision: str = ""
    llm_max_output_tokens: int = 1400
    llm_context_tokens: int = 4096
    llm_cpu_threads: int = 4
    llm_thinking: bool | None = None
    provider_min_interval_seconds: float = Field(default=0, ge=0, le=120)
    embedding_base_url: str = ""
    embedding_document_prefix: str = ""
    embedding_query_prefix: str = ""
    internal_token: str
    embedding_backend: str = "hash"
    embedding_model: str = ""
    embedding_revision: str = ""
    corpus_manifest: str = "corpus/demo/manifest.json"
    data_dir: str = "data"
    prompt_version: str = "v2"
    max_steps: int = 12
    max_tool_calls: int = 8
    max_run_seconds: int = 90
    call_timeout_seconds: float = 12
    max_retries: int = 2
    breaker_threshold: int = 3
    breaker_reset_seconds: int = 30
    rate_limit_per_minute: int = 12
    cache_enabled: bool = True
    cache_ttl_seconds: int = 900
    input_price_per_million: float = 0
    output_price_per_million: float = 0
    cost_currency: str = "USD"
    pricing_label: str = "unpriced"
    otel_exporter_otlp_endpoint: str = ""
    service_name: str = "triage"
    metrics_port: int = 9101
    stub_delay_seconds: float = 0.3
    stub_admin_enabled: bool = False
    api_client_keys: str = ""
    quality_sample_every: int = 5
    slo_p95_seconds: int = 60

    @model_validator(mode="after")
    def validate_mode(self):
        if self.app_mode not in {"demo", "production"}:
            raise ValueError("APP_MODE must be demo or production")
        if len(self.internal_token) < 16:
            raise ValueError("INTERNAL_TOKEN must contain at least 16 characters")
        if self.prompt_version not in {"v1", "v2", "v3", "v4", "v5", "v6"}:
            raise ValueError("unknown prompt version")
        if self.app_mode == "production":
            if self.embedding_backend not in {"sentence-transformers", "ollama"} or not self.embedding_model:
                raise ValueError("production requires local semantic embeddings")
            if self.embedding_backend == "ollama" and not self.embedding_base_url:
                raise ValueError("Ollama embeddings require EMBEDDING_BASE_URL")
            if self.llm_backend != "ollama" and not self.llm_api_key:
                raise ValueError("Hosted provider mode requires a provider key")
            if self.pricing_label == "unpriced":
                raise ValueError("production requires an explicit pricing label")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
