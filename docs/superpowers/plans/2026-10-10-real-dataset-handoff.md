# Real Dataset Gate and Member 2 Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-backed real-data readiness decision and a reproducible Member 1 to Member 2 handoff without changing Member 2's prediction or label implementation.

**Architecture:** Audit candidate provenance and access terms first; integrate only data whose authorization and temporal semantics are verified. With no authorized real dataset available locally, preserve the `NOT_READY` decision, document the concrete access blocker, and provide a synthetic, runnable example of the existing tenant-scoped point-in-time query API.

**Tech Stack:** Python standard library, existing SQLite prototype, `unittest`, Markdown, Git.

## Global Constraints

- Preserve the existing `feature/data-foundation` branch and commits `862025e`, `7bbab08`, and `3450afa`.
- Do not rewrite Member 2 prediction or label-building work; Member 2 owns feature engineering, labels, temporal splits, training, calibration, and evaluation.
- Do not invent events, availability times, churn-effective dates, observation coverage, labels, or probabilities.
- Do not accept external dataset terms on the user's behalf or commit restricted customer data.
- Do not begin a full PostgreSQL migration; document the SQLite/PostgreSQL gap accurately.
- Every local project commit must include a truthful `TEAM_LOG.md` entry in that same commit.
- Do not push, merge, or create a pull request.

---

### Task 1: Verify dataset candidates and acquisition boundary

**Files:**
- Read: outer project requirements and `AGENT.md`, `TEAM_LOG.md`; repository importer, replay, API, migration, tests, and current status
- Modify: `DATASET_CARD.md`

**Interfaces:**
- Consumes: official dataset pages and competition terms; current `retaniq` import/query APIs.
- Produces: a measured-vs-unavailable evidence record, candidate comparison, permission decision, and precise `NOT_READY` status.

- [x] Confirm candidate source evidence, access requirements, use restrictions, and suitability. Record only counts actually measured from locally acquired files; if no files are authorized/available, state that counts were not measured.
- [x] Check local Kaggle CLI availability without reading credentials or accepting terms. Record the exact command/tool availability result.
- [x] Update the dataset card with primary source URLs, suitability assessment, authorization blocker, readiness, and what exact evidence is missing.

### Task 2: Add a runnable point-in-time handoff example using TDD

**Files:**
- Create: `examples/member2_as_of_history.py`
- Create: `tests/test_member2_handoff.py`

**Interfaces:**
- Consumes: `create_tenant(path, tenant_id)`, `create_integration(...)`, `authenticate_integration(...)`, `ingest_event(...)`, `list_eligible_accounts_as_of(...)`, `get_account_snapshot_as_of(...)` from `retaniq.data_foundation`.
- Produces: `load_example_history(as_of: str) -> dict` returning one eligible synthetic account and its time-valid snapshot, with future events excluded and no labels or probabilities.

- [x] Write a test that imports `load_example_history`, checks one eligible account, and verifies an event after `as_of` is absent.
- [x] Run `python -m unittest discover -s tests -p test_member2_handoff.py -v`; confirm the expected `ModuleNotFoundError` before implementation.
- [x] Implement the smallest isolated temporary-SQLite example, explicitly label its records synthetic, and use existing ingestion/query functions.
- [x] Run the focused test and executable example; inspect output for absence of labels/probabilities.

### Task 3: Document the Member 2 contract and compliance crosswalk

**Files:**
- Create: `docs/MEMBER1_TO_MEMBER2_DATA_HANDOFF.md`
- Create: `docs/MEMBER1_DATA_CONTRACT_COMPLIANCE.md`
- Modify: `DATASET_CARD.md`

**Interfaces:**
- Consumes: verified candidate audit, code paths, schema, tests, example output.
- Produces: exact source/access status, commands and local access path, canonical schema and mapping boundaries, identity and timestamp semantics, PIT example, horizon/support gaps, and criteria-by-criteria compliance statuses with evidence.

- [x] Document existing canonical usage, billing, subscription, identity, availability, purpose, and tenant contracts; clearly distinguish verified facts from future candidate mapping work.
- [x] Provide an executable command and sample output for the synthetic example; explain that it demonstrates API use only and does not clear real-data readiness.
- [x] Assess each required criterion as `PASS`, `PARTIAL`, `BLOCKED`, `FAIL`, or `NOT VERIFIED`, including storage engine, HTTP endpoints, authorization/purpose, PIT, MRR/currency, labels, Member 2 training readiness, Member 3 valuation, minimization, and replay.

### Task 4: Verify, log, and commit the handoff

**Files:**
- Modify: `TEAM_LOG.md`
- Modify: outer `D:\dunno\dormathon\TEAM_LOG.md` as a synchronized sidecar if present

**Interfaces:**
- Consumes: all changed docs/example/tests and the pre-existing 31-test suite.
- Produces: reproducible command/results record and one local commit containing all relevant changes plus the repository `TEAM_LOG.md` entry.

- [x] Run the focused handoff test, executable example, and complete existing test suite; report synthetic/example checks separately from real-data integration evidence.
- [x] Review the working tree and `git diff --check`; all pending paths are task files, but the final staged diff and `TEAM_LOG.md` inclusion will be checked before commit.
- [x] Commit locally on `feature/data-foundation`; do not push or merge.
