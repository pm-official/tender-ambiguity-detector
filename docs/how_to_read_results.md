# How to read the results

1. **Triage by verdict**: UNRESOLVED flags are the ones you need to address. RESOLVED flags have supporting context.
2. **Watch agreement_rate**: a 2/3 agreement flag is confirmed; 1/3 is in the review queue.
3. **Open the 3 expanders on each flag card** — they show the ensemble, adjudication, and rewrite respectively.
4. **The false-resolution rate is the safety metric** — keep it ≤ 10%. A high FRR means RESOLVED labels are untrustworthy.
5. **For G/H flags**, check the Graph Explorer tab to see the priority rule / quantity mismatch that drove the flag.
