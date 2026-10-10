# Member 1 database backend configuration

This document records the 06B database foundation. It covers target parsing,
connection lifecycle, and transaction ownership. It does not claim PostgreSQL
schema or feature parity.

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
- SQLite query parameters continue to use `?`; direct PostgreSQL calls use
  psycopg's `%s` placeholders. Shared repository query adaptation belongs to
  06D rather than an unsafe string-rewrite layer in 06B.
- SQLite migration scripts are intentionally rejected for PostgreSQL. No
  PostgreSQL migration runner, schema, RLS policy, or Supabase integration is
  included in this milestone.

The existing Data Foundation repository is still SQLite-schema-only. Passing a
PostgreSQL `DatabaseConfig` to `initialize_database` or another repository
operation raises an explicit readiness error instead of sending SQLite SQL to
PostgreSQL or silently opening another backend. This boundary prevents a
connection primitive from being mistaken for feature parity.

`POSTGRESQL_CONNECTION_READY` therefore means only that a validated DSN and
connection lifecycle exist. It does not mean
`POSTGRESQL_FEATURE_PARITY`: that requires the PostgreSQL schema, migrations,
query compatibility, tenant isolation, and regression evidence planned for
06C/06D.

## Verification and limitations

The dependency-free regression commands are:

```powershell
python -B -m unittest discover -s tests -v
python -B -m compileall -q retaniq tests
git diff --check
```

06B adds parser, lifecycle, rollback, explicit PostgreSQL rejection, and
missing-driver tests. No PostgreSQL smoke test is claimed for this checkout:
there is no safe configured PostgreSQL instance or DSN, psycopg 3 is not
installed in the bundled runtime, and no database service was started.

Next work is 06C PostgreSQL schema and migrations, followed by 06D query and
repository parity. Supabase remains deferred to the later infrastructure phase
and is not configured by this foundation.
