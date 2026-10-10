"""Checksum-protected PostgreSQL schema migrations for RetainIQ 06C."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .database import DatabaseConnection, DatabaseConnectionError, DatabaseDriverUnavailable, DatabaseError
from .database_config import DatabaseConfig, DatabaseConfigurationError, resolve_database_config


_MIGRATION_FILENAME = re.compile(r"^(?P<version>[0-9]{3})_(?P<name>[a-z0-9_]+)\.sql$")
_SCHEMA_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MIGRATION_TABLE = "retaniq_schema_migrations"
_DEFAULT_MIGRATION_DIRECTORY = Path(__file__).resolve().parent.parent / "migrations" / "postgresql"


class PostgreSQLMigrationError(DatabaseError):
    """Base class for safe PostgreSQL migration errors."""


class MigrationDirectoryError(PostgreSQLMigrationError):
    """Raised when the migration directory or file names are invalid."""


class MigrationHistoryError(PostgreSQLMigrationError):
    """Raised when applied database history is incompatible with local files."""


class MigrationChecksumError(MigrationHistoryError):
    """Raised when a previously applied migration file has been changed."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    name: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True, slots=True)
class MigrationRunResult:
    schema: str
    applied_versions: tuple[str, ...]
    current_version: str | None


def discover_migrations(directory: str | Path | None = None) -> tuple[Migration, ...]:
    """Read and validate the ordered migration files without connecting to a DB."""
    root = Path(directory) if directory is not None else _DEFAULT_MIGRATION_DIRECTORY
    if not root.is_dir():
        raise MigrationDirectoryError("PostgreSQL migration directory is missing")
    files = sorted(root.glob("*.sql"), key=lambda path: path.name)
    if not files:
        raise MigrationDirectoryError("PostgreSQL migration directory contains no SQL migrations")

    migrations: list[Migration] = []
    versions: set[str] = set()
    for path in files:
        match = _MIGRATION_FILENAME.fullmatch(path.name)
        if match is None:
            raise MigrationDirectoryError("PostgreSQL migration filename must use NNN_lowercase_name.sql")
        version = match.group("version")
        if version in versions:
            raise MigrationDirectoryError(f"duplicate PostgreSQL migration version {version}")
        versions.add(version)
        try:
            raw = path.read_bytes()
            sql = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            raise MigrationDirectoryError(f"PostgreSQL migration {version} cannot be read as UTF-8") from None
        migrations.append(Migration(
            version=version,
            name=match.group("name"),
            path=path,
            checksum=hashlib.sha256(raw).hexdigest(),
            sql=sql,
        ))

    expected = [f"{value:03d}" for value in range(1, len(migrations) + 1)]
    actual = [migration.version for migration in migrations]
    if actual != expected:
        raise MigrationDirectoryError("PostgreSQL migration versions must be contiguous starting at 001")
    return tuple(migrations)


def plan_migrations(
    migrations: Sequence[Migration],
    applied_checksums: Mapping[str, str],
) -> tuple[Migration, ...]:
    """Validate recorded history and return the unapplied suffix."""
    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise MigrationDirectoryError("duplicate PostgreSQL migration version")
    by_version = {migration.version: migration for migration in migrations}
    unknown = sorted(set(applied_checksums) - set(by_version))
    if unknown:
        raise MigrationHistoryError(
            f"database has migration version {unknown[0]} with no local migration file",
        )
    applied_versions = set(applied_checksums)
    for migration in migrations:
        recorded_checksum = applied_checksums.get(migration.version)
        if recorded_checksum is not None and recorded_checksum != migration.checksum:
            raise MigrationChecksumError(
                f"applied PostgreSQL migration {migration.version} checksum does not match its file",
            )

    pending_started = False
    pending: list[Migration] = []
    for migration in migrations:
        if migration.version not in applied_versions:
            pending_started = True
            pending.append(migration)
        elif pending_started:
            raise MigrationHistoryError("database migration history is not a contiguous prefix")
    return tuple(pending)


def split_sql_statements(script: str) -> tuple[str, ...]:
    """Split plain PostgreSQL migration SQL while respecting quoted strings/comments."""
    statements: list[str] = []
    start = 0
    index = 0
    single_quote = False
    double_quote = False
    line_comment = False
    block_comment = False
    dollar_tag: str | None = None
    length = len(script)

    while index < length:
        char = script[index]
        following = script[index:index + 2]
        if line_comment:
            if char in "\r\n":
                line_comment = False
        elif block_comment:
            if following == "*/":
                block_comment = False
                index += 1
        elif dollar_tag is not None:
            if script.startswith(dollar_tag, index):
                index += len(dollar_tag) - 1
                dollar_tag = None
        elif single_quote:
            if char == "'":
                if following == "''":
                    index += 1
                else:
                    single_quote = False
        elif double_quote:
            if char == '"':
                if following == '""':
                    index += 1
                else:
                    double_quote = False
        elif following == "--":
            line_comment = True
            index += 1
        elif following == "/*":
            block_comment = True
            index += 1
        elif char == "'":
            single_quote = True
        elif char == '"':
            double_quote = True
        elif char == "$":
            tag_match = re.match(r"\$[A-Za-z_0-9]*\$", script[index:])
            if tag_match:
                dollar_tag = tag_match.group(0)
                index += len(dollar_tag) - 1
        elif char == ";":
            statement = script[start:index].strip()
            if statement:
                statements.append(statement)
            start = index + 1
        index += 1

    if single_quote or double_quote or block_comment or dollar_tag is not None:
        raise MigrationDirectoryError("PostgreSQL migration contains an unterminated SQL quote or comment")
    tail = script[start:].strip()
    if tail:
        statements.append(tail)
    return tuple(statements)


