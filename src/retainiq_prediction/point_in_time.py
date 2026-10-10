"""Point-in-time-safe historical facts and replaceable adapter interface.

This module provides an in-memory implementation for tests. Member 1 can later
implement the same protocol against canonical storage without changing the
eligibility logic.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Iterable, Literal, Protocol, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FactCategory(str, Enum):
    SUBSCRIPTION = "subscription"
    USAGE = "usage"
    BILLING = "billing"


class AvailabilityPolicy(str, Enum):
    """Local adapter policy; precedence remains a Member 1 integration item."""

    SOURCE_THEN_RECEIVED = "source_then_received"
    SOURCE_ONLY = "source_only"
    RECEIVED_ONLY = "received_only"


class PointInTimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HistoricalFact(PointInTimeModel):
    """A source-backed fact with both event and availability provenance."""

    record_id: NonEmptyText
    tenant_id: NonEmptyText
    customer_id: NonEmptyText
    source: NonEmptyText
    category: FactCategory
    occurred_at: AwareDatetime | None = None
    effective_at: AwareDatetime | None = None
    source_available_at: AwareDatetime | None = None
    received_at: AwareDatetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_event_or_effective_time(self) -> Self:
        if self.occurred_at is None and self.effective_at is None:
            raise ValueError("a historical fact requires occurred_at or effective_at")
        return self

    def point_in_time(self) -> datetime:
        """Return the timestamp used to place this fact in historical order."""

        return self.effective_at or self.occurred_at  # type: ignore[return-value]


class SubscriptionFact(HistoricalFact):
    category: Literal[FactCategory.SUBSCRIPTION] = FactCategory.SUBSCRIPTION
    subscription_id: NonEmptyText
    event_type: NonEmptyText = "state_observation"
    status: NonEmptyText
    is_paying: bool | None = None
    cancellation_requested_at: AwareDatetime | None = None
    scheduled_termination_at: AwareDatetime | None = None


class UsageFact(HistoricalFact):
    category: Literal[FactCategory.USAGE] = FactCategory.USAGE
    event_type: NonEmptyText


class BillingFact(HistoricalFact):
    category: Literal[FactCategory.BILLING] = FactCategory.BILLING
    event_type: NonEmptyText
    payment_status: NonEmptyText | None = None


class PointInTimeSnapshot(PointInTimeModel):
    """Facts available for one exact tenant/account/cutoff request."""

    tenant_id: NonEmptyText
    customer_id: NonEmptyText
    as_of: AwareDatetime
    availability_policy: AvailabilityPolicy
    subscriptions: tuple[SubscriptionFact, ...] = ()
    usage_events: tuple[UsageFact, ...] = ()
    billing_events: tuple[BillingFact, ...] = ()
    availability_basis_by_record: dict[str, str] = Field(default_factory=dict)
    excluded_record_counts: dict[str, int] = Field(default_factory=dict)
    limitations: tuple[str, ...] = ()


class PointInTimeDataAdapter(Protocol):
    """Replaceable interface for historical point-in-time reads."""

    def snapshot_for(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> PointInTimeSnapshot:
        """Return only facts knowable for the requested scoped cutoff."""


def _require_scoped_request(tenant_id: str, customer_id: str, as_of: datetime) -> None:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id must be a non-empty string")
    if not isinstance(customer_id, str) or not customer_id.strip():
        raise ValueError("customer_id must be a non-empty string")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")


class InMemoryPointInTimeAdapter:
    """Read-only adapter over explicitly supplied in-memory facts."""

    def __init__(
        self,
        facts: Iterable[HistoricalFact],
        *,
        availability_policy: AvailabilityPolicy = AvailabilityPolicy.SOURCE_THEN_RECEIVED,
    ) -> None:
        self._facts = tuple(facts)
        self.availability_policy = availability_policy

    def _availability_time(self, fact: HistoricalFact) -> tuple[datetime | None, str | None]:
        if self.availability_policy is AvailabilityPolicy.SOURCE_ONLY:
            return fact.source_available_at, "source_available_at" if fact.source_available_at else None
        if self.availability_policy is AvailabilityPolicy.RECEIVED_ONLY:
            return fact.received_at, "received_at" if fact.received_at else None
        if fact.source_available_at is not None:
            return fact.source_available_at, "source_available_at"
        if fact.received_at is not None:
            return fact.received_at, "received_at"
        return None, None

    def snapshot_for(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> PointInTimeSnapshot:
        _require_scoped_request(tenant_id, customer_id, as_of)

        included: list[HistoricalFact] = []
        availability_basis: dict[str, str] = {}
        excluded: dict[str, int] = {}
        limitations: list[str] = []
        seen_source_records: dict[tuple[str, str, str, FactCategory, str], HistoricalFact] = {}

        def exclude(reason: str) -> None:
            excluded[reason] = excluded.get(reason, 0) + 1

        for fact in self._facts:
            if fact.tenant_id != tenant_id or fact.customer_id != customer_id:
                continue

            source_record_key = (
                fact.tenant_id,
                fact.customer_id,
                fact.source,
                fact.category,
                fact.record_id,
            )
            previous = seen_source_records.get(source_record_key)
            if previous is not None:
                if previous != fact:
                    raise ValueError(
                        "conflicting facts share a tenant/customer/source record identity"
                    )
                exclude("duplicate_source_record")
                continue
            seen_source_records[source_record_key] = fact

            event_time = fact.point_in_time()
            if event_time > as_of:
                exclude("future_event_or_effective_time")
                continue

            available_at, basis = self._availability_time(fact)
            if available_at is None:
                exclude("historical_availability_unknown")
                continue
            if available_at > as_of:
                exclude("late_arriving_fact")
                continue

            included.append(fact)
            if basis is not None:
                availability_basis[fact.record_id] = basis

        if excluded.get("historical_availability_unknown"):
            limitations.append(
                "Some matching facts have no usable source availability or received_at timestamp; they were excluded."
            )
        if excluded.get("late_arriving_fact"):
            limitations.append(
                "Some matching facts occurred earlier but were unavailable after the requested cutoff; they were excluded."
            )
        if excluded.get("future_event_or_effective_time"):
            limitations.append(
                "Some matching facts have occurred_at/effective_at after the requested cutoff; they were excluded."
            )

        subscriptions = tuple(
            sorted(
                (fact for fact in included if isinstance(fact, SubscriptionFact)),
                key=lambda fact: (fact.point_in_time(), fact.record_id),
            )
        )
        usage_events = tuple(
            sorted(
                (fact for fact in included if isinstance(fact, UsageFact)),
                key=lambda fact: (fact.point_in_time(), fact.record_id),
            )
        )
        billing_events = tuple(
            sorted(
                (fact for fact in included if isinstance(fact, BillingFact)),
                key=lambda fact: (fact.point_in_time(), fact.record_id),
            )
        )
        return PointInTimeSnapshot(
            tenant_id=tenant_id,
            customer_id=customer_id,
            as_of=as_of,
            availability_policy=self.availability_policy,
            subscriptions=subscriptions,
            usage_events=usage_events,
            billing_events=billing_events,
            availability_basis_by_record=availability_basis,
            excluded_record_counts=excluded,
            limitations=tuple(dict.fromkeys(limitations)),
        )


__all__ = [
    "AvailabilityPolicy",
    "BillingFact",
    "FactCategory",
    "HistoricalFact",
    "InMemoryPointInTimeAdapter",
    "PointInTimeDataAdapter",
    "PointInTimeSnapshot",
    "SubscriptionFact",
    "UsageFact",
]
