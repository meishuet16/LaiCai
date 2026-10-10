"""Historical dataset evidence and readiness checks for Part 2.

The adapter in this module is an input boundary for Member 1's canonical
tables. It is not a replacement database schema and does not persist data.
The validator reports whether the supplied evidence can support genuine
7/14/30-day churn forecasting; it never invents events, labels, or outcomes.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field


Row = Mapping[str, Any]
ValueParser = Callable[[Any], bool]


class DatasetStatus(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class ProvenanceEvidenceType(str, Enum):
    REAL_AUTHORIZED = "real_authorized"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


class FieldState(str, Enum):
    ABSENT = "absent"
    PRESENT_EMPTY = "present_empty"
    USABLE = "usable"
    INVALID = "invalid"


class _ReadinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetProvenance(_ReadinessModel):
    """Source evidence supplied alongside the adapted records."""

    source_name: str | None = None
    license_or_authorization: str | None = None
    evidence_type: ProvenanceEvidenceType = ProvenanceEvidenceType.UNKNOWN
    availability_assumption: str | None = None


class FieldEvidence(_ReadinessModel):
    table: str
    field: str
    exists_in_rows: bool
    usable_value_count: int = Field(ge=0)
    missing_value_count: int = Field(ge=0)
    invalid_value_count: int = Field(ge=0)
    state: FieldState


class DatasetReadinessReport(_ReadinessModel):
    """Structured, non-PII readiness result."""

    status: DatasetStatus
    eligible_for_genuine_training: bool
    available_data_categories: list[str] = Field(default_factory=list)
    missing_required_fields: list[str] = Field(default_factory=list)
    data_quality_issues: list[str] = Field(default_factory=list)
    supported_horizons: list[int] = Field(default_factory=list)
    unsupported_or_unverified: list[str] = Field(default_factory=list)
    dataset_source: DatasetProvenance
    blockers: list[str] = Field(default_factory=list)
    field_checks: list[FieldEvidence] = Field(default_factory=list)
    row_counts: dict[str, int] = Field(default_factory=dict)


@dataclass(frozen=True)
class DatasetFieldMapping:
    """Mapping from Member 1/source fields to readiness concepts.

    The defaults match the documented canonical naming, but callers can map a
    source dataset without changing Member 1's ingestion or database schema.
    """

    tenant_id: str = "tenant_id"
    account_id: str = "customer_id"
    subscription_id: str = "subscription_id"
    event_id: str = "event_id"
    event_occurred_at: str = "occurred_at"
    source_available_at: str | None = "received_at"
    subscription_started_at: str = "started_at"
    subscription_ended_at: str = "ended_at"
    subscription_status: str = "status"
    subscription_event_type: str = "event_type"
    outcome_id: str = "outcome_id"
    outcome_as_of: str = "as_of"
    outcome_observed_through: str = "label_observed_through"
    churn_effective_at: str = "churn_effective_at"
    cancellation_requested_at: str = "cancellation_requested_at"


@dataclass(frozen=True)
class HistoricalDatasetAdapter:
    """Read-only normalized view over source records supplied by Member 1.

    Each collection contains mappings from one source table/category. The
    validator reads these collections but never stores or mutates their rows.
    """

    accounts: Sequence[Row] = field(default_factory=tuple)
    subscriptions: Sequence[Row] = field(default_factory=tuple)
    subscription_events: Sequence[Row] = field(default_factory=tuple)
    usage_events: Sequence[Row] = field(default_factory=tuple)
    billing_events: Sequence[Row] = field(default_factory=tuple)
    outcomes: Sequence[Row] = field(default_factory=tuple)


@dataclass(frozen=True)
class DatasetReadinessConfig:
    """Explicit, adjustable gate heuristics.

    The 28-day baseline span is a readiness heuristic, not a finalized model
    feature contract. Team policy and development data must confirm it later.
    """

    required_horizons: tuple[int, ...] = (7, 14, 30)
    baseline_min_history_days: int = 28


_TABLE_NAMES = (
    "accounts",
    "subscriptions",
    "subscription_events",
    "usage_events",
    "billing_events",
    "outcomes",
)


def _non_empty(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _parse_id(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _field_evidence(
    table: str,
    rows: Sequence[Row],
    field_name: str | None,
    parser: ValueParser = _non_empty,
) -> FieldEvidence:
    if not field_name:
        return FieldEvidence(
            table=table,
            field="<not mapped>",
            exists_in_rows=False,
            state=FieldState.ABSENT,
        )

    exists = any(field_name in row for row in rows)
    usable = 0
    missing = 0
    invalid = 0
    for row in rows:
        value = row.get(field_name)
        if not _non_empty(value):
            missing += 1
        elif parser(value):
            usable += 1
        else:
            invalid += 1

    if not exists:
        state = FieldState.ABSENT
    elif invalid:
        state = FieldState.INVALID
    elif not usable:
        state = FieldState.PRESENT_EMPTY
    else:
        state = FieldState.USABLE

    return FieldEvidence(
        table=table,
        field=field_name,
        exists_in_rows=exists,
        usable_value_count=usable,
        missing_value_count=missing,
        invalid_value_count=invalid,
        state=state,
    )


def _row_key(row: Row, mapping: DatasetFieldMapping) -> tuple[str, str] | None:
    tenant = row.get(mapping.tenant_id)
    account = row.get(mapping.account_id)
    if not (_parse_id(tenant) and _parse_id(account)):
        return None
    return tenant.strip(), account.strip()


def _duplicate_count(rows: Sequence[Row], key_fields: Sequence[str]) -> int:
    keys: list[str] = []
    for row in rows:
        if all(_non_empty(row.get(field_name)) for field_name in key_fields):
            keys.append(
                json.dumps(
                    [str(row.get(field_name)) for field_name in key_fields],
                    ensure_ascii=False,
                )
            )
        else:
            keys.append(json.dumps(sorted((str(key), repr(value)) for key, value in row.items())))
    return sum(count - 1 for count in Counter(keys).values() if count > 1)


def _add_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def assess_dataset_readiness(
    adapter: HistoricalDatasetAdapter | None,
    *,
    provenance: DatasetProvenance | None = None,
    field_mapping: DatasetFieldMapping | None = None,
    config: DatasetReadinessConfig | None = None,
) -> DatasetReadinessReport:
    """Assess whether adapted historical evidence supports multi-horizon labels.

    The function returns counts, field names, and issue descriptions only. It
    does not include customer identifiers or raw records in its report.
    """

    mapping = field_mapping or DatasetFieldMapping()
    gate = config or DatasetReadinessConfig()
    source = provenance or DatasetProvenance()
    if adapter is None:
        return DatasetReadinessReport(
            status=DatasetStatus.BLOCKED,
            eligible_for_genuine_training=False,
            dataset_source=source,
            unsupported_or_unverified=["All dataset requirements are unverified."],
            blockers=["No historical dataset was supplied."],
            row_counts={table: 0 for table in _TABLE_NAMES},
        )

    tables = {table: list(getattr(adapter, table)) for table in _TABLE_NAMES}
    row_counts = {table: len(rows) for table, rows in tables.items()}
    if not any(row_counts.values()):
        return DatasetReadinessReport(
            status=DatasetStatus.BLOCKED,
            eligible_for_genuine_training=False,
            dataset_source=source,
            unsupported_or_unverified=["All dataset requirements are unverified."],
            blockers=["The supplied adapter contains no records."],
            row_counts=row_counts,
        )

    field_checks: list[FieldEvidence] = []
    missing_required: list[str] = []
    quality_issues: list[str] = []
    unsupported: list[str] = []
    blockers: list[str] = []
    categories: list[str] = []

    def check(
        table: str,
        field_name: str | None,
        *,
        required: bool = False,
        parser: ValueParser = _non_empty,
        label: str | None = None,
    ) -> FieldEvidence:
        evidence = _field_evidence(table, tables[table], field_name, parser)
        field_checks.append(evidence)
        name = label or f"{table}.{field_name or '<not mapped>'}"
        if required and evidence.state is not FieldState.USABLE:
            _add_unique(missing_required, name)
            if evidence.state is FieldState.INVALID:
                _add_unique(blockers, f"Required field has invalid values: {name}.")
            else:
                _add_unique(blockers, f"Required field is missing or unusable: {name}.")
        if evidence.missing_value_count:
            _add_unique(
                quality_issues,
                f"{name} has {evidence.missing_value_count} missing value(s).",
            )
        if evidence.invalid_value_count:
            _add_unique(
                quality_issues,
                f"{name} has {evidence.invalid_value_count} invalid value(s).",
            )
        return evidence

    account_tenant = check(
        "accounts", mapping.tenant_id, required=True, parser=_parse_id, label="accounts.tenant_id"
    )
    account_ids = check(
        "accounts", mapping.account_id, required=True, parser=_parse_id, label="accounts.customer_id"
    )
    account_keys = {
        key for row in tables["accounts"] if (key := _row_key(row, mapping)) is not None
    }
    if account_tenant.state is FieldState.USABLE and account_ids.state is FieldState.USABLE:
        _add_unique(categories, "stable_account_identifiers")
        if _duplicate_count(tables["accounts"], (mapping.tenant_id, mapping.account_id)):
            _add_unique(quality_issues, "Duplicate tenant/account identifiers found in accounts.")
            blockers.append("Account identity is not unique within the supplied evidence.")

    check(
        "subscriptions", mapping.tenant_id, required=True, parser=_parse_id, label="subscriptions.tenant_id"
    )
    check(
        "subscriptions", mapping.account_id, required=True, parser=_parse_id, label="subscriptions.customer_id"
    )
    check(
        "subscriptions",
        mapping.subscription_id,
        required=True,
        parser=_parse_id,
        label="subscriptions.subscription_id",
    )
    check(
        "subscriptions",
        mapping.subscription_started_at,
        required=True,
        parser=lambda value: _parse_timestamp(value) is not None,
        label="subscriptions.started_at",
    )
    subscription_status = check(
        "subscriptions", mapping.subscription_status, parser=_non_empty, label="subscriptions.status"
    )
    subscription_ended = check(
        "subscriptions",
        mapping.subscription_ended_at,
        parser=lambda value: _parse_timestamp(value) is not None,
        label="subscriptions.ended_at",
    )

    check(
        "subscription_events",
        mapping.tenant_id,
        required=True,
        parser=_parse_id,
        label="subscription_events.tenant_id",
    )
    check(
        "subscription_events",
        mapping.account_id,
        required=True,
        parser=_parse_id,
        label="subscription_events.customer_id",
    )
    lifecycle_event_id = check(
        "subscription_events",
        mapping.event_id,
        required=True,
        parser=_parse_id,
        label="subscription_events.event_id",
    )
    lifecycle_event_time = check(
        "subscription_events",
        mapping.event_occurred_at,
        required=True,
        parser=lambda value: _parse_timestamp(value) is not None,
        label="subscription_events.occurred_at",
    )
    lifecycle_event_type = check(
        "subscription_events",
        mapping.subscription_event_type,
        required=True,
        parser=_non_empty,
        label="subscription_events.event_type",
    )
    if lifecycle_event_time.state is FieldState.USABLE and lifecycle_event_type.state is FieldState.USABLE:
        _add_unique(categories, "subscription_lifecycle_history")
    elif tables["subscriptions"] and subscription_status.state is FieldState.USABLE:
        _add_unique(unsupported, "Append-only subscription lifecycle event history is not established.")

    for table, category, event_id_label in (
        ("usage_events", "timestamped_usage_events", "usage_events.event_id"),
        ("billing_events", "timestamped_billing_events", "billing_events.event_id"),
    ):
        check(table, mapping.tenant_id, required=bool(tables[table]), parser=_parse_id, label=f"{table}.tenant_id")
        check(table, mapping.account_id, required=bool(tables[table]), parser=_parse_id, label=f"{table}.customer_id")
        event_id = check(
            table,
            mapping.event_id,
            required=bool(tables[table]),
            parser=_parse_id,
            label=event_id_label,
        )
        event_time = check(
            table,
            mapping.event_occurred_at,
            required=bool(tables[table]),
            parser=lambda value: _parse_timestamp(value) is not None,
            label=f"{table}.occurred_at",
        )
        if event_id.state is FieldState.USABLE and event_time.state is FieldState.USABLE:
            _add_unique(categories, category)

    if not tables["usage_events"] and not tables["billing_events"]:
        blockers.append("No timestamped usage or billing events were supplied.")

    outcome_account = check(
        "outcomes", mapping.account_id, required=True, parser=_parse_id, label="outcomes.customer_id"
    )
    outcome_as_of = check(
        "outcomes",
        mapping.outcome_as_of,
        required=True,
        parser=lambda value: _parse_timestamp(value) is not None,
        label="outcomes.as_of",
    )
    outcome_observed = check(
        "outcomes",
        mapping.outcome_observed_through,
        required=True,
        parser=lambda value: _parse_timestamp(value) is not None,
        label="outcomes.label_observed_through",
    )
    outcome_churn = check(
        "outcomes",
        mapping.churn_effective_at,
        required=True,
        parser=lambda value: _parse_timestamp(value) is not None,
        label="outcomes.churn_effective_at",
    )

    if outcome_churn.usable_value_count == 0:
        blockers.append("No usable churn-effective timestamps were supplied.")
    if outcome_account.state is FieldState.USABLE and outcome_as_of.state is FieldState.USABLE:
        _add_unique(categories, "dated_prediction_cutoffs")

    cancellation = check(
        "outcomes",
        mapping.cancellation_requested_at,
        parser=lambda value: _parse_timestamp(value) is not None,
        label="outcomes.cancellation_requested_at",
    )
    if cancellation.usable_value_count:
        _add_unique(categories, "known_cancellation_timestamps")
    else:
        _add_unique(unsupported, "Known cancellation request timestamps are unavailable or unverified.")

    all_reference_tables = (
        "subscriptions",
        "subscription_events",
        "usage_events",
        "billing_events",
        "outcomes",
    )
    for table in all_reference_tables:
        for row in tables[table]:
            key = _row_key(row, mapping)
            if key is None:
                continue
            if key not in account_keys:
                _add_unique(
                    quality_issues,
                    f"{table} contains account references not present in accounts.",
                )
                blockers.append("Tenant/account mapping is incomplete.")
                break
    if account_keys and not blockers and all(tables[table] for table in ("subscriptions", "outcomes")):
        _add_unique(categories, "tenant_account_mapping")

    for table, key_fields in (
        ("subscriptions", (mapping.tenant_id, mapping.subscription_id)),
        ("subscription_events", (mapping.tenant_id, mapping.event_id)),
        ("usage_events", (mapping.tenant_id, mapping.event_id)),
        ("billing_events", (mapping.tenant_id, mapping.event_id)),
        ("outcomes", (mapping.tenant_id, mapping.outcome_id)),
    ):
        if tables[table] and _duplicate_count(tables[table], key_fields):
            _add_unique(quality_issues, f"Duplicate records found in {table}.")
            blockers.append(f"Duplicate records prevent reliable use of {table}.")

    availability_evidence: list[FieldEvidence] = []
    for table in ("subscription_events", "usage_events", "billing_events"):
        if tables[table]:
            availability_evidence.append(
                check(
                    table,
                    mapping.source_available_at,
                    parser=lambda value: _parse_timestamp(value) is not None,
                    label=f"{table}.received_at",
                )
            )
    availability_values = sum(item.usable_value_count for item in availability_evidence)
    availability_invalid = sum(item.invalid_value_count for item in availability_evidence)
    if availability_values:
        _add_unique(categories, "source_availability_timestamps")
        if availability_invalid:
            _add_unique(unsupported, "Some source-availability timestamps are invalid.")
    else:
        _add_unique(unsupported, "Original source-availability timestamps are unavailable or unverified.")
        if not source.availability_assumption:
            _add_unique(
                unsupported,
                "No documented defensible availability-time assumption was supplied.",
            )

    supported_horizons: list[int] = []
    horizon_counts: dict[int, dict[str, int]] = {
        horizon: {"positive": 0, "negative": 0, "covered": 0}
        for horizon in gate.required_horizons
    }
    if outcome_as_of.state is FieldState.USABLE and outcome_observed.state is FieldState.USABLE:
        for row in tables["outcomes"]:
            as_of = _parse_timestamp(row.get(mapping.outcome_as_of))
            observed_through = _parse_timestamp(row.get(mapping.outcome_observed_through))
            churn_at = _parse_timestamp(row.get(mapping.churn_effective_at))
            if not as_of or not observed_through:
                continue
            if churn_at and churn_at <= as_of:
                _add_unique(
                    quality_issues,
                    "An outcome contains churn effective at or before its prediction cutoff.",
                )
                continue
            for horizon in gate.required_horizons:
                horizon_end = as_of + timedelta(days=horizon)
                if churn_at and churn_at <= horizon_end:
                    horizon_counts[horizon]["positive"] += 1
                    horizon_counts[horizon]["covered"] += 1
                elif observed_through >= horizon_end:
                    horizon_counts[horizon]["negative"] += 1
                    horizon_counts[horizon]["covered"] += 1
        for horizon, counts in horizon_counts.items():
            if counts["positive"] and counts["negative"]:
                supported_horizons.append(horizon)
                _add_unique(categories, f"{horizon}_day_observation_coverage")
            else:
                _add_unique(
                    unsupported,
                    f"{horizon}-day coverage lacks both an observed positive and a fully observed negative.",
                )
    else:
        for horizon in gate.required_horizons:
            _add_unique(unsupported, f"{horizon}-day observation coverage is not established.")

    usage_rows = tables["usage_events"]
    baseline_ready = False
    if usage_rows and outcome_as_of.state is FieldState.USABLE:
        usage_by_account: dict[tuple[str, str], list[datetime]] = {}
        for row in usage_rows:
            key = _row_key(row, mapping)
            occurred_at = _parse_timestamp(row.get(mapping.event_occurred_at))
            if key and occurred_at:
                usage_by_account.setdefault(key, []).append(occurred_at)
        for row in tables["outcomes"]:
            key = _row_key(row, mapping)
            cutoff = _parse_timestamp(row.get(mapping.outcome_as_of))
            if not key or not cutoff:
                continue
            prior = sorted(
                event_time for event_time in usage_by_account.get(key, []) if event_time < cutoff
            )
            if len(prior) >= 2 and (prior[-1] - prior[0]).days >= gate.baseline_min_history_days:
                baseline_ready = True
                break
    if baseline_ready:
        _add_unique(categories, "personalized_baseline_history")
    else:
        _add_unique(
            unsupported,
            f"No account demonstrates the configured {gate.baseline_min_history_days}-day pre-cutoff usage history for a personalized baseline.",
        )

    if source.evidence_type is ProvenanceEvidenceType.REAL_AUTHORIZED and source.license_or_authorization:
        _add_unique(categories, "provenance_and_authorization")
    else:
        _add_unique(unsupported, "Dataset provenance and authorization/license evidence is incomplete.")
        if source.evidence_type is ProvenanceEvidenceType.UNKNOWN:
            blockers.append("Dataset provenance and authorization/license are not established.")
        elif source.evidence_type is ProvenanceEvidenceType.REAL_AUTHORIZED and not source.license_or_authorization:
            blockers.append("Authorized dataset is missing license/authorization documentation.")

    if not supported_horizons:
        blockers.append("No prediction horizon has sufficient observed positive and negative outcomes.")
    if len(supported_horizons) < len(gate.required_horizons):
        _add_unique(unsupported, "Full 7/14/30-day multi-horizon readiness is not established.")

    # Deduplicate blockers while preserving the order in which evidence was found.
    blockers = list(dict.fromkeys(blockers))
    if blockers:
        status = DatasetStatus.BLOCKED
    elif (
        len(supported_horizons) < len(gate.required_horizons)
        or not baseline_ready
        or availability_values == 0
        or source.evidence_type is not ProvenanceEvidenceType.REAL_AUTHORIZED
    ):
        status = DatasetStatus.PARTIAL
    else:
        status = DatasetStatus.PASS

    eligible = status is DatasetStatus.PASS and supported_horizons == list(gate.required_horizons)
    return DatasetReadinessReport(
        status=status,
        eligible_for_genuine_training=eligible,
        available_data_categories=categories,
        missing_required_fields=missing_required,
        data_quality_issues=list(dict.fromkeys(quality_issues)),
        supported_horizons=supported_horizons,
        unsupported_or_unverified=list(dict.fromkeys(unsupported)),
        dataset_source=source,
        blockers=blockers,
        field_checks=field_checks,
        row_counts=row_counts,
    )


__all__ = [
    "DatasetFieldMapping",
    "DatasetProvenance",
    "DatasetReadinessConfig",
    "DatasetReadinessReport",
    "DatasetStatus",
    "FieldEvidence",
    "FieldState",
    "HistoricalDatasetAdapter",
    "ProvenanceEvidenceType",
    "assess_dataset_readiness",
]
