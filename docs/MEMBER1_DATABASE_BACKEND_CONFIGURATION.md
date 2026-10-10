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
- SQLite query parameters continue to use `?`; direct PostgreSQL calls use
  psycopg's `%s` placeholders. Shared repository query adaptation belongs to
  06D rather than an unsafe string-rewrite layer in 06B.
- SQLite migration scripts are intentionally rejected for PostgreSQL. The
  PostgreSQL-specific schema and explicit migration runner were added in 06C;
  RLS and Supabase integration remain outside this milestone.

The existing Data Foundation repository remains SQLite-query-only. The
explicit `init-db` command applies PostgreSQL schema migrations, while other
repository operations reject PostgreSQL until 06D rather than sending SQLite
SQL to PostgreSQL or silently opening another backend.

`POSTGRESQL_CONNECTION_READY` and `POSTGRESQL_SCHEMA_VERIFIED` do not mean
`POSTGRESQL_FEATURE_PARITY`. Query compatibility, tenant isolation, and
application regression evidence remain planned for 06D.

## Verification and limitations

The dependency-free regression commands are:

```powershell
python -B -m unittest discover -s tests -v
python -B -m compileall -q retaniq tests
git diff --check
```

06B added parser, lifecycle, rollback, explicit PostgreSQL rejection, and
missing-driver tests. In 06C, the PostgreSQL driver and local cluster were
installed/created in temporary paths; the real disposable-server results are
recorded in `docs/MEMBER1_POSTGRESQL_SCHEMA_AND_MIGRATIONS.md` and
`TEAM_LOG.md`. Next work is 06D query and repository parity. Supabase remains
deferred to the later infrastructure phase and is not configured here.
