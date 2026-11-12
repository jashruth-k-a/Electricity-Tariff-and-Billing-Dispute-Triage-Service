# Genuine development incidents

## 2026-11-07 - malformed drafts contaminated the evaluation circuit breaker

- Symptom: after several malformed v1 answers, later cases and the final prompt variant
  returned near-immediate fallbacks without model calls.
- Cause: validation errors after a successful, costed HTTP response were counted as provider
  availability failures. A weak prompt could therefore open the shared outage breaker.
- Recovery: malformed model content now fails the current run without retrying the same
  deterministic draft or incrementing the shared availability failure counter. Availability
  errors still use retries/backoff/circuit recovery. A regression test checks that malformed
  content is costed once and neither increments nor opens the shared breaker.
- The contaminated comparison was preserved separately and excluded from quality reporting.
  The corrected adapter passed 50 unit tests; both prompt variants were restarted together.

## 2026-11-07 - model accuracy, availability and daily quota

- Local CPU probes: the first model fabricated unsupported material and later exceeded
  the 600-second deadline. A smaller model repeated a search and then misread an explicit
  household exception. Drafts were rejected or referred; these were failed reference tests.
- Changes: native constrained output, derived citation metadata, shorter instructions,
  duplicate-tool rejection and removal of unverified tariff advice from public escalation
  prose. The model's rejected reasoning remains in the audit.
- Hosted probe: Gemini authenticated successfully. One available model timed out; another
  returned the correct residential position but omitted a separate supply-condition citation.
  The v5 prompt and an explicit verifier policy now require both source kinds for an
  approved-corpus home-business recommendation. The reference then passed in 68.64 seconds.
- Batch failure: the configured Flash model hit HTTP 429. The provider reported a 20-request
  daily free-tier limit and a retry delay of roughly 19 hours. The partial comparison was
  stopped and preserved as quota-interruption evidence, not interpreted as model quality.
- Recovery work: added parsing for Gemini's list-wrapped RetryInfo as well as Retry-After;
  retries that cannot fit the deadline fail safely. Added shared per-model request pacing
  across workers and selected an available Flash-Lite model for the next reference/batch run.
- Accounting correction: preserve raw usage and include reasoning reported in total_tokens
  but omitted from completion_tokens when estimating token cost.
- Browser QA: the in-app browser timed out again. No screenshot-based visual QA is claimed.

## 2026-11-07 - clean startup regression

- Started the built image with fresh Redis/Chroma volumes in the isolated
  `electricity-triage-cleancheck` project on host port 8012.
- All nine public API smoke checks and all 46 then-current unit tests passed.
- Removed the temporary project's containers/network afterward; the main official stack
  and its evaluation were kept separate. Synthetic tests establish engineering behaviour,
  not official model accuracy.

## 2026-11-06 - corpus initialization rejected custom Chroma client

- Symptom: `corpus-init` exited with `Unsupported Chroma API implementation triage.chroma_http.BoundedAPI`; dependent agents never started.
- Confirmation: container traceback and installed Chroma 1.5.9 source showed a fixed allowlist of HTTP API implementations.
- Cause: a subclass was supplied through a configuration field that does not accept custom implementations, while trying to add missing SDK HTTP timeouts.
- Recovery: retained the supported HTTP client and applied a narrow, idempotent request wrapper adding a timeout before constructing the client. Re-ran corpus initialization successfully.
- Prevention: container startup is a required integration check; pinned SDK and a regression test verify the timeout wrapper.

## 2026-11-06 - API host port already allocated

- Symptom: all agents started, but Docker could not bind host port 8000.
- Confirmation: Docker networking error explicitly reported `port is already allocated`.
- Recovery: changed this project's configured API host port to 8011 and recreated its services. Did not stop the unrelated application.
- Prevention: ports are runtime configuration; document the conflict recovery path and check readiness after startup.

## 2026-11-06 - local test runner stalled in Windows socket setup

- Symptom: FastAPI TestClient stalled before issuing a request.
- Confirmation: pytest faulthandler showed the thread inside Windows `socketpair` / asyncio event-loop construction.
- Recovery: execute the authoritative suite in the Linux application container. Local execution depends on host socket/security configuration.
- Prevention: provide a container test command and keep host Python optional.

## 2026-11-06 - keyless stub request rejected by HTTP client

- Symptom: a valid queued run immediately failed with `LocalProtocolError` and opened the circuit after bounded retries.
- Confirmation: durable run audit showed three model failures before any provider response; the demo configuration had no API key.
- Cause: the adapter emitted an empty `Bearer ` header, whose trailing whitespace is rejected by the HTTP stack.
- Recovery: omit Authorization when no key is configured. Added a MockTransport regression test and reran the full real-queue smoke test successfully.
- Related integration issue: the worker entry script initially imported an older installed package instead of a development source mount. Explicit project import path/PYTHONPATH and a rebuilt image resolved that; default deployment uses current built sources.
