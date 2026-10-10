from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from retaniq.api import create_app
from retaniq.data_foundation import (
    DataFoundationError,
    authenticate_service_principal,
    create_customer,
    create_integration,
    create_service_principal,
    create_tenant,
    get_prediction_by_id,
    get_prediction_history,
    initialize_database,
    map_customer_identity,
    store_prediction,
)


AS_OF = "2026-10-10T00:00:00Z"


def request(app, path, token=None, query=""):
    environ = {
        "REQUEST_METHOD": "GET", "PATH_INFO": path, "QUERY_STRING": query,
        "CONTENT_LENGTH": "0", "wsgi.input": io.BytesIO(b""),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    response = {}

    def start_response(status, headers):
        response["status"] = status
        response["headers"] = dict(headers)

    response["body"] = json.loads(b"".join(app(environ, start_response)))
    return response


class Member1APIHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.db = Path(self.temporary.name) / "handoff.sqlite3"
        initialize_database(self.db)
        for tenant, customer in (("tenant-a", "customer-a"), ("tenant-b", "customer-b")):
            create_tenant(self.db, tenant)
            create_customer(self.db, tenant, customer)
            create_integration(
                self.db, tenant, "product_app", authorized_categories=("usage",),
            )
            map_customer_identity(self.db, tenant, "product_app", f"external-{customer}", customer)
        self.read_token = create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("product_app",),
            authorized_purposes=("retention_inference",),
        )
        self.read_principal = authenticate_service_principal(self.db, self.read_token)
        self.write_token = create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("product_app",),
            authorized_purposes=("retention_inference", "model_artifact_write", "billing_valuation"),
        )
        self.writer = authenticate_service_principal(self.db, self.write_token)
        self.app = create_app(self.db)
        self._prediction("pred-a1", AS_OF, status="scored")
        self._prediction("pred-a2", "2026-10-09T00:00:00Z", status="abstained")
        self._prediction("pred-b1", AS_OF, customer_id="customer-b", status="scored")

    def tearDown(self):
        self.temporary.cleanup()

    def _prediction(self, prediction_id, as_of, *, customer_id="customer-a", status):
        probabilities = (0.1, 0.2, 0.3) if status == "scored" else (None, None, None)
        principal = self.writer
        if customer_id == "customer-b":
            # The tenant-B writer is set up only for this synthetic isolation fixture.
            if not hasattr(self, "tenant_b_writer"):
                token = create_service_principal(
                    self.db, "tenant-b", role="analyst", authorized_sources=("product_app",),
                    authorized_purposes=("retention_inference", "model_artifact_write"),
                )
                self.tenant_b_writer = authenticate_service_principal(self.db, token)
            principal = self.tenant_b_writer
        store_prediction(self.db, principal, {
            "prediction_id": prediction_id, "prediction_run_id": f"run-{prediction_id}",
            "customer_id": customer_id, "as_of": as_of, "generated_at": as_of,
            "status": status, "p_churn_7d": probabilities[0], "p_churn_14d": probabilities[1],
            "p_churn_30d": probabilities[2], "feature_version": "features-v1",
            "model_version": "demo-model-v1", "calibration_version": "cal-v1",
            "reliability_status": "limited_evidence" if status == "scored" else "insufficient_evidence",
            "data_freshness_status": "unknown", "reliability_reasons": [],
            "explanations_by_horizon": (
                {"7d": {"mrr_minor": 1500}} if customer_id == "customer-a"
                else {"7d": {"sessions_7d": 5}}
            ),
        })

    def test_prediction_history_is_authenticated_bounded_and_redacted(self):
        history = get_prediction_history(self.db, self.read_principal, "customer-a", limit=1)
        self.assertEqual(history["status"], "available")
        self.assertEqual(history["predictions"][0]["prediction_id"], "pred-a1")
        self.assertTrue(history["has_more"])
        self.assertEqual(history["next_offset"], 1)
        self.assertEqual(history["predictions"][0]["explanations_by_horizon"], {})
        serialized = json.dumps(history)
        for forbidden in ("churn_labels", "label_policy_version", "mrr_minor", "tenant-b"):
            self.assertNotIn(forbidden, serialized)
        second_page = get_prediction_history(
            self.db, self.read_principal, "customer-a", limit=1, offset=1,
        )
        self.assertEqual(second_page["predictions"][0]["prediction_id"], "pred-a2")
        self.assertEqual(second_page["predictions"][0]["status"], "abstained")
        self.assertIsNone(second_page["predictions"][0]["p_churn_30d"])

    def test_prediction_id_and_customer_lookups_do_not_cross_tenant(self):
        self.assertEqual(get_prediction_by_id(self.db, self.read_principal, "pred-a1")["prediction_id"], "pred-a1")
        for operation in (
            lambda: get_prediction_by_id(self.db, self.read_principal, "pred-b1"),
            lambda: get_prediction_history(self.db, self.read_principal, "customer-b"),
        ):
            with self.assertRaises(DataFoundationError) as denied:
                operation()
            self.assertEqual(denied.exception.code, "not_found")

    def test_authenticated_wsgi_routes_and_query_rejections(self):
        unauthenticated = request(self.app, "/v1/predictions", query="customer_id=customer-a")
        self.assertTrue(unauthenticated["status"].startswith("401"))
        history = request(
            self.app, "/v1/predictions", self.read_token,
            "customer_id=customer-a&limit=1&offset=0",
        )
        self.assertTrue(history["status"].startswith("200"))
        self.assertEqual(history["body"]["predictions"][0]["prediction_id"], "pred-a1")
        prediction = request(self.app, "/v1/predictions/pred-a1", self.read_token)
        self.assertTrue(prediction["status"].startswith("200"))
        self.assertNotIn("label", json.dumps(prediction["body"]))
        invalid = request(
            self.app, "/v1/predictions", self.read_token,
            "customer_id=customer-a&tenant_id=tenant-b",
        )
        self.assertTrue(invalid["status"].startswith("400"))
        cross_tenant = request(self.app, "/v1/predictions/pred-b1", self.read_token)
        self.assertTrue(cross_tenant["status"].startswith("404"))

    def test_member2_history_route_uses_verified_tenant_and_point_in_time_cutoff(self):
        response = request(
            self.app, "/v1/data/accounts/customer-a/history", self.read_token,
            "as_of=2026-10-10T00%3A00%3A00Z",
        )
        self.assertTrue(response["status"].startswith("200"))
        self.assertEqual(response["body"]["account"]["tenant_id"], "tenant-a")
        self.assertEqual(response["body"]["account"]["customer_id"], "customer-a")
        self.assertEqual(response["body"]["cutoff"]["as_of"], "2026-10-10T00:00:00.000000Z")
        serialized = json.dumps(response["body"])
        self.assertNotIn("external-customer-a", serialized)
        self.assertNotIn("tenant-b", serialized)
        self.assertEqual(response["body"]["source_freshness_status"], "unknown")
        future = request(
            self.app, "/v1/data/accounts/customer-a/history", self.read_token,
            "as_of=2027-01-01T00%3A00%3A00Z",
        )
        self.assertTrue(future["status"].startswith("400"))

    def test_history_limits_and_reader_purpose_are_enforced(self):
        with self.assertRaises(DataFoundationError):
            get_prediction_history(self.db, self.read_principal, "customer-a", limit=101)
        valuation_token = create_service_principal(
            self.db, "tenant-a", role="analyst", authorized_sources=("product_app",),
            authorized_purposes=("retention_inference", "billing_valuation"),
        )
        valuation_reader = authenticate_service_principal(self.db, valuation_token)
        response = request(
            self.app, "/v1/data/accounts/customer-a/history", valuation_token,
            "as_of=2026-10-10T00%3A00%3A00Z",
        )
        self.assertTrue(response["status"].startswith("403"))


if __name__ == "__main__":
    unittest.main()
