"""Local operator commands and development server."""

from __future__ import annotations

import argparse
import json
import os
import sys
from wsgiref.simple_server import make_server

from .api import create_app
from .data_foundation import (
    DataFoundationError,
    authenticate_integration,
    create_customer,
    create_integration,
    create_tenant,
    initialize_database,
    map_customer_identity,
)
from .importer import import_csv, iter_replay_events


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m retaniq", description="RetainIQ Part 1 data foundation")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init-db", help="create or migrate the local SQLite database")
    init.add_argument("--db", required=True)

    tenant = commands.add_parser("create-tenant", help="create a tenant (trusted local operator only)")
    tenant.add_argument("--db", required=True)
    tenant.add_argument("--tenant-id", required=True)

    integration = commands.add_parser("create-integration", help="create a scoped integration token")
    integration.add_argument("--db", required=True)
    integration.add_argument("--tenant-id", required=True)
    integration.add_argument("--source", required=True)
    integration.add_argument(
        "--purpose", action="append",
        choices=("retention_inference", "billing_valuation", "operational_contact", "identity_mapping"),
        help="explicitly grant one purpose; repeat to grant multiple purposes",
    )

    customer = commands.add_parser("create-customer", help="create a paying account (trusted local operator only)")
    customer.add_argument("--db", required=True)
    customer.add_argument("--tenant-id", required=True)
    customer.add_argument("--customer-id", required=True)
    customer.add_argument("--inactive", action="store_true")

    identity = commands.add_parser("map-customer", help="add an explicit source account mapping")
    identity.add_argument("--db", required=True)
    identity.add_argument("--tenant-id", required=True)
    identity.add_argument("--source", required=True)
    identity.add_argument("--external-customer-id", required=True)
    identity.add_argument("--customer-id", required=True)

    server = commands.add_parser("serve", help="run the local WSGI API")
    server.add_argument("--db", required=True)
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)

    importer = commands.add_parser("import-csv", help="import CSV rows through canonical event normalization")
    importer.add_argument("--db", required=True)
    importer.add_argument("--csv", required=True)
    importer.add_argument("--mapping", required=True, help="JSON source-to-canonical mapping file")
    importer.add_argument("--token-env", default="RETAINIQ_IMPORT_TOKEN")
    importer.add_argument("--trust-source-availability", action="store_true")

    replay = commands.add_parser("replay", help="enumerate authorized events by original availability time")
    replay.add_argument("--db", required=True)
    replay.add_argument("--available-from", required=True)
    replay.add_argument("--available-through", required=True)
    replay.add_argument("--token-env", default="RETAINIQ_IMPORT_TOKEN")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init-db":
            initialize_database(args.db)
            print(json.dumps({"status": "ready", "database": args.db}))
        elif args.command == "create-tenant":
            initialize_database(args.db)
            create_tenant(args.db, args.tenant_id)
            print(json.dumps({"status": "created", "tenant_id": args.tenant_id}))
        elif args.command == "create-integration":
            initialize_database(args.db)
            purposes = tuple(args.purpose) if args.purpose else ("retention_inference", "billing_valuation")
            token = create_integration(args.db, args.tenant_id, args.source, authorized_purposes=purposes)
            print(json.dumps({"source": args.source, "token": token, "store_this_token_securely": True}))
        elif args.command == "create-customer":
            create_customer(args.db, args.tenant_id, args.customer_id,
                            account_status="inactive" if args.inactive else "active")
            print(json.dumps({"status": "created", "customer_id": args.customer_id}))
        elif args.command == "map-customer":
            map_customer_identity(args.db, args.tenant_id, args.source,
                                  args.external_customer_id, args.customer_id)
            print(json.dumps({"status": "mapped", "source": args.source, "customer_id": args.customer_id}))
        elif args.command == "serve":
            app = create_app(args.db)
            with make_server(args.host, args.port, app) as server:
                server.serve_forever()
        elif args.command in {"import-csv", "replay"}:
            token = os.environ.get(args.token_env)
            principal = authenticate_integration(args.db, token)
            if args.command == "import-csv":
                with open(args.mapping, "r", encoding="utf-8") as stream:
                    mapping = json.load(stream)
                result = import_csv(
                    args.db, principal, args.csv, mapping,
                    trust_source_availability=args.trust_source_availability,
                )
            else:
                result = {"events": list(iter_replay_events(
                    args.db, principal, args.available_from, args.available_through,
                ))}
            print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
        return 0
    except DataFoundationError as error:
        print(json.dumps({"error": error.code, "message": str(error)}), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError):
        print(json.dumps({"error": "invalid_command_input"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
