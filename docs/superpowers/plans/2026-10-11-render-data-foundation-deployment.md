# RetainIQ Data Foundation Render Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the RetainIQ Part 1 Data Foundation WSGI backend for Render with environment-selected SQLite staging or Supabase PostgreSQL.

**Architecture:** Add `/healthz` to the existing WSGI router, then expose the existing `create_app()` through a Gunicorn import target that reads `DatabaseConfig.from_environment()`. Render-specific dependencies, Blueprint settings, and operator instructions live in separate root-level and deployment-doc files. The existing app remains responsible for authentication, tenant isolation, SQLite initialization, and PostgreSQL schema verification.

**Tech Stack:** Python 3.11+, existing `retaniq.api` WSGI app, `DatabaseConfig`, Gunicorn, Render Blueprint YAML, unittest/pytest.

## Global Constraints

- The service is the RetainIQ Data Foundation only. Do not modify or deploy Member 3's separate Decision Engine.
- `GET /healthz` returns `{"status":"ok"}` with HTTP 200.
- SQLite staging uses `RETAINIQ_DATABASE_BACKEND=sqlite` and `RETAINIQ_SQLITE_PATH=/tmp/retainiq-staging.sqlite3`; label it temporary and not persistent production storage.
- Supabase production uses `RETAINIQ_DATABASE_BACKEND=supabase`, existing `RETAINIQ_SUPABASE_*` variables, and a restricted application database credential. Never hardcode Supabase credentials.
- Preserve existing route authentication and tenant isolation.
- Do not run automatic PostgreSQL migrations or dataset imports. Do not deploy, push, or merge.
- The final implementation commit must include `TEAM_LOG.md` with real verification results.

---

### Task 1: Add the Data Foundation health endpoint

**Files:**
- Modify: `retaniq/api.py`
- Create: `tests/test_render_deployment.py`

**Interfaces:**
- Consumes: `create_app(DatabaseConfig | path)` and the existing `_response` helper.
- Produces: `GET /healthz` returns status 200 and the JSON object `{"status":"ok"}` without a bearer token.

- [x] **Step 1: Write the failing health check test**

```python
import io
import json

from retaniq.api import create_app
from retaniq.database_config import DatabaseConfig


def request(app, method, path):
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
    }
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    response["body"] = json.loads(b"".join(app(environ, start_response)))
    return response


def test_healthz_returns_ok_without_authentication(tmp_path):
    app = create_app(DatabaseConfig.from_value(tmp_path / "health.sqlite3"))
    response = request(app, "GET", "/healthz")
    assert response["status"] == "200 OK"
    assert response["body"] == {"status": "ok"}
```

- [x] **Step 2: Run the test and confirm the expected 404**

Run: `python -m pytest tests/test_render_deployment.py -q`

Expected before implementation: the app returns `404 Not Found` for `/healthz`.

- [x] **Step 3: Add the health route before protected dispatch**

```python
        if method == "GET" and path == "/healthz":
            return _response(start_response, HTTPStatus.OK, {"status": "ok"})
```

- [x] **Step 4: Re-run the health test**

Run: `python -m pytest tests/test_render_deployment.py -q`

Expected: the health test passes, and the endpoint requires no authorization header.

- [x] **Step 5: Commit Task 1 with a `TEAM_LOG.md` entry**

Commit subject: `feat: add Data Foundation health check`.

### Task 2: Add environment-based Gunicorn startup coverage

**Files:**
- Create: `render_wsgi.py`
- Modify: `tests/test_render_deployment.py`

**Interfaces:**
- Consumes: `DatabaseConfig.from_environment()` and `retaniq.api.create_app()`.
- Produces: module-level WSGI callable `render_wsgi.application`.

- [x] **Step 1: Add failing tests for SQLite and Supabase environment selection**

Extend `tests/test_render_deployment.py` with a test that imports the WSGI module under a temporary SQLite environment and verifies it constructs a real app backed by the requested SQLite file. Add a separate Supabase test using a fake test DSN and a patched `retaniq.api.create_app`; assert the factory receives a `DatabaseConfig` with `is_supabase` true and `is_postgresql` true. Do not open a remote connection in this unit test.

