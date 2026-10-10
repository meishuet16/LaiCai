# Member 2 Final Integration Report

**Final status: BLOCKED — integration code is verified, but no genuine Prompt 34 three-horizon fitted and calibrated model bundle exists.**

## Integrated commits

| Track | Source commit | Integration result |
|---|---|---|
| A | `74b03407c82f2fcf6c6888279ff3a18973acae9b` | Already an ancestor of the starting branch; not cherry-picked again. |
| B | `3a295f07504901da58d6390b3734bb8017148afd` | Cherry-picked as `a8948d5`; only the additive `TEAM_LOG.md` conflict was resolved, preserving both entries. |
| C | `5119e89e4c4c2e03286666e5753534730e90203d` | Cherry-picked as `43425c3`; only the additive `TEAM_LOG.md` conflict was resolved, preserving both entries. |

Integration was performed in the separate `codex/member2-final-integration` worktree. No reset, force-push, main-branch modification, training, calibration fitting, historical preparation, held-out evaluation, or dataset generation was performed.

## Existing artifact inventory

| Required item | Status | Evidence |
|---|---|---|
| Prompt 34 synthetic source manifest | AVAILABLE | Dataset `synthetic-saas-v1-2-prompt34_demo-s2034-316bec2deb46`; existing recorded SHA-256 `75a687071f3fee639e3ce057b59404834accb2fc01ec39a7cb122cb9883e5aac`. |
| Finalized prepared dataset manifest | MISSING | `prompt34-three-horizon-reduced-v1/prepared/preparation_manifest.json` is absent. The directory contains partial TRAIN/VALIDATION files and `calibration_features.jsonl.gz.tmp`. |
| Fitted 7/14/30 LightGBM artifacts | MISSING | No Prompt 34 model artifact files were found. |
| Fitted 7/14/30 calibration artifacts | MISSING | No Prompt 34 calibrator artifact files were found. |
| Shared model bundle ID | MISSING | No finalized Prompt 34 bundle manifest or metadata exists. |
| Prompt 34 model/calibrator hashes | MISSING | No fitted artifacts exist to supply the required recorded hashes. |
| Compatible finalized feature schema | MISSING | The incomplete preparation has no final manifest/schema contract that can be matched to a three-horizon bundle. |

Pre-existing Prompt 31 files include only synthetic, uncalibrated 14-day and 30-day LightGBM models. They are not Prompt 34 artifacts, do not provide a 7-day model or calibrators, and were not substituted for the required bundle.

## Supported horizons

The integrated code and synthetic fixture contract structurally cover 7, 14, and 30 days. **Operationally supported Prompt 34 horizons: none**, because no finalized fitted/calibrated bundle exists. Production scoring remains `MODEL_BUNDLE_NOT_READY`.

## Minimal verification

Exactly one focused pytest invocation was run with a 90-second subprocess timeout:

```text
tests/test_lightgbm_model.py::test_missing_or_incompatible_artifacts_fail_safely
tests/test_horizon_coherence.py::test_cumulative_max_adjustment_is_explicit_and_ordered
tests/test_operational_inference.py::test_replay_is_chronological_and_returns_persisted_risk_changes_without_outcomes
```

Result: **PASSED — 3 passed in 4.94s.** This covers safe artifact loading/compatibility failure, monotonic horizon adjustment, and chronological prediction replay/persistence without fitting a model.

Reused Track evidence, not rerun: Track B reported 22 focused model tests passing; Track C reported its synthetic save/load → calibration → SHAP → replay → persistence fixture passing. Track C's fixture is test-only and is not a Prompt 34 artifact bundle.

## End-to-end smoke status

**BLOCKED and intentionally skipped.** The prerequisite finalized prepared manifest plus fitted 7/14/30 models and calibrators is absent. Running Load → Predict → Calibrate → SHAP → Replay → Persist would require fabricating evidence, using the ineligible Prompt 31 artifacts, or performing prohibited fitting. No held-out evaluation was run.

## Remaining Member 3/4 blockers

- Member 3 must keep the model-unavailable route and must not rank, route, or trigger actions from fabricated or uncalibrated probabilities.
- Member 4 must not display Prompt 34 scores, calibration quality, model-backed replay, or outcome claims until a complete verified bundle and persisted predictions exist.
- Both consumers still need a genuine shared bundle ID, compatible feature/model/calibration versions, artifact hashes, and all three horizons before enabling scored workflows.
- Synthetic evidence remains non-production. Authorized real longitudinal evidence and the existing approval/readiness gates remain required for any production claim.

