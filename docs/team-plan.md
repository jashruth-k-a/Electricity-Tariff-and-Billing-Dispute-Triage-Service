# Three-member ownership

| Member | Owns | Main files | Evidence to explain at viva |
|---|---|---|---|
| Jashruth | Agent design and verification, the most technically difficult workstream. Own the investigator and verifier graphs, tool selection, prompts, citation checks, bounded re-search, and provider failure handling. | `triage/agents.py`, `triage/verifier.py`, `triage/verification.py`, `triage/provider.py`, `prompts/` | Walk through the tailoring case from retrieval to verification and show how an unsupported answer is caught. |
| Harshitha | Corpus, retrieval, and evaluation. Own source selection and amendment review, PDF annotations, local embeddings, the Chroma index, reference labels, and the quality and cost comparison. Coordinate faculty corpus confirmation. | `corpus/`, `triage/corpus.py`, `triage/evaluation.py`, `evaluation/`, `docs/official-evaluation.md` | Show the two tailoring provisions and explain the before-and-after results and the nine reference misses. |
| Hamsa | API, deployment, and operations. Own intake validation and quarantine, the queue, officer UI, Docker Compose, dashboards, tracing, and load and scaling experiments. | `triage/api.py`, `triage/worker.py`, `web/`, `compose.yaml`, `monitoring/`, `loadtests/` | Start the system, show quarantine and tracing, and explain the measured p95, scaling, and cache results. |

Each member owns one third of the team deliverables and takes roughly one third of the
demo and viva preparation. Jashruth covers agent design and verification in the report.
Harshitha covers corpus scope, retrieval, and evaluation. Hamsa covers deployment,
observability, and performance. All three rehearse the same reference case, review the
final report, and check the repository before submission.
