"""Point-in-time-safe personalized usage features.

This module computes only source-backed behavioral features.  It does not build
churn labels, fit a model, or produce a prediction.  Usage event semantics and
coverage evidence are explicit inputs so an empty event collection is never
silently interpreted as zero customer activity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math
from typing import Iterable, Mapping, Protocol, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from .point_in_time import PointInTimeDataAdapter, PointInTimeSnapshot, UsageFact


NonEmptyText = StringConstraints(strip_whitespace=True, min_length=1)


class UsageCoverageStatus(str, Enum):
    """Evidence status for the usage periods used by the feature builder."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class PersonalBaselineStatus(str, Enum):
    """Whether a customer-relative baseline is safe to expose."""

    AVAILABLE = "available"
    ZERO_BASELINE = "zero_baseline"
    INSUFFICIENT_HISTORY = "insufficient_history"
    UNAVAILABLE = "unavailable"


class _FeatureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UsageCoverage(_FeatureModel):
    """Explicit evidence that a usage period was observable.

    Coverage boundaries are inclusive for the purpose of proving that a
    feature window was observed.  ``available_at`` is required because
    coverage metadata is itself historical evidence and must be knowable by
    the prediction cutoff.
    """

    coverage_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    observed_from: AwareDatetime
    observed_to: AwareDatetime
    available_at: AwareDatetime
    complete: bool = True


class FeatureValues(_FeatureModel):
    """Versioned behavioral feature values, with null for unavailable facts."""

    sessions_prev_7d: int | None = Field(default=None, ge=0)
    sessions_prev_30d: int | None = Field(default=None, ge=0)
    days_since_last_observed_session: int | None = Field(default=None, ge=0)
    recent_usage_trend: float | None = None
    observed_weeks: int = Field(default=0, ge=0)
    valid_usage_history: bool = False
    historical_avg_sessions_per_week: float | None = Field(default=None, ge=0)
    recent_avg_sessions_per_week: float | None = Field(default=None, ge=0)
    absolute_usage_deviation: float | None = None
    percentage_usage_deviation: float | None = None
    recent_to_baseline_usage_ratio: float | None = Field(default=None, ge=0)
    historical_weekly_usage_variability: float | None = Field(default=None, ge=0)
    personal_baseline_availability_status: PersonalBaselineStatus = (
        PersonalBaselineStatus.UNAVAILABLE
    )


class FeatureQuality(_FeatureModel):
    """Coverage and missingness metadata accompanying the feature values."""

    usage_coverage_status: UsageCoverageStatus
    personal_baseline_status: PersonalBaselineStatus
    observed_history_days: int = Field(default=0, ge=0)
    observed_weeks: int = Field(default=0, ge=0)
    baseline_weeks_requested: int = Field(ge=1, le=8)
    baseline_weeks_available: int = Field(default=0, ge=0, le=8)
    recent_window_covered: bool = False
    baseline_window_covered: bool = False
    missingness: dict[str, bool] = Field(default_factory=dict)
    limitations: tuple[str, ...] = ()


class FeatureSnapshot(_FeatureModel):
    """Immutable-in-memory model input for one account and cutoff."""

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    as_of: AwareDatetime
    feature_version: str = Field(min_length=1)
    data_cutoff_at: AwareDatetime
    feature_values: FeatureValues
    data_quality: FeatureQuality
    source_evidence_refs: tuple[str, ...] = ()

    @property
    def features(self) -> FeatureValues:
        """Convenient alias for callers that refer to the values as features."""

        return self.feature_values

    @property
    def quality(self) -> FeatureQuality:
        """Convenient alias for callers that refer to data quality as quality."""

        return self.data_quality


