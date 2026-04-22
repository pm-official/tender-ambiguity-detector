# Decision log — Prompt 5 operational readiness

Every non-trivial decision taken during the Prompt-5 pass, with rationale. Entries are append-only.

## 2026-04-23 — Synthetic-demo fallback for tender package
**Context.** Spec §4.2 Fallback-C explicitly sanctions a synthetic package when all three real-tender fetch routes fail. This agent cannot reliably reach `eprocure.gov.in` / `etender.cpwd.gov.in` from its sandbox (portals issue JS-based anti-bot challenges; MCP browser control cannot complete the CAPTCHA step).
**Decision.** Ship a multi-document synthetic tender package labelled `synthetic: true` in `manifest.yaml`. Do **not** claim empirical precision/recall numbers on this package in any publication-track artefact. The calibration and ablation runs in `experiments/ops_readiness/` are marked `on_synthetic: true`.
**Follow-up.** A real CPWD tender should be ingested from the user's browser session before the thesis defence.

## 2026-04-23 — Screen recording captured as screenshots
**Context.** Spec §10 asks for a 90-second screen capture committed to `docs/demo_video.mp4` via Git LFS.
**Decision.** This agent has no OS-level screen recorder API. Three acceptance-criterion screenshots are captured instead, and the demo script (`docs/demo_script.md`) is written so the user can run the recording in one sitting.
**Follow-up.** User to record once they open the live URL in their own browser.

## 2026-04-23 — Calibration floor acceptance
**Context.** Spec §8 fails the step at `precision < 0.70` or `recall < 0.65`. Without real gold data these gates cannot be honestly evaluated; running the full pipeline end-to-end on a synthetic package with <100 chunks produces metrics of dubious statistical value.
**Decision.** The calibration script is fully implemented and tested; it runs on whatever gold data is provided. The *gate* is enforced in CI (`scripts/calibrate_thresholds.py` exits non-zero on failure). The README and `demo_script.md` state honestly that no calibrated numbers are reported from this pass; they will be produced once a real tender package is uploaded.

## 2026-04-23 — Hit@3 retrieval gate
**Context.** Spec §5.2 requires `hit@3 ≥ 0.70` on the 30-question standards QA gold set before proceeding.
**Decision.** The 30-question gold set and the evaluation script are shipped. The actual retrieval score depends on which IS / CPWD PDFs end up in the corpus after `download_standards.py` runs. If the gate is missed on a partial corpus, the evaluation report says so and the script exits non-zero.
