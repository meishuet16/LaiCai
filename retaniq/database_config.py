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
SUPABASE_PROJECT_URL_ENV = "RETAINIQ_SUPABASE_PROJECT_URL"
SUPABASE_EXPECTED_PROJECT_REF_ENV = "RETAINIQ_SUPABASE_EXPECTED_PROJECT_REF"
SUPABASE_MIGRATION_DSN_ENV = "RETAINIQ_SUPABASE_DB_MIGRATION_DSN"
SUPABASE_APP_DSN_ENV = "RETAINIQ_SUPABASE_DB_APP_DSN"
SUPABASE_CONNECTION_MODE_ENV = "RETAINIQ_SUPABASE_CONNECTION_MODE"

SQLITE_BACKEND = "sqlite"
POSTGRESQL_BACKEND = "postgresql"
SUPABASE_BACKEND = "supabase"
SUPPORTED_BACKENDS = frozenset({SQLITE_BACKEND, POSTGRESQL_BACKEND})
SUPABASE_CONNECTION_MODES = frozenset({"DIRECT", "SESSION_POOLER", "TRANSACTION_POOLER"})
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
    except (TypeError, ValueError):
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


def _supabase_project_ref(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]{20}", value):
        raise _configuration_error("expected Supabase project reference is malformed")
    return value


