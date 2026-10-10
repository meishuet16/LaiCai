"""Canonical CSV import and historical replay input."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from .data_foundation import (
    DataFoundationError,
    ReadPrincipal,
    _db,
    _assert_read_principal,
    _require_purposes,
    _validate_id,
    authenticate_integration,
    get_events_as_of,
    ingest_event,
    normalize_timestamp,
    update_mapping_version,
    SCHEMA_VERSION,
)

REQUIRED_TARGETS = {"source_event_id", "external_customer_id", "event_type", "occurred_at", "attributes"}
ALLOWED_TARGETS = REQUIRED_TARGETS | {"source_available_at"}


def _validate_mapping(mapping: Any, trust_source_availability: bool) -> tuple[str, dict[str, str]]:
    if not isinstance(mapping, dict) or set(mapping) - {"mapping_version", "columns"}:
        raise DataFoundationError("invalid_import_mapping")
    version = mapping.get("mapping_version")
    columns = mapping.get("columns")
    try:
        version = _validate_id(version)
    except DataFoundationError:
        raise DataFoundationError("invalid_import_mapping") from None
    if not isinstance(columns, dict) or not REQUIRED_TARGETS.issubset(columns):
        raise DataFoundationError("invalid_import_mapping")
    if not set(columns).issubset(ALLOWED_TARGETS):
        raise DataFoundationError("invalid_import_mapping")
    if any(not isinstance(header, str) or not header or len(header) > 128 for header in columns.values()):
        raise DataFoundationError("invalid_import_mapping")
    if "source_available_at" in columns and not trust_source_availability:
        raise DataFoundationError("invalid_import_mapping")
    if len(set(columns.values())) != len(columns):
        raise DataFoundationError("invalid_import_mapping")
    return version, dict(columns)


def import_csv(
    database_path: str,
    principal: IntegrationPrincipal,
    csv_path: str,
    mapping: dict[str, Any],
    *,
    received_at: str | None = None,
    trust_source_availability: bool = False,
) -> dict[str, Any]:
    mapping_version, columns = _validate_mapping(mapping, trust_source_availability)
    counts = Counter()
    failures: Counter[str] = Counter()
    try:
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or any(header not in reader.fieldnames for header in columns.values()):
                raise DataFoundationError("invalid_csv")
            principal = update_mapping_version(database_path, principal, mapping_version)
            for row in reader:
                try:
                    attributes_value = row[columns["attributes"]]
                    attributes = json.loads(attributes_value) if attributes_value else {}
                    envelope = {
                        "source": principal.source,
                        "source_event_id": row[columns["source_event_id"]],
                        "external_customer_id": row[columns["external_customer_id"]],
                        "event_type": row[columns["event_type"]],
                        "occurred_at": row[columns["occurred_at"]],
                        "attributes": attributes,
                        "schema_version": SCHEMA_VERSION,
                    }
                    available_at = None
                    if "source_available_at" in columns:
                        available_at = row[columns["source_available_at"]] or None
                    result = ingest_event(
                        database_path, principal, envelope, received_at=received_at,
                        trusted_source_available_at=available_at,
                    )
                    if result["duplicate"]:
                        counts["duplicates"] += 1
                    else:
                        counts["accepted"] += 1
                except (DataFoundationError, json.JSONDecodeError) as error:
                    code = error.code if isinstance(error, DataFoundationError) else "invalid_event"
                    counts["rejected"] += 1
                    failures[code] += 1
    except DataFoundationError:
        raise
    except (OSError, UnicodeError, csv.Error):
        raise DataFoundationError("invalid_csv") from None
    return {
        "accepted": counts["accepted"], "duplicates": counts["duplicates"],
        "rejected": counts["rejected"], "rejected_by_code": dict(sorted(failures.items())),
        "mapping_version": mapping_version,
    }


def import_csv_with_token(
    database_path: str,
    token: str | None,
    csv_path: str,
    mapping: dict[str, Any],
    *,
    received_at: str | None = None,
    trust_source_availability: bool = False,
) -> dict[str, Any]:
    principal = authenticate_integration(database_path, token)
    return import_csv(
        database_path, principal, csv_path, mapping,
        received_at=received_at, trust_source_availability=trust_source_availability,
    )


def iter_replay_events(
    database_path: str,
    principal: ReadPrincipal,
    available_from: str,
    available_through: str,
) -> Iterator[dict[str, Any]]:
    start = normalize_timestamp(available_from)
    end = normalize_timestamp(available_through)
    if end < start:
        raise DataFoundationError("invalid_contract")
    with _db(database_path) as connection:
        authorized_sources = _assert_read_principal(connection, principal)
        _require_purposes(principal, "retention_inference")
        source_placeholders = ",".join("?" for _ in authorized_sources)
        rows = connection.execute(
            "SELECT DISTINCT customer_id FROM canonical_events "
            f"WHERE tenant_id = ? AND source IN ({source_placeholders})",
            (principal.tenant_id, *authorized_sources),
        ).fetchall()
    replay: list[dict[str, Any]] = []
    for row in rows:
        for event in get_events_as_of(database_path, principal, row["customer_id"], end):
            if start <= event["available_at"] <= end:
                replay.append(event)
    replay.sort(key=lambda event: (event["available_at"], event["occurred_at"], event["event_id"]))
    yield from replay
