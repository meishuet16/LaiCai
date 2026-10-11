"""Start the hosted Dashboard API from the bundled synthetic SQLite seed."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import uvicorn

from retaniq.data_foundation import create_service_principal


TENANT_ID = "tenant-01"
ROOT = Path(__file__).resolve().parents[1]
SEED_DATABASE = ROOT / "backend" / "decision" / "dashboard_seed.db"


def prepare_runtime_database() -> Path:
    if not SEED_DATABASE.is_file():
        raise FileNotFoundError(f"dashboard seed database is unavailable: {SEED_DATABASE}")

    runtime_database = Path(tempfile.gettempdir()) / "laicai-dashboard.sqlite3"
    shutil.copyfile(SEED_DATABASE, runtime_database)
    with closing(sqlite3.connect(runtime_database)) as connection:
        sources = tuple(
            row[0]
            for row in connection.execute(
                "SELECT source FROM integrations WHERE tenant_id = ? ORDER BY source",
                (TENANT_ID,),
            )
        )
        connection.execute("DELETE FROM service_principals")
        connection.execute("DELETE FROM service_principal_credential_audit")
    if not sources:
        raise RuntimeError("dashboard seed has no authorized sources")

    reader_token = create_service_principal(
        runtime_database,
        TENANT_ID,
        role="analyst",
        authorized_sources=sources,
        authorized_purposes=("retention_inference", "billing_valuation", "integration_health"),
    )
    os.environ["RETAINIQ_DASHBOARD_DB"] = str(runtime_database)
    os.environ["RETAINIQ_DASHBOARD_AS_OF"] = "2026-10-01T00:00:00Z"
    os.environ["RETAINIQ_DASHBOARD_LIMIT"] = "30"
    os.environ["RETAINIQ_MODEL_TOKEN"] = reader_token
    return runtime_database


def main() -> int:
    prepare_runtime_database()
    port = int(os.environ.get("PORT", "8003"))
    uvicorn.run("backend.decision.main:app", host="0.0.0.0", port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