@dataclass(frozen=True)
class FeatureBuilderConfig:
    """Explicit, replaceable feature and event-semantics configuration."""

    feature_version: str = "features_personalized_baseline_v1"
    baseline_weeks: int = 4
    recent_window_days: int = 7
    session_event_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"session_started"})
    )

    def __post_init__(self) -> None:
        if not self.feature_version.strip():
            raise ValueError("feature_version must be non-empty")
        if not 4 <= self.baseline_weeks <= 8:
            raise ValueError("baseline_weeks must be between 4 and 8")
        if self.recent_window_days != 7:
            raise ValueError("recent_window_days must remain 7 for this feature version")
        if not self.session_event_types:
            raise ValueError("session_event_types must define at least one event type")


class UsageCoverageProvider(Protocol):
    """Optional Member 1 boundary for source completeness evidence."""

    def coverage_for(
        self, tenant_id: str, customer_id: str, as_of: datetime
    ) -> Sequence[UsageCoverage]:
        """Return coverage evidence that was knowable by ``as_of``."""


def _event_time(fact: UsageFact) -> datetime:
    return fact.point_in_time()


def _in_closed_window(event_time: datetime, start: datetime, end: datetime) -> bool:
    return start <= event_time <= end


def _in_half_open_window(event_time: datetime, start: datetime, end: datetime) -> bool:
    return start <= event_time < end


def _interval_covered(
    coverages: Sequence[UsageCoverage], start: datetime, end: datetime
) -> bool:
    """Return whether complete coverage spans the full inclusive interval."""

    usable = sorted(
        (
            coverage
            for coverage in coverages
            if coverage.complete
            and coverage.observed_from <= end
            and coverage.observed_to >= start
        ),
        key=lambda coverage: coverage.observed_from,
    )
    cursor = start
    for coverage in usable:
        if coverage.observed_from > cursor:
            continue
        if coverage.observed_to >= cursor:
            cursor = max(cursor, coverage.observed_to)
        if cursor >= end:
            return True
    return False


