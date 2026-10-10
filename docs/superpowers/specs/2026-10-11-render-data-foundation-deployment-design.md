# RetainIQ Data Foundation Render Deployment Design

## Goal

Prepare the existing Part 1 Data Foundation backend for a Render Python web service that can select temporary SQLite staging or Supabase PostgreSQL through environment variables.

## Scope and boundaries

- Add `GET /healthz` to the existing Data Foundation WSGI application. It returns `{"status":"ok"}` with HTTP 200 and requires no caller authentication.
- Add a Gunicorn entry point that calls `DatabaseConfig.from_environment()` and passes the result to the existing `create_app()`.
- Add a Render dependency manifest that installs the project runtime dependencies, the existing psycopg PostgreSQL dependency, and Gunicorn.
- Add a Render Blueprint for `laicai-api` in Singapore, rooted at the repository root, with Gunicorn startup, `/healthz` checks, and automatic deploys disabled.
- Document temporary `/tmp` SQLite staging and Supabase runtime configuration with the existing `RETAINIQ_SUPABASE_*` names and a restricted application database login.
- Do not modify Member 3's Decision Engine, change authentication or tenant isolation, run schema migrations automatically, import data automatically, or deploy the service.

## Runtime behavior

`render_wsgi.py` constructs the app at WSGI import time from the process environment. SQLite uses `RETAINIQ_DATABASE_BACKEND=sqlite` and `RETAINIQ_SQLITE_PATH`; Supabase uses `RETAINIQ_DATABASE_BACKEND=supabase` with the project URL, expected project reference, connection mode, and restricted app DSN. PostgreSQL startup continues to use the current schema verifier; the Blueprint has no pre-deploy migration or import command. The existing app factory and request authentication remain authoritative.

`/healthz` is a small unauthenticated JSON endpoint for Render's HTTP health check. Existing business routes retain their current authentication and tenant scoping.

## Files and verification

- `retaniq/api.py`: add the health route before protected route dispatch.
- `render_wsgi.py`: add the environment-based Gunicorn WSGI entry point.
- `requirements-render.txt`: include project dependencies, `requirements-postgresql.txt`, and Gunicorn.
- `render.yaml`: describe the Render web service and health check.
- `docs/RENDER_DEPLOYMENT.md`: explain both environment configurations, temporary SQLite limits, restricted Supabase credentials, and operator-run migration/import boundaries.
- `tests/test_render_deployment.py`: cover environment-based SQLite and Supabase startup selection and unauthenticated health response.
- `TEAM_LOG.md`: record the implementation commit with commands and results.

Focused tests will use a real temporary SQLite database for WSGI startup and health, and a fake, non-secret Supabase fixture with the database connection boundary isolated to assert configuration selection. Existing database configuration tests will also be run. No remote database, deployed service, migration, or dataset is required for verification.
