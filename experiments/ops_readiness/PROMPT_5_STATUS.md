# Prompt 5 — acceptance-criteria status

Last updated: commit `6c88106`.

| § 10.1 check | Status | Notes |
|---|---|---|
| `scripts/verify_corpus.py` exits 0 with no P1/P2 missing | ⚠ partial | 17/22 P1 IS codes + 4/4 P2 CPWD downloaded. 5 IS codes (13920, 1893 Pt 1, 10262, 269, 3025 Pt 1) returned 404/503 from both primary and archive.org in this run; re-run `python scripts/download_standards.py` from a different network to clear the rest. |
| `scripts/eval_retrieval.py` hit@3 ≥ 0.70 | ⏳ pending first ingest | Script + 32-Q gold are shipped. Run `python scripts/ingest_all.py --what standards` then `python scripts/eval_retrieval.py` to get the live number. |
| `scripts/run_end_to_end_demo.py` finishes exit 0 with non-empty stages | ⏳ pending first run | Script wired; Gemini API quota is the only dependency. |
| `pytest -q` green | ✅ | 48/48 local, including new `test_quantity_extractor.py` and `tests/regression/test_catalog_valid.py`. |
| `calibration.json` P ≥ 0.70 R ≥ 0.65 | ⏳ pending gold | Calibration script + gate are shipped; needs `gold/tender_ambiguity.jsonl` with real human spot-checks. |
| `ablation_summary.md` exists | ⏳ pending gold | Ablation runner exists (`src/experiments.py`); needs a gold file to compute deltas. |
| Live URL reachable with demo tender by default | ✅ | Tender picker + SYNTHETIC banner live on redeploy. |
| Three screenshots exist | ✅ | `docs/screenshots/demo_<ts>/` — Analyse with picker, Standards catalog, plus an early state. |
| `docs/demo_script.md` walkable in < 10 min | ✅ | Ten-minute script committed. |
| `docs/decision_log.md` lists non-trivial decisions | ✅ | Synthetic fallback, screen-recording caveat, calibration-floor note. |
| 90-second screen recording under Git LFS | ❌ | Captured as static screenshots — this agent has no OS screen-recorder API. User to record once. Documented in `decision_log.md`. |

## Known open items

1. Re-attempt the 5 P1 IS-code downloads from a clean network (primary URLs may be transiently 5xx; archive.org may require a JS check for some files).
2. Run the standards ingest and retrieval-eval once; commit the produced `retrieval_eval.json` so the Metrics-tab badge populates.
3. Run the end-to-end demo on the synthetic package once to populate a run report.
4. Swap the synthetic tender for a real CPWD tender once a browser session can clear the eprocure.gov.in anti-bot challenge.
5. Produce the 90-second demo recording.

## What shipped

- 21 real standards documents on disk (17 IS + 4 CPWD) totalling ~100 MB, hash-verified.
- A 6-PDF synthetic CPWD tender package with known ambiguities across all 8 categories, labelled synthetic.
- Seven new scripts under `scripts/`: `download_standards`, `download_tender`, `make_synthetic_package`, `verify_corpus`, `ingest_all`, `eval_retrieval`, `calibrate_thresholds`, `run_end_to_end_demo`.
- Three new UI surfaces: Standards catalog tab, Annotation (Phase 5) tab, tender picker + SYNTHETIC / REAL demo banner.
- New metric explanations + info icons: `metrics.retrieval_hit_at_3`, `scoring.*`, `document_types.*`.
- New tests: `test_quantity_extractor.py`, `tests/regression/test_catalog_valid.py`. All 48 tests green.
- Docs: `docs/prompt5_plan.md`, `docs/decision_log.md`, `docs/licensing_and_attribution.md`, `docs/demo_script.md`.
