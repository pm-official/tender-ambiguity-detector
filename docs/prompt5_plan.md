# Prompt 5 — Operational readiness plan

## 1. Audit (pre-Prompt-5 state)

The repo is at commit `e331a1b` (Prompt-4 refresh). Relevant state:

- `standards/raw/` — **absent** before this commit; created here with `.gitkeep`.
- `tenders/real/` — **absent** before this commit; created here with `.gitkeep`. The only tender artefact is `data/sample_tenders/synthetic_ohsr_tender.pdf` (labelled synthetic since Prompt 3).
- No SQLite artifact store exists; Chroma persists under `chroma_store/` and is gitignored.
- `output/` contains past runs from Prompt-3/4; Prompt-5 runs will land in `experiments/ops_readiness/run_<timestamp>/`.
- Gold sets: none. `gold/` is created here.
- Calibration: the code path for per-category threshold calibration exists (`src/config.load_detection_thresholds`) but has never been executed on real data.

## 2. Download plan

### Priority 1 — BIS Indian Standards via `law.resource.org` mirror

| Code | Year | Primary URL | Archive.org fallback |
|---|---|---|---|
| IS 456 | 2000 | `https://law.resource.org/pub/in/bis/S03/is.456.2000.pdf` | `https://archive.org/download/gov.in.is.456.2000/gov.in.is.456.2000.pdf` |
| IS 383 | 1970 | `https://law.resource.org/pub/in/bis/S03/is.383.1970.pdf` | `https://archive.org/download/gov.in.is.383.1970/gov.in.is.383.1970.pdf` |
| IS 800 | 2007 | `https://law.resource.org/pub/in/bis/S03/is.800.2007.pdf` | `https://archive.org/download/gov.in.is.800.2007/gov.in.is.800.2007.pdf` |
| IS 875 Pt 1 | 1987 | `https://law.resource.org/pub/in/bis/S03/is.875.1.1987.pdf` | — |
| IS 875 Pt 2 | 1987 | `https://law.resource.org/pub/in/bis/S03/is.875.2.1987.pdf` | — |
| IS 875 Pt 3 | 1987 | `https://law.resource.org/pub/in/bis/S03/is.875.3.1987.pdf` | — |
| IS 875 Pt 4 | 1987 | `https://law.resource.org/pub/in/bis/S03/is.875.4.1987.pdf` | — |
| IS 875 Pt 5 | 1987 | `https://law.resource.org/pub/in/bis/S03/is.875.5.1987.pdf` | — |
| IS 1786 | 2008 | `https://law.resource.org/pub/in/bis/S03/is.1786.2008.pdf` | — |
| IS 13920 | 2016 | `https://law.resource.org/pub/in/bis/S03/is.13920.2016.pdf` | fallback archive.org |
| IS 1893 Pt 1 | 2016 | `https://law.resource.org/pub/in/bis/S03/is.1893.1.2016.pdf` | fallback archive.org |
| IS 10262 | 2019 | `https://law.resource.org/pub/in/bis/S03/is.10262.2019.pdf` | fallback archive.org |
| IS 269 | 2015 | `https://law.resource.org/pub/in/bis/S03/is.269.2015.pdf` | fallback archive.org |
| IS 12269 | 2013 | `https://law.resource.org/pub/in/bis/S03/is.12269.2013.pdf` | fallback archive.org |
| IS 516 | 1959 | `https://law.resource.org/pub/in/bis/S03/is.516.1959.pdf` | fallback archive.org |
| IS 1200 Pt 1 | 1992 | `https://law.resource.org/pub/in/bis/S03/is.1200.1.1992.pdf` | fallback archive.org |
| IS 2212 | 1991 | `https://law.resource.org/pub/in/bis/S03/is.2212.1991.pdf` | fallback archive.org |
| IS 2386 Pt 1 | 1963 | `https://law.resource.org/pub/in/bis/S03/is.2386.1.1963.pdf` | fallback archive.org |
| IS 2386 Pt 3 | 1963 | `https://law.resource.org/pub/in/bis/S03/is.2386.3.1963.pdf` | fallback archive.org |
| IS 4031 Pt 1 | 1996 | `https://law.resource.org/pub/in/bis/S03/is.4031.1.1996.pdf` | fallback archive.org |
| IS 9103 | 1999 | `https://law.resource.org/pub/in/bis/S03/is.9103.1999.pdf` | fallback archive.org |
| IS 3025 Pt 1 | 1987 | `https://law.resource.org/pub/in/bis/S03/is.3025.1.1987.pdf` | fallback archive.org |

