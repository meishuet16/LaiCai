# Synthetic SaaS v1.2 Implementation Plan

> **For agentic workers:** Follow this plan in order. Keep each change in the Member 1 scope and update `TEAM_LOG.md` in the same commit.

**Goal:** Repair the synthetic source history and canonical importer, generate v1.2 QUICK/STANDARD/FULL, and provide a verified STANDARD dataset handoff for Member 2.

**Architecture:** Stream deterministic account histories into versioned CSV/gzip exports. Keep source observation intervals separate from canonical event attributes, bind each SQLite file to one immutable dataset manifest, and ingest normalized records in resumable bounded batches. An independent validator and a read-only smoke command verify source evidence through authorized point-in-time reads.

**Tech Stack:** Python standard library, SQLite migrations, `unittest`, CSV/gzip, SHA-256.

## Global Constraints

- Preserve the canonical event allowlist and Member 1–4 shared identifiers, time semantics, target semantics, purpose grants, and route/status enums.
- Use a 24-month simulation from `2024-10-01T00:00:00Z` through `2026-10-01T00:00:00Z` (exclusive end) for default profiles.
- Keep all generated artifacts and databases outside Git; never overwrite v1.1.
- Do not train models, modify KKBox, push, merge, or create a PR.
- Unknown or censored outcomes remain unknown; generator latent values never enter model-source files.

---

### Task 1: Capture v1.2 regressions

**Files:**
- Create/modify: `tests/test_synthetic_generator.py`
- Create/modify: `tests/test_synthetic_integration.py`
- Modify: `tests/test_data_foundation.py`

- [ ] Add failing tests for version/date defaults, daily completed-window usage semantics, source coverage intervals, source-verified scenario records, and a PASS quality status.
- [ ] Add failing tests for dataset identity mismatch, authorized coverage reads, batch idempotency/resume, future-start subscription exclusion, calendar period arithmetic, and partial subscription cancellation.
- [ ] Run each targeted `python -m unittest ... -v` command and confirm failures identify missing behavior.

### Task 2: Implement calendar lifecycle and stochastic daily usage

**Files:**
- Modify: `retaniq/synthetic/config.py`
- Modify: `retaniq/synthetic/generator.py`
- Create/modify: `retaniq/synthetic/scenarios.py`
- Modify: `retaniq/synthetic/validator.py`

- [ ] Implement interval arithmetic with end-of-month preservation, leap-year handling, and interval counts.
- [ ] Generate daily completed-window aggregates, event-backed feature adoption, independent per-profile deterministic random streams, stochastic lifecycle outcomes, explicit renewals, plan transitions, partial cancellation, and later reactivation episodes.
- [ ] Export weekly customer/source coverage intervals with explicit status and availability; keep delayed/outage source periods separate from observed low activity.
- [ ] Independently detect scenarios from source records, calculate quality and label feasibility, and validate hashes/schema/reproducibility.
- [ ] Run focused red-green tests, then QUICK generation and validation.

### Task 3: Enforce dataset storage identity and coverage reads

**Files:**
- Create: `migrations/004_dataset_identity_and_observation_coverage.sql`
- Modify: `retaniq/data_foundation.py`
- Modify: `tests/test_data_foundation.py`

- [ ] Bind empty SQLite databases to dataset ID, manifest digest, generator version, and target policy; reject a conflicting or unbound non-empty database.
- [ ] Add validated, source-granted coverage ingestion and retention-authorized as-of coverage reads.
- [ ] Verify historical eligibility, known-cancellation exclusion, partial termination, tenant/source isolation, and source-availability time.

### Task 4: Batch and resume canonical imports

**Files:**
- Modify: `retaniq/data_foundation.py`
- Modify: `retaniq/synthetic/canonical_adapter.py`
- Modify: `retaniq/synthetic/__main__.py`
- Modify: `tests/test_synthetic_integration.py`

- [ ] Add customer/identity batch provisioning with validation and conflict checks.
- [ ] Add bounded event and coverage batches that normalize every row, use row savepoints, rebuild each affected subscription projection once per batch, and persist checkpoints atomically.
- [ ] Add dataset mismatch preflight and repeat-import verification.
- [ ] Measure QUICK first/repeat and STANDARD first/repeat runtime, accepted/duplicate/rejected counts, database size, and memory where available.

### Task 5: Verify chronology and the dataset family

**Files:**
- Modify: `retaniq/synthetic/generator.py`
- Modify: `retaniq/synthetic/validator.py`
- Modify: `tests/test_synthetic_generator.py`
- Modify: `tests/test_synthetic_integration.py`

- [ ] Export dataset-bound split windows and a weekly account-cutoff policy with horizon and source-coverage maturity embargoes.
- [ ] Report eligible accounts/cutoffs, known cancellations, positive/negative/unknown outcomes by horizon and split, distinct accounts/episodes, usage sufficiency, and observation coverage.
- [ ] Set predetermined acceptance rules in validator code before evaluating the final population.
- [ ] Generate and validate all three profiles; independently reproduce QUICK and one representative STANDARD result.

### Task 6: Import STANDARD and prove handoff usability

**Files:**
- Create: `examples/member2_synthetic_smoke.py`
- Modify: `retaniq/synthetic/__main__.py`
- Modify: `docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`
- Modify: `docs/SYNTHETIC_SAAS_DATASET.md`
- Modify: `docs/HYBRID_DATASET_STRATEGY.md`
- Modify: `docs/MEMBER1_TO_MEMBER2_DATA_HANDOFF.md`
- Modify: `DATASET_CARD.md`

- [ ] Import and validate the complete STANDARD dataset in its own private SQLite database.
- [ ] Provide exact-principal provisioning and executable smoke commands; independently check 7/14/30 source-backed outcomes in a separate oracle section.
- [ ] Verify Member 3/4 source compatibility without adding downstream workflows or fake predictions, approvals, or revenue outcomes.
- [ ] Keep the real-data gate and KKBox decision unchanged.

### Task 7: Generate FULL, finalize evidence, and commit

**Files:**
- Modify: `TEAM_LOG.md`
- Stage only the source, tests, migrations, plans/spec, and documentation touched by this task.

- [ ] Generate and validate FULL; benchmark a bounded resumable import and complete FULL import only when measured resource use permits.
- [ ] Run the complete test suite, compile checks, CLI help, smoke test, manifest verification, and `git diff --check`.
- [ ] Confirm generated data/database files are outside Git, update `TEAM_LOG.md` with actual measurements, and commit locally on `member1`.
- [ ] Verify the commit SHA and clean working tree; leave push and merge untouched.
