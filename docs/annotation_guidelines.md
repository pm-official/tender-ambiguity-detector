# Annotation guidelines

The UI speaks the user-facing **display names** (Undefined Terms, Vague Qualifiers, Unnamed References, Word-Level Ambiguity, Unclear Pronouns, Priority Conflicts, Numerical Inconsistencies, Incomplete Specifications). Letter codes (F / B / I / A / E / G / H / J) are internal identifiers only and appear in CSVs / schemas, never in labels shown to the reviewer.

The LLM-as-Judge annotation protocol and spot-check flow are unchanged from Prompt 3 and documented in `app/explanations/annotation_protocol.yaml`. Phase 5 (the human spot-check) covers 20% of TRUE_POSITIVE (stratified), 100% of UNCERTAIN, 100% of missed-recall, 100% of cross-seed disagreements.
