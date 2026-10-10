# RetainIQ Data Foundation Implementation Plan

> **For agentic workers:** Execute inline against the current checkout. Keep the canonical requirements below as the global contract and stage only this workstream.

**Goal:** Add a tenant-scoped Part 1 data foundation for validated live ingestion, point-in-time history, subscription valuation, import/replay, and downstream storage contracts.

**Architecture:** Use Python's standard library and SQLite because the checkout contains no application stack, package configuration, or database layer. A SQL migration defines tenant-aware canonical tables; small service modules implement authenticated event intake, explicit identity mapping, historical import/replay, as-of access, and MRR. The HTTP surface stays limited to `POST /v1/ingest/events` and `GET /v1/integrations`.

**Tech Stack:** Python 3.14 standard library, SQLite, `unittest`, WSGI.

## Global Constraints

- Derive tenant scope from a server-authenticated integration token; never trust payload `tenant_id`.
- Require explicit `(tenant_id, source, external_customer_id) -> customer_id` mapping.
- Persist only allowlisted, typed event fields; never persist the raw request body or credential.
- An as-of fact must satisfy `occurred_at <= as_of` and `COALESCE(source_available_at, received_at) <= as_of`.
- Preserve `occurred_at`, `received_at`, `source_available_at`, `as_of`, and `generated_at` separately.
- A cancellation request is not effective churn; a failed payment is not churn.
- Store money in integer minor units and ISO currency; never aggregate mixed currencies or replace missing prices with zero.
- Keep feature and churn-label storage as shared contracts; do not implement Part 2 feature engineering, label generation, or prediction logic.
- Record the dataset as `NOT_READY` unless authorized longitudinal evidence is found.
- Every project-file commit includes a truthful `TEAM_LOG.md` entry; do not push or merge.

---

## Planned Files

- Create `retaniq/__init__.py`, `retaniq/data_foundation.py`, `retaniq/api.py`, `retaniq/importer.py`, and `retaniq/__main__.py` for initialization, domain operations, WSGI endpoints, CSV import/replay, and CLI routing.
- Create `migrations/001_data_foundation.sql` for tenants, integrations, canonical customers/identities, typed events, subscription history/projection, and Part 2 storage contracts.
- Create `tests/test_data_foundation.py` for API auth, tenant isolation, validation/minimization, idempotency, identity, as-of reconstruction, MRR, importer/replay, and health.
- Create `DATASET_CARD.md` and expand `README.md` with setup, API/auth, importer/replay, valuation policy, limitations, and downstream handoff.
- Add the first accurate `TEAM_LOG.md` entry in the same commit as the implementation.

## Tasks

### Task 1: Prove the canonical contracts with tests

- Test unauthenticated WSGI ingestion returns 401.
- Test valid token context supplies tenant/source, and payload tenant or unapproved fields are rejected without echoing values.
- Test explicit identity mapping, safe unknown-identity rejection, duplicate idempotency, and conflicting duplicate detection.
- Test point-in-time filters exclude both late availability and late receipt.
- Test subscription history, pending cancellation, and payment failure remain distinct.
- Test monthly/quarterly/annual/weekly recurring MRR, discounts, missing pricing, multiple subscriptions, mixed currency, and zero-decimal minor units.
- Test shared feature/label/prediction storage constraints without implementing downstream logic.
- Test CSV import summary and replay preserve source timestamps.
- Test tenant-scoped integration health returns no credentials.

### Task 2: Implement canonical storage and core services

- Add the SQLite migration and standard-library database helpers.
- Add tenant/integration/customer provisioning helpers; persist only SHA-256 token digests.
- Validate typed allowlisted event payloads; normalize UTC timestamps and monetary fields.
- Store a safe event envelope plus category-specific usage, billing, and subscription rows in one transaction.
- Fold append-only subscription changes at a cutoff and calculate account MRR with policy `mrr-monthly-v1`.
- Add `feature_snapshots`, `churn_labels`, and unified `predictions` storage contracts with tenant-aware keys.

### Task 3: Add authenticated HTTP, historical import, replay, and health

- Expose `POST /v1/ingest/events` and `GET /v1/integrations` through WSGI.
- Add canonical-mapping CSV import that calls the same normalization service and only trusts availability when explicitly mapped by an operator.
- Add replay enumeration ordered by historical availability, keeping original event and availability time.
- Return unknown health when no source evidence exists; never return a token/hash.

### Task 4: Document, verify, log, and commit

- Document the prototype stack, environment-free local commands, contracts, MRR policy, dataset gate, limitations, and Member 2/3 handoff.
- Run `python -m unittest discover -s tests -v`, compile checks, CLI help, and `git diff --check`.
- Inspect staged paths and content; include only Part 1 files plus `TEAM_LOG.md`.
- Commit locally on `feature/data-foundation`; do not push or merge.
