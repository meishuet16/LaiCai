"""Read one imported synthetic account using a separately provisioned model token."""

from __future__ import annotations

import argparse
import json
import os

from retaniq.data_foundation import authenticate_service_principal, get_account_snapshot_as_of


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--token-env", default="RETAINIQ_MODEL_TOKEN")
    args = parser.parse_args()
    principal = authenticate_service_principal(args.db, os.environ.get(args.token_env))
    if principal.tenant_id != args.tenant_id:
        raise SystemExit("the authenticated principal is not scoped to the requested tenant")
    snapshot = get_account_snapshot_as_of(args.db, principal, args.customer_id, args.as_of)
    print(json.dumps({"dataset_kind": "synthetic_saas", "account": snapshot}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