class FeatureBuilder:
    """Build personalized usage features from a point-in-time adapter."""

    def __init__(
        self,
        adapter: PointInTimeDataAdapter,
        *,
        config: FeatureBuilderConfig | None = None,
        coverage_provider: UsageCoverageProvider | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or FeatureBuilderConfig()
        self.coverage_provider = coverage_provider

    def build(
        self,
        tenant_id: str,
        customer_id: str,
        as_of: datetime,
        *,
        usage_coverage: Sequence[UsageCoverage] | None = None,
    ) -> FeatureSnapshot:
        """Build one feature snapshot using only adapter-returned facts.

        ``usage_coverage`` is an optional explicit override for tests or a
        caller that already has a canonical coverage view.  When omitted, the
        configured provider is used.  The provider is not a database and is a
        replaceable integration seam for Member 1.
        """

        snapshot = self.adapter.snapshot_for(tenant_id, customer_id, as_of)
        coverage = tuple(
            usage_coverage
            if usage_coverage is not None
            else (
                self.coverage_provider.coverage_for(tenant_id, customer_id, as_of)
                if self.coverage_provider is not None
                else ()
            )
        )
        return self._build_from_snapshot(snapshot, coverage)

    def build_snapshot(
        self,
        tenant_id: str,
        customer_id: str,
        as_of: datetime,
        *,
        usage_coverage: Sequence[UsageCoverage] | None = None,
    ) -> FeatureSnapshot:
        """Named alias for callers that prefer the snapshot terminology."""

        return self.build(
            tenant_id,
            customer_id,
            as_of,
            usage_coverage=usage_coverage,
        )

    def _build_from_snapshot(
        self, snapshot: PointInTimeSnapshot, coverage: Sequence[UsageCoverage]
    ) -> FeatureSnapshot:
        as_of = snapshot.as_of
        recent_start = as_of - timedelta(days=self.config.recent_window_days)
        baseline_start = recent_start - timedelta(days=7 * self.config.baseline_weeks)
        baseline_end = recent_start
        thirty_day_start = as_of - timedelta(days=30)

        limitations = list(snapshot.limitations)
        usable_coverage: list[UsageCoverage] = []
        for item in coverage:
            if item.available_at > as_of:
                limitations.append(f"Coverage {item.coverage_id} became available after as_of.")
                continue
            usable_coverage.append(item)

        if coverage and len(usable_coverage) != len(coverage):
            coverage_status = UsageCoverageStatus.PARTIAL
        elif coverage:
            coverage_status = UsageCoverageStatus.PARTIAL
        else:
            coverage_status = (
                UsageCoverageStatus.PARTIAL
                if snapshot.usage_events
                else UsageCoverageStatus.UNKNOWN
            )

        baseline_week_counts: list[int] = []
        baseline_week_covered: list[bool] = []
        for week_index in range(self.config.baseline_weeks):
            week_start = baseline_start + timedelta(days=7 * week_index)
            week_end = week_start + timedelta(days=7)
            baseline_week_covered.append(
                _interval_covered(usable_coverage, week_start, week_end)
            )
            baseline_week_counts.append(
                self._count_sessions(
                    snapshot.usage_events,
                    week_start,
                    week_end,
                    upper_inclusive=False,
                )
            )

        recent_covered = _interval_covered(usable_coverage, recent_start, as_of)
        baseline_covered = all(baseline_week_covered)
        if coverage and recent_covered and baseline_covered and not snapshot.limitations:
            coverage_status = UsageCoverageStatus.COMPLETE
        elif coverage_status is UsageCoverageStatus.UNKNOWN and snapshot.limitations:
            coverage_status = UsageCoverageStatus.UNKNOWN
        elif coverage_status is UsageCoverageStatus.COMPLETE:
            coverage_status = UsageCoverageStatus.PARTIAL

        recent_sessions_observed = self._count_sessions(
            snapshot.usage_events, recent_start, as_of, upper_inclusive=True
        )
        sessions_30d = self._count_sessions(
            snapshot.usage_events, thirty_day_start, as_of, upper_inclusive=True
        )
        session_times = sorted(
            _event_time(fact)
            for fact in snapshot.usage_events
            if self._is_session(fact) and _event_time(fact) <= as_of
        )

        sessions_prev_7d = self._observed_count(
            recent_sessions_observed, recent_covered, snapshot.usage_events, recent_start, as_of
        )
        sessions_prev_30d_value = self._observed_count(
            sessions_30d, _interval_covered(usable_coverage, thirty_day_start, as_of),
            snapshot.usage_events, thirty_day_start, as_of,
        )
        baseline_weeks_available = sum(baseline_week_covered)
        baseline_ready = baseline_covered and baseline_weeks_available == self.config.baseline_weeks

        historical_avg: float | None = None
        recent_avg: float | None = None
        absolute_deviation: float | None = None
        percentage_deviation: float | None = None
        ratio: float | None = None
        variability: float | None = None
        trend: float | None = None
        if baseline_ready:
            historical_avg = sum(baseline_week_counts) / self.config.baseline_weeks
            recent_avg = recent_sessions_observed / (self.config.recent_window_days / 7)
            absolute_deviation = recent_avg - historical_avg
            variability = self._population_stddev(baseline_week_counts)
            prior_week = baseline_week_counts[-1]
            trend = recent_avg - float(prior_week)
            if historical_avg > 0:
                percentage_deviation = absolute_deviation / historical_avg
                ratio = recent_avg / historical_avg

        if baseline_ready and historical_avg == 0:
            baseline_status = PersonalBaselineStatus.ZERO_BASELINE
        elif baseline_ready:
            baseline_status = PersonalBaselineStatus.AVAILABLE
        elif baseline_weeks_available:
            baseline_status = PersonalBaselineStatus.INSUFFICIENT_HISTORY
        else:
            baseline_status = PersonalBaselineStatus.UNAVAILABLE

        if recent_covered and baseline_covered and not snapshot.limitations:
            coverage_status = UsageCoverageStatus.COMPLETE
        elif coverage_status is not UsageCoverageStatus.UNKNOWN:
            coverage_status = UsageCoverageStatus.PARTIAL

        observed_history_days = max(
            0,
            (as_of - min((
                _event_time(fact) for fact in snapshot.usage_events
                if _event_time(fact) <= as_of
            ), default=as_of)).days,
        )
        missingness = {
            "sessions_prev_7d": sessions_prev_7d is None,
            "sessions_prev_30d": sessions_prev_30d_value is None,
            "days_since_last_observed_session": not bool(session_times),
            "personal_baseline": baseline_status
            in {
                PersonalBaselineStatus.INSUFFICIENT_HISTORY,
                PersonalBaselineStatus.UNAVAILABLE,
            },
            "usage_coverage": coverage_status is not UsageCoverageStatus.COMPLETE,
        }
        features = FeatureValues(
            sessions_prev_7d=sessions_prev_7d,
            sessions_prev_30d=sessions_prev_30d_value,
            days_since_last_observed_session=(
                (as_of - session_times[-1]).days if session_times else None
            ),
            recent_usage_trend=trend,
            observed_weeks=baseline_weeks_available,
            valid_usage_history=(
                coverage_status is UsageCoverageStatus.COMPLETE and baseline_ready
            ),
            historical_avg_sessions_per_week=historical_avg,
            recent_avg_sessions_per_week=recent_avg,
            absolute_usage_deviation=absolute_deviation,
            percentage_usage_deviation=percentage_deviation,
            recent_to_baseline_usage_ratio=ratio,
            historical_weekly_usage_variability=variability,
            personal_baseline_availability_status=baseline_status,
        )
        quality = FeatureQuality(
            usage_coverage_status=coverage_status,
            personal_baseline_status=baseline_status,
            observed_history_days=observed_history_days,
            observed_weeks=baseline_weeks_available,
            baseline_weeks_requested=self.config.baseline_weeks,
            baseline_weeks_available=baseline_weeks_available,
            recent_window_covered=recent_covered,
            baseline_window_covered=baseline_covered,
            missingness=missingness,
            limitations=tuple(dict.fromkeys(limitations)),
        )
        evidence_refs = tuple(
            dict.fromkeys(
                [fact.record_id for fact in snapshot.usage_events]
                + [item.coverage_id for item in usable_coverage]
            )
        )
        return FeatureSnapshot(
            tenant_id=snapshot.tenant_id,
            customer_id=snapshot.customer_id,
            as_of=as_of,
            feature_version=self.config.feature_version,
            data_cutoff_at=as_of,
            feature_values=features,
            data_quality=quality,
            source_evidence_refs=evidence_refs,
        )

    def _is_session(self, fact: UsageFact) -> bool:
        return fact.event_type.strip().lower() in {
            event_type.strip().lower() for event_type in self.config.session_event_types
        }

    def _count_sessions(
        self,
        facts: Sequence[UsageFact],
        start: datetime,
        end: datetime,
        *,
        upper_inclusive: bool,
    ) -> int:
        return sum(
            1
            for fact in facts
            if self._is_session(fact)
            and (
                _in_closed_window(_event_time(fact), start, end)
                if upper_inclusive
                else _in_half_open_window(_event_time(fact), start, end)
            )
        )

    @staticmethod
    def _observed_count(
        count: int,
        covered: bool,
        facts: Sequence[UsageFact],
        start: datetime,
        end: datetime,
    ) -> int | None:
        if covered or count > 0:
            return count
        # No event and no explicit coverage is unknown, not confirmed zero.
        if any(start <= _event_time(fact) <= end for fact in facts):
            return count
        return None

    @staticmethod
    def _population_stddev(values: Sequence[int]) -> float:
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


__all__ = [
    "FeatureBuilder",
    "FeatureBuilderConfig",
    "FeatureQuality",
    "FeatureSnapshot",
    "FeatureValues",
    "PersonalBaselineStatus",
    "UsageCoverage",
    "UsageCoverageProvider",
    "UsageCoverageStatus",
]
