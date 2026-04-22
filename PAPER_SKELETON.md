# TAD — Paper skeleton (Prompt-4)

## 1. Introduction
Construction tender ambiguity causes disputes. Prior work is either keyword-brittle or domain-blind. We present a **package-aware**, dual-scoring ambiguity-detection and rewriting system with two-stage RAG (intra-tender-package + standards corpus) and a transparent self-explaining interface.

## 2. Related work
Keyword/heuristic systems; zero-shot LLM detectors (Arora 2024; Fischbach 2024); RAG for legal/contract (BifrostRAG; NCKG).

## 3. Method
- Eight-category taxonomy with intuitive display names (F: Undefined Terms … J: Incomplete Specifications).
- Four-stage pipeline: package upload → dual-scoring detection → package context resolution → standards-grounded rewrite.
- Guardrails: G2 negative-control probe, G3 LLM-as-judge citation verification, G4 grounding verification.
- Legacy 3-pass ensemble preserved behind a flag for ablation.

## 4. Annotation protocol
LLM-as-Judge with three-seed majority vote + targeted human spot-check. Phase-6 gold emit; Phase-7 optional kappa study.

## 5. Evaluation metrics
Per-category P/R/F1, false-resolution rate, resolved-by-context rate, keyword-vs-LLM contribution split, graph-retrieval recall for Priority Conflicts / Numerical Inconsistencies, Cohen's kappa.

## 6. Ablations
1. Dual-scoring vs 3-pass ensemble.
2. α sweep (0.0 → 1.0, 0.1 steps).
3. Hybrid retrieval on vs off.
4. Per-guardrail off (G2 / G3 / G4).
5. Keyword baseline, zero-shot LLM baseline.

## 7. Discussion
Resolved-by-context rate demonstrates real package-level work; cases where the package genuinely fails to resolve; keyword-vs-LLM split by category; failure modes.

## 8. Limitations
Scanned PDFs, standards-PDF supply quality, entity canonicalisation breadth, annotation-protocol vs full double-annotation.

## 9. Conclusion
A package-aware, dual-scoring, two-stage-RAG, self-explaining ambiguity detector is tractable and publishable.
