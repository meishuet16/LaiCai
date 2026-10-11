# RetainIQ v2 — Team Change Log

This file records the implementation, verification evidence, limitations, and
handoffs that accompany repository commits. Entries are newest first.

## 1. Purpose

Keep cross-part changes traceable without inventing implementation or model
evidence. Every code or documentation commit includes one entry.

## 2. Evidence labels

- `real`: verified against a live external system or real authorized dataset.
- `synthetic`: verified against the repository's synthetic evaluation data.
- `assumption`: configured scenario input, not measured performance.
- `N/A`: no data/model evidence is claimed by the change.

## 3. Entry template

```text
### <UTC timestamp> — <member/agent> — <branch> — <commit subject>
- Changed: <paths and behavior>
- Contracts/downstream: <API, migration, and owner impact>
- Verification: <actual PASS/FAIL/NOT RUN commands>
- Evidence: <real/synthetic/assumption/N/A and limitations>
- Blockers/handoff: <known blockers and next action>
```

## 4. Entries

### 2026-10-11T00:15:14Z — Codex — `codex/connect-main-review` — `deploy: add hosted dashboard API service`

- Changed: added `laicai-dashboard-api` to `render.yaml`; added its minimal Python requirements and startup command; added a compact, credential-free `backend/decision/dashboard_seed.db`; and added a reproducible seed builder that retains only the 30-account dashboard cohort.
- Contracts/downstream: the new service exposes the existing `/health` and `/v1/dashboard/*` FastAPI contracts without changing the existing `laicai-api` WSGI service. At process start it copies the bundled SQLite seed to ephemeral runtime storage and provisions a fresh tenant-scoped internal reader credential. The frontend deployment must set `VITE_API_BASE_URL` to the new service URL and rebuild.
- Verification: PASS `npm run test:frontend` (39); PASS `python -m pytest tests/decision -q` with `PYTHONPATH=src;tests` (92); PASS `python -m pytest tests/test_data_foundation.py tests/test_member1_api_handoff.py -q` with `PYTHONPATH=src;tests` (56); PASS `npm run build`; PASS local hosted-startup smoke for `/health`, accounts, integrations, cases, learning, and Vercel-origin CORS preflight. The unrestricted `pytest tests -q` collection was also attempted and failed because optional scikit-learn is not installed and several tests use sibling imports that require `tests` on `PYTHONPATH`; the scoped suites above passed.
- Evidence: `synthetic`. The checked-in seed contains the source-backed synthetic evaluation cohort only. It carries no service-principal credential and all copied integration credential digests are rotated. No production performance, causal retention, or saved-revenue claim is introduced.
- Blockers/handoff: create the new Render service from the pushed commit, verify its public API/CORS, update the production Vercel `VITE_API_BASE_URL`, redeploy the frontend, and run browser-to-API verification.
