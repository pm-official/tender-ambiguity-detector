# Standards corpus

This directory holds the Indian Standards and CPWD publications TAD reads from at Stage-3 rewrite time.

- `raw/` — the original downloaded PDFs. **Gitignored.** Re-populate per environment with `python scripts/download_standards.py`.
- `processed/` — chunked artefacts (parquet) written by `python scripts/ingest_all.py --what standards`.
- `metadata/catalog.yaml` — the authoritative list of what we ingest, with source URLs, SHAs, license notes.
- `metadata/download_log.jsonl` — append-only, one JSON line per download attempt.

**Licensing.** BIS and CPWD retain copyright on their publications. TAD reads them at retrieval time only; no source text is republished. See `docs/licensing_and_attribution.md` for the full statement.
