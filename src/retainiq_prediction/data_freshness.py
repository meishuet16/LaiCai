"""Point-in-time source freshness assessment for prediction inputs.

Freshness describes source coverage and synchronization health.  It is not a
proxy for customer activity: an account with no sessions can still have fresh
usage coverage.  This module consumes source heartbeat/watermark evidence and
does not read a database or infer missing events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Mapping, Sequence, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .contracts import FreshnessStatus
from .point_in_time import AvailabilityPolicy


class FreshnessSource(str, Enum):
    SUBSCRIPTION_LIFECYCLE = "subscription_lifecycle"
    BILLING_EVENTS = "billing_events"
    USAGE_COVERAGE = "usage_coverage"


class FreshnessReasonCode(str, Enum):
    SOURCE_FRESH = "SOURCE_FRESH"
    SOURCE_PARTIALLY_STALE = "SOURCE_PARTIALLY_STALE"
    SOURCE_STALE = "SOURCE_STALE"
    SOURCE_NOT_CONNECTED = "SOURCE_NOT_CONNECTED"
    SOURCE_METADATA_MISSING = "SOURCE_METADATA_MISSING"
    SOURCE_COVERAGE_MISSING = "SOURCE_COVERAGE_MISSING"
    SOURCE_COVERAGE_INCOMPLETE = "SOURCE_COVERAGE_INCOMPLETE"
    FUTURE_METADATA_EXCLUDED = "FUTURE_METADATA_EXCLUDED"
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"
    CUSTOMER_SCOPE_MISMATCH = "CUSTOMER_SCOPE_MISMATCH"
    OPTIONAL_SOURCE_MISSING = "OPTIONAL_SOURCE_MISSING"
    ESSENTIAL_SOURCE_MISSING = "ESSENTIAL_SOURCE_MISSING"


class _FreshnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceFreshnessEvidence(_FreshnessModel):
    """Source health facts known for one tenant/account and cutoff."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_available_at: AwareDatetime | None = None
    received_at: AwareDatetime | None = None
    last_sync_at: AwareDatetime | None = None
    watermark_at: AwareDatetime | None = None
    complete: bool | None = None
    # `None` means the source's operational connection state was not
    # independently observed. It must not be inferred from account event
    # silence. Freshness can still be established from independently supplied
    # complete, scoped coverage evidence without claiming connectivity.
    connected: bool | None = None
    source_record_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class SourceFreshnessAssessment(_FreshnessModel):
    source: str = Field(min_length=1)
    status: FreshnessStatus
    reason_codes: tuple[FreshnessReasonCode, ...] = ()
    input_data_as_of: AwareDatetime | None = None
    availability_basis: str | None = None
    evidence: SourceFreshnessEvidence | None = None
    missing: bool = False
    limitations: tuple[str, ...] = ()