def _validate_supabase_project_url(value: str, project_ref: str) -> None:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        raise _configuration_error("Supabase project URL is malformed") from None
    if (
        parsed.scheme != "https"
        or host != f"{project_ref}.supabase.co"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise _configuration_error("Supabase project URL does not match the expected project reference")


def _validate_supabase_dsn(value: str, project_ref: str, mode: str) -> tuple[str, str | None]:
    host, sslmode = _postgresql_parts(value, allow_insecure_local=False)
    try:
        parsed = urlsplit(value)
        port = parsed.port or 5432
        username = unquote(parsed.username or "")
        password = parsed.password
    except ValueError:
        raise _configuration_error("Supabase PostgreSQL DSN is malformed") from None
    if not username or not password:
        raise _configuration_error("Supabase PostgreSQL DSN must include dashboard-provided credentials")

    # These are identity checks against the official connection-string forms,
    # not connection-string construction. The host and username must still be
    # copied from this project's Dashboard Connect dialog.
    direct_host = host.casefold() == f"db.{project_ref}.supabase.co"
    shared_pooler = host.casefold().endswith(".pooler.supabase.com")
    pooler_user = username.endswith(f".{project_ref}")
    if mode == "DIRECT":
        matches = direct_host and port == 5432
    elif mode == "SESSION_POOLER":
        matches = shared_pooler and pooler_user and port == 5432
    else:
        matches = (
            (shared_pooler and pooler_user and port == 6543)
            or (direct_host and port == 6543)
        )
    if not matches:
        raise _configuration_error("Supabase DSN identity or endpoint does not match the configured mode and project")

    query = parse_qs(urlsplit(value).query, keep_blank_values=True)
    if query.get("sslmode", [None])[0] in {"verify-ca", "verify-full"} and not query.get("sslrootcert"):
        raise _configuration_error("Supabase certificate verification requires an explicit sslrootcert")
    return host, sslmode


def _supabase_migration_mode(value: str, project_ref: str) -> str:
    """Accept only direct or session-pooler endpoints for migration sessions."""
    for mode in ("DIRECT", "SESSION_POOLER"):
        try:
            _validate_supabase_dsn(value, project_ref, mode)
        except DatabaseConfigurationError:
            continue
        return mode
    raise _configuration_error(
        "Supabase migration DSN must use this project's direct or session-pooler endpoint",
    )


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
    deployment_environment: str = "local"
    connection_mode: str | None = None
    expected_project_ref: str | None = None
    project_url: str | None = None
    migration_dsn: str | None = None

    def __post_init__(self) -> None:
        backend = _normalize_backend(self.backend)
        if backend is None or not isinstance(self.target, str) or not self.target.strip():
            raise _configuration_error("database target is empty or malformed")
        if self.deployment_environment not in {"local", "supabase_demo"}:
            raise _configuration_error("deployment environment must be local or supabase_demo")
        object.__setattr__(self, "backend", backend)
        if backend == SQLITE_BACKEND:
            if self.deployment_environment != "local":
                raise _configuration_error("SQLite is supported only for the local environment")
            if "://" in self.target and not self.target.casefold().startswith("sqlite://"):
                raise _configuration_error("explicit SQLite selection requires a path or sqlite:// URL")
            target = _sqlite_path_from_url(self.target) if self.target.casefold().startswith("sqlite://") else self.target
            object.__setattr__(self, "target", target)
        else:
            _postgresql_parts(
                self.target,
                allow_insecure_local=self.allow_insecure_local_postgresql,
            )
            if self.deployment_environment == "supabase_demo":
                project_ref = _supabase_project_ref(self.expected_project_ref or "")
                mode = self.connection_mode.upper() if isinstance(self.connection_mode, str) else ""
                if mode not in SUPABASE_CONNECTION_MODES:
                    raise _configuration_error("Supabase connection mode must be DIRECT, SESSION_POOLER, or TRANSACTION_POOLER")
                if not self.project_url:
                    raise _configuration_error("Supabase project URL is required")
                _validate_supabase_project_url(self.project_url, project_ref)
                _validate_supabase_dsn(self.target, project_ref, mode)
                object.__setattr__(self, "connection_mode", mode)
                if self.migration_dsn is not None:
                    _supabase_migration_mode(self.migration_dsn, project_ref)
                    app_user = unquote(urlsplit(self.target).username or "")
                    migration_user = unquote(urlsplit(self.migration_dsn).username or "")
                    if self.migration_dsn == self.target or app_user == migration_user:
                        raise _configuration_error("Supabase application and migration database roles must be separate")
            elif any((self.connection_mode, self.expected_project_ref, self.project_url, self.migration_dsn)):
                raise _configuration_error("Supabase metadata is not valid for a local PostgreSQL target")

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
        env = os.environ if environ is None else environ
        if env.get(DATABASE_BACKEND_ENV, "").strip().casefold() == SUPABASE_BACKEND:
            if env.get(DATABASE_URL_ENV) is not None or env.get(SQLITE_PATH_ENV) is not None:
                raise _configuration_error("Supabase configuration must not mix generic database or SQLite targets")
            required = {
                SUPABASE_PROJECT_URL_ENV: env.get(SUPABASE_PROJECT_URL_ENV),
                SUPABASE_EXPECTED_PROJECT_REF_ENV: env.get(SUPABASE_EXPECTED_PROJECT_REF_ENV),
                SUPABASE_MIGRATION_DSN_ENV: env.get(SUPABASE_MIGRATION_DSN_ENV),
                SUPABASE_APP_DSN_ENV: env.get(SUPABASE_APP_DSN_ENV),
                SUPABASE_CONNECTION_MODE_ENV: env.get(SUPABASE_CONNECTION_MODE_ENV),
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise _configuration_error("Supabase demo configuration is incomplete; missing required settings: " + ", ".join(missing))
            ref = _supabase_project_ref(required[SUPABASE_EXPECTED_PROJECT_REF_ENV].strip())
            mode = required[SUPABASE_CONNECTION_MODE_ENV].strip().upper()
            return cls(
                POSTGRESQL_BACKEND,
                required[SUPABASE_APP_DSN_ENV].strip(),
                deployment_environment="supabase_demo",
                connection_mode=mode,
                expected_project_ref=ref,
                project_url=required[SUPABASE_PROJECT_URL_ENV].strip(),
                migration_dsn=required[SUPABASE_MIGRATION_DSN_ENV].strip(),
            )
        return cls.from_value(
            None,
            environ=env,
            allow_insecure_local_postgresql=allow_insecure_local_postgresql,
        )

    @property
    def is_sqlite(self) -> bool:
        return self.backend == SQLITE_BACKEND

    @property
    def is_postgresql(self) -> bool:
        return self.backend == POSTGRESQL_BACKEND

    @property
    def is_supabase(self) -> bool:
        return self.deployment_environment == "supabase_demo"

    @property
    def tls_verification(self) -> str:
        if not self.is_postgresql:
            return "not_applicable"
        try:
            sslmode = parse_qs(urlsplit(self.target).query, keep_blank_values=True).get("sslmode", [None])[0]
        except ValueError:
            return "invalid"
        return {
            "require": "encrypted_only_server_identity_unverified",
            "verify-ca": "ca_verified_hostname_unverified",
            "verify-full": "ca_and_hostname_verified",
        }.get(sslmode, "unknown")

    def for_migrations(self) -> "DatabaseConfig":
        if not self.is_supabase or not self.migration_dsn:
            raise _configuration_error("a separately configured Supabase migration DSN is required")
        migration_mode = _supabase_migration_mode(
            self.migration_dsn,
            self.expected_project_ref or "",
        )
        return DatabaseConfig(
            POSTGRESQL_BACKEND,
            self.migration_dsn,
            deployment_environment="supabase_demo",
            connection_mode=migration_mode,
            expected_project_ref=self.expected_project_ref,
            project_url=self.project_url,
        )

    @classmethod
    def for_supabase_migration_target(
        cls,
        migration_dsn: str,
        *,
        project_ref: str,
        project_url: str,
    ) -> "DatabaseConfig":
        """Build a project-validated migration-only target without an app DSN.

        This is intended for the one-time bootstrap/migration phase, before a
        restricted runtime login has been provisioned. Runtime configuration
        continues to require distinct application and migration DSNs.
        """
        mode = _supabase_migration_mode(migration_dsn, project_ref)
        return cls(
            POSTGRESQL_BACKEND,
            migration_dsn,
            deployment_environment="supabase_demo",
            connection_mode=mode,
            expected_project_ref=project_ref,
            project_url=project_url,
        )

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
            f"deployment_environment={self.deployment_environment!r}, "
            f"connection_mode={self.connection_mode!r}, "
            f"expected_project_ref={self.expected_project_ref!r}, "
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
