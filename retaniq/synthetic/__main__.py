"""Command line interface for synthetic dataset generation, validation and import."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .canonical_adapter import import_dataset, provision_member2_reader
from .config import SyntheticConfig
from .generator import generate_dataset
from .validator import validate_dataset
from retaniq.secret_store import store_dpapi_secret


def _default_output() -> Path:
    return Path.home() / "RetainIQ-private" / "synthetic_saas_v1_2"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m retaniq.synthetic", description="RetainIQ synthetic SaaS datasets")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="stream a versioned synthetic dataset family")
    generate.add_argument("--profile", choices=("quick", "standard", "full", "stress"), required=True)
    generate.add_argument("--seed", type=int, default=2026)
    generate.add_argument("--accounts", type=int, dest="account_count")
    generate.add_argument("--tenants", type=int, dest="tenant_count")
    generate.add_argument("--start-date")
    generate.add_argument("--end-date")
    generate.add_argument("--event-density", type=float)
    generate.add_argument("--usage-frequency", type=float)
    generate.add_argument("--source-outage-frequency", type=float)
    generate.add_argument("--billing-failure-frequency", type=float)
    generate.add_argument("--churn-hazard-multiplier", type=float)
    generate.add_argument("--output", type=Path, default=_default_output())

    for name in ("validate", "import"):
        command = commands.add_parser(name, help=f"{name} an existing generated dataset")
        command.add_argument("--dataset", type=Path)
        command.add_argument("--profile", choices=("quick", "standard", "full", "stress"))
        command.add_argument("--output", type=Path, default=_default_output())
        if name == "import":
            command.add_argument("--db", type=Path, required=True)
            command.add_argument("--verify-idempotency", action="store_true")
    reader = commands.add_parser("provision-reader", help="create a one-time, tenant/source-scoped Member 2 credential")
    reader.add_argument("--dataset", type=Path, required=True)
    reader.add_argument("--db", type=Path, required=True)
    reader.add_argument("--tenant-id", required=True)
    reader.add_argument("--secret-file", type=Path, required=True,
                        help="destination for the current-user DPAPI-protected token")
    return parser


def _resolve_dataset(args: argparse.Namespace) -> Path:
    if args.dataset:
        return args.dataset.expanduser().resolve()
    if not args.profile:
        raise ValueError("provide --dataset or --profile")
    profile_dir = args.output.expanduser().resolve() / args.profile
    candidates = [path for path in profile_dir.glob("synthetic-saas-v1-*") if path.is_dir()]
    if not candidates:
        raise ValueError(f"no generated {args.profile} dataset found under {profile_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    started = time.perf_counter()
    try:
        if args.command == "generate":
            overrides = {
                name: getattr(args, name)
                for name in (
                    "account_count", "tenant_count", "start_date", "end_date", "event_density",
                    "usage_frequency", "source_outage_frequency", "billing_failure_frequency",
                    "churn_hazard_multiplier",
                )
                if getattr(args, name) is not None
            }
            result = generate_dataset(SyntheticConfig.from_profile(args.profile, seed=args.seed, **overrides), args.output)
            result = {
                "status": "GENERATED", "dataset_id": result["dataset_id"],
                "dataset_path": result["dataset_path"], "actual_counts": result["actual_counts"],
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        elif args.command == "validate":
            result = validate_dataset(_resolve_dataset(args))
            result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        elif args.command == "import":
            result = import_dataset(
                _resolve_dataset(args), args.db,
                verify_idempotency=args.verify_idempotency,
            )
            result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        else:
            result = provision_member2_reader(
                args.dataset, args.db, args.tenant_id,
                deliver_token=lambda token: store_dpapi_secret(args.secret_file, token),
            )
            result["secret_file"] = str(args.secret_file.expanduser().resolve())
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if result.get("status") not in {"FAIL", "PARTIAL"} else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=True, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
