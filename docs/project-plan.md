# Project plan and three-member ownership

Scope: assist an officer with Karnataka LT tariff-category and billing-dispute triage,
using cited official evidence and human referral for unresolved facts. Do not recalculate
bills, train a model or require cloud deployment.

| Workstream | Owner | Reviewable outputs |
|---|---|---|
| Agents and verification | Jashruth | Investigator and independent verifier, tool selection, bounded re-search, prompt variants, citation checks, and provider failure handling |
| Corpus, retrieval, and evaluation | Harshitha | Primary PDFs, amendment review, annotations, embeddings, Chroma index, reference labels, before-and-after metrics, and token and cost evidence |
| Platform and operations | Hamsa | Validated API and quarantine, Redis queue and polling, officer UI, Compose, tracing, metrics, and load, scaling, and cache experiments |

All members review the shared contracts and the tailoring reference case. The team plan
maps files and viva topics to each member's assigned workstream.

## Course milestones

1. Evaluation 1: show corpus passages and reference inputs from reference-case.md; obtain
   faculty confirmation and incorporate corrections. Faculty confirmation is not yet recorded.
2. Implementation review: validate intake, retrieval, both agents, verified results, human
   escalation, deadlines/retries, cost recording and observability. Use synthetic failures
   for controlled infrastructure testing and official cases for actual model evaluation.
3. One week before the presentation: submit the plain report and final GitHub repository
   specified by the manual. Review README startup, fixed evaluation evidence, runbook,
   incident log and environment examples. The team controls Git commits and publication.
4. Evaluation 2: live demonstration and viva using demo.md, including the confirmed tailoring
   case, invalid ingestion, audit, provider failure, scaling, SLO, cost and limitations.

Implementation and measured evidence are tracked in requirements.md and validation.md.
This document is not a claim that the academic milestones have already been completed.
