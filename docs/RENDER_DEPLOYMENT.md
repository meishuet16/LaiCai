# Render deployment: Data Foundation API

This guide configures the existing Data Foundation WSGI application for a
Render web service. The Blueprint builds the package and starts Gunicorn; it
does not apply database migrations or import a dataset during build or start.

## Configure the backend before the first deploy

For the first deployment, use **New → Web Service** in the Render Dashboard
and connect the repository and the approved deployment branch. Configure the
creation form with the settings from `render.yaml`:

| Setting | Value |
| --- | --- |
| Name | `laicai-api` |
| Language / runtime | Python |
| Region | Singapore (`singapore`) |
| Root directory | Repository root (leave the Dashboard field empty; Blueprint `rootDir: .`) |
| Build command | `pip install -r requirements-render.txt` |
| Start command | `gunicorn render_wsgi:application --bind 0.0.0.0:$PORT` |
| Health check path | `/healthz` |
| Auto-deploy | Off |

In the creation form's **Advanced** section, enter exactly one database
configuration below, including the restricted app DSN for Supabase, **before
clicking Create Web Service**. For Supabase, first complete the authorized
database preparation described below. Create Web Service immediately starts
the first build and deployment with those values; auto-deploy being off does
not prevent this initial deployment. See [Render Web Services](https://render.com/docs/web-services).

The checked-in Blueprint intentionally has no database environment variables.
Do not use **Deploy Blueprint** to create a new service from it unchanged:
that action immediately provisions and starts the service, leaving no interval
to supply database settings before startup. If initial Blueprint creation is
preferred, first add an `envVars` entry with `sync: false` for **each** variable
in the selected mode below, under the `laicai-api` service. Render then prompts
for those values during initial Blueprint creation; supply all of them before
Deploy Blueprint. Include only the selected mode's keys and commit no values
or credentials. See [Blueprint secret prompts](https://render.com/docs/blueprint-spec#prompting-for-secret-values).

`autoDeployTrigger: "off"` disables deployments triggered by Git commits.
Blueprint configuration sync is separate: for any Blueprint you create or
adopt, also set **Blueprint Settings → Auto Sync → No**. Apply later Blueprint
changes only with an authorized Manual Sync. See [Render Blueprint sync settings](https://render.com/docs/infrastructure-as-code#disabling-automatic-sync).

For later backend changes, update the service's protected **Environment**
settings and perform an authorized deployment. The same application code runs
against either backend. Remove `RETAINIQ_SQLITE_PATH` and
`RETAINIQ_DATABASE_URL` entirely when selecting Supabase; even empty values
conflict with its configuration. Leave `RETAINIQ_DATABASE_URL` unset for the
SQLite settings below so the stated path is used.

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
