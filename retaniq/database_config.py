"""Typed, non-secret database target configuration.

This module only parses and validates database targets.  It never opens a
connection or creates a SQLite file. PostgreSQL schema migrations are
available through the explicit 06C migration command; the existing Data
Foundation repository remains SQLite-query-only until 06D compatibility work.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, unquote, urlencode, urlsplit, urlunsplit


DATABASE_URL_ENV = "RETAINIQ_DATABASE_URL"
DATABASE_BACKEND_ENV = "RETAINIQ_DATABASE_BACKEND"
SQLITE_PATH_ENV = "RETAINIQ_SQLITE_PATH"

SQLITE_BACKEND = "sqlite"
POSTGRESQL_BACKEND = "postgresql"
SUPPORTED_BACKENDS = frozenset({SQLITE_BACKEND, POSTGRESQL_BACKEND})
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_LOCAL_POSTGRES_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SECURE_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})
_INSECURE_SSLMODES = frozenset({"disable", "allow", "prefer"})
_SECRET_QUERY_KEYS = frozenset({"password", "passfile", "sslpassword", "secret", "token"})


class DatabaseConfigurationError(ValueError):
    """Raised when a database target is malformed or insecurely specified."""


def _configuration_error(message: str) -> DatabaseConfigurationError:
    return DatabaseConfigurationError(message)


def _normalize_backend(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _configuration_error("database backend must be sqlite or postgresql")
    normalized = value.strip().casefold()
    if normalized not in SUPPORTED_BACKENDS:
        raise _configuration_error("database backend must be sqlite or postgresql")
    return normalized


def _sqlite_path_from_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise _configuration_error("SQLite database URL is malformed") from None
    if parsed.scheme.casefold() != SQLITE_BACKEND or parsed.query or parsed.fragment:
        raise _configuration_error("SQLite URLs must not contain query or fragment components")
    if parsed.username or parsed.password or parsed.port:
        raise _configuration_error("SQLite database URL must not contain credentials or a port")
    if parsed.netloc not in {"", "localhost"}:
        raise _configuration_error("SQLite database URL has an unsupported host")
    path = unquote(parsed.path)
    if path == "/:memory:":
        return ":memory:"
    # urlsplit represents sqlite:///C:/... as /C:/....  Remove only that
    # URL-required slash; do not alter ordinary Unix absolute paths.
    if re.match(r"^/[A-Za-z]:[\\/]", path):
        path = path[1:]
    if not path:
        raise _configuration_error("SQLite database URL must identify a file or :memory:")
    return path


def _postgresql_parts(value: str, *, allow_insecure_local: bool) -> tuple[str, str | None]:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise _configuration_error("PostgreSQL DSN is malformed") from None
    if parsed.scheme.casefold() != POSTGRESQL_BACKEND:
        raise _configuration_error("PostgreSQL DSNs must use the postgresql:// scheme")
    if not host or parsed.path in {"", "/"}:
        raise _configuration_error("PostgreSQL DSN must include a host and database name")
    if port is not None and not 1 <= port <= 65535:
        raise _configuration_error("PostgreSQL DSN port is invalid")
    try:
        query = parse_qs(parsed.query, keep_blank_values=True)
    except ValueError:
        raise _configuration_error("PostgreSQL DSN query is malformed") from None
    sslmodes = query.get("sslmode", [])
    if len(sslmodes) > 1:
        raise _configuration_error("PostgreSQL DSN must specify sslmode at most once")
    sslmode = sslmodes[0] if sslmodes else None
    if sslmode is not None and sslmode not in _SECURE_SSLMODES | _INSECURE_SSLMODES:
        raise _configuration_error("PostgreSQL DSN sslmode is unsupported")
    is_local = host.casefold().strip("[]") in _LOCAL_POSTGRES_HOSTS
    if is_local:
        if sslmode in _INSECURE_SSLMODES or sslmode is None:
            if not allow_insecure_local:
                raise _configuration_error(
                    "local PostgreSQL without verified TLS requires explicit isolated-test opt-in",
                )
    elif sslmode not in _SECURE_SSLMODES:
        raise _configuration_error(
            "remote PostgreSQL DSNs must specify sslmode=require, verify-ca, or verify-full",
        )
    return host, sslmode


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        netloc = parsed.netloc
        if "@" in netloc:
            credentials, host = netloc.rsplit("@", 1)
            username = credentials.split(":", 1)[0]
            netloc = f"{username}:***@{host}" if ":" in credentials else f"{username}@{host}"
        query_parts = []
        for key, item in parse_qs(parsed.query, keep_blank_values=True).items():
            rendered = "***" if key.casefold() in _SECRET_QUERY_KEYS else item[-1]
            query_parts.append((key, rendered))
        query = urlencode(query_parts)
        return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))
    except (TypeError, ValueError):
        return "<redacted database target>"


@dataclass(frozen=True, slots=True, repr=False)
class DatabaseConfig:
    """Validated database target with a deliberately redacted representation."""

    backend: str
    target: str
    allow_insecure_local_postgresql: bool = False

    def __post_init__(self) -> None:
        backend = _normalize_backend(self.backend)
        if backend is None or not isinstance(self.target, str) or not self.target.strip():
            raise _configuration_error("database target is empty or malformed")
        object.__setattr__(self, "backend", backend)
        if backend == SQLITE_BACKEND:
            if "://" in self.target and not self.target.casefold().startswith("sqlite://"):
                raise _configuration_error("explicit SQLite selection requires a path or sqlite:// URL")
            target = _sqlite_path_from_url(self.target) if self.target.casefold().startswith("sqlite://") else self.target
            object.__setattr__(self, "target", target)
        else:
            _postgresql_parts(
                self.target,
                allow_insecure_local=self.allow_insecure_local_postgresql,
            )

    @classmethod
    def from_value(
        cls,
        value: str | Path | "DatabaseConfig" | None = None,
        *,
        backend: str | None = None,
        environ: Mapping[str, str] | None = None,
        allow_insecure_local_postgresql: bool = False,
    ) -> "DatabaseConfig":
        """Parse a filesystem path, supported URL, or configured environment target."""
        selected_backend = _normalize_backend(backend)
        if isinstance(value, cls):
            if selected_backend is not None and selected_backend != value.backend:
                raise _configuration_error("explicit database backend does not match the target")
            return value
        if value is None:
            env = os.environ if environ is None else environ
            if selected_backend is None:
                selected_backend = _normalize_backend(env.get(DATABASE_BACKEND_ENV))
            value = env.get(DATABASE_URL_ENV)
            if value is None and (env.get(DATABASE_BACKEND_ENV) or selected_backend) == SQLITE_BACKEND:
                value = env.get(SQLITE_PATH_ENV)
            if value is None:
                raise _configuration_error(
                    f"database target is required; set {DATABASE_URL_ENV} or pass --db",
                )
        if isinstance(value, Path):
            raw = str(value)
        elif isinstance(value, str):
            raw = value.strip()
        else:
            raise _configuration_error("database target must be a path, URL, or DatabaseConfig")
        if not raw:
            raise _configuration_error("database target must not be empty")

        try:
            parsed = urlsplit(raw)
        except ValueError:
            raise _configuration_error("database target is malformed") from None
        scheme = parsed.scheme.casefold()
        if scheme == SQLITE_BACKEND:
            inferred_backend = SQLITE_BACKEND
            target = _sqlite_path_from_url(raw)
        elif scheme == POSTGRESQL_BACKEND:
            inferred_backend = POSTGRESQL_BACKEND
            target = raw
        elif "://" in raw:
            raise _configuration_error("unsupported database URL scheme")
        elif selected_backend == POSTGRESQL_BACKEND:
            raise _configuration_error("explicit PostgreSQL selection requires a postgresql:// DSN")
        elif selected_backend == SQLITE_BACKEND or not scheme or _WINDOWS_PATH.match(raw):
            inferred_backend = SQLITE_BACKEND
            target = raw
        else:
            raise _configuration_error("ambiguous database target scheme")
        if selected_backend is not None and selected_backend != inferred_backend:
            raise _configuration_error("explicit database backend does not match the target")
        return cls(
            inferred_backend,
            target,
            allow_insecure_local_postgresql=allow_insecure_local_postgresql,
        )

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        allow_insecure_local_postgresql: bool = False,
    ) -> "DatabaseConfig":
        return cls.from_value(
            None,
            environ=environ,
            allow_insecure_local_postgresql=allow_insecure_local_postgresql,
        )

    @property
    def is_sqlite(self) -> bool:
        return self.backend == SQLITE_BACKEND

    @property
    def is_postgresql(self) -> bool:
        return self.backend == POSTGRESQL_BACKEND

    @property
    def sqlite_path(self) -> str:
        if not self.is_sqlite:
            raise _configuration_error("SQLite path requested for a PostgreSQL configuration")
        return self.target

    @property
    def postgresql_dsn(self) -> str:
        if not self.is_postgresql:
            raise _configuration_error("PostgreSQL DSN requested for a SQLite configuration")
        return self.target

    @property
    def redacted_target(self) -> str:
        return _redact_url(self.target) if self.is_postgresql else self.target

    def __repr__(self) -> str:
        return (
            f"DatabaseConfig(backend={self.backend!r}, "
            f"target={self.redacted_target!r}, "
            f"allow_insecure_local_postgresql={self.allow_insecure_local_postgresql!r})"
        )


def resolve_database_config(
    value: str | Path | DatabaseConfig | None = None,
    *,
    backend: str | None = None,
    environ: Mapping[str, str] | None = None,
    allow_insecure_local_postgresql: bool = False,
) -> DatabaseConfig:
    """Convenience wrapper used by connection and repository code."""
    return DatabaseConfig.from_value(
        value,
        backend=backend,
        environ=environ,
        allow_insecure_local_postgresql=allow_insecure_local_postgresql,
    )
