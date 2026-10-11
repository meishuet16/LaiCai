"""Build a compact, credential-free SQLite seed for the hosted dashboard API.

The source workspace contains the complete synthetic evaluation dataset.  The
hosted dashboard only needs the accounts represented by ``dashboard_cases``.
This utility copies the source database, removes every other tenant/account,
rotates integration credential digests, and clears service-principal records.
"""

from __future__ import annotations

import argparse
import hashlib
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path


TENANT_ID = "tenant-01"


def _tables(connection: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def build_seed(source: Path, target: Path, *, replace: bool = False) -> dict[str, int]:
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    working = target.with_name(f".{target.name}.working")
    if not source.is_file():
        raise FileNotFoundError(f"source database does not exist: {source}")
    if source == target:
        raise ValueError("source and target databases must be different")
    if target.exists():
        if not replace:
            raise FileExistsError(f"target already exists: {target}")
        target.unlink()
    if working.exists():
        working.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as source_connection, closing(
        sqlite3.connect(working)
    ) as target_connection:
        source_connection.backup(target_connection)

    with closing(sqlite3.connect(working)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        keep_accounts = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT customer_id FROM dashboard_cases WHERE tenant_id = ?",
                (TENANT_ID,),
            )
        }
        if not keep_accounts:
            raise RuntimeError("dashboard_cases does not contain a hosted cohort")

        tables = _tables(connection)
        for table in tables:
            columns = _columns(connection, table)
            if "tenant_id" in columns:
                connection.execute(f'DELETE FROM "{table}" WHERE tenant_id <> ?', (TENANT_ID,))

        marks = ",".join("?" for _ in keep_accounts)
        account_parameters = tuple(sorted(keep_accounts))
        for table in tables:
            if "customer_id" in _columns(connection, table):
                connection.execute(
                    f'DELETE FROM "{table}" WHERE customer_id NOT IN ({marks})',
                    account_parameters,
                )

        connection.execute("DELETE FROM service_principals")
        connection.execute("DELETE FROM service_principal_credential_audit")
        connection.execute("DELETE FROM synthetic_import_checkpoints")

        integrations = connection.execute(
            "SELECT integration_id FROM integrations ORDER BY integration_id"
        ).fetchall()
        for (integration_id,) in integrations:
            replacement = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
            connection.execute(
                "UPDATE integrations SET token_digest = ? WHERE integration_id = ?",
                (replacement, integration_id),
            )

        connection.commit()
        connection.execute("VACUUM")
        connection.execute("PRAGMA journal_mode = DELETE")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_key_errors:
            raise RuntimeError("compacted dashboard database failed integrity checks")
        counts = {
            "accounts": connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            "cases": connection.execute("SELECT COUNT(*) FROM dashboard_cases").fetchone()[0],
            "events": connection.execute("SELECT COUNT(*) FROM canonical_events").fetchone()[0],
            "predictions": connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0],
        }

    # On Windows, VACUUM can leave the original file's trailing allocation in
    # place even after SQLite has reduced its logical page count.  A final
    # backup into a new file guarantees the checked-in artifact is compact.
    source_connection = sqlite3.connect(working)
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
        source_connection.close()
    for attempt in range(5):
        try:
            working.unlink()
            break
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1)
    counts["bytes"] = target.stat().st_size
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    counts = build_seed(args.source, args.target, replace=args.replace)
    print(
        "Dashboard seed ready: "
        f"{counts['accounts']} accounts, {counts['cases']} cases, "
        f"{counts['events']} events, {counts['predictions']} predictions, "
        f"{counts['bytes']} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
