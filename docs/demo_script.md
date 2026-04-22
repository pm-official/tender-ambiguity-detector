# TAD demo script — 10-minute walkthrough for the thesis meeting

Target: Prof. + student, live Streamlit URL.

## 0:00 — The problem (1 min)
Say, roughly: "Construction tender clauses are often ambiguous. Ambiguity drives disputes, cost overruns, re-tenders. My tool reads a full tender *package* — GCC, NIT, Specs, BOQ, Drawings, Addenda — flags eight categories of ambiguity, checks whether the rest of the package resolves each flag, and rewrites the truly ambiguous ones citing IS codes and CPWD specifications."

Open the live URL: **https://tender-ambiguity-detector.streamlit.app/**

## 1:00 — The corpus (1 min)
Click the **Standards catalog** tab. Point to the headline metrics (21 ingested OK, priority-1 IS codes + priority-2 CPWD). Click one IS-code row; show the source URL, SHA-256 hash, and licensing note. "Every chunk is content-hashed and attributed. The retrieval hit@3 over 32 expert-written questions is shown on the Metrics tab."

## 2:00 — The input (1 min)
Click **Analyse**. In the "Pre-staged demo packages" expander, pick `sample_01_synthetic_cpwd`. Click **Use this package as the input**. Point to the yellow **SYNTHETIC demo package** banner above the upload lane and to the package table showing NIT / GCC / Additional Conditions / Tech Specs / BOQ / Addendum with doc_role pre-filled.

> **Honesty note to say aloud.** "This is a synthetic tender package so we can demo the flow; empirical precision/recall are not claimed on it. A real CPWD tender is the next upload."

## 3:00 — Stage 1 (dual scoring) (2 min)
Click **▶ Run pipeline**. Watch the stage tracker light up: Parse → Chunk → Index Package → Dual-Scoring → Package Context Resolution → Standards-Grounded Rewrite.

Once flags appear, pick one. Point to the three score gauges — **keyword**, **LLM**, **combined**. Click the (ℹ) on each one — explain the formula `combined = α·keyword + (1 − α)·llm` and say "α defaults to 0.3 — LLM-dominant. We ablate α 0.0 → 1.0 in 0.1 steps to pick the per-category optimum."

Open the **Why was this flagged?** expander. Show the exact keyword matches with weights from `data/keywords/B.yaml` and the LLM's justification.

## 5:00 — Stage 2 (package context resolution) (1 min)
Find a **Resolved by Context** flag (bottom panel of the Analyse tab). Open its *Stage 2 — context resolution* expander. Point to the retrieved contexts — they come from *other documents* in the same tender package. "This is the methodology's signature output: an ambiguity that looks ambiguous in one clause is often disambiguated by a later document. The system doesn't silently drop it — it labels it Resolved and shows the evidence."

## 6:30 — Stage 3 (standards-grounded rewrite) (1 min)
Pick a **Confirmed Ambiguous** flag. Open the *Stage 3 — suggested rewrite* expander. Read the suggested clause aloud. Point to the cited IS-code / CPWD clause number. "Every IS-code number in the rewrite is verified against the retrieved standards block — if the model invents a clause number, our grounding verifier strips it and downgrades the rewrite to INSUFFICIENT_GROUNDING. No fabricated citations reach the user."

## 8:00 — Numbers for the paper (1 min)
Click **Metrics**. Walk through the five panels:
1. **Flag distribution** by category.
2. **Stage-2 verdicts** — Confirmed vs Resolved vs Partial.
3. **Resolved-by-context rate** — "a healthy rate is 25–45%; too low means Stage 2 is permissive."
4. **Keyword vs LLM contribution** — per category, where the signal came from.
5. **hit@3** on the 32-question gold set — upstream retrieval quality, from `scripts/eval_retrieval.py`.

Click **Experiments** — point to the dual-scoring-vs-ensemble and alpha-sweep ablations (and the guardrail-off ablations from Prompt 4).

## 9:00 — Open questions (1 min)
Point to the **About this method** tab for the four-stage diagram and the **Design changes vs initial build** section. List three research questions in `docs/decision_log.md` that the thesis will explore:

1. **Cross-tender generalisation** — ingest a second real tender and measure per-category F1 drift.
2. **Hindi / bilingual tenders** — CPWD and state-PWD tenders sometimes include Hindi clauses; our embedding model handles multilingual inputs, but the keyword lexicon is English-only.
3. **Active learning for category imbalance** — one synthetic tender rarely covers G and H adequately; the annotation queue should prioritise low-coverage categories automatically.

## 9:30 — Wrap
"Live URL is bookmarkable. The full pipeline is one command: `python scripts/run_end_to_end_demo.py --tender <name>`. Every flag card has an (ℹ) on every number, backed by a YAML explanation — so the tool explains itself."
