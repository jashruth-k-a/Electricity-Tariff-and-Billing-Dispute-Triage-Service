# Official corpus and review boundary

The real-model profile uses three packaged primary-source PDFs under
`corpus/official/sources/`. Their URLs, SHA-256 identities and selected page/clause
annotations are recorded in `corpus/official/manifest.json`. Ingestion checks each
annotation against the source page before embedding it with the local semantic model.
The synthetic corpus remains a separate teaching fixture.

| Source | Selected evidence |
|---|---|
| [KERC Combined Tariff Order 2025](https://kerc.karnataka.gov.in/uploads/96731743148968.pdf), Annexure 9, FY2026-27 | LT-1 p.550, LT-3(a) p.552, LT-5 p.555, general provisions pp.539–543 |
| [KERC-hosted Conditions of Supply compilation](https://kerc.karnataka.gov.in/storage/pdf-files/Regulations/ConditionsofSupplyofElectricitywithIandIIAmendments.pdf) | Selected portions of 42.02(a), 42.02(c), 39.01(a)-(b), and meter accuracy provision 27.01 |
| [KERC Consumer Rights Regulations 2022](https://kerc.karnataka.gov.in/uploads/media_to_upload1720004194.pdf) | Complaint handling, grievance referral and precedence provisions, pp.14–18 |

There are 14 curated annotations. PDF page numbers are physical, one-based page numbers;
printed page labels can differ. No reconstructed tariff table or block marked OLD VERSION
is indexed. An older publication date does not itself mean a provision has expired.

The technical review checked the regulator's current regulations index and the listed
Conditions of Supply amendments. The inventory is in `corpus/official/amendment-review.json`.
The selected opening of 39.01(a)-(b) is also repeated in the sixth amendment; later amended
subclauses are excluded. A Supply Code PDF with a DRAFT footer was excluded rather than
treated as operative law.

The manifest's approval records a bounded technical source review. It does **not** record
faculty approval, legal certification or exhaustive coverage of all electricity disputes.
The review cutoff is 2026-11-06, not a statutory expiry date. Requests outside the reviewed
billing period or selected LT scope go to a human officer. Re-review later amendments before
extending that boundary. Faculty confirmation and the presentation/viva remain human actions.

## Mandatory tailoring scenario

LT-1 expressly includes tailoring in part of an occupant's residential house. LT-5 also
mentions tailoring shops. These describe different premises; a business name alone is
insufficient to choose between them. The reference case states that the occupant lives in
the dwelling and partly uses it for tailoring. The agent must retrieve the applicability
and relevant supply modifiers, distinguish an independent shop, and support its position
with exact citations. Unsupported area or load thresholds must be rejected.

`evaluation/official-cases.json` contains 24 source-labelled cases, including that reference
case and explicit out-of-scope referrals. Expected labels are evaluation inputs only; they
are never supplied to the investigator. A dataset's existence is not a passing evaluation.

## Run the official profile

For the measured hosted profile with local embeddings, copy `.env.gemini.example` to
`.env.official`, set `LLM_API_KEY` and replace the example secrets. Use the same Compose
commands below. The configured model must be accessible to the provider account; run the
provider preflight if a model is retired or unavailable. A Gemini key's name in AI Studio is
only a label. The configured cost uses published standard list rates as an estimate, not
an invoice; free-tier usage may have no actual API charge. Pricing and quotas can change.

Gemini Flash-Lite is the completed final-evaluation provider. `.env.groq.example` is an
alternate Groq preset with a passing reference probe. A daily free-tier limit interrupted
the earlier larger Gemini Flash comparison; that is a different model quota. Keep
provider keys matched to their endpoint. The exact model and token usage are retained
in the audit. A new key in the same provider project does not necessarily increase quota.
The base `.env` is also required by the base Compose file; create it from `.env.example`
once if it does not exist. Do not overwrite an already configured environment file.

The hosted path uses a conventional OpenAI-compatible HTTP contract. There is no OpenAI
account or SDK dependency when using these providers. The server attaches exact source
quotes and metadata from model-selected IDs. Embeddings remain local in Ollama.

For an initial hosted setup, create the environment files only if absent, then fill the
provider key and replace example secrets before starting. Existing configured files are
preserved by these commands:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path .env.official)) { Copy-Item .env.gemini.example .env.official }
# Set LLM_API_KEY and replace example INTERNAL_TOKEN/Grafana secrets in .env.official.
docker compose --env-file .env.official -f compose.yaml -f compose.official.yaml up --build -d
docker compose --env-file .env.official -f compose.yaml -f compose.official.yaml run --rm tools evaluate --cases evaluation/official-cases.json --versions v1 v6 --concurrency 1 --output output/official-evaluation.json
```

The overlay bootstraps the local embedding model in Ollama. Initial image/model downloads
require internet and can be slow on a limited connection. Hosted generation needs the
matching provider key. For experimental fully local generation, use `.env.official.example`
instead; it also downloads the configured generation model and needs more CPU/memory.
That CPU profile did not pass the reference probes in this development environment.
Zero API charges do not imply zero electricity or hardware costs. The base Compose profile
remains the separately labelled synthetic infrastructure demo.
