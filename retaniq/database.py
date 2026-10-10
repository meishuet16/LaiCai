"""Backend-aware connection and transaction primitives.

The generic connection layer can open SQLite and, when the optional psycopg 3
dependency is installed, PostgreSQL. PostgreSQL schema migrations are
implemented separately. A deliberately limited set of Member 1 ingestion,
identity and authorization operations supports both backends; other Data
Foundation repository operations reject PostgreSQL until their parity work.
"""

from __future__ import annotations

import sqlite3
import re
from contextlib import contextmanager
from typing import Any, Iterator

from .database_config import (
    DatabaseConfig,
    DatabaseConfigurationError,
    POSTGRESQL_BACKEND,
    SQLITE_BACKEND,
    resolve_database_config,
)


class DatabaseError(RuntimeError):
    """Base class for safe, backend-neutral database errors."""


class DatabaseDriverUnavailable(DatabaseError):
    """Raised when an explicitly requested optional database driver is absent."""


class DatabaseConnectionError(DatabaseError):
    """Raised when a backend connection cannot be established."""


class DatabaseTransactionError(DatabaseError):
    """Raised when a transaction cannot be committed or rolled back."""


class DatabaseIntegrityError(DatabaseError):
    """Safe integrity failure metadata without the driver's SQL or payload."""

    def __init__(self, sqlstate: str | None, constraint_name: str | None = None):
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name
        super().__init__("database integrity constraint failed")


class UnsupportedDatabaseOperation(DatabaseError):
    """Raised when a requested operation is not implemented for a backend."""


class PostgreSQLSchemaNotReady(UnsupportedDatabaseOperation):
    """The current SQLite repository operations are not PostgreSQL-compatible."""


_DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$")


def _postgresql_placeholders(statement: str) -> str:
    """Translate SQLite qmarks outside SQL strings/comments to psycopg markers."""
    output: list[str] = []
    index = 0
    block_depth = 0
    quote: str | None = None
    escape_string = False
    dollar_quote: str | None = None
    line_comment = False
    while index < len(statement):
        char = statement[index]
        next_char = statement[index + 1] if index + 1 < len(statement) else ""
        if line_comment:
            output.append(char)
            if char in "\r\n":
                line_comment = False
            index += 1
        elif dollar_quote is not None:
            if statement.startswith(dollar_quote, index):
                output.append(dollar_quote)
                index += len(dollar_quote)
                dollar_quote = None
            else:
                output.append(char)
                index += 1
        elif quote is not None:
            output.append(char)
            if quote == "'" and escape_string and char == "\\" and next_char:
                output.append(next_char)
                index += 2
                continue
            if char == quote:
                if next_char == quote:
                    output.append(next_char)
                    index += 2
                    continue
                quote = None
                escape_string = False
            index += 1
        elif block_depth:
            if char == "/" and next_char == "*":
                output.extend((char, next_char))
                block_depth += 1
                index += 2
            elif char == "*" and next_char == "/":
                output.extend((char, next_char))
                block_depth -= 1
                index += 2
            else:
                output.append(char)
                index += 1
        elif char == "-" and next_char == "-":
            output.extend((char, next_char))
            line_comment = True
            index += 2
        elif char == "/" and next_char == "*":
            output.extend((char, next_char))
            block_depth = 1
            index += 2
        elif char in {"'", '"'}:
            output.append(char)
            quote = char
            escape_string = (
                char == "'" and index > 0 and statement[index - 1] in "eE"
                and (index < 2 or not (statement[index - 2].isalnum() or statement[index - 2] in "_$"))
            )
            index += 1
        elif char == "$":
            match = _DOLLAR_QUOTE.match(statement, index)
            if match:
                dollar_quote = match.group(0)
                output.append(dollar_quote)
                index = match.end()
            else:
                output.append(char)
                index += 1
        elif char == "?":
            output.append("%s")
            index += 1
        else:
            output.append(char)
            index += 1
    return "".join(output)


def _safe_driver_error(message: str, error: BaseException | None = None) -> DatabaseError:
    """Create an error without copying backend messages that may contain a DSN."""
    if error is None:
        return DatabaseError(message)
    return DatabaseError(message)