### Priority 2 — CPWD

| Document | URL |
|---|---|
| CPWD Specifications 2019 Vol 1 | `https://cpwd.gov.in/Publication/Specs2019V1.pdf` |
| CPWD Specifications 2019 Vol 2 | `https://cpwd.gov.in/Publication/Specs2019V2.pdf` |
| CPWD GCC 2019 (Construction) | `https://www.cpwd.gov.in/Publication/GCC_Construction_2019.pdf` |
| CPWD Works Manual 2019 (NDMC mirror) | `https://www.ndmc.gov.in/departments/Departments/Finance/nodal_cell/CPWD%20Works%20Manual%202019.pdf` |

SHA-256 values are blank in `catalog.yaml` until downloads complete — the script writes them back on successful fetch.

## 3. Verification criteria I can run here

- ✅ `scripts/verify_corpus.py` — runs locally; reports status per tier.
- ✅ `scripts/eval_retrieval.py` — runs locally against the standards vector store; needs downloaded PDFs for meaningful numbers.
- ✅ `pytest -q` — existing + new tests.
- ⚠ `scripts/run_end_to_end_demo.py` — completes if Gemini API is reachable; demo run is capped at US$2 with the Flash-only fallback.
- ⚠ Live deploy verification — achievable via `git push` to main; Streamlit Community Cloud auto-rebuilds.
- ❌ 90-second screen capture — requires host-side screen recorder access not available to this agent. Captured as screenshots + demo script instead; documented in `decision_log.md`.

## 4. First five commits

1. `chore(p5): scaffold directories, plan, .gitkeeps, .gitignore updates`
2. `feat(standards): catalog.yaml with priority 1–3 entries + download/verify scripts`
3. `feat(standards): attempt real downloads, commit download_log.jsonl and licensing doc`
4. `feat(tender): real-or-synthetic demo package with manifest and ingestion glue`
5. `feat(ui): Standards catalog tab, tender picker, annotation page, demo banner, YAMLs`

## 5. Risk register

| Risk | Mitigation |
|---|---|
| `law.resource.org` or `cpwd.gov.in` blocks the agent's network (DNS / 403 / 404) | `download_standards.py` attempts primary → archive.org fallback → logs `status: MISSING` without crashing. Re-run later from a clean network. |
| `eprocure.gov.in` anti-bot prevents real tender download | Use the Fallback-C route explicitly sanctioned by the spec: build a synthetic multi-doc package with `synthetic: true` and refuse to claim empirical results on it. |
| Gemini quota / rate limits during end-to-end run | Dual-scoring path is Flash-dominant; adjudication + judge + rewrite default to Pro with an escape hatch to Flash when a `CHEAP_MODE=true` env flag is set; backoff+retry already in `src.utils.call_llm`. |
| Scanned PDFs with no OCR layer | `scripts/ingest_all.py` detects `text_extractable: false` and logs an honest warning; OCR path left for follow-up (ocrmypdf requires Tesseract — a system dep). |
| Context overflow on large clauses | Chunker already caps at ~500 tokens; rewriter splits remaining overflow at sentence boundaries. |
| 90-second video is not producible in this environment | Capture three canonical screenshots instead; document the gap in `decision_log.md` so the supervisor sees it immediately. |