def run_postgresql_migrations(
    value: str | DatabaseConfig,
    *,
    directory: str | Path | None = None,
    schema: str = "public",
) -> MigrationRunResult:
    """Apply the pending PostgreSQL schema migrations under a transaction lock.

    Each migration and its checksum row commit atomically. The session-level
    advisory lock serializes concurrent initializers. An optional schema is
    useful for isolated tests; its name is restricted to a simple SQL identifier.
    """
    if not isinstance(schema, str) or not _SCHEMA_IDENTIFIER.fullmatch(schema):
        raise DatabaseConfigurationError("PostgreSQL migration schema name is invalid")
    config = resolve_database_config(value)
    if not config.is_postgresql:
        raise DatabaseConfigurationError("PostgreSQL migrations require an explicit PostgreSQL target")
    if config.is_supabase:
        if config.connection_mode == "TRANSACTION_POOLER":
            raise PostgreSQLMigrationError(
                "Supabase transaction pooling is incompatible with the session-level migration advisory lock; use the DIRECT migration DSN",
            )
        if config.migration_dsn is not None:
            config = config.for_migrations()
        elif config.connection_mode != "DIRECT":
            raise PostgreSQLMigrationError(
                "Supabase schema migrations require the separately configured DIRECT migration connection",
            )
    migrations = discover_migrations(directory)
    try:
        connection = DatabaseConnection.open(config)
    except DatabaseDriverUnavailable as error:
        raise PostgreSQLMigrationError(str(error)) from None
    except DatabaseConnectionError:
        raise PostgreSQLMigrationError("PostgreSQL migration connection failed") from None
    except Exception:
        raise PostgreSQLMigrationError("PostgreSQL migration connection failed") from None
    applied_now: list[str] = []
    locked = False
    try:
        # Ensure migration transactions are outermost and independent. The
        # session advisory lock remains held between each transaction. Acquire
        # it before schema creation too: concurrent CREATE SCHEMA IF NOT EXISTS
        # calls can race in PostgreSQL's catalogs.
        connection.raw_connection.autocommit = True
        quoted_schema = '"' + schema.replace('"', '""') + '"'
        connection.execute(
            "SELECT pg_advisory_lock(hashtext(%s), hashtext(%s))",
            ("retaniq_postgresql_migrations", schema),
        )
        locked = True
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
        connection.execute(f"SET search_path TO {quoted_schema}")
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {_MIGRATION_TABLE} ("
            "version TEXT PRIMARY KEY, checksum CHAR(64) NOT NULL, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        rows = connection.execute(
            f"SELECT version, checksum FROM {_MIGRATION_TABLE} ORDER BY version",
        ).fetchall()
        applied = {str(row["version"]): str(row["checksum"]).strip() for row in rows}
        pending = plan_migrations(migrations, applied)

        for migration in pending:
            try:
                with connection.transaction():
                    for statement in split_sql_statements(migration.sql):
                        connection.execute(statement)
                    connection.execute(
                        f"INSERT INTO {_MIGRATION_TABLE}(version, checksum) VALUES (%s, %s)",
                        (migration.version, migration.checksum),
                    )
            except Exception:
                raise PostgreSQLMigrationError(
                    f"PostgreSQL migration {migration.version} failed and was rolled back",
                ) from None
            applied_now.append(migration.version)

        current = migrations[-1].version if migrations else None
        return MigrationRunResult(schema, tuple(applied_now), current)
    except PostgreSQLMigrationError:
        raise
    except Exception:
        raise PostgreSQLMigrationError("PostgreSQL migration initialization failed") from None
    finally:
        if locked:
            try:
                connection.execute(
                    "SELECT pg_advisory_unlock(hashtext(%s), hashtext(%s))",
                    ("retaniq_postgresql_migrations", schema),
                )
            except Exception:
                # Closing the connection releases any remaining session lock.
                pass
        connection.close()


def verify_postgresql_schema(
    value: str | DatabaseConfig,
    *,
    directory: str | Path | None = None,
    schema: str = "public",
) -> MigrationRunResult:
    """Verify the PostgreSQL migration history without applying or changing schema."""
    if not isinstance(schema, str) or not _SCHEMA_IDENTIFIER.fullmatch(schema):
        raise DatabaseConfigurationError("PostgreSQL migration schema name is invalid")
    config = resolve_database_config(value)
    if not config.is_postgresql:
        raise DatabaseConfigurationError("PostgreSQL schema verification requires an explicit PostgreSQL target")
    migrations = discover_migrations(directory)
    try:
        connection = DatabaseConnection.open(config)
    except DatabaseDriverUnavailable as error:
        raise PostgreSQLMigrationError(str(error)) from None
    except Exception:
        raise PostgreSQLMigrationError("PostgreSQL schema verification connection failed") from None
    try:
        connection.raw_connection.autocommit = True
        quoted_schema = '"' + schema.replace('"', '""') + '"'
        qualified_migration_table = f"{quoted_schema}.\"{_MIGRATION_TABLE}\""
        row = connection.execute(
            "SELECT to_regclass(?) AS migration_table", (f"{schema}.{_MIGRATION_TABLE}",),
        ).fetchone()
        if row is None or row["migration_table"] is None:
            raise MigrationHistoryError("PostgreSQL schema has not been initialized")
        rows = connection.execute(
            f"SELECT version, checksum FROM {qualified_migration_table} ORDER BY version",
        ).fetchall()
        applied = {str(item["version"]): str(item["checksum"]).strip() for item in rows}
        if plan_migrations(migrations, applied):
            raise MigrationHistoryError("PostgreSQL schema migrations are incomplete")
        latest = migrations[-1].version if migrations else None
        return MigrationRunResult(schema, (), latest)
    finally:
        connection.close()
