# Token-cost assumptions

Checked 2026-11-07 against the providers' primary pricing pages. These are configured
standard list-rate estimates in USD, not invoices or a claim that free-tier usage was charged.

| Preset | Model | Input / 1M tokens | Output / 1M tokens | Source |
|---|---|---:|---:|---|
| Gemini | gemini-3.1-flash-lite | 0.25 | 1.50 | [Google pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| Groq | qwen/qwen3.8-27b | 0.80 | 4.00 | [Groq models/pricing](https://console.groq.com/docs/models) |
| Synthetic fixture or local Ollama | Configured local model | 0 API charge | 0 API charge | Local hardware/electricity are outside this token-price estimate |

The per-response estimate is `(input_tokens * input_rate + output_tokens * output_rate) / 1_000_000`.
Per-100-run evaluation cost is the mean recorded run cost multiplied by 100, for the same
case mix. It includes costed invalid responses. Failed calls without usage remain unknown.
The adapter preserves raw provider usage and includes reported thinking output; provider-side
cache discounts are not inferred unless explicitly reflected in the configured pricing model.

Each response records its rates, currency and pricing label, so a later rate change does not
rewrite historical measurements. Recheck rates and quotas before changing providers or plans.
Free-tier request and token limits can prevent a full benchmark even when monetary cost is zero.
The controlled load tests use a delayed stub to measure the service independently of those limits.
