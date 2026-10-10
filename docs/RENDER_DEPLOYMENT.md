# Render deployment: Data Foundation API

This guide configures the existing Data Foundation WSGI application for a
Render web service. The Blueprint builds the package and starts Gunicorn; it
does not apply database migrations or import a dataset during build or start.

## Configure the backend before the first deploy

Create the web service from `render.yaml`, then set exactly one of the
database configurations below in the service's protected Environment
settings before starting a manual deploy. The Blueprint leaves database
selection to the operator so the same application code can run against either
backend.

## Temporary SQLite staging

For a short-lived staging deployment, set:

```text
RETAINIQ_DATABASE_BACKEND=sqlite
RETAINIQ_SQLITE_PATH=/tmp/retainiq-staging.sqlite3
```

This is temporary staging storage under `/tmp`. Its contents are lost when the
service restarts or redeploys, so it is unsuitable for persistent production
data. The existing `create_app` startup path initializes the SQLite schema at
the configured path. This SQLite initialization is separate from PostgreSQL
schema migrations.

## Supabase PostgreSQL runtime

For a prepared Supabase database, configure the runtime backend and the
existing project and connection settings using values from the intended
project:

```text
RETAINIQ_DATABASE_BACKEND=supabase
RETAINIQ_SUPABASE_PROJECT_URL=https://<PROJECT_REF>.supabase.co
RETAINIQ_SUPABASE_EXPECTED_PROJECT_REF=<PROJECT_REF>
RETAINIQ_SUPABASE_CONNECTION_MODE=<DIRECT_OR_POOLER_MODE>
RETAINIQ_SUPABASE_DB_APP_DSN=<RESTRICTED_APP_LOGIN_DSN>
```

Set the connection mode to `DIRECT`, `SESSION_POOLER`, or
`TRANSACTION_POOLER` to match the host and port in the dashboard-provided app
DSN.

Use placeholders in documentation and examples; enter real values only in the
Render service's protected environment settings. The app DSN must use a
restricted application database login with only the privileges required by
the runtime. Never use `postgres`, `service_role`, or migration credentials
for the app login, and never commit credentials to the repository.

Optional migration or maintenance DSNs belong only in authorized operator
workflows. Do not configure those credentials on the runtime service. Supabase
schema migrations are applied only through an explicit, authorized operator
process. Before runtime use, operators must apply the approved migrations and
prepare the database. Application startup verifies the PostgreSQL schema; it
does not apply migrations. Dataset imports are also explicit operator work and
never run during the Render build or service start.

## Runtime behavior and scope

The Render health check uses `GET /healthz`. Existing authentication and
tenant-isolation behavior remain with the Data Foundation application; this
deployment configuration does not change authenticated routes or tenant
scope. Member 3's Decision Engine is a separate workstream and is outside this
deployment's scope.
