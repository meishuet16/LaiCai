from datetime import datetime, timedelta, timezone

import pytest

from retainiq_prediction import (
    FeatureBuilder,
    FeatureBuilderConfig,
    InMemoryPointInTimeAdapter,
    PersonalBaselineStatus,
    UsageCoverage,
    UsageCoverageStatus,
    UsageFact,
)


UTC = timezone.utc
BASE = datetime(2026, 10, 1, tzinfo=UTC)
CUTOFF = BASE + timedelta(days=70)
RECENT_START = CUTOFF - timedelta(days=7)
BASELINE_START = CUTOFF - timedelta(days=35)


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


def usage(
    record_id: str,
    day: int,
    *,
    event_type: str = "session_started",
    tenant_id: str = "tenant-a",
    customer_id: str = "customer-a",
    available_day: int = 70,
) -> UsageFact:
    return UsageFact(
        record_id=record_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
        source="synthetic_usage",
        event_type=event_type,
        occurred_at=at(day),
        source_available_at=at(available_day),
        received_at=at(available_day),
    )


def coverage(
    coverage_id: str = "usage-window",
    *,
    start: datetime = BASELINE_START,
    end: datetime = CUTOFF,
    available_at: datetime = CUTOFF,
    complete: bool = True,
) -> UsageCoverage:
    return UsageCoverage(
        coverage_id=coverage_id,
        source="synthetic_usage",
        observed_from=start,
        observed_to=end,
        available_at=available_at,
        complete=complete,
    )


def builder(facts, *, config=None) -> FeatureBuilder:
    return FeatureBuilder(
        InMemoryPointInTimeAdapter(facts),
        config=config,
    )


def test_normal_7_day_and_30_day_session_calculations():
    facts = [
        usage("recent-1", 64),
        usage("recent-2", 68),
        usage("older-1", 45),
        usage("older-2", 50),
        usage("older-3", 55),
        usage("not-session", 68, event_type="login"),
    ]

    snapshot = builder(facts).build("tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()])

    assert snapshot.features.sessions_prev_7d == 2
    assert snapshot.features.sessions_prev_30d == 5
    assert snapshot.features.days_since_last_observed_session == 2


def test_personal_baseline_and_usage_deviations_are_calculated_from_earlier_weeks():
    facts = []
    for week, count in enumerate((2, 4, 6, 8)):
        facts.extend(
            usage(
                f"baseline-{week}-{index}",
                35 + week * 7 + (index % 7),
            )
            for index in range(count)
        )
    facts.append(usage("recent", 66))

    snapshot = builder(facts).build("tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()])
    features = snapshot.features

    assert features.historical_avg_sessions_per_week == 5
    assert features.recent_avg_sessions_per_week == 1
    assert features.absolute_usage_deviation == -4
    assert features.percentage_usage_deviation == pytest.approx(-0.8)
    assert features.recent_to_baseline_usage_ratio == pytest.approx(0.2)
    assert features.recent_usage_trend == -7
    assert features.observed_weeks == 4
    assert features.personal_baseline_availability_status is PersonalBaselineStatus.AVAILABLE
    assert features.valid_usage_history is True


def test_boundary_event_belongs_to_recent_window_not_baseline():
    facts = [usage("boundary", 63)]
    snapshot = builder(facts).build("tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()])

    assert snapshot.features.sessions_prev_7d == 1
    assert snapshot.features.historical_avg_sessions_per_week == 0
    assert snapshot.features.personal_baseline_availability_status is PersonalBaselineStatus.ZERO_BASELINE


def test_zero_baseline_never_divides_by_zero():
    snapshot = builder([usage("recent", 65)]).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )

    assert snapshot.features.historical_avg_sessions_per_week == 0
    assert snapshot.features.absolute_usage_deviation == 1
    assert snapshot.features.percentage_usage_deviation is None
    assert snapshot.features.recent_to_baseline_usage_ratio is None
    assert snapshot.features.personal_baseline_availability_status is PersonalBaselineStatus.ZERO_BASELINE


def test_cold_start_account_marks_personal_history_unavailable():
    snapshot = builder([usage("recent", 66)]).build("tenant-a", "customer-a", CUTOFF)

    assert snapshot.features.sessions_prev_7d == 1
    assert snapshot.features.historical_avg_sessions_per_week is None
    assert snapshot.features.valid_usage_history is False
    assert snapshot.quality.personal_baseline_status is PersonalBaselineStatus.UNAVAILABLE


def test_missing_usage_coverage_is_not_treated_as_zero_activity():
    snapshot = builder([]).build("tenant-a", "customer-a", CUTOFF)

    assert snapshot.features.sessions_prev_7d is None
    assert snapshot.features.sessions_prev_30d is None
    assert snapshot.quality.usage_coverage_status is UsageCoverageStatus.UNKNOWN
    assert snapshot.quality.missingness["sessions_prev_7d"] is True


def test_confirmed_zero_usage_is_distinct_from_unknown_usage():
    confirmed_zero = builder([]).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )
    unknown = builder([]).build("tenant-a", "customer-a", CUTOFF)

    assert confirmed_zero.features.sessions_prev_7d == 0
    assert confirmed_zero.features.sessions_prev_30d == 0
    assert confirmed_zero.quality.usage_coverage_status is UsageCoverageStatus.COMPLETE
    assert unknown.features.sessions_prev_7d is None
    assert unknown.quality.usage_coverage_status is UsageCoverageStatus.UNKNOWN


def test_late_arriving_and_future_events_are_excluded_by_adapter():
    facts = [
        usage("late", 65, available_day=71),
        usage("future", 71, available_day=71),
        usage("known", 66),
    ]
    snapshot = builder(facts).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )

    assert snapshot.features.sessions_prev_7d == 1
    assert "late" not in snapshot.source_evidence_refs
    assert "future" not in snapshot.source_evidence_refs
    assert snapshot.quality.limitations


