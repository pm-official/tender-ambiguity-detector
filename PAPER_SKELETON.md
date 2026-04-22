# TAD — Paper skeleton

## 1. Introduction
Construction tender ambiguity causes disputes; prior work is either keyword-brittle or domain-blind. We introduce an eight-category, tender-specific, hybrid-retrieval ambiguity-detection and rewriting system with a transparent self-explaining interface.

## 2. Related work
Keyword/heuristic; zero-shot LLM detectors (Arora 2024; Fischbach 2024); general-purpose RAG for legal/contract (BifrostRAG; NCKG).

## 3. Method
- Eight-category taxonomy (F, B, I, A, E, G, H, J).
- Four-stage pipeline: parse → chunk → detect (3-pass ensemble) → resolve (hybrid) → rewrite (IS-code-grounded).
- Four guardrails: ensemble (G1), negative probe (G2), citation judge (G3), grounding verification (G4).

## 4. Annotation protocol
LLM-as-Judge + targeted human spot-check; Phase-6 gold emit; Phase-7 optional kappa study.

## 5. Evaluation
Per-category P/R/F1, false-resolution rate, graph recall for G/H, kappa.

## 6. Ablations
Ensemble on/off, hybrid vs vector-only, per-guardrail off, detector model swap, prompt-framing, keyword baseline, zero-shot baseline.

## 7. Discussion
What works; failure modes; where the system cries wolf; where it misses.

## 8. Limitations
Scanned PDFs, IS-code supply quality, entity canonicalisation breadth, annotation-protocol vs full double-annotation.

## 9. Conclusion
Tender-specific, domain-grounded, hybrid-retrieval ambiguity detection with a transparent rewrite loop is a tractable and publishable setting.