- [x] **Step 2: Run the focused tests and confirm the WSGI module is missing**

Run: `python -m pytest tests/test_render_deployment.py -q`

Expected before implementation: import of `render_wsgi` fails because the module does not exist.

- [x] **Step 3: Create the WSGI import target**

```python
from retaniq.api import create_app
from retaniq.database_config import DatabaseConfig

application = create_app(DatabaseConfig.from_environment())
```

- [x] **Step 4: Re-run focused deployment tests**

Run: `python -m pytest tests/test_render_deployment.py -q`

Expected: health, SQLite WSGI startup, and Supabase configuration-selection tests pass.

- [x] **Step 5: Commit Task 2 with a `TEAM_LOG.md` entry**

Commit subject: `feat: add environment-configured Render WSGI entry point`.

### Task 3: Add Render dependencies, Blueprint, and operator guide

**Files:**
- Create: `requirements-render.txt`
- Create: `render.yaml`
- Create: `docs/RENDER_DEPLOYMENT.md`

**Interfaces:**
- Render installs the project package, existing PostgreSQL dependency list, and Gunicorn from `requirements-render.txt`.
- The Blueprint defines a Python web service named `laicai-api`, region `singapore`, repository root, Gunicorn startup, `/healthz`, and auto deploy off.
- The guide explains the requested SQLite staging variables and Supabase production variables, restricted app credentials, and operator-run migration/import boundaries.

- [x] **Step 1: Write the deployment dependency file**

```text
-e .
-r requirements-postgresql.txt
gunicorn>=26,<27
```

- [x] **Step 2: Write the Render Blueprint**

```yaml
services:
  - type: web
    name: laicai-api
    runtime: python
    region: singapore
    rootDir: .
    buildCommand: pip install -r requirements-render.txt
    startCommand: gunicorn render_wsgi:application --bind 0.0.0.0:$PORT
    healthCheckPath: /healthz
    autoDeployTrigger: "off"
```

- [x] **Step 3: Write `docs/RENDER_DEPLOYMENT.md`**

Include the exact staging values `RETAINIQ_DATABASE_BACKEND=sqlite` and `RETAINIQ_SQLITE_PATH=/tmp/retainiq-staging.sqlite3`; label `/tmp` storage temporary, restart/redeploy-volatile, and unsuitable for persistent production. For Supabase, list the existing project URL, expected project reference, connection mode, and app DSN names. Tell operators to put only a restricted app login in the service, never credentials in the repository, and ensure PostgreSQL schema migrations and dataset imports are run explicitly by their authorized operators before runtime use. State that deployment does not run migrations/imports and that authenticated routes and tenant scope remain unchanged.

- [x] **Step 4: Review the configuration and documentation against the design**

Run: `git diff --check`

Expected: no whitespace errors; all service fields match the requested values; no credential values, migration commands, or import commands appear in the Blueprint startup/build sequence.

- [x] **Step 5: Commit Task 3 with a `TEAM_LOG.md` entry**

Commit subject: `docs: configure Render Data Foundation deployment`.

### Task 4: Focused verification and final implementation commit

**Files:**
- Modify: `TEAM_LOG.md`
- Include: all implementation paths and this plan in the final commit or earlier task commits.

- [x] **Step 1: Run the focused tests for both database modes, WSGI startup, and health**

Run: `python -m pytest tests/test_render_deployment.py tests/test_database_config.py tests/test_supabase_configuration.py -q`

Expected: all selected tests pass. Tests use a temporary local SQLite file and non-secret fake Supabase configuration; they make no remote database connection.

- [x] **Step 2: Check changed-file scope and whitespace**

Run: `git status --short --branch` and `git diff --check`.

Expected: changes are limited to Data Foundation health/WSGI, Render config/dependencies, deployment docs/tests, plan, and `TEAM_LOG.md`; Decision Engine files are absent.

- [x] **Step 3: Commit all remaining implementation and log changes**

Commit subject: `feat: prepare Data Foundation backend for Render`.

Keep the branch local. Do not push, merge, or deploy.
