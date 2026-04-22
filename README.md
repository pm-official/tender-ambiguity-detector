# Tender Ambiguity Detector (TAD)

A self-explaining web application that reads an **Indian construction tender package**, detects **eight categories** of ambiguity, checks whether each flag is resolved by other documents in the same package, and — for genuinely ambiguous clauses — suggests a rewrite grounded in IS codes and CPWD specifications.

Built as an M.Tech thesis project, Civil Engineering, IIT Bombay.

---

## What it does (in one screen)

1. **Upload the whole tender package** — GCC, NIT, Specifications, BOQ, Drawings, Addenda. Tag each document and pick which ones to analyse.
2. **Parse & chunk** — clause-aware, ~500-token chunks; the whole package is indexed for Stage-2 retrieval.
3. **Detect (Stage 1)** — dual scoring: a **keyword score** from the category lexicon plus a single-call **LLM score**. Combined above the threshold → flagged. (The legacy 3-pass ensemble is preserved behind a feature flag for ablation.)
4. **Package context resolution (Stage 2)** — retrieve top-k context from across the whole tender package and decide **Confirmed Ambiguous** / **Resolved by Context** / **Partially Resolved**. An LLM-as-judge pass verifies every cited context id.
5. **Standards-grounded rewrite (Stage 3)** — Confirmed flags get a rewrite grounded in IS codes and CPWD specifications; a grounding-verification pass strips any fabricated clause number.

Every number, badge, and stage in the UI has an **(ℹ)** icon that opens a "what / why / how / benchmark / worked example" card drawn from `app/explanations/*.yaml`. The app is designed to be understandable without a walkthrough.

---

## The eight categories (display names; letter codes are internal)

| Code | Display name | Short definition |
|---|---|---|
| F | **Undefined Terms** | "suitable aggregate", "approved make" |
| B | **Vague Qualifiers** | "adequate drainage", "good quality sand" |
| I | **Unnamed References** | "as per the relevant IS code" |
| A | **Word-Level Ambiguity** | "access" (physical vs rights), "fair" |
| E | **Unclear Pronouns** | "They shall provide materials." |
| G | **Priority Conflicts** | priority rule fails to resolve a disagreement |
| H | **Numerical Inconsistencies** | same quantity, different values |
| J | **Incomplete Specifications** | "apply primer coat" — type/thickness/cure missing |

Full definitions with positive and negative examples live in `app/explanations/categories.yaml`.

---

## Accuracy guardrails

- **G1** — 3-pass ensemble with IoU clustering and 2/3 agreement gate.
- **G2** — negative-control probe for confirmed flags (F, B, I, A, E, J).
- **G3** — LLM-as-judge citation verification on every resolution.
- **G4** — rewrite grounding verification (strips fabricated IS-code refs).
- **G5** — per-category threshold calibration via `output/calibration.json`.
- **G6** — dead-letter queue for every failed LLM call (`output/{run_id}/dead_letters.jsonl`).
- **G7** — deterministic seed (`RANDOM_SEED = 1729`) for reproducibility.

---

## Quickstart (local)

```bash
git clone https://github.com/<your-handle>/tender-ambiguity-detector.git
cd tender-ambiguity-detector
python -m venv .venv
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate

pip install -r requirements.txt

# Set API key (one of these)
$env:GOOGLE_API_KEY = "..."        # PowerShell
export GOOGLE_API_KEY=...          # bash
# or drop it in .streamlit/secrets.toml

streamlit run app/streamlit_app.py
```

Open http://localhost:8501 and either upload a tender PDF or pick one of the bundled samples in `data/sample_tenders/`.

---

## Deploying on Streamlit Community Cloud

1. Push this repo to GitHub.
2. Visit https://share.streamlit.io and click *Deploy an app*.
3. Select the repo; main file = `app/streamlit_app.py`.
4. Add secret `GOOGLE_API_KEY` under the app settings.
5. Deploy. First boot takes ~4 minutes (installs dependencies).

The Chroma store is ephemeral — each cold start re-embeds whatever tenders you upload.

---

## Project structure

```
tender-ambiguity-detector/
├── app/                    # Streamlit UI + YAML-backed explanations
│   ├── streamlit_app.py
│   ├── components/
│   └── explanations/*.yaml # every info icon reads from here
├── prompts/                # detection × 3 variants × 8 categories + aux prompts
├── src/
│   ├── config.py           # all model names, thresholds, paths
│   ├── schemas.py          # pydantic v2 schemas
│   ├── utils.py            # LLM wrapper, logging, span IoU
│   ├── parser.py           # PDF → pages
│   ├── chunker.py          # clause-aware chunking
│   ├── embeddings.py       # ChromaDB + text-embedding-004
│   ├── detector.py         # 3-pass ensemble + negative probe (G1 + G2)
│   ├── graph_store.py      # NetworkX knowledge graph
│   ├── graph_builder.py    # LLM extraction of entities / quantities / priority rules
│   ├── graph_retriever.py  # graph retrieval for G, H
│   ├── resolver.py         # hybrid router + LLM-as-judge (G3)
│   ├── rewriter.py         # IS-code-grounded rewrite + verification (G4)
│   ├── pipeline.py         # orchestrator
│   ├── evaluator.py        # precision/recall/F1, kappa, FRR
│   ├── iaa.py              # Cohen's kappa
│   ├── annotation_protocol.py  # LLM-as-Judge gold-set protocol
│   └── baselines/          # keyword + zero-shot baselines
├── data/sample_tenders/    # bundled sample PDFs for demo
├── is_codes/               # user-supplied IS-code PDFs (gitignored)
├── output/                 # run artifacts (gitignored)
├── docs/                   # method write-up, glossary
├── tests/
├── requirements.txt
└── .streamlit/config.toml
```

---

## Novelty claims

1. **Eight-category construction-tender-specific ambiguity taxonomy**, operationalised with per-category detection prompts and edge cases.
2. **Hybrid vector + graph retrieval** with a router that directs G/H to a knowledge graph built from typed extraction.
3. **Self-consistency detection with review queue** — precision-first ensemble that records disagreement as a first-class output.
4. **IS-code-grounded rewriting with grounding verification** — refuses to hallucinate clause numbers.
5. **Reproducible, self-explaining deployed application** — every number has a YAML-backed explanation; every LLM call is logged and displayable.
6. **LLM-as-judge + human spot-check annotation protocol** — defensible gold set without full double-annotation.

Each claim is backed by an ablation or a reported metric; see `app/explanations/ablations.yaml`.

---

## Author

Prakhar — M.Tech (Civil), IIT Bombay.

Licensed under MIT.
