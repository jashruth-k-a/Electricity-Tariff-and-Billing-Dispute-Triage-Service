# Reference case for faculty confirmation

This is a technical reference prepared for review. It does not claim that Evaluation 1
or faculty confirmation has already taken place.

## Facts to demonstrate

Karnataka, LT, billed domestic; occupant lives in the house and uses one room for tailoring;
connected load 3 kW, sanctioned load 5 kW, billing date 2026-10-01. These are the facts in
`evaluation/official-cases.json`, case `tailoring-reference`. They are not facts inferred
by the model. Independent tailoring shops are a separate reference case.

## Passages to show

| Provision | Exact short excerpts | Role |
|---|---|---|
| KERC Combined Tariff Order 2025, Annexure 9 / LT-1, PDF p.550 | "houses where a portion is used by the occupant for" and "(e) Tailoring" | The residential applicability expressly lists this activity in part of the occupant's dwelling. These are separate excerpts, not a stitched quote. |
| KERC Conditions of Supply, 42.02(a), PDF p.79, amended portion above OLD VERSION | "misused for purpose for which a higher method of charging is in force" | The higher-charging-purpose condition must be considered alongside the specific residential applicability. |

The complete exact passages, page numbers, URLs and source hashes are in
`corpus/official/annotations/` and `corpus/official/manifest.json`. The independent shop
definition is in Annexure 9 / LT-5, PDF p.555. Tariff general provision 29, PDF p.543,
requires reading the supply conditions and amendments on discrepancy.

Technical reference position: on these stated facts, the express residential inclusion
supports the domestic category; the presence of tailoring alone does not establish a
higher-charging purpose. The expected route is `bill-stands-with-reason`, supported by
both LT-1 and 42.02(a). No bill amount, penalty or binding liability is computed. Different
premises facts, a relevant conflicting amendment or missing essential facts can require
officer review. The technical source-review boundary is explained in official-corpus.md.

## Confirmation record

- Faculty reviewer: not yet recorded.
- Evaluation 1 confirmation: not yet recorded.
- Any faculty corrections to premises facts, corpus or expected position: awaiting review.
- Real-model reference run: see `evaluation/results/official-reference-answer.json`,
  the separate provider probes and the full local audit.

Once faculty confirms or corrects the reference, update this record and the fixed evaluation
labels together. Do not change labels merely to make a model's answer pass.
