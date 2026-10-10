import unittest
from datetime import date, datetime, time, timedelta, timezone

from examples.member2_synthetic_smoke import _usage_features


def _stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class SyntheticSmokeTests(unittest.TestCase):
    def test_usage_windows_count_daily_aggregate_once_and_keep_nonoverlapping_baseline(self):
        cutoff_date = date(2026, 4, 6)
        cutoff = datetime.combine(cutoff_date, time(12), tzinfo=timezone.utc)
        aggregate_end = datetime.combine(cutoff_date - timedelta(days=2), time.min, tzinfo=timezone.utc)
        raw_end = datetime.combine(cutoff_date - timedelta(days=2), time(hour=9), tzinfo=timezone.utc)
        left = datetime.combine(cutoff_date - timedelta(days=58), time.min, tzinfo=timezone.utc)
        right = datetime.combine(cutoff_date, time.min, tzinfo=timezone.utc)
        coverage = [{
            "source_category": "usage", "covered_from": _stamp(left), "covered_through": _stamp(right),
            "coverage_status": "complete", "coverage_completeness": 1.0,
        }]
        events = [
            {"event_type": "usage_aggregate_updated", "occurred_at": _stamp(aggregate_end),
             "attributes": {"quantity": 4, "unit": "sessions"}},
            {"event_type": "session_started", "occurred_at": _stamp(raw_end),
             "attributes": {"quantity": 100, "unit": "sessions"}},
        ]

        features = _usage_features(events, coverage, cutoff_date, cutoff)

        self.assertEqual(features["7d"]["sessions"], 4)
        self.assertEqual(features["7d"]["active_days"], 1)
        self.assertEqual(features["raw_usage_event_rows"], 1)
        self.assertTrue(features["baseline_non_overlaps_30d"])
        self.assertTrue(features["baseline_28d"]["coverage_complete"])
        self.assertEqual(features["baseline_28d"]["sessions"], 0)


if __name__ == "__main__":
    unittest.main()
