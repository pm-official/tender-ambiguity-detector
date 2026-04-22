# TAD — Method (Prompt-4, rendered into the About tab)

## Problem
Construction tenders routinely contain ambiguous clauses. Ambiguity causes disputes, cost overruns, re-tenders, and litigation. Our operational definition: *a clause where two competent readers acting in good faith could reasonably interpret the requirement differently.*

## Approach
TAD treats the tender as a **package** (not a single PDF). The user uploads every document — GCC, NIT, Specifications, BOQ, Drawings, Addenda — tags each document's type, and optionally picks a subset (and page range) to analyse. Flags are generated only from the selected subset, but every uploaded document is indexed and contributes to Stage-2 retrieval.

The pipeline runs four stages:

**Stage 0 — Package upload + scoping.** Parse PDFs → clause-aware chunks → embed into the tender-package vector store with `package_id` and `document_type` metadata. Build the knowledge graph over selected chunks.

**Stage 1 — Dual-scoring detection.**  For each chunk × each enabled category:
- **Keyword score** from `data/keywords/{category_id}.yaml` — terms, weights, optional context rules (requires/forbids). Normalised per 100 tokens, capped at 1.0.
- **LLM score** from a single Gemini 2.5 Flash call with `prompts/detection_score_{category_id}.txt`. Returns a calibrated score in [0,1], a span, and a justification.
- **Combined score** `= α · keyword + (1 − α) · llm`, α defaults to 0.3. Flag if combined ≥ threshold (default 0.5, per-category after calibration).
- Optional negative-control probe post-pass may downgrade confidence (G2).

**Stage 2 — Package context resolution.** For each confirmed flag, retrieve top-k context **from the whole tender package** (across all uploaded documents, not only the flagged doc). Adjudicator (Gemini 2.5 Pro, `prompts/resolution_package.txt`) returns one of:
- **Confirmed Ambiguous** — context did not resolve.
- **Resolved by Context** — another document names/defines/specifies the term sufficiently.
- **Partially Resolved** — narrowed but not settled.

For **Priority Conflicts** and **Numerical Inconsistencies**, the graph retriever (built at Stage 0d) is used instead of vector retrieval. The LLM-as-judge citation verifier (G3) runs on every Stage-2 verdict and strips fabricated citations.

**Stage 3 — Standards-grounded rewrite.** Only for Confirmed Ambiguous (and optionally Partially Resolved). Query the **standards corpus** — IS codes and CPWD specifications, stored in `standards_chunks`. Adjudicator (Gemini 2.5 Pro, `prompts/rewrite_standards.txt`) writes a rewrite citing specific IS / CPWD clause numbers that appear in the grounding block. If nothing defensible exists, it returns `INSUFFICIENT_GROUNDING` with an empty suggestion.

A grounding verification pass (G4) strips any IS-code or CPWD reference not present in the standards block and downgrades to `INSUFFICIENT_GROUNDING` if nothing remains.

## The eight categories
F · **Undefined Terms** — engineering noun phrases with no definition.
B · **Vague Qualifiers** — adjectives as criteria with no threshold.
I · **Unnamed References** — references to documents/clauses with no target named.
A · **Word-Level Ambiguity** — polysemous construction terms.
E · **Unclear Pronouns** — pronouns / definite references with unclear antecedent.
G · **Priority Conflicts** — cross-document conflicts the priority rule does not settle.
H · **Numerical Inconsistencies** — same quantity, different values, no reconciliation.
J · **Incomplete Specifications** — procedures that omit required parameters.

Definitions, positive and negative examples live in `app/explanations/categories.yaml` and are shown verbatim in the UI's info popovers.

## Accuracy guardrails
- **G1 — Dual-scoring (default).** Replaces the Prompt-3 3-pass ensemble. The legacy ensemble is preserved behind `USE_LEGACY_ENSEMBLE` for the dual-scoring-vs-ensemble ablation.
- **G2 — Negative-control probe.** Opposite-framing probe on confirmed local flags; downgrades combined score on strong disagreement.
- **G3 — LLM-as-judge citation verification.** Stage 2 citations are verified against the retrieved block; fabricated IDs are stripped; re-adjudication if reasoning becomes unsupported.
- **G4 — Rewrite grounding verification.** IS / CPWD references in the suggested rewrite must appear in the standards block; fabricated ones are stripped; empty grounding → INSUFFICIENT_GROUNDING.
- **G5 — Per-category calibrated thresholds.** Stored in `output/calibration.json`.
- **G6 — Dead-letter queue.** Every failed LLM call lands in `output/{run_id}/dead_letters.jsonl`.
- **G7 — Deterministic seed.** `RANDOM_SEED = 1729`.

## Annotation protocol
Retained from Prompt 3: Phase-1 recall sweep, Phase-2 LLM-as-Judge three-seed majority vote, Phase-3 filter, Phase-4 open-ended recall audit, Phase-5 targeted human spot-check, Phase-6 emit gold, Phase-7 optional 50-flag Cohen's kappa study. See `app/explanations/annotation_protocol.yaml` and `prompts/llm_judge_annotation.txt`.

## Evaluation metrics
- Precision / Recall / F1 per category (target ≥ 0.75 / ≥ 0.70).
- **False-resolution rate** — safety metric, target ≤ 10%.
- **Resolved-by-context rate** — methodology-signature metric (target 25-45% healthy range).
- **Keyword vs LLM contribution** — per category, share of flags where the keyword signal dominated.
- Graph retrieval recall for Priority Conflicts and Numerical Inconsistencies.
- Cohen's kappa (optional, 50-flag subset).

## Ablations
1. **dual_scoring_vs_ensemble** — Prompt-4 default vs legacy 3-pass ensemble on the same gold slice.
2. **alpha_sweep** — α from 0.0 (LLM-only) to 1.0 (keyword-only) in 0.1 steps; F1 per category.
3. Hybrid retrieval on vs off (G/H F1 delta with graph disabled).
4. Per-guardrail off (G2 / G3 / G4 individually).
5. Keyword baseline and zero-shot LLM baseline (unchanged from Prompt 3).

## Design changes vs the initial Prompt-3 build
- **Package, not a single document.** Stage 2 retrieves across the whole package so ambiguities resolved elsewhere are surfaced explicitly, not silently dropped.
- **Dual-scoring, not 3-pass ensemble.** Cheaper and easier to explain to engineers; ablation reports the delta honestly.
- **Two-stage RAG.** Stage 2 = tender-package context (is this flag real?); Stage 3 = IS/CPWD standards (how do we fix it?).
- **Intuitive display names.** Letter codes stay internal; every user-facing surface uses names like *Undefined Terms*, *Resolved by Context*.

## Limitations (report honestly)
- Scanned PDFs without an OCR layer are unsupported.
- IS / CPWD grounding quality depends on the PDFs ingested via `src.is_code_ingest`.
- Entity canonicalisation in the graph is surface-form-based and misses some aliases.
- LLM-as-Judge annotation is a mitigation for full double-annotation, not a replacement.
