# TAD — Method (rendered into the About tab)

## Problem statement
Construction tenders routinely contain ambiguous clauses. Ambiguity causes disputes, cost overruns, re-tenders and litigation. Empirical studies (Koc & Gurgun 2022; Fischbach et al. 2024) show that experienced engineers frequently disagree on what a given clause means. Our operational definition is: *a clause where two competent readers acting in good faith could reasonably interpret the requirement differently.*

## Prior work and gap
1. Keyword / heuristic systems are brittle and transfer poorly across tenders.
2. Zero-shot LLM ambiguity detectors lack domain grounding.
3. General-purpose RAG for legal / contract analysis (BifrostRAG, NCKG) misses tender-specific structure.

Our contribution is a tender-specific, domain-grounded, hybrid-retrieval system with an explicit eight-category taxonomy, IS-code-grounded rewriting, and a transparent self-explaining UI that is defensible to engineers, not just ML researchers.

## The eight categories
F — Undefined technical terms.
B — Vague qualitative adjectives.
I — Missing reference targets.
A — Lexical ambiguity.
E — Anaphoric ambiguity.
G — Cross-document priority conflict.
H — Cross-document numerical inconsistency.
J — Incomplete specifications.

Definitions and edge cases are in `app/explanations/categories.yaml`.

## Pipeline

**Stage 0 — Parse & chunk.** PDF → text (per page) → clause-aware chunks with stable IDs.

**Stage 1 — Detection ensemble.** For each chunk × each category, run three detection prompts with different framings:
- v1 positive-led: "Identify spans that match category X."
- v2 open-ended: "Review this clause; if any category-X issues, list them."
- v3 adversarial: "A bidder and an engineer disagree. Could category X be the reason?"

Merge spans across passes by IoU ≥ 0.5. Confirm at agreement ≥ 2/3. 1/3 clusters go to the review queue. A negative-control probe optionally reduces confidence.

**Stage 2 — Hybrid resolution.** Route by category:
- Local categories (F/B/I/A/E/J) → vector retrieval over tender + IS-codes.
- Cross-document categories (G/H) → knowledge-graph retrieval.

Adjudicator (Gemini 2.5 Pro) returns RESOLVED / PARTIALLY_RESOLVED / UNRESOLVED. A second LLM-as-judge pass strips any cited context IDs that don't appear in the retrieved block.

**Stage 3 — IS-code-grounded rewrite.** For non-RESOLVED verdicts, the rewriter cites specific IS-code clause numbers that appear in the grounding block. A grounding-verification pass strips fabricated references; if nothing defensible remains, status is downgraded to INSUFFICIENT_GROUNDING.

## Accuracy guardrails
G1 — Ensemble (IoU clustering, 2/3 agreement).
G2 — Negative-control probe (opposite framing).
G3 — LLM-as-judge citation verification.
G4 — Rewrite grounding verification.
G5 — Per-category threshold calibration.
G6 — Dead-letter queue for all failed LLM calls.
G7 — Deterministic seed (RANDOM_SEED = 1729).

## Annotation protocol
Phase 1 recall sweep → Phase 2 LLM-judge (3 seeds, majority vote) → Phase 3 filter → Phase 4 open-ended recall audit → Phase 5 human spot-check (20% TP, 100% UNCERTAIN, 100% missed-recall, 100% cross-seed disagreements) → Phase 6 gold emit → Phase 7 optional 50-flag Cohen's-kappa study. Details in `app/explanations/annotation_protocol.yaml`.

## Evaluation metrics
- Precision / Recall / F1 per category (target ≥ 0.75 / ≥ 0.70).
- **False-resolution rate** (target ≤ 10%) — the safety metric.
- Graph retrieval recall for G/H.
- Cohen's kappa (where a second annotator is available).
- Ablations: ensemble on/off, hybrid vs vector-only, per-guardrail off, detector model swap, prompt-framing ablation, keyword baseline, zero-shot LLM baseline, annotation-protocol-vs-human.

## Limitations (report honestly)
- Scanned PDFs without an OCR layer are not supported.
- IS-code grounding quality depends on the supplied PDFs.
- Entity canonicalisation in the graph is surface-form-based; it will miss some aliases.
- The LLM-as-Judge annotation protocol is a mitigation for full double-annotation, not a replacement.
