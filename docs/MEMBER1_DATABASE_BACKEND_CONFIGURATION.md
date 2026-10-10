# Member 1 database backend configuration

This document records the 06B database foundation and the bounded 06D-1
PostgreSQL ingestion/identity/authentication support. It does not claim full
PostgreSQL feature parity.

## Supported configuration

The existing filesystem-path form remains the default local interface:

```powershell
python -m retaniq init-db --db .\data\retaniq.sqlite3
```

The typed configuration layer also accepts:

```text
sqlite:///C:/RetainIQ/data/retaniq.sqlite3
sqlite:///:memory:
```

For process configuration, set `RETAINIQ_DATABASE_URL`. A SQLite-only
installation may instead set `RETAINIQ_DATABASE_BACKEND=sqlite` and
`RETAINIQ_SQLITE_PATH`. An explicit backend is never silently changed and a
PostgreSQL target never falls back to a SQLite file.

PostgreSQL targets use the standard `postgresql://` DSN scheme. Remote targets
must specify verified TLS through `sslmode=require`, `verify-ca`, or
`verify-full`; a production deployment should use certificate verification
appropriate to its managed database:

```text
postgresql://<user>:<password>@db.example.com:5432/retaniq?sslmode=verify-full
```

Schema changes run only from the explicit `init-db` command. A TLS-disabled
loopback test server additionally requires
`--allow-insecure-local-postgresql`; this flag does not relax remote TLS rules.

The optional psycopg 3 driver is declared in
[`requirements-postgresql.txt`](../requirements-postgresql.txt):

```powershell
python -m pip install -r requirements-postgresql.txt
```

Local PostgreSQL without verified TLS is only accepted for an isolated test
when the caller explicitly opts in with
`allow_insecure_local_postgresql=True` and uses a local host such as
`localhost`. For example, test-only code may pass:

```text
postgresql://<user>:<password>@localhost:5432/retaniq?sslmode=disable
```

Do not commit credentials or place real passwords in shell history, CI logs,
error reports, or this repository. `DatabaseConfig.__repr__` and connection
errors redact passwords and sensitive query parameters. Inject the DSN through
an approved secret store or runtime environment, and avoid printing it.

## Connection and transaction behavior

`retaniq.database.DatabaseConnection` is the shared lifecycle boundary:

- SQLite opens with foreign-key enforcement and a 30-second busy timeout, and
  preserves `sqlite3.Row` and native integrity exceptions for the existing
  repository.
- PostgreSQL opens through psycopg 3 with dictionary rows when the optional
  driver is installed. Driver absence and connection failure are reported as
  safe, backend-neutral errors without copying a DSN into the message.
- `with connection:` owns the outer commit/rollback and closes the native
  connection. `connection.transaction()` owns one explicit transaction and
  rolls it back on an exception.
- Nested transactions are rejected explicitly in 06B. Savepoints are not
  introduced here.
- SQLite statements keep their `?` placeholders. PostgreSQL adapts qmarks
  outside SQL literals/comments using a quote-aware scanner; conflict handling,
  generated-key retrieval, and row locking remain explicit PostgreSQL SQL.
- SQLite migration scripts are intentionally rejected for PostgreSQL. The
  PostgreSQL-specific schema and explicit migration runner were added in 06C;
  RLS and Supabase integration remain outside this milestone.

The explicit `init-db` command applies PostgreSQL schema migrations. As of
06D-1, tenant/integration/customer setup, source/category grants, integration
and service-principal authentication, identity mapping, mapping-version and
health updates, canonical single/batch ingestion, usage/billing/subscription
subtypes, subscription ownership, and import checkpoints run on both
backends. Other operations still reject PostgreSQL explicitly; they do not
send unsupported SQLite queries or silently fall back.

`POSTGRESQL_CONNECTION_READY`, `POSTGRESQL_SCHEMA_VERIFIED`, and the bounded
06D-1 ingestion parity do not mean `POSTGRESQL_FEATURE_PARITY`. Historical
queries, observation coverage, account valuation, feature/label/prediction
storage, and the WSGI API remain SQLite-only. Application-level principal
checks are not database RLS; RLS and production authentication remain deferred.

## Verification and limitations

The dependency-free regression commands are:

```powershell
python -B -m unittest discover -s tests -v
python -B -m compileall -q retaniq tests
git diff --check
```

06B added parser, lifecycle, rollback, explicit PostgreSQL rejection, and
missing-driver tests. 06C schema results are in
[`MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md`](MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md).
06D-1 behavior and limitations are in
[`MEMBER1_POSTGRESQL_INGESTION_PARITY.md`](MEMBER1_POSTGRESQL_INGESTION_PARITY.md).
Next work is 06D-2 historical queries and coverage. Supabase remains deferred
to the later infrastructure phase and is not configured here.
