# Requirement-to-implementation map

Implemented paths below are code capabilities, not blanket claims of assessed compliance.
Default runtime/evaluation uses labelled synthetic fixtures. Official corpus confirmation,
regulatory accuracy and faculty confirmation remain separate gates. The
official profile now packages three source PDFs, 14 annotations and 24 labelled cases;
the real-model comparison matched 15/24 strict references, up from 6/24. All 51 unit tests
and nine official public smoke checks passed. Model misses are documented, not hidden.

| ID | Implementation / evidence | Qualification |
|---|---|---|
| F1 | FastAPI POST /v1/disputes, OpenAPI, contracts | Async 202 + status resource |
| F2 | Pydantic boundary, custom validation handler, Redis quarantine | Rejected records never enter RQ |
| F3 | Investigator extracts request fields and issue type | Real evaluation includes all five types; arrears/disconnection cases still failed the strict reference |
| F4 | Agent-selected category search then modifier search/lookup | Hybrid LangChain retrieval over Chroma |
| F5 | Exact citations, claim links, provenance and semantic verifier | Mandatory reference passed; final model matched 15/24 strict cases |
| F6 | Three route enums and advisory basis | No bill changes |
| F7 | Unsupported/conflicting/out-of-scope -> human | Genuine unresolved mixed use judged by verifier; explicit official exceptions may settle a case |
| F8 | Health, metrics, structured JSON audit/logs | Full dependency stack in Compose |
| A1 | LangGraph, three LangChain StructuredTools, step/tool/time budgets | Retrieval is a chosen action |
| A2 | Investigator worker and independent verifier service/graph | Defined authenticated handoff and failure behaviour |
| A3 | Verify before return; retry query then search or escalate | Maximum two candidate verification attempts |
| A4 | FastAPI -> Redis RQ -> workers; polling | Queue included in end-to-end timing |
| A5 | Provider timeouts/backoff/circuit breaker, bounded tool timeout/retry, fallback | Failure drill saved under output/ |
| A6 | Per-agent steps/calls/outcomes/latency/retries, uptime metrics and Grafana | Workers use multiprocess Prometheus registry |
| A7 | Stateless competing RQ worker replicas | Measured controlled Locust comparison |
| A8 | Web intake/result/quotes/referral/audit/feedback | Static assets served by API |
| L1 | LangChain Runnable/splitter, local embeddings, Chroma, hybrid ranking | Hash fixture default; official overlay uses local Ollama semantic embeddings |
| L2 | Versioned prompts v1–v6, resolved/artifact hashes with model responses | v1/v2 synthetic and v1/v6 official comparisons use fixed respective cases |
| L3 | Separate 22-case synthetic and 24-case official sets, CLI evaluator, four metrics, checkpoints | Completed real comparison in official-evaluation.md; faculty review still required |
| L4 | All text screening, tool allowlist, output authority policy, toxicity patterns | Baseline regex coverage; not comprehensive adversarial defence |
| L5 | Per-response usage/prices/cost, per-run and per-100 evaluation | Real prices/usage require provider configuration; unknown failed-call cost disclosed |
| L6 | Persisted feedback, aggregates, sampled live audit quality proxies | Trends in web/Grafana |
| D1 | Schemas, cross-field validation, OpenAPI and contract docs | Extra fields and nonfinite loads rejected |
| D2 | CLI idempotent PDF pipeline, hash/version/freshness/throughput | OCR cases fail visibly for review |
| D3 | API, worker, verifier, Redis, Chroma, initializer, stub and monitoring | Single Compose startup; boundaries documented |
| D4 | Runtime settings, ignored .env, .env.example | Source-document URLs are provenance, not deployment secrets |
| D5 | Correlation ID/W3C context, OTel->Jaeger, Prometheus/Grafana/cAdvisor | Audit reconstructs each run; Jaeger storage is ephemeral in this course deployment |
| D6 | Declared p95 SLO, delayed stub, Locust full-run latency/throughput | Measurements include verified fraction and bottleneck analysis |
| D7 | Client rate limit, fingerprinted verified-result cache | Controlled cache experiment; cache preserves original audit |
| D8 | Two principal failure runbooks and real development incident log | Startup failures recorded honestly |