class DataFreshnessAssessment(_FreshnessModel):
    """Aggregate freshness result retained separately from PredictionOutput."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    status: FreshnessStatus
    input_data_as_of: AwareDatetime | None = None
    source_assessments: tuple[SourceFreshnessAssessment, ...] = ()
    missing_sources: tuple[str, ...] = ()
    reason_codes: tuple[FreshnessReasonCode, ...] = ()
    source_availability_by_source: dict[str, AwareDatetime] = Field(default_factory=dict)
    source_record_refs: tuple[str, ...] = ()
    policy_version: str = Field(min_length=1)
    evaluated_at: AwareDatetime
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class FreshnessPolicy:
    """Versioned source-specific freshness policy.

    The defaults are conservative synthetic-test examples, not validated
    production SLAs.  Member 1 must confirm source-specific thresholds.
    """

    policy_version: str = "freshness_v1"
    availability_policy: AvailabilityPolicy = AvailabilityPolicy.SOURCE_THEN_RECEIVED
    source_max_age: Mapping[str, timedelta] = field(
        default_factory=lambda: {
            FreshnessSource.SUBSCRIPTION_LIFECYCLE.value: timedelta(days=2),
            FreshnessSource.BILLING_EVENTS.value: timedelta(days=2),
            FreshnessSource.USAGE_COVERAGE.value: timedelta(days=2),
        }
    )
    essential_sources: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                FreshnessSource.SUBSCRIPTION_LIFECYCLE.value,
                FreshnessSource.USAGE_COVERAGE.value,
            }
        )
    )

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("policy_version must be non-empty")
        if any(not source.strip() for source in self.source_max_age):
            raise ValueError("freshness source names must be non-empty")
        if any(limit < timedelta(0) for limit in self.source_max_age.values()):
            raise ValueError("freshness limits must not be negative")
        if not self.essential_sources.issubset(self.source_max_age):
            raise ValueError("essential sources require configured freshness limits")


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _availability_time(
    evidence: SourceFreshnessEvidence, policy: AvailabilityPolicy
) -> tuple[datetime | None, str | None]:
    if policy is AvailabilityPolicy.SOURCE_ONLY:
        return evidence.source_available_at, "source_available_at"
    if policy is AvailabilityPolicy.RECEIVED_ONLY:
        return evidence.received_at, "received_at"
    if evidence.source_available_at is not None:
        return evidence.source_available_at, "source_available_at"
    if evidence.received_at is not None:
        return evidence.received_at, "received_at"
    return None, None


T = TypeVar("T")


def _unique(values: Iterable[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(values))


def _source_assessment(
    source: str,
    evidence: SourceFreshnessEvidence | None,
    *,
    tenant_id: str,
    customer_id: str,
    as_of: datetime,
    policy: FreshnessPolicy,
) -> SourceFreshnessAssessment:
    if evidence is None:
        reason = (
            FreshnessReasonCode.ESSENTIAL_SOURCE_MISSING
            if source in policy.essential_sources
            else FreshnessReasonCode.OPTIONAL_SOURCE_MISSING
        )
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.UNKNOWN,
            reason_codes=(reason, FreshnessReasonCode.SOURCE_METADATA_MISSING),
            missing=True,
            limitations=("No source freshness evidence was supplied.",),
        )

    scope_reasons: list[FreshnessReasonCode] = []
    if evidence.tenant_id != tenant_id:
        scope_reasons.append(FreshnessReasonCode.TENANT_SCOPE_MISMATCH)
    if evidence.customer_id != customer_id:
        scope_reasons.append(FreshnessReasonCode.CUSTOMER_SCOPE_MISMATCH)
    if scope_reasons:
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.UNKNOWN,
            reason_codes=tuple(scope_reasons),
            evidence=evidence,
            limitations=("Out-of-scope freshness evidence was ignored.",),
        )

    available_at, basis = _availability_time(evidence, policy.availability_policy)
    future_fields = [
        timestamp
        for timestamp in (
            available_at,
            evidence.last_sync_at,
            evidence.watermark_at,
        )
        if timestamp is not None and timestamp > as_of
    ]
    if future_fields:
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.UNKNOWN,
            reason_codes=(FreshnessReasonCode.FUTURE_METADATA_EXCLUDED,),
            evidence=evidence,
            limitations=(
                "Source metadata after the prediction cutoff was excluded.",
            ),
        )
    if evidence.connected is False:
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.STALE,
            reason_codes=(FreshnessReasonCode.SOURCE_NOT_CONNECTED,),
            input_data_as_of=available_at,
            availability_basis=basis,
            evidence=evidence,
            limitations=("The source is not connected at the cutoff.",),
        )
    if evidence.connected is None and (available_at is None or evidence.watermark_at is None):
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.UNKNOWN,
            reason_codes=(FreshnessReasonCode.SOURCE_METADATA_MISSING,),
            evidence=evidence,
            missing=True,
            limitations=(
                "Operational connection state and source coverage are not established; "
                "event silence is not evidence of disconnection or health.",
            ),
        )
    if available_at is None or evidence.watermark_at is None:
        missing_reason = (
            FreshnessReasonCode.SOURCE_METADATA_MISSING
            if available_at is None
            else FreshnessReasonCode.SOURCE_COVERAGE_MISSING
        )
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.UNKNOWN,
            reason_codes=(missing_reason,),
            input_data_as_of=available_at,
            availability_basis=basis,
            evidence=evidence,
            limitations=(
                "Availability and source coverage cannot establish freshness at the cutoff.",
            ),
        )

    age = as_of - evidence.watermark_at
    max_age = policy.source_max_age.get(source)
    if max_age is None or age > max_age:
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.STALE,
            reason_codes=(FreshnessReasonCode.SOURCE_STALE,),
            input_data_as_of=available_at,
            availability_basis=basis,
            evidence=evidence,
            limitations=("The source watermark is older than its configured limit.",),
        )
    if evidence.complete is False or evidence.complete is None:
        reasons = [FreshnessReasonCode.SOURCE_PARTIALLY_STALE]
        if evidence.complete is False:
            reasons.append(FreshnessReasonCode.SOURCE_COVERAGE_INCOMPLETE)
        return SourceFreshnessAssessment(
            source=source,
            status=FreshnessStatus.PARTIALLY_STALE,
            reason_codes=tuple(reasons),
            input_data_as_of=available_at,
            availability_basis=basis,
            evidence=evidence,
            limitations=("Source freshness is current, but complete coverage is not proven.",),
        )
    return SourceFreshnessAssessment(
        source=source,
        status=FreshnessStatus.FRESH,
        reason_codes=(FreshnessReasonCode.SOURCE_FRESH,),
        input_data_as_of=available_at,
        availability_basis=basis,
        evidence=evidence,
    )


def assess_data_freshness(
    tenant_id: str,
    customer_id: str,
    as_of: datetime,
    evidence: Sequence[SourceFreshnessEvidence],
    *,
    policy: FreshnessPolicy | None = None,
    evaluated_at: datetime | None = None,
) -> DataFreshnessAssessment:
    """Assess only source evidence available by the requested prediction cutoff."""

    if not tenant_id.strip() or not customer_id.strip():
        raise ValueError("tenant_id and customer_id must be non-empty")
    _require_aware(as_of, "as_of")
    evaluated = evaluated_at or datetime.now(timezone.utc)
    _require_aware(evaluated, "evaluated_at")
    selected_policy = policy or FreshnessPolicy()
    by_source: dict[str, SourceFreshnessEvidence] = {}
    for item in evidence:
        if item.source not in by_source:
            by_source[item.source] = item

    source_names = tuple(dict.fromkeys((*selected_policy.source_max_age.keys(), *by_source.keys())))
    assessments = tuple(
        _source_assessment(
            source,
            by_source.get(source),
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=as_of,
            policy=selected_policy,
        )
        for source in source_names
    )
    status_by_source = {item.source: item.status for item in assessments}
    essential_statuses = [
        status_by_source.get(source, FreshnessStatus.UNKNOWN)
        for source in selected_policy.essential_sources
    ]
    optional_statuses = [
        assessment.status
        for assessment in assessments
        if assessment.source not in selected_policy.essential_sources
    ]
    if any(status is FreshnessStatus.STALE for status in essential_statuses):
        status = FreshnessStatus.STALE
    elif any(status is FreshnessStatus.UNKNOWN for status in essential_statuses):
        status = FreshnessStatus.UNKNOWN
    elif any(status in {FreshnessStatus.STALE, FreshnessStatus.PARTIALLY_STALE} for status in optional_statuses):
        status = FreshnessStatus.PARTIALLY_STALE
    elif any(status is FreshnessStatus.PARTIALLY_STALE for status in essential_statuses):
        status = FreshnessStatus.PARTIALLY_STALE
    else:
        status = FreshnessStatus.FRESH

    accepted = [item for item in assessments if item.input_data_as_of is not None]
    source_availability = {
        item.source: item.input_data_as_of
        for item in accepted
        if item.input_data_as_of is not None
    }
    all_refs = [
        ref
        for item in assessments
        if item.evidence is not None
        for ref in item.evidence.source_record_refs
    ]
    reasons = [reason for item in assessments for reason in item.reason_codes]
    missing = [item.source for item in assessments if item.missing]
    limitations = [limitation for item in assessments for limitation in item.limitations]
    return DataFreshnessAssessment(
        tenant_id=tenant_id,
        customer_id=customer_id,
        as_of=as_of,
        status=status,
        input_data_as_of=max(source_availability.values()) if source_availability else None,
        source_assessments=assessments,
        missing_sources=tuple(missing),
        reason_codes=_unique(reasons),
        source_availability_by_source=source_availability,
        source_record_refs=_unique(all_refs),
        policy_version=selected_policy.policy_version,
        evaluated_at=evaluated,
        limitations=_unique(limitations),
    )


__all__ = [
    "DataFreshnessAssessment",
    "FreshnessPolicy",
    "FreshnessReasonCode",
    "FreshnessSource",
    "SourceFreshnessAssessment",
    "SourceFreshnessEvidence",
    "assess_data_freshness",
]
