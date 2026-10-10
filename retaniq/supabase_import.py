"""Operator-mediated STANDARD tenant-01 import using DPAPI-protected runtime logins."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .database_config import (
    DATABASE_BACKEND_ENV,
    SUPABASE_APP_DSN_ENV,
    SUPABASE_CONNECTION_MODE_ENV,
    SUPABASE_EXPECTED_PROJECT_REF_ENV,
    SUPABASE_MAINTENANCE_DSN_ENV,
    SUPABASE_PROJECT_URL_ENV,
    SUPABASE_BACKEND,
    DatabaseConfig,
)
from .secret_store import load_dpapi_secret
from .supabase_first_bind import (
    APP_LOGIN,
    APPROVED_DATASET_ID,
    DEFAULT_DATASET,
    LOGIN_CAPABILITIES,
    MAINTENANCE_LOGIN,
    PROJECT_REF,
    TENANT_ID,
    FirstBindBlocked,
    credential_store_path,
)
from .synthetic.canonical_adapter import import_dataset
from .synthetic.validator import validate_dataset


def _runtime_configs() -> tuple[DatabaseConfig, DatabaseConfig]:
    try:
        payload = json.loads(load_dpapi_secret(credential_store_path()))
    except (OSError, ValueError, json.JSONDecodeError):
        raise FirstBindBlocked("protected_runtime_credential_store_unreadable") from None
    if payload.get("project_ref") != PROJECT_REF:
        raise FirstBindBlocked("protected_runtime_credential_store_project_mismatch")
    logins = payload.get("logins")
    if not isinstance(logins, dict) or set(logins) != {APP_LOGIN, MAINTENANCE_LOGIN}:
        raise FirstBindBlocked("restricted_runtime_login_pair_missing")
    if any(logins[login].get("capability") != capability for login, capability in LOGIN_CAPABILITIES.items()):
        raise FirstBindBlocked("restricted_runtime_capability_mismatch")
    app = logins[APP_LOGIN]
    maintenance = logins[MAINTENANCE_LOGIN]
    if app.get("database_role") != APP_LOGIN or maintenance.get("database_role") != MAINTENANCE_LOGIN:
        raise FirstBindBlocked("restricted_runtime_login_name_mismatch")
    environment = {
        DATABASE_BACKEND_ENV: SUPABASE_BACKEND,
        SUPABASE_PROJECT_URL_ENV: payload.get("project_url"),
        SUPABASE_EXPECTED_PROJECT_REF_ENV: PROJECT_REF,
        SUPABASE_CONNECTION_MODE_ENV: payload.get("connection_mode"),
        SUPABASE_APP_DSN_ENV: app.get("dsn"),
        SUPABASE_MAINTENANCE_DSN_ENV: maintenance.get("dsn"),
    }
    try:
        app_config = DatabaseConfig.from_environment(environment)
        maintenance_config = app_config.for_maintenance()
    except ValueError:
        raise FirstBindBlocked("restricted_runtime_database_configuration_invalid") from None
    if app_config.postgresql_dsn == maintenance_config.postgresql_dsn:
        raise FirstBindBlocked("backend_and_maintenance_logins_must_be_distinct")
    return app_config, maintenance_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m retaniq.supabase_import",
        description="Import only the approved STANDARD dataset into tenant-01 using restricted Supabase logins.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--tenant-id", default=TENANT_ID)
    parser.add_argument("--verify-idempotency", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not sys.stdin.isatty():
        print(json.dumps({"status": "BLOCKED", "reason": "interactive_terminal_required", "mutations_performed": False}))
        return 2
    started = False
    try:
        if args.tenant_id != TENANT_ID:
            raise FirstBindBlocked("tenant_scope_must_be_tenant_01")
        dataset_path = args.dataset.expanduser().resolve()
        validation = validate_dataset(dataset_path)
        if validation.get("status") != "PASS" or validation.get("dataset_id") != APPROVED_DATASET_ID:
            raise FirstBindBlocked("approved_standard_dataset_validation_failed")
        app_config, maintenance_config = _runtime_configs()
        phrase = f"IMPORT STANDARD {TENANT_ID} {PROJECT_REF} {APPROVED_DATASET_ID}"
        confirmation = input(f"This writes only synthetic tenant-01 data. Type {phrase}: ")
        if confirmation != phrase:
            print(json.dumps({"status": "CANCELLED", "project_ref": PROJECT_REF, "mutations_performed": False}))
            return 4
        started = True
        result = import_dataset(
            dataset_path,
            app_config,
            tenant_id=TENANT_ID,
            maintenance_database_path=maintenance_config,
            verify_idempotency=args.verify_idempotency,
        )
        result.update({"project_ref": PROJECT_REF, "mutations_performed": True})
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result.get("status") == "VERIFIED" else 1
    except Exception as error:
        result: dict[str, Any] = {
            "status": "BLOCKED",
            "project_ref": PROJECT_REF,
            "reason": error.reason if isinstance(error, FirstBindBlocked) else type(error).__name__,
            "tenant_scope": TENANT_ID,
            "mutation_status": "MAY_HAVE_OCCURRED" if started else "NONE",
            "mutations_performed": started,
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
