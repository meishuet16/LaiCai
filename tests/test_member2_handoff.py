import unittest

from examples.member2_as_of_history import load_example_history


class Member2HandoffExampleTests(unittest.TestCase):
    def test_as_of_history_contains_eligible_account_without_future_events(self):
        result = load_example_history("2026-10-10T00:00:00Z")

        self.assertEqual(result["dataset_kind"], "synthetic demonstration only")
        self.assertEqual(result["account"]["status"], "eligible")
        self.assertEqual(result["account"]["customer_id"], "customer-demo")
        self.assertEqual(
            [event["event_type"] for event in result["account"]["usage_events"]],
            ["session_started"],
        )
        self.assertTrue(
            all(event["occurred_at"] <= result["account"]["as_of"]
                and event["available_at"] <= result["account"]["as_of"]
                for event in result["account"]["usage_events"])
        )
        self.assertNotIn("labels", result["account"])
        self.assertNotIn("predictions", result["account"])


if __name__ == "__main__":
    unittest.main()