class DatabaseConnection:
    """Small lifecycle wrapper around a backend-native connection.

    SQLite preserves the existing ``sqlite3.Row`` behavior.  PostgreSQL uses
    psycopg's ``dict_row`` policy for generic callers. PostgreSQL adapts qmark
    placeholders outside literals and comments. Backend-specific conflict and
    generated-key statements remain explicit in the repository.
    """

    def __init__(self, config: DatabaseConfig, raw_connection: Any):
        self.config = config
        self._raw_connection = raw_connection
        self._closed = False
        self._transaction_depth = 0

    @classmethod
    def open(cls, config: DatabaseConfig, *, timeout_seconds: float = 30.0) -> "DatabaseConnection":
        if not isinstance(config, DatabaseConfig):
            config = resolve_database_config(config)
        if config.backend == SQLITE_BACKEND:
            try:
                connection = sqlite3.connect(config.sqlite_path, timeout=timeout_seconds)
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
            except sqlite3.Error:
                raise DatabaseConnectionError("SQLite connection failed") from None
            return cls(config, connection)

        if config.backend != POSTGRESQL_BACKEND:
            raise DatabaseConfigurationError("unsupported database backend")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError:
            raise DatabaseDriverUnavailable(
                "PostgreSQL driver is not installed; install requirements-postgresql.txt",
            ) from None
        try:
            connection = psycopg.connect(
                config.postgresql_dsn,
                connect_timeout=max(1, int(timeout_seconds)),
                row_factory=dict_row,
            )
        except Exception:
            raise DatabaseConnectionError("PostgreSQL connection failed") from None
        return cls(config, connection)

    @property
    def backend(self) -> str:
        return self.config.backend

    @property
    def raw_connection(self) -> Any:
        """Return the native connection for narrowly scoped adapter code."""
        self._ensure_open()
        return self._raw_connection

    @property
    def closed(self) -> bool:
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise DatabaseConnectionError("database connection is closed")

    def cursor(self) -> Any:
        self._ensure_open()
        try:
            return self._raw_connection.cursor()
        except Exception:
            raise DatabaseConnectionError("database cursor creation failed") from None

    def execute(self, statement: str, parameters: Any = ()) -> Any:
        self._ensure_open()
        if self.backend == SQLITE_BACKEND:
            # Preserve sqlite3.IntegrityError and related exceptions for the
            # existing repository's stable error translation.
            return self._raw_connection.execute(statement, parameters)
        try:
            cursor = self._raw_connection.cursor()
            cursor.execute(_postgresql_placeholders(statement), parameters)
            return cursor
        except Exception as error:
            if getattr(error, "sqlstate", None) and str(error.sqlstate).startswith("23"):
                diagnostic = getattr(error, "diag", None)
                raise DatabaseIntegrityError(
                    error.sqlstate, getattr(diagnostic, "constraint_name", None),
                ) from None
            raise DatabaseError("database statement execution failed") from None

    def executemany(self, statement: str, parameters: Any) -> Any:
        self._ensure_open()
        if self.backend == SQLITE_BACKEND:
            return self._raw_connection.executemany(statement, parameters)
        try:
            cursor = self._raw_connection.cursor()
            cursor.executemany(_postgresql_placeholders(statement), parameters)
            return cursor
        except Exception as error:
            if getattr(error, "sqlstate", None) and str(error.sqlstate).startswith("23"):
                diagnostic = getattr(error, "diag", None)
                raise DatabaseIntegrityError(
                    error.sqlstate, getattr(diagnostic, "constraint_name", None),
                ) from None
            raise DatabaseError("database batch execution failed") from None

    def executescript(self, script: str) -> Any:
        self._ensure_open()
        if self.backend != SQLITE_BACKEND:
            raise UnsupportedDatabaseOperation(
                "SQL migration scripts are SQLite-only until the PostgreSQL migration runner is implemented",
            )
        return self._raw_connection.executescript(script)

    def commit(self) -> None:
        self._ensure_open()
        if self.backend == SQLITE_BACKEND:
            self._raw_connection.commit()
            return
        try:
            self._raw_connection.commit()
        except Exception:
            raise DatabaseTransactionError("database commit failed") from None

    def rollback(self) -> None:
        self._ensure_open()
        if self.backend == SQLITE_BACKEND:
            self._raw_connection.rollback()
            return
        try:
            self._raw_connection.rollback()
        except Exception:
            raise DatabaseTransactionError("database rollback failed") from None

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator["DatabaseConnection"]:
        """Own one transaction and reject unsupported nesting explicitly."""
        self._ensure_open()
        if self._transaction_depth:
            raise DatabaseTransactionError("nested transactions are not supported by this foundation")
        self._transaction_depth += 1
        try:
            if self.backend == SQLITE_BACKEND:
                self._raw_connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                try:
                    yield self
                except Exception:
                    self.rollback()
                    raise
                else:
                    self.commit()
            else:
                try:
                    with self._raw_connection.transaction():
                        yield self
                except Exception:
                    raise
        finally:
            self._transaction_depth -= 1

    def require_sqlite_schema_support(self) -> None:
        if self.backend == POSTGRESQL_BACKEND:
            raise PostgreSQLSchemaNotReady(
                "RetainIQ PostgreSQL repository compatibility is deferred to 06D",
            )

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._raw_connection.close()
        except Exception:
            raise DatabaseConnectionError("database connection close failed") from None
        finally:
            self._closed = True

    def __enter__(self) -> "DatabaseConnection":
        self._ensure_open()
        return self

    def __exit__(self, exception_type: Any, exception: Any, traceback: Any) -> None:
        try:
            if exception_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


def connect_database(
    value: str | DatabaseConfig,
    *,
    allow_insecure_local_postgresql: bool = False,
    timeout_seconds: float = 30.0,
) -> DatabaseConnection:
    """Resolve and open an explicitly selected database backend."""
    config = resolve_database_config(
        value,
        allow_insecure_local_postgresql=allow_insecure_local_postgresql,
    )
    return DatabaseConnection.open(config, timeout_seconds=timeout_seconds)


open_database = connect_database
