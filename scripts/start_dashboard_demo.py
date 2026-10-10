"""Start the local API against the DPAPI-protected dashboard workspace."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from retaniq.secret_store import load_dpapi_secret


DATASET_ID = "synthetic-saas-v1-2-standard-s2026-970a9d231e68"
DEFAULT_DIRECTORY = (
    Path.home() / "RetainIQ-private" / "synthetic_saas_v1_2" / "working" / "dashboard-workspace"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DIRECTORY / f"{DATASET_ID}-dashboard.sqlite3",
    )
    parser.add_argument(
        "--reader-secret",
        type=Path,
        default=DEFAULT_DIRECTORY / "dashboard-reader.dpapi",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args()

    database = args.database.expanduser().resolve()
    secret = args.reader_secret.expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(f"dashboard database does not exist: {database}")
    if not secret.is_file():
        raise FileNotFoundError(f"protected reader secret does not exist: {secret}")

    os.environ["RETAINIQ_DASHBOARD_DB"] = str(database)
    os.environ["RETAINIQ_DASHBOARD_AS_OF"] = "2026-10-01T00:00:00Z"
    os.environ["RETAINIQ_DASHBOARD_LIMIT"] = "30"
    os.environ["RETAINIQ_MODEL_TOKEN"] = load_dpapi_secret(secret)
    uvicorn.run("backend.decision.main:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