def test_cutoff_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        builder([]).build("tenant-a", "customer-a", datetime(2026, 12, 10))


def test_cross_tenant_and_customer_records_cannot_leak():
    facts = [
        usage("correct", 66),
        usage("other-tenant", 66, tenant_id="tenant-b"),
        usage("other-customer", 66, customer_id="customer-b"),
    ]
    snapshot = builder(facts).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )

    assert snapshot.features.sessions_prev_7d == 1
    assert snapshot.source_evidence_refs == ("correct", "usage-window")


def test_feature_version_is_consistent_and_mapping_is_configurable():
    config = FeatureBuilderConfig(
        feature_version="features_test_v2",
        session_event_types=frozenset({"completed_session"}),
    )
    facts = [usage("login", 66, event_type="login"), usage("session", 67, event_type="completed_session")]

    first = builder(facts, config=config).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )
    second = builder(facts, config=config).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )

    assert first.feature_version == "features_test_v2"
    assert first.features.sessions_prev_7d == 1
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_features_do_not_include_cancellation_or_churn_labels():
    snapshot = builder([usage("recent", 66)]).build(
        "tenant-a", "customer-a", CUTOFF, usage_coverage=[coverage()]
    )

    feature_names = set(snapshot.features.__class__.model_fields)
    assert not any("cancellation" in name or "churn" in name or "label" in name for name in feature_names)


def test_incomplete_coverage_keeps_observed_events_but_disables_valid_history():
    snapshot = builder([usage("recent", 66)]).build(
        "tenant-a",
        "customer-a",
        CUTOFF,
        usage_coverage=[coverage(complete=False)],
    )

    assert snapshot.features.sessions_prev_7d == 1
    assert snapshot.features.valid_usage_history is False
    assert snapshot.quality.usage_coverage_status is UsageCoverageStatus.PARTIAL
