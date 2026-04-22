# Glossary

Every term rendered in the app is defined in `app/explanations/*.yaml` and surfaced through the **Glossary** button in the header.

Key Prompt-4 additions:

- **Tender package** — the set of all PDFs belonging to one tender (GCC, NIT, Specifications, BOQ, Drawings, Addenda, etc.). TAD treats the package as one unit for retrieval.
- **Document type** — GCC / Additional Conditions / NIT / Technical Specifications / BOQ / Conditions of Contract / Addendum / Drawing / Other. Tagged at upload.
- **Dual scoring** — keyword score + LLM score → combined score → threshold decides whether a chunk is flagged.
- **Combined score** — α · keyword + (1 − α) · llm (default α = 0.3).
- **Resolved by Context** — Stage-2 verdict: another document in the package disambiguates the flag; no rewrite needed.
- **Confirmed Ambiguous** — Stage-2 verdict: retrieval did not resolve the flag; Stage 3 rewrites this one.
- **Standards corpus** — IS codes and CPWD specifications, ingested via `src.is_code_ingest`, used only for Stage-3 grounding.
