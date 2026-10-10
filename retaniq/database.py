"""Backend-aware connection and transaction primitives.

The generic connection layer can open SQLite and, when the optional psycopg 3
dependency is installed, PostgreSQL.  The existing RetainIQ Data Foundation
repository deliberately uses only the SQLite-schema path until 06C/06D; it
must call :meth:`DatabaseConnection.require_sqlite_schema_support` rather than
silently sending SQLite SQL to PostgreSQL.
"""

from __future__ import annotations

import sqlite3
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


class UnsupportedDatabaseOperation(DatabaseError):
    """Raised when a requested operation is not implemented for a backend."""


class PostgreSQLSchemaNotReady(UnsupportedDatabaseOperation):
    """The PostgreSQL connection exists, but the RetainIQ schema is not 06C-ready."""


def _safe_driver_error(message: str, error: BaseException | None = None) -> DatabaseError:
    """Create an error without copying backend messages that may contain a DSN."""
    if error is None:
        return DatabaseError(message)
    return DatabaseError(message)


class DatabaseConnection:
    """Small lifecycle wrapper around a backend-native connection.

    SQLite preserves the existing ``sqlite3.Row`` behavior.  PostgreSQL uses
    psycopg's ``dict_row`` policy for generic callers.  SQL placeholder syntax
    is intentionally not rewritten: SQLite callers use ``?`` and PostgreSQL
    callers use psycopg's native ``%s`` placeholders until the repository
    compatibility work in 06D defines shared query helpers.
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
            cursor.execute(statement, parameters)
            return cursor
        except Exception:
            raise DatabaseError("database statement execution failed") from None

    def executemany(self, statement: str, parameters: Any) -> Any:
        self._ensure_open()
        if self.backend == SQLITE_BACKEND:
            return self._raw_connection.executemany(statement, parameters)
        try:
            cursor = self._raw_connection.cursor()
            cursor.executemany(statement, parameters)
            return cursor
        except Exception:
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
                "RetainIQ PostgreSQL schema operations are deferred to 06C/06D",
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
