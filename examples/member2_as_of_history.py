"""Synthetic, local-only demonstration of Member 2's point-in-time read path.

This fixture is not a RetainIQ training dataset and contains no labels or scores.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from retaniq.data_foundation import (
    authenticate_integration,
    create_customer,
    create_integration,
    create_tenant,
    get_account_snapshot_as_of,
    initialize_database,
    ingest_event,
    list_eligible_accounts_as_of,
    map_customer_identity,
)


SYNTHETIC_TENANT_ID = "tenant-demo"
SYNTHETIC_SOURCE = "product-demo"
SYNTHETIC_EXTERNAL_ACCOUNT_ID = "external-demo-account"
SYNTHETIC_CUSTOMER_ID = "customer-demo"
SYNTHETIC_CUTOFF = "2026-10-10T00:00:00Z"


def load_example_history(as_of: str = SYNTHETIC_CUTOFF) -> dict[str, Any]:
    """Build a temporary synthetic account and read its eligible history at ``as_of``."""
    with tempfile.TemporaryDirectory(prefix="retaniq-member2-example-") as directory:
        database_path = Path(directory) / "retaniq.sqlite3"
        initialize_database(database_path)
        create_tenant(database_path, SYNTHETIC_TENANT_ID)
        token = create_integration(
            database_path,
            SYNTHETIC_TENANT_ID,
            SYNTHETIC_SOURCE,
            authorized_purposes=("retention_inference",),
        )
        create_customer(database_path, SYNTHETIC_TENANT_ID, SYNTHETIC_CUSTOMER_ID)
        map_customer_identity(
            database_path,
            SYNTHETIC_TENANT_ID,
            SYNTHETIC_SOURCE,
            SYNTHETIC_EXTERNAL_ACCOUNT_ID,
            SYNTHETIC_CUSTOMER_ID,
        )
        principal = authenticate_integration(database_path, token)

        subscription_start = "2026-10-01T00:00:00Z"
        events = (
            {
                "source_event_id": "synthetic-subscription-created",
                "event_type": "subscription_created",
                "occurred_at": subscription_start,
                "attributes": {
                    "subscription_id": "synthetic-subscription",
                    "status": "active",
                    "started_at": subscription_start,
                },
            },
            {
                "source_event_id": "synthetic-session-before-cutoff",
                "event_type": "session_started",
                "occurred_at": "2026-10-03T00:00:00Z",
                "attributes": {"feature": "reports"},
            },
            {
                "source_event_id": "synthetic-session-after-cutoff",
                "event_type": "session_started",
                "occurred_at": "2026-10-12T00:00:00Z",
                "attributes": {"feature": "exports"},
            },
        )
        for event in events:
            ingest_event(
                database_path,
                principal,
                {
                    **event,
                    "source": SYNTHETIC_SOURCE,
                    "external_customer_id": SYNTHETIC_EXTERNAL_ACCOUNT_ID,
                    "schema_version": "1.0",
                },
                # Synthetic fixture timestamps keep the example deterministic. Production
                # imports must use verified source availability or actual ingestion time.
                received_at=event["occurred_at"],
            )

        eligible = list_eligible_accounts_as_of(database_path, principal, as_of)
        account = next(
            (row for row in eligible if row["customer_id"] == SYNTHETIC_CUSTOMER_ID),
            None,
        )
        if account is None:
            raise RuntimeError("synthetic example account is not eligible at the requested cutoff")
        account = get_account_snapshot_as_of(
            database_path, principal, account["customer_id"], as_of,
        )
        return {"dataset_kind": "synthetic demonstration only", "account": account}


def main() -> None:
    print(json.dumps(load_example_history(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
