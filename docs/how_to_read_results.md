# How to read the results

Every flag card has three scores at the top and three expanders below.

## The three scores

- **Keyword score** — from the category's curated lexicon (`data/keywords/{id}.yaml`). Transparent, fast, cheap. If it is high, you can point to the specific matched terms in the expander.
- **LLM score** — from a single Gemini Flash call with `prompts/detection_score_{id}.txt`. Covers phrasings the lexicon cannot anticipate.
- **Combined score** `= α · keyword + (1 − α) · llm`, default α = 0.3. The flag is kept when combined ≥ detection threshold (default 0.5, per-category after calibration).

## The three expanders

1. **Why was this flagged?** — keyword matches (with weights + any context rule that fired) plus the LLM's justification.
2. **Stage 2 — context resolution.** The adjudicator's verdict:
   - **Confirmed Ambiguous** — context elsewhere in the package did not resolve the flag. Address it: raise a clarification, propose the rewrite, or accept the risk.
   - **Resolved by Context** — another document in the package defined/specified the term. The flag is *not* silently dropped — it is shown in its own panel below the confirmed bucket so reviewers can verify.
   - **Partially Resolved** — some of the gap closed, at least one parameter still open. Rewrite may still help.
3. **Stage 3 — suggested rewrite.** Only for Confirmed / Partially Resolved. The rewrite cites specific IS or CPWD clause numbers from the standards grounding block. If no defensible grounding exists, the rewriter honestly says `INSUFFICIENT_GROUNDING`.

## Order-of-attention

1. Read the **Confirmed Ambiguous** bucket first — these are the items to action.
2. Scan the **Resolved by Context** bucket to verify the adjudicator's reasoning is sound and the cited context really resolves each flag.
3. Open **Metrics** for the resolved-by-context rate (a healthy package sits 25-45%) and the keyword-vs-LLM contribution split per category.
4. Open **Graph Explorer** to inspect Priority Conflict / Numerical Inconsistency findings.
