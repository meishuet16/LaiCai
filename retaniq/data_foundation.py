"""Canonical tenant-scoped event storage and point-in-time data access.

This module intentionally contains no feature engineering, churn label builder,
or predictor. It owns only the Part 1 storage and evidence contracts.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable
from contextlib import contextmanager
from .currency_codes import ISO4217_CURRENT_CODES


SCHEMA_VERSION = "1.0"
DEFAULT_MAPPING_VERSION = "canonical-v1"
MRR_POLICY_VERSION = "mrr-monthly-v1"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
SENSITIVE_KEY_PARTS = (
    "email", "phone", "address", "card", "cvv", "password", "secret",
    "token", "contact", "name", "private", "raw_payload", "api_key",
    "api_secret", "authorization", "auth_header", "note", "comment", "message",
)
FINANCIAL_KEY_PARTS = (
    "mrr", "arr", "amount", "currency", "price", "discount", "revenue",
    "contract_value", "billing_interval", "valuation", "subscription_fee",
    "exposure_proxy", "lifetime_value", "lifetime_revenue", "monetary",
    "arpu", "ltv", "acv",
)
EMAIL_VALUE_PATTERN = re.compile(r"(?i)\b[^\s@]+@[^\s@]+\.[a-z]{2,}\b")
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)\b(?:e-?mail|phone(?:\s+number)?|telephone(?:\s+number)?|mobile(?:\s+number)?|address|"
    r"card(?:\s+number)?|cvv|password|secret|token|api[\s_-]+(?:key|secret|token)|authorization|bearer|"
    r"contact|full\s+name|first\s+name|last\s+name|raw\s+payload)\b\s*[:=]\s*\S+"
)
SAFE_RELIABILITY_REASON_CODES = frozenset({
    "short_personal_usage_history", "missing_usage_source", "missing_billing_source",
    "missing_subscription_source", "insufficient_identity_mapping", "stale_source_data",
    "partial_source_coverage", "unsupported_dataset", "insufficient_event_history",
    "unverified_source_availability", "unknown_observation_coverage",
    "feature_quality_limited", "model_applicability_limited",
})
SERVICE_ROLES = frozenset({"analyst", "admin", "operator"})
PURPOSES = frozenset({
    "retention_inference", "billing_valuation", "operational_contact", "identity_mapping",
    "integration_health", "model_artifact_write",
})
EVENT_CATEGORIES = frozenset({"usage", "billing", "subscription"})
SAFE_CATEGORICAL_FIELDS = frozenset({
    "feature", "plan_id", "status", "subscription_status", "billing_interval", "currency",
    "source", "event_type", "unit", "direction", "trend", "cohort", "tier", "plan_tier",
    "payment_status", "data_quality_status",
    "reliability_status", "data_freshness_status", "reason_code",
})
SAFE_CATEGORY_SUFFIXES = ("_category",)
SAFE_CATEGORY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
SAFE_TIER_VALUES = frozenset({
    "basic", "business", "enterprise", "free", "growth", "premium", "professional",
    "pro", "starter", "standard", "ultimate", "unknown",
})
SENSITIVE_CATEGORY_MARKERS = (
    "sk_live_", "sk_test_", "pk_live_", "pk_test_", "bearer", "authorization",
    "password", "secret", "token", "api_key", "api-key", "api_secret", "api-secret",
    "ghp_", "gho_", "github_pat_", "xoxb-", "xoxp-", "ya29.", "akia",
)

EVENT_TYPES: dict[str, tuple[str, set[str]]] = {
    "session_started": ("usage", {"feature"}),
    "feature_used": ("usage", {"feature", "quantity", "unit"}),
    "usage_aggregate_updated": ("usage", {"feature", "quantity", "unit"}),
    "payment_failed": ("billing", {"subscription_id", "amount_minor", "currency"}),
    "payment_succeeded": ("billing", {"subscription_id", "amount_minor", "currency"}),
    "invoice_payment_failed": ("billing", {"subscription_id", "amount_minor", "currency"}),
    "invoice_paid": ("billing", {"subscription_id", "amount_minor", "currency"}),
    "subscription_created": (
        "subscription",
        {"subscription_id", "status", "plan_id", "started_at", "current_period_end",
         "billing_interval", "billing_interval_count", "amount_minor", "discount_minor", "currency"},
    ),
    "subscription_updated": (
        "subscription",
        {"subscription_id", "status", "plan_id", "started_at", "current_period_end",
         "ended_at", "cancellation_requested_at", "billing_interval", "billing_interval_count",
         "amount_minor", "discount_minor", "currency"},
    ),
    "cancellation_requested": ("subscription", {"subscription_id", "current_period_end"}),
    "subscription_cancelled_effective": ("subscription", {"subscription_id"}),
    "subscription_non_renewed_effective": ("subscription", {"subscription_id"}),
    "subscription_involuntary_terminated": ("subscription", {"subscription_id"}),
}

SUBSCRIPTION_FIELDS = (
    "status", "plan_id", "started_at", "current_period_end", "ended_at",
    "cancellation_requested_at", "billing_interval", "billing_interval_count",
    "amount_minor", "discount_minor", "currency",
)
ACTIVE_ENTITLEMENT_STATUSES = {"active", "past_due", "pending_cancel"}
SUBSCRIPTION_STATUSES = {"trialing", "active", "past_due", "pending_cancel", "ended"}
INTERVALS = {"day", "week", "month", "quarter", "year"}
RELIABILITY_STATUSES = {"sufficient_evidence", "limited_evidence", "insufficient_evidence"}
FRESHNESS_STATUSES = {"fresh", "partially_stale", "stale", "unknown"}
PREDICTION_STATUSES = {"scored", "abstained", "known_cancellation", "not_eligible"}

SAFE_MESSAGES = {
    "unauthorized": "Authentication is required.",
    "invalid_event": "The event is invalid or contains unsupported fields.",
    "source_not_authorized": "The authenticated integration is not authorized for this source.",
    "event_category_not_authorized": "The authenticated integration is not authorized for this event category.",
    "purpose_not_authorized": "The integration is not authorized for this data purpose.",
    "identity_not_mapped": "The source customer ID has no explicit tenant mapping.",
    "idempotency_conflict": "The source event ID was already used for different normalized data.",
    "not_found": "The requested tenant-scoped record was not found.",
    "contract_conflict": "The immutable record conflicts with an existing record.",
    "invalid_contract": "The record does not satisfy the shared storage contract.",
    "invalid_import_mapping": "The import mapping is invalid.",
    "invalid_csv": "The CSV file could not be processed.",
}


class DataFoundationError(Exception):
    """Safe, stable error intended for API responses and operational logs."""

    def __init__(self, code: str):
        self.code = code if code in SAFE_MESSAGES else "invalid_contract"
        super().__init__(SAFE_MESSAGES[self.code])


@dataclass(frozen=True)
class IntegrationPrincipal:
    integration_id: str
    tenant_id: str
    source: str
    schema_version: str
    mapping_version: str
    authorized_purposes: tuple[str, ...]
    authorized_categories: tuple[str, ...] = ("usage",)


@dataclass(frozen=True)
class ServicePrincipal:
    """Separately provisioned, tenant-scoped internal service authority."""

    service_principal_id: str
    tenant_id: str
    role: str
    authorized_sources: tuple[str, ...]
    authorized_purposes: tuple[str, ...]


ReadPrincipal = IntegrationPrincipal | ServicePrincipal


def _utc_now() -> str:
    return _format_timestamp(datetime.now(timezone.utc))


def _format_timestamp(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def normalize_timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise DataFoundationError("invalid_event")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except (ValueError, OverflowError):
        raise DataFoundationError("invalid_event") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataFoundationError("invalid_event")
    return _format_timestamp(parsed)


@contextmanager
def _db(path: str | Path):
    connection = sqlite3.connect(str(path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(path: str | Path) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    with _db(db_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        migrations = (
            ("001_data_foundation", migrations_dir / "001_data_foundation.sql"),
            (
                "002_authorized_services_and_subscription_owners",
                migrations_dir / "002_authorized_services_and_subscription_owners.sql",
            ),
            (
                "003_integration_event_categories",
                migrations_dir / "003_integration_event_categories.sql",
            ),
        )
        for version, migration in migrations:
            applied = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?", (version,),
            ).fetchone()
            if applied is not None:
                continue
            if version == "002_authorized_services_and_subscription_owners":
                conflicts = connection.execute(
                    "WITH claims AS ("
                    " SELECT tenant_id, subscription_id, customer_id FROM subscriptions"
                    " UNION SELECT tenant_id, subscription_id, customer_id FROM subscription_events"
                    " UNION SELECT tenant_id, subscription_id, customer_id FROM billing_events"
                    " WHERE subscription_id IS NOT NULL) "
                    "SELECT tenant_id, subscription_id FROM claims "
                    "GROUP BY tenant_id, subscription_id HAVING COUNT(DISTINCT customer_id) > 1 LIMIT 1"
                ).fetchone()
                if conflicts is not None:
                    raise DataFoundationError("contract_conflict")
            script = migration.read_text(encoding="utf-8")
            applied_at = _utc_now().replace("'", "''")
            connection.executescript(
                "BEGIN IMMEDIATE;\n" + script +
                f"\nINSERT INTO schema_migrations(version, applied_at) VALUES ('{version}', '{applied_at}');\nCOMMIT;"
            )


def _validate_id(value: Any) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise DataFoundationError("invalid_contract")
    return value


def _validate_slug(value: Any) -> str:
    if not isinstance(value, str) or not SLUG_PATTERN.fullmatch(value):
        raise DataFoundationError("invalid_event")
    return value


def create_tenant(path: str | Path, tenant_id: str) -> None:
    tenant_id = _validate_id(tenant_id)
    with _db(path) as connection:
        connection.execute("INSERT OR IGNORE INTO tenants(tenant_id) VALUES (?)", (tenant_id,))


def create_integration(
    path: str | Path,
    tenant_id: str,
    source: str,
    *,
    schema_version: str = SCHEMA_VERSION,
    mapping_version: str = DEFAULT_MAPPING_VERSION,
    authorized_purposes: tuple[str, ...] = ("retention_inference", "billing_valuation"),
    authorized_categories: tuple[str, ...] = ("usage",),
) -> str:
    tenant_id = _validate_id(tenant_id)
    source = _validate_id(source)
    if schema_version != SCHEMA_VERSION:
        raise DataFoundationError("invalid_contract")
    mapping_version = _validate_id(mapping_version)
    allowed_purposes = {"retention_inference", "billing_valuation", "operational_contact", "identity_mapping"}
    if not isinstance(authorized_purposes, (tuple, list)) or not authorized_purposes:
        raise DataFoundationError("invalid_contract")
    if any(purpose not in allowed_purposes for purpose in authorized_purposes):
        raise DataFoundationError("invalid_contract")
    if (not isinstance(authorized_categories, (tuple, list)) or not authorized_categories
            or any(not isinstance(category, str) or category not in EVENT_CATEGORIES
                   for category in authorized_categories)):
        raise DataFoundationError("invalid_contract")
    purposes_json = json.dumps(sorted(set(authorized_purposes)), separators=(",", ":"))
    categories = tuple(sorted(set(authorized_categories)))
    token = secrets.token_urlsafe(32)
    token_digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    integration_id = secrets.token_urlsafe(18)
    with _db(path) as connection:
        try:
            connection.execute(
                "INSERT INTO integrations(integration_id, tenant_id, source, token_digest, authorized_purposes_json, "
                "schema_version, mapping_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (integration_id, tenant_id, source, token_digest, purposes_json, schema_version, mapping_version, _utc_now()),
            )
            connection.executemany(
                "INSERT INTO integration_event_categories(tenant_id, source, category) VALUES (?, ?, ?)",
                ((tenant_id, source, category) for category in categories),
            )
        except sqlite3.IntegrityError:
            raise DataFoundationError("contract_conflict") from None
    return token


def set_integration_event_categories(
    path: str | Path,
    tenant_id: str,
    source: str,
    authorized_categories: tuple[str, ...] | list[str],
) -> None:
    """Replace an integration's category grants as a trusted local operator action."""
    tenant_id = _validate_id(tenant_id)
    source = _validate_id(source)
    if (not isinstance(authorized_categories, (tuple, list)) or not authorized_categories
            or any(not isinstance(category, str) or category not in EVENT_CATEGORIES
                   for category in authorized_categories)):
        raise DataFoundationError("invalid_contract")
    categories = tuple(sorted(set(authorized_categories)))
    with _db(path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM integrations WHERE tenant_id = ? AND source = ?",
            (tenant_id, source),
        ).fetchone()
        if exists is None:
            raise DataFoundationError("not_found")
        connection.execute(
            "DELETE FROM integration_event_categories WHERE tenant_id = ? AND source = ?",
            (tenant_id, source),
        )
        connection.executemany(
            "INSERT INTO integration_event_categories(tenant_id, source, category) VALUES (?, ?, ?)",
            ((tenant_id, source, category) for category in categories),
        )


def create_customer(
    path: str | Path,
    tenant_id: str,
    customer_id: str,
    *,
    account_status: str = "active",
) -> None:
    tenant_id = _validate_id(tenant_id)
    customer_id = _validate_id(customer_id)
    if account_status not in {"active", "inactive"}:
        raise DataFoundationError("invalid_contract")
    with _db(path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO customers(tenant_id, customer_id, account_status, created_at) "
            "VALUES (?, ?, ?, ?)",
            (tenant_id, customer_id, account_status, _utc_now()),
        )


def map_customer_identity(
    path: str | Path,
    tenant_id: str,
    source: str,
    external_customer_id: str,
    customer_id: str,
) -> None:
    tenant_id = _validate_id(tenant_id)
    source = _validate_id(source)
    external_customer_id = _validate_id(external_customer_id)
    customer_id = _validate_id(customer_id)
    with _db(path) as connection:
        customer = connection.execute(
            "SELECT 1 FROM customers WHERE tenant_id = ? AND customer_id = ?",
            (tenant_id, customer_id),
        ).fetchone()
        if customer is None:
            raise DataFoundationError("not_found")
        existing = connection.execute(
            "SELECT customer_id FROM customer_identities "
            "WHERE tenant_id = ? AND source = ? AND external_customer_id = ?",
            (tenant_id, source, external_customer_id),
        ).fetchone()
        if existing:
            if existing["customer_id"] != customer_id:
                raise DataFoundationError("contract_conflict")
            return
        connection.execute(
            "INSERT INTO customer_identities(tenant_id, source, external_customer_id, customer_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tenant_id, source, external_customer_id, customer_id, _utc_now()),
        )


def authenticate_integration(path: str | Path, token: str | None) -> IntegrationPrincipal:
    if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
        raise DataFoundationError("unauthorized")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _db(path) as connection:
        row = connection.execute(
            "SELECT integration_id, tenant_id, source, authorized_purposes_json, schema_version, mapping_version "
            "FROM integrations WHERE token_digest = ?",
            (digest,),
        ).fetchone()
        categories = () if row is None else tuple(
            item["category"] for item in connection.execute(
                "SELECT category FROM integration_event_categories "
                "WHERE tenant_id = ? AND source = ? ORDER BY category",
                (row["tenant_id"], row["source"]),
            ).fetchall()
        )
    if row is None:
        raise DataFoundationError("unauthorized")
    return IntegrationPrincipal(
        row["integration_id"], row["tenant_id"], row["source"],
        row["schema_version"], row["mapping_version"], tuple(json.loads(row["authorized_purposes_json"])),
        categories,
    )


def create_service_principal(
    path: str | Path,
    tenant_id: str,
    *,
    role: str,
    authorized_sources: tuple[str, ...] | list[str],
    authorized_purposes: tuple[str, ...] | list[str],
) -> str:
    """Provision an internal bearer credential with exact tenant/source/purpose grants.

    This local operator provisioning function must not be exposed as an application endpoint.
    """
    tenant_id = _validate_id(tenant_id)
    if not isinstance(role, str) or role not in SERVICE_ROLES:
        raise DataFoundationError("invalid_contract")
    if not isinstance(authorized_sources, (tuple, list)) or not authorized_sources:
        raise DataFoundationError("invalid_contract")
    if not isinstance(authorized_purposes, (tuple, list)) or not authorized_purposes:
        raise DataFoundationError("invalid_contract")
    if any(not isinstance(purpose, str) for purpose in authorized_purposes):
        raise DataFoundationError("invalid_contract")
    sources = tuple(sorted({_validate_id(source) for source in authorized_sources}))
    purposes = tuple(sorted(set(authorized_purposes)))
    if any(purpose not in PURPOSES for purpose in purposes):
        raise DataFoundationError("invalid_contract")
    token = secrets.token_urlsafe(32)
    token_digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    service_principal_id = secrets.token_urlsafe(18)
    with _db(path) as connection:
        tenant = connection.execute("SELECT 1 FROM tenants WHERE tenant_id = ?", (tenant_id,)).fetchone()
        if tenant is None:
            raise DataFoundationError("not_found")
        known_sources = {
            row["source"] for row in connection.execute(
                "SELECT source FROM integrations WHERE tenant_id = ?", (tenant_id,),
            ).fetchall()
        }
        if not set(sources).issubset(known_sources):
            raise DataFoundationError("source_not_authorized")
        connection.execute(
            "INSERT INTO service_principals(service_principal_id, tenant_id, token_digest, role, "
            "authorized_sources_json, authorized_purposes_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (service_principal_id, tenant_id, token_digest, role,
             json.dumps(sources, separators=(",", ":")),
             json.dumps(purposes, separators=(",", ":")), _utc_now()),
        )
    return token


def authenticate_service_principal(path: str | Path, token: str | None) -> ServicePrincipal:
    if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
        raise DataFoundationError("unauthorized")
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _db(path) as connection:
        row = connection.execute(
            "SELECT service_principal_id, tenant_id, role, authorized_sources_json, authorized_purposes_json "
            "FROM service_principals WHERE token_digest = ?", (digest,),
        ).fetchone()
    if row is None:
        raise DataFoundationError("unauthorized")
    return ServicePrincipal(
        row["service_principal_id"], row["tenant_id"], row["role"],
        tuple(json.loads(row["authorized_sources_json"])),
        tuple(json.loads(row["authorized_purposes_json"])),
    )


def _assert_principal(connection: sqlite3.Connection, principal: IntegrationPrincipal) -> sqlite3.Row:
    if not isinstance(principal, IntegrationPrincipal):
        raise DataFoundationError("unauthorized")
    row = connection.execute(
        "SELECT integration_id, tenant_id, source, authorized_purposes_json, schema_version, mapping_version "
        "FROM integrations WHERE integration_id = ? AND tenant_id = ? AND source = ?",
        (principal.integration_id, principal.tenant_id, principal.source),
    ).fetchone()
    if row is None:
        raise DataFoundationError("unauthorized")
    categories = tuple(
        item["category"] for item in connection.execute(
            "SELECT category FROM integration_event_categories "
            "WHERE tenant_id = ? AND source = ? ORDER BY category",
            (principal.tenant_id, principal.source),
        ).fetchall()
    )
    if (principal.schema_version != row["schema_version"]
            or principal.authorized_purposes != tuple(json.loads(row["authorized_purposes_json"]))
            or principal.authorized_categories != categories):
        raise DataFoundationError("unauthorized")
    return row


def _assert_service_principal(connection: sqlite3.Connection, principal: ServicePrincipal) -> sqlite3.Row:
    if not isinstance(principal, ServicePrincipal):
        raise DataFoundationError("unauthorized")
    row = connection.execute(
        "SELECT service_principal_id, tenant_id, role, authorized_sources_json, authorized_purposes_json "
        "FROM service_principals WHERE service_principal_id = ? AND tenant_id = ?",
        (principal.service_principal_id, principal.tenant_id),
    ).fetchone()
    if row is None:
        raise DataFoundationError("unauthorized")
    sources = tuple(json.loads(row["authorized_sources_json"]))
    purposes = tuple(json.loads(row["authorized_purposes_json"]))
    if (principal.role != row["role"] or principal.authorized_sources != sources
            or principal.authorized_purposes != purposes):
        raise DataFoundationError("unauthorized")
    known_sources = {
        item["source"] for item in connection.execute(
            "SELECT source FROM integrations WHERE tenant_id = ?", (principal.tenant_id,),
        ).fetchall()
    }
    if not set(sources).issubset(known_sources):
        raise DataFoundationError("unauthorized")
    return row


def _assert_read_principal(connection: sqlite3.Connection, principal: ReadPrincipal) -> tuple[str, ...]:
    if isinstance(principal, IntegrationPrincipal):
        _assert_principal(connection, principal)
        return (principal.source,)
    row = _assert_service_principal(connection, principal)
    if row["role"] not in SERVICE_ROLES:
        raise DataFoundationError("unauthorized")
    return tuple(json.loads(row["authorized_sources_json"]))


def update_mapping_version(
    path: str | Path,
    principal: IntegrationPrincipal,
    mapping_version: str,
) -> IntegrationPrincipal:
    """Record an operator-approved source mapping version during local import setup."""
    mapping_version = _validate_id(mapping_version)
    with _db(path) as connection:
        row = _assert_principal(connection, principal)
        connection.execute(
            "UPDATE integrations SET mapping_version = ? WHERE integration_id = ?",
            (mapping_version, row["integration_id"]),
        )
    return IntegrationPrincipal(
        principal.integration_id, principal.tenant_id, principal.source,
        principal.schema_version, mapping_version, principal.authorized_purposes,
        principal.authorized_categories,
    )


def record_integration_failure(
    path: str | Path,
    principal: IntegrationPrincipal,
    error_code: str,
    occurred_at: str | None = None,
) -> None:
    code = error_code if error_code in SAFE_MESSAGES else "invalid_event"
    at = normalize_timestamp(occurred_at) if occurred_at else _utc_now()
    with _db(path) as connection:
        row = _assert_principal(connection, principal)
        connection.execute(
            "UPDATE integrations SET last_failure_at = ?, last_failure_code = ? WHERE integration_id = ?",
            (at, code, row["integration_id"]),
        )


def _integer(value: Any, *, minimum: int = 0, maximum: int = 2**62) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise DataFoundationError("invalid_event")
    return value


def _currency(value: Any) -> str:
    if not isinstance(value, str) or not CURRENCY_PATTERN.fullmatch(value) or value not in ISO4217_CURRENT_CODES:
        raise DataFoundationError("invalid_event")
    return value


def _require_purposes(principal: ReadPrincipal, *purposes: str) -> None:
    if not isinstance(principal, (IntegrationPrincipal, ServicePrincipal)) or any(
        purpose not in principal.authorized_purposes for purpose in purposes
    ):
        raise DataFoundationError("purpose_not_authorized")


def _normalize_attributes(event_type: str, attributes: Any, occurred_at: str) -> tuple[str, dict[str, Any]]:
    category, allowed = EVENT_TYPES[event_type]
    if not isinstance(attributes, dict) or any(not isinstance(key, str) for key in attributes):
        raise DataFoundationError("invalid_event")
    if not set(attributes).issubset(allowed):
        raise DataFoundationError("invalid_event")
    result: dict[str, Any] = {}

    if category == "usage":
        if "feature" in attributes:
            result["feature"] = _validate_slug(attributes["feature"])
        if "quantity" in attributes:
            result["quantity"] = _integer(attributes["quantity"])
        if "unit" in attributes:
            result["unit"] = _validate_slug(attributes["unit"])
        if "quantity" in result and "unit" not in result:
            raise DataFoundationError("invalid_event")
        return category, result

    if category == "billing":
        if "subscription_id" in attributes:
            result["subscription_id"] = _validate_id(attributes["subscription_id"])
        event_status = "failed" if event_type in {"payment_failed", "invoice_payment_failed"} else "succeeded"
        if "amount_minor" in attributes:
            result["amount_minor"] = _integer(attributes["amount_minor"])
        if "currency" in attributes:
            result["currency"] = _currency(attributes["currency"])
        if ("amount_minor" in result) != ("currency" in result):
            raise DataFoundationError("invalid_event")
        result["payment_status"] = event_status
        return category, result

    if "subscription_id" not in attributes:
        raise DataFoundationError("invalid_event")
    result["subscription_id"] = _validate_id(attributes["subscription_id"])
    if event_type == "cancellation_requested":
        result["status"] = "pending_cancel"
        result["cancellation_requested_at"] = occurred_at
        if "current_period_end" in attributes:
            value = attributes["current_period_end"]
            result["current_period_end"] = normalize_timestamp(value) if value is not None else None
        return category, result
    if event_type in {
        "subscription_cancelled_effective", "subscription_non_renewed_effective",
        "subscription_involuntary_terminated",
    }:
        result["status"] = "ended"
        result["ended_at"] = occurred_at
        return category, result

    if event_type == "subscription_created":
        if "status" not in attributes or "started_at" not in attributes:
            raise DataFoundationError("invalid_event")
    if "status" in attributes:
        status = attributes["status"]
        permitted_statuses = SUBSCRIPTION_STATUSES - {"ended"}
        if status not in permitted_statuses:
            raise DataFoundationError("invalid_event")
        result["status"] = status
    if "plan_id" in attributes:
        result["plan_id"] = _validate_slug(attributes["plan_id"])
    for field in ("started_at", "current_period_end", "ended_at", "cancellation_requested_at"):
        if field in attributes:
            value = attributes[field]
            result[field] = normalize_timestamp(value) if value is not None else None
    if "billing_interval" in attributes:
        if attributes["billing_interval"] not in INTERVALS:
            raise DataFoundationError("invalid_event")
        result["billing_interval"] = attributes["billing_interval"]
    if "billing_interval_count" in attributes:
        result["billing_interval_count"] = _integer(attributes["billing_interval_count"], minimum=1, maximum=1200)
    for field in ("amount_minor", "discount_minor"):
        if field in attributes:
            result[field] = _integer(attributes[field]) if attributes[field] is not None else None
    if "currency" in attributes:
        result["currency"] = _currency(attributes["currency"]) if attributes["currency"] is not None else None
    if event_type == "subscription_created" and result.get("amount_minor") is not None and "currency" not in result:
        raise DataFoundationError("invalid_event")
    if event_type == "subscription_updated":
        price_fields = {"amount_minor", "currency", "discount_minor"}
        if set(attributes).intersection(price_fields):
            if not {"amount_minor", "currency"}.issubset(attributes):
                raise DataFoundationError("invalid_event")
    if result.get("discount_minor") is not None:
        if result.get("amount_minor") is None or result["discount_minor"] > result["amount_minor"]:
            raise DataFoundationError("invalid_event")
    if result.get("amount_minor") is not None and not result.get("currency"):
        raise DataFoundationError("invalid_event")
    if result.get("discount_minor") is not None and not result.get("currency"):
        raise DataFoundationError("invalid_event")
    if event_type == "subscription_updated" and len(result) == 1:
        raise DataFoundationError("invalid_event")
    return category, result


def _normalize_envelope(
    principal: IntegrationPrincipal,
    payload: Any,
    *,
    trusted_source_available_at: str | None,
) -> dict[str, Any]:
    if not isinstance(principal, IntegrationPrincipal):
        raise DataFoundationError("unauthorized")
    if not isinstance(payload, dict):
        raise DataFoundationError("invalid_event")
    required = {
        "source", "source_event_id", "external_customer_id", "event_type",
        "occurred_at", "attributes", "schema_version",
    }
    if set(payload) != required:
        raise DataFoundationError("invalid_event")
    if payload.get("source") != principal.source:
        raise DataFoundationError("source_not_authorized")
    if payload.get("schema_version") != principal.schema_version or payload.get("schema_version") != SCHEMA_VERSION:
        raise DataFoundationError("invalid_event")
    source_event_id = _validate_id(payload.get("source_event_id"))
    external_customer_id = _validate_id(payload.get("external_customer_id"))
    event_type = payload.get("event_type")
    if not isinstance(event_type, str) or event_type not in EVENT_TYPES:
        raise DataFoundationError("invalid_event")
    occurred_at = normalize_timestamp(payload.get("occurred_at"))
    category, attributes = _normalize_attributes(event_type, payload.get("attributes"), occurred_at)
    source_available_at = (
        normalize_timestamp(trusted_source_available_at)
        if trusted_source_available_at is not None else None
    )
    return {
        "source": principal.source,
        "source_event_id": source_event_id,
        "external_customer_id": external_customer_id,
        "event_type": event_type,
        "category": category,
        "occurred_at": occurred_at,
        "attributes": attributes,
        "schema_version": SCHEMA_VERSION,
        "source_available_at": source_available_at,
    }


def _event_hash(event: dict[str, Any]) -> str:
    fields = {
        key: event[key]
        for key in ("source", "source_event_id", "external_customer_id", "event_type", "occurred_at", "attributes", "source_available_at")
    }
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _claim_subscription_owner(
    connection: sqlite3.Connection,
    tenant_id: str,
    subscription_id: str,
    customer_id: str,
) -> None:
    owner = connection.execute(
        "SELECT customer_id FROM subscription_owners WHERE tenant_id = ? AND subscription_id = ?",
        (tenant_id, subscription_id),
    ).fetchone()
    if owner is not None:
        if owner["customer_id"] != customer_id:
            raise DataFoundationError("contract_conflict")
        return
    connection.execute(
        "INSERT INTO subscription_owners(tenant_id, subscription_id, customer_id) VALUES (?, ?, ?)",
        (tenant_id, subscription_id, customer_id),
    )


def _record_subscription_event(
    connection: sqlite3.Connection,
    tenant_id: str,
    event_id: int,
    customer_id: str,
    event: dict[str, Any],
    received_at: str,
) -> None:
    attributes = event["attributes"]
    subscription_id = attributes["subscription_id"]
    changes = {field: attributes[field] for field in SUBSCRIPTION_FIELDS if field in attributes}
    changed_fields = list(changes)
    columns = [changes.get(field) for field in SUBSCRIPTION_FIELDS]
    connection.execute(
        "INSERT INTO subscription_events(tenant_id, event_id, subscription_id, customer_id, event_type, "
        "changed_fields_json, status, plan_id, started_at, current_period_end, ended_at, "
        "cancellation_requested_at, billing_interval, billing_interval_count, amount_minor, "
        "discount_minor, currency, occurred_at, received_at, source_available_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tenant_id, event_id, subscription_id, customer_id, event["event_type"],
         json.dumps(changed_fields, separators=(",", ":")), *columns,
         event["occurred_at"], received_at, event["source_available_at"]),
    )
    _rebuild_subscription_projection(connection, tenant_id, customer_id, subscription_id)


def _fold_subscription_rows(rows: Iterable[sqlite3.Row], subscription_id: str, customer_id: str) -> dict[str, Any]:
    state: dict[str, Any] = {"subscription_id": subscription_id, "customer_id": customer_id}
    for row in rows:
        try:
            changed_fields = json.loads(row["changed_fields_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        for field in changed_fields:
            if field in SUBSCRIPTION_FIELDS:
                state[field] = row[field]
    return state


def _rebuild_subscription_projection(
    connection: sqlite3.Connection,
    tenant_id: str,
    customer_id: str,
    subscription_id: str,
) -> None:
    rows = connection.execute(
        "SELECT se.* FROM subscription_events se JOIN canonical_events ce "
        "ON ce.tenant_id = se.tenant_id AND ce.event_id = se.event_id "
        "WHERE se.tenant_id = ? AND se.customer_id = ? AND se.subscription_id = ? "
        "ORDER BY ce.occurred_at, COALESCE(ce.source_available_at, ce.received_at), ce.event_id",
        (tenant_id, customer_id, subscription_id),
    ).fetchall()
    if not rows:
        return
    state = _fold_subscription_rows(rows, subscription_id, customer_id)
    if state.get("status") not in SUBSCRIPTION_STATUSES:
        state["status"] = "trialing"
    values = [state.get(field) for field in SUBSCRIPTION_FIELDS]
    updated_at = max(row["received_at"] for row in rows)
    connection.execute(
        "INSERT INTO subscriptions(tenant_id, subscription_id, customer_id, status, plan_id, started_at, "
        "current_period_end, ended_at, cancellation_requested_at, billing_interval, billing_interval_count, "
        "amount_minor, discount_minor, currency, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(tenant_id, subscription_id) DO UPDATE SET "
        "plan_id=excluded.plan_id, status=excluded.status, started_at=excluded.started_at, "
        "current_period_end=excluded.current_period_end, ended_at=excluded.ended_at, "
        "cancellation_requested_at=excluded.cancellation_requested_at, billing_interval=excluded.billing_interval, "
        "billing_interval_count=excluded.billing_interval_count, amount_minor=excluded.amount_minor, "
        "discount_minor=excluded.discount_minor, currency=excluded.currency, updated_at=excluded.updated_at",
        (tenant_id, subscription_id, customer_id, *values, updated_at),
    )


def ingest_event(
    path: str | Path,
    principal: IntegrationPrincipal,
    payload: Any,
    *,
    received_at: str | None = None,
    trusted_source_available_at: str | None = None,
) -> dict[str, Any]:
    received = normalize_timestamp(received_at) if received_at else _utc_now()
    try:
        event = _normalize_envelope(
            principal, payload, trusted_source_available_at=trusted_source_available_at,
        )
        digest = _event_hash(event)
        with _db(path) as connection:
            integration = _assert_principal(connection, principal)
            if event["category"] not in principal.authorized_categories:
                raise DataFoundationError("event_category_not_authorized")
            required_purposes = {"retention_inference"}
            if any(key in event["attributes"] for key in ("amount_minor", "discount_minor", "currency")):
                required_purposes.add("billing_valuation")
            if not required_purposes.issubset(principal.authorized_purposes):
                raise DataFoundationError("source_not_authorized")
            connection.execute("BEGIN IMMEDIATE")
            identity = connection.execute(
                "SELECT customer_id FROM customer_identities "
                "WHERE tenant_id = ? AND source = ? AND external_customer_id = ?",
                (principal.tenant_id, principal.source, event["external_customer_id"]),
            ).fetchone()
            if identity is None:
                raise DataFoundationError("identity_not_mapped")
            prior = connection.execute(
                "SELECT event_id, normalized_payload_sha256 FROM canonical_events "
                "WHERE tenant_id = ? AND source = ? AND source_event_id = ?",
                (principal.tenant_id, principal.source, event["source_event_id"]),
            ).fetchone()
            if prior:
                if prior["normalized_payload_sha256"] != digest:
                    raise DataFoundationError("idempotency_conflict")
                connection.execute(
                    "UPDATE integrations SET last_successful_ingestion_at = ?, last_failure_code = NULL "
                    "WHERE integration_id = ?",
                    (received, principal.integration_id),
                )
                return {
                    "event_id": prior["event_id"], "customer_id": identity["customer_id"],
                    "duplicate": True, "status": "duplicate",
                }
            subscription_id = event["attributes"].get("subscription_id")
            if subscription_id is not None:
                _claim_subscription_owner(
                    connection, principal.tenant_id, subscription_id, identity["customer_id"],
                )
            cursor = connection.execute(
                "INSERT INTO canonical_events(tenant_id, source, source_event_id, customer_id, category, "
                "event_type, occurred_at, received_at, source_available_at, schema_version, mapping_version, "
                "normalized_payload_sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (principal.tenant_id, principal.source, event["source_event_id"], identity["customer_id"],
                 event["category"], event["event_type"], event["occurred_at"], received,
                 event["source_available_at"], event["schema_version"], integration["mapping_version"], digest),
            )
            event_id = int(cursor.lastrowid)
            attrs = event["attributes"]
            if event["category"] == "usage":
                connection.execute(
                    "INSERT INTO usage_events(tenant_id, event_id, customer_id, event_type, feature, quantity, unit, "
                    "occurred_at, received_at, source_available_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (principal.tenant_id, event_id, identity["customer_id"], event["event_type"],
                     attrs.get("feature"), attrs.get("quantity"), attrs.get("unit"), event["occurred_at"],
                     received, event["source_available_at"]),
                )
            elif event["category"] == "billing":
                connection.execute(
                    "INSERT INTO billing_events(tenant_id, event_id, customer_id, subscription_id, event_type, "
                    "payment_status, amount_minor, currency, occurred_at, received_at, source_available_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (principal.tenant_id, event_id, identity["customer_id"], attrs.get("subscription_id"),
                     event["event_type"], attrs["payment_status"], attrs.get("amount_minor"),
                     attrs.get("currency"), event["occurred_at"], received, event["source_available_at"]),
                )
            else:
                _record_subscription_event(
                    connection, principal.tenant_id, event_id, identity["customer_id"], event, received,
                )
            connection.execute(
                "UPDATE integrations SET last_successful_ingestion_at = ?, last_failure_code = NULL "
                "WHERE integration_id = ?",
                (received, principal.integration_id),
            )
            return {
                "event_id": event_id, "customer_id": identity["customer_id"],
                "duplicate": False, "status": "accepted",
            }
    except DataFoundationError as exc:
        if exc.code not in {"unauthorized"}:
            try:
                record_integration_failure(path, principal, exc.code, received)
            except DataFoundationError:
                pass
        raise
    except sqlite3.IntegrityError:
        record_integration_failure(path, principal, "invalid_event", received)
        raise DataFoundationError("invalid_event") from None


def _as_of_query() -> str:
    return "ce.occurred_at <= ? AND COALESCE(ce.source_available_at, ce.received_at) <= ?"


def get_events_as_of(
    path: str | Path,
    principal: ReadPrincipal,
    customer_id: str,
    as_of: str,
    *,
    category: str | None = None,
) -> list[dict[str, Any]]:
    customer_id = _validate_id(customer_id)
    cutoff = normalize_timestamp(as_of)
    if category not in {None, "usage", "billing", "subscription"}:
        raise DataFoundationError("invalid_contract")
    _require_purposes(principal, "retention_inference")
    include_billing = "billing_valuation" in principal.authorized_purposes
    with _db(path) as connection:
        authorized_sources = _assert_read_principal(connection, principal)
        source_placeholders = ",".join("?" for _ in authorized_sources)
        sql = (
            "SELECT ce.*, COALESCE(ce.source_available_at, ce.received_at) AS available_at, "
            "u.feature, u.quantity, u.unit, b.subscription_id AS billing_subscription_id, "
            "b.payment_status, b.amount_minor AS billing_amount_minor, b.currency AS billing_currency, "
            "se.subscription_id AS changed_subscription_id, se.changed_fields_json, "
            "se.status AS changed_status, se.plan_id, se.started_at, se.current_period_end, se.ended_at, "
            "se.cancellation_requested_at, se.billing_interval, se.billing_interval_count, "
            "se.amount_minor AS subscription_amount_minor, se.discount_minor, se.currency AS subscription_currency "
            "FROM canonical_events ce "
            "LEFT JOIN usage_events u ON u.tenant_id=ce.tenant_id AND u.event_id=ce.event_id "
            "LEFT JOIN billing_events b ON b.tenant_id=ce.tenant_id AND b.event_id=ce.event_id "
            "LEFT JOIN subscription_events se ON se.tenant_id=ce.tenant_id AND se.event_id=ce.event_id "
            f"WHERE ce.tenant_id = ? AND ce.customer_id = ? AND ce.source IN ({source_placeholders}) "
            f"AND {_as_of_query()}"
        )
        params: list[Any] = [principal.tenant_id, customer_id, *authorized_sources, cutoff, cutoff]
        if category:
            sql += " AND ce.category = ?"
            params.append(category)
        sql += " ORDER BY ce.occurred_at, available_at, ce.event_id"
        rows = connection.execute(sql, params).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "event_id": row["event_id"], "source": row["source"],
            "source_event_id": row["source_event_id"], "customer_id": row["customer_id"],
            "category": row["category"], "event_type": row["event_type"],
            "occurred_at": row["occurred_at"], "received_at": row["received_at"],
            "source_available_at": row["source_available_at"], "available_at": row["available_at"],
            "schema_version": row["schema_version"], "mapping_version": row["mapping_version"],
        }
        if row["category"] == "usage":
            item["attributes"] = {key: row[key] for key in ("feature", "quantity", "unit") if row[key] is not None}
        elif row["category"] == "billing":
            item["attributes"] = {
                key: value for key, value in (
                    ("subscription_id", row["billing_subscription_id"]),
                    ("payment_status", row["payment_status"]),
                    ("amount_minor", row["billing_amount_minor"]), ("currency", row["billing_currency"]),
                ) if value is not None and (include_billing or key not in {"amount_minor", "currency"})
            }
        else:
            item["attributes"] = {
                "subscription_id": row["changed_subscription_id"],
                "changes": {
                    field: row[column] for field, column in zip(
                        SUBSCRIPTION_FIELDS,
                        ("changed_status", "plan_id", "started_at", "current_period_end", "ended_at",
                         "cancellation_requested_at", "billing_interval", "billing_interval_count",
                         "subscription_amount_minor", "discount_minor", "subscription_currency"),
                     ) if field in json.loads(row["changed_fields_json"])
                     and (include_billing or field not in {
                         "billing_interval", "billing_interval_count", "amount_minor", "discount_minor", "currency",
                     })
                },
            }
            item["subscription_id"] = row["changed_subscription_id"]
        if row["category"] == "billing":
            item["payment_status"] = row["payment_status"]
            item["subscription_id"] = row["billing_subscription_id"]
            if include_billing:
                item["amount_minor"] = row["billing_amount_minor"]
                item["currency"] = row["billing_currency"]
        result.append(item)
    return result


def _subscription_mrr_minor(state: dict[str, Any]) -> int | None:
    amount = state.get("amount_minor")
    discount = state.get("discount_minor") or 0
    interval = state.get("billing_interval")
    count = state.get("billing_interval_count")
    if amount is None or interval not in INTERVALS or not isinstance(count, int) or count <= 0:
        return None
    net = amount - discount
    ratios = {
        "day": (365, 12 * count),
        "week": (52, 12 * count),
        "month": (1, count),
        "quarter": (1, 3 * count),
        "year": (1, 12 * count),
    }
    numerator, denominator = ratios[interval]
    return int((Decimal(net * numerator) / Decimal(denominator)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_subscriptions_as_of(
    path: str | Path,
    principal: ReadPrincipal,
    customer_id: str,
    as_of: str,
) -> list[dict[str, Any]]:
    customer_id = _validate_id(customer_id)
    cutoff = normalize_timestamp(as_of)
    with _db(path) as connection:
        authorized_sources = _assert_read_principal(connection, principal)
        _require_purposes(principal, "retention_inference")
        source_placeholders = ",".join("?" for _ in authorized_sources)
        rows = connection.execute(
            "SELECT se.*, ce.occurred_at AS parent_occurred_at, ce.received_at AS parent_received_at, "
            "ce.source_available_at AS parent_source_available_at, ce.event_id AS parent_event_id "
            "FROM subscription_events se JOIN canonical_events ce "
            "ON ce.tenant_id=se.tenant_id AND ce.event_id=se.event_id "
            f"WHERE se.tenant_id = ? AND se.customer_id = ? AND ce.source IN ({source_placeholders}) "
            f"AND {_as_of_query()} "
            "ORDER BY ce.occurred_at, COALESCE(ce.source_available_at, ce.received_at), ce.event_id",
            (principal.tenant_id, customer_id, *authorized_sources, cutoff, cutoff),
        ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["subscription_id"], []).append(row)
    subscriptions: list[dict[str, Any]] = []
    for subscription_id, history in grouped.items():
        state = _fold_subscription_rows(history, subscription_id, customer_id)
        for field in SUBSCRIPTION_FIELDS:
            state.setdefault(field, None)
        started_at = state.get("started_at")
        if started_at and started_at > cutoff:
            continue
        state["mrr_minor"] = _subscription_mrr_minor(state)
        state["valuation_policy_version"] = MRR_POLICY_VERSION
        state["last_event_available_at"] = max(
            row["parent_source_available_at"] or row["parent_received_at"] for row in history
        )
        if "billing_valuation" not in principal.authorized_purposes:
            for field in (
                "billing_interval", "billing_interval_count", "amount_minor", "discount_minor", "currency",
                "mrr_minor", "valuation_policy_version",
            ):
                state.pop(field, None)
        subscriptions.append(state)
    subscriptions.sort(key=lambda value: value["subscription_id"])
    return subscriptions


def _account_valuation(subscriptions: list[dict[str, Any]]) -> dict[str, Any]:
    active = [row for row in subscriptions if row.get("status") in ACTIVE_ENTITLEMENT_STATUSES]
    if not active:
        return {
            "mrr_minor": None, "currency": None, "valuation_as_of": None,
            "valuation_policy_version": MRR_POLICY_VERSION, "status": "no_active_subscriptions",
        }
    if any(row.get("started_at") is None for row in active):
        return {
            "mrr_minor": None, "currency": None, "valuation_as_of": None,
            "valuation_policy_version": MRR_POLICY_VERSION, "status": "missing_subscription_state",
        }
    currencies = {row.get("currency") for row in active if row.get("currency") is not None}
    if len(currencies) > 1:
        return {
            "mrr_minor": None, "currency": None, "valuation_as_of": None,
            "valuation_policy_version": MRR_POLICY_VERSION, "status": "mixed_currency",
        }
    currency = next(iter(currencies), None)
    if any(row.get("mrr_minor") is None or row.get("currency") is None for row in active):
        return {
            "mrr_minor": None, "currency": currency, "valuation_as_of": None,
            "valuation_policy_version": MRR_POLICY_VERSION, "status": "missing_price",
        }
    return {
        "mrr_minor": sum(row["mrr_minor"] for row in active), "currency": currency,
        "valuation_as_of": None, "valuation_policy_version": MRR_POLICY_VERSION, "status": "available",
    }


def get_account_snapshot_as_of(
    path: str | Path,
    principal: ReadPrincipal,
    customer_id: str,
    as_of: str,
) -> dict[str, Any]:
    customer_id = _validate_id(customer_id)
    cutoff = normalize_timestamp(as_of)
    with _db(path) as connection:
        authorized_sources = _assert_read_principal(connection, principal)
        _require_purposes(principal, "retention_inference")
        source_placeholders = ",".join("?" for _ in authorized_sources)
        customer = connection.execute(
            "SELECT 1 FROM customer_identities WHERE tenant_id = ? AND customer_id = ? "
            f"AND source IN ({source_placeholders}) LIMIT 1",
            (principal.tenant_id, customer_id, *authorized_sources),
        ).fetchone()
    if customer is None:
        raise DataFoundationError("not_found")
    events = get_events_as_of(path, principal, customer_id, cutoff)
    subscriptions = get_subscriptions_as_of(path, principal, customer_id, cutoff)
    active = [
        row for row in subscriptions
        if row.get("status") in ACTIVE_ENTITLEMENT_STATUSES
        and row.get("started_at") is not None and row["started_at"] <= cutoff
    ]
    has_known_cancel = bool(active) and all(
        row.get("status") == "pending_cancel" or row.get("cancellation_requested_at") is not None
        for row in active
    )
    # `customers.account_status` has no effective timestamp. Historical eligibility is
    # therefore reconstructed exclusively from dated, source-backed subscription state.
    if not active:
        status = "not_eligible"
    elif has_known_cancel:
        status = "known_cancellation"
    else:
        status = "eligible"
    valuation = None
    if "billing_valuation" in principal.authorized_purposes:
        valuation = _account_valuation(subscriptions)
        valuation["valuation_as_of"] = cutoff if valuation["status"] == "available" else None
    availability = [event["available_at"] for event in events]
    return {
        "tenant_id": principal.tenant_id,
        "customer_id": customer_id,
        "as_of": cutoff,
        "status": status,
        "eligible": status == "eligible",
        "subscriptions": subscriptions,
        "usage_events": [event for event in events if event["category"] == "usage"],
        "billing_events": [event for event in events if event["category"] == "billing"],
        "valuation": valuation,
        "input_data_as_of": max(availability) if availability else None,
    }


def list_eligible_accounts_as_of(
    path: str | Path,
    principal: ReadPrincipal,
    as_of: str,
) -> list[dict[str, Any]]:
    """Enumerate active accounts, including silent accounts, at a trusted cutoff."""
    cutoff = normalize_timestamp(as_of)
    with _db(path) as connection:
        authorized_sources = _assert_read_principal(connection, principal)
        _require_purposes(principal, "retention_inference")
        source_placeholders = ",".join("?" for _ in authorized_sources)
        customers = connection.execute(
            "SELECT DISTINCT customer_id FROM customer_identities "
            f"WHERE tenant_id = ? AND source IN ({source_placeholders}) "
            "ORDER BY customer_id",
            (principal.tenant_id, *authorized_sources),
        ).fetchall()
    snapshots = [
        get_account_snapshot_as_of(path, principal, row["customer_id"], cutoff)
        for row in customers
    ]
    return [snapshot for snapshot in snapshots if snapshot["eligible"]]


def _assert_customer(connection: sqlite3.Connection, principal: ReadPrincipal, customer_id: str) -> None:
    authorized_sources = _assert_read_principal(connection, principal)
    if isinstance(principal, ServicePrincipal):
        if principal.role != "analyst":
            raise DataFoundationError("unauthorized")
        _require_purposes(principal, "retention_inference", "model_artifact_write")
    else:
        _require_purposes(principal, "retention_inference")
    source_placeholders = ",".join("?" for _ in authorized_sources)
    row = connection.execute(
        "SELECT 1 FROM customer_identities WHERE tenant_id = ? AND customer_id = "
        f"? AND source IN ({source_placeholders}) LIMIT 1",
        (principal.tenant_id, customer_id, *authorized_sources),
    ).fetchone()
    if row is None:
        raise DataFoundationError("not_found")


def _has_sensitive_category_value(value: str) -> bool:
    folded = value.casefold()
    if (EMAIL_VALUE_PATTERN.search(value) or SENSITIVE_VALUE_PATTERN.search(value)
            or any(marker in folded for marker in SENSITIVE_CATEGORY_MARKERS)):
        return True
    # Categorical fields are identifiers, never numeric measurements. Count digits
    # after removing punctuation so separators cannot disguise a card or phone value.
    # Rejecting long digit-bearing categories also avoids storing account/contact IDs.
    digits = "".join(character for character in value if character.isdigit())
    return len(digits) >= 7


def _looks_like_payment_card_number(value: int) -> bool:
    digits = str(abs(value))
    if len(digits) not in range(13, 20):
        return False
    total = 0
    parity = len(digits) % 2
    for index, character in enumerate(digits):
        digit = int(character)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _check_feature_tree(
    value: Any,
    *,
    allow_billing: bool = False,
    field_name: str | None = None,
    depth: int = 0,
    nodes: list[int] | None = None,
) -> None:
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    if nodes[0] > 2048 or depth > 8:
        raise DataFoundationError("invalid_contract")
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or not SAFE_CATEGORY_PATTERN.fullmatch(key):
                raise DataFoundationError("invalid_contract")
            normalized_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).casefold()
            if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
                raise DataFoundationError("invalid_contract")
            financial_key = re.sub(r"[^a-z0-9]+", "_", normalized_key).strip("_")
            if not allow_billing and any(
                f"_{part}_" in f"_{financial_key}_" for part in FINANCIAL_KEY_PARTS
            ):
                raise DataFoundationError("invalid_contract")
            _check_feature_tree(
                nested, allow_billing=allow_billing, field_name=normalized_key,
                depth=depth + 1, nodes=nodes,
            )
    elif isinstance(value, list):
        for nested in value:
            _check_feature_tree(
                nested, allow_billing=allow_billing, field_name=field_name,
                depth=depth + 1, nodes=nodes,
            )
    elif isinstance(value, str):
        if (field_name is None
                or not (field_name in SAFE_CATEGORICAL_FIELDS
                        or any(field_name.endswith(suffix) for suffix in SAFE_CATEGORY_SUFFIXES))
                or not SAFE_CATEGORY_PATTERN.fullmatch(value)
                or _has_sensitive_category_value(value)):
            raise DataFoundationError("invalid_contract")
        if field_name in {"status", "subscription_status"} and value not in SUBSCRIPTION_STATUSES | {"unknown"}:
            raise DataFoundationError("invalid_contract")
        if field_name == "payment_status" and value not in {"failed", "succeeded", "unknown"}:
            raise DataFoundationError("invalid_contract")
        if field_name in {"tier", "plan_tier"} and value.casefold() not in SAFE_TIER_VALUES:
            raise DataFoundationError("invalid_contract")
        if field_name == "event_type" and value not in EVENT_TYPES:
            raise DataFoundationError("invalid_contract")
        if field_name == "billing_interval" and value not in INTERVALS:
            raise DataFoundationError("invalid_contract")
        if field_name == "currency" and value not in ISO4217_CURRENT_CODES:
            raise DataFoundationError("invalid_contract")
        if field_name == "reliability_status" and value not in RELIABILITY_STATUSES:
            raise DataFoundationError("invalid_contract")
        if field_name == "data_freshness_status" and value not in FRESHNESS_STATUSES:
            raise DataFoundationError("invalid_contract")
        if field_name == "data_quality_status" and value not in {"available", "limited", "insufficient", "unknown"}:
            raise DataFoundationError("invalid_contract")
        if field_name == "reason_code" and value not in SAFE_RELIABILITY_REASON_CODES:
            raise DataFoundationError("invalid_contract")
        if field_name == "direction" and value not in {"positive", "negative", "increasing", "decreasing"}:
            raise DataFoundationError("invalid_contract")
        if field_name == "trend" and value not in {"increasing", "decreasing", "stable", "flat", "unknown"}:
            raise DataFoundationError("invalid_contract")
    elif value is None or isinstance(value, bool):
        return
    elif isinstance(value, int):
        if _looks_like_payment_card_number(value):
            raise DataFoundationError("invalid_contract")
        return
    elif isinstance(value, float) and math.isfinite(value):
        if value.is_integer() and _looks_like_payment_card_number(int(value)):
            raise DataFoundationError("invalid_contract")
        return
    else:
        raise DataFoundationError("invalid_contract")


def _check_reliability_reasons(reasons: Any) -> None:
    if not isinstance(reasons, list):
        raise DataFoundationError("invalid_contract")
    for reason in reasons:
        if not isinstance(reason, str) or reason not in SAFE_RELIABILITY_REASON_CODES:
            raise DataFoundationError("invalid_contract")


def store_feature_snapshot(
    path: str | Path,
    principal: ReadPrincipal,
    customer_id: str,
    as_of: str,
    feature_version: str,
    data_cutoff_at: str,
    features: dict[str, Any],
    data_quality_status: str,
) -> str:
    customer_id = _validate_id(customer_id)
    as_of = normalize_timestamp(as_of)
    data_cutoff_at = normalize_timestamp(data_cutoff_at)
    feature_version = _validate_id(feature_version)
    if data_cutoff_at > as_of or data_quality_status not in {"available", "limited", "insufficient", "unknown"}:
        raise DataFoundationError("invalid_contract")
    if not isinstance(features, dict):
        raise DataFoundationError("invalid_contract")
    _check_feature_tree(
        features,
        allow_billing="billing_valuation" in principal.authorized_purposes,
    )
    # This identifier is passed back through the canonical ID validator when a
    # prediction links to its feature snapshot. token_urlsafe may contain an
    # underscore, which the canonical ID alphabet intentionally excludes.
    feature_snapshot_id = secrets.token_hex(18)
    encoded = json.dumps(features, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with _db(path) as connection:
        _assert_customer(connection, principal, customer_id)
        try:
            connection.execute(
                "INSERT INTO feature_snapshots(feature_snapshot_id, tenant_id, customer_id, as_of, feature_version, "
                "data_cutoff_at, features_json, data_quality_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (feature_snapshot_id, principal.tenant_id, customer_id, as_of, feature_version,
                 data_cutoff_at, encoded, data_quality_status),
            )
        except sqlite3.IntegrityError:
            raise DataFoundationError("contract_conflict") from None
    return feature_snapshot_id


def store_churn_label(
    path: str | Path,
    principal: ReadPrincipal,
    customer_id: str,
    as_of: str,
    horizon_days: int,
    label: str | int,
    label_observed_through: str,
    label_policy_version: str,
    *,
    churn_type: str | None = None,
    outcome_at: str | None = None,
) -> None:
    customer_id = _validate_id(customer_id)
    as_of = normalize_timestamp(as_of)
    observed = normalize_timestamp(label_observed_through)
    label_policy_version = _validate_id(label_policy_version)
    if isinstance(horizon_days, bool) or horizon_days not in {7, 14, 30}:
        raise DataFoundationError("invalid_contract")
    if isinstance(label, bool):
        raise DataFoundationError("invalid_contract")
    if isinstance(label, int) and label in (0, 1):
        normalized_label = str(label)
    elif isinstance(label, str) and label in {"0", "1", "unknown"}:
        normalized_label = label
    else:
        raise DataFoundationError("invalid_contract")
    if churn_type is not None:
        churn_type = _validate_slug(churn_type)
    normalized_outcome = normalize_timestamp(outcome_at) if outcome_at is not None else None
    as_of_dt = datetime.fromisoformat(as_of[:-1] + "+00:00")
    observed_dt = datetime.fromisoformat(observed[:-1] + "+00:00")
    end_dt = as_of_dt + timedelta(days=horizon_days)
    if normalized_label == "1":
        if normalized_outcome is None:
            raise DataFoundationError("invalid_contract")
        outcome_dt = datetime.fromisoformat(normalized_outcome[:-1] + "+00:00")
        if not (as_of_dt < outcome_dt <= end_dt) or outcome_dt > observed_dt:
            raise DataFoundationError("invalid_contract")
    elif normalized_label == "0" and observed_dt < end_dt:
        raise DataFoundationError("invalid_contract")
    elif normalized_label == "unknown" and normalized_outcome is not None:
        raise DataFoundationError("invalid_contract")
    with _db(path) as connection:
        _assert_customer(connection, principal, customer_id)
        try:
            connection.execute(
                "INSERT INTO churn_labels(tenant_id, customer_id, as_of, horizon_days, label, churn_type, outcome_at, "
                "label_observed_through, label_policy_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (principal.tenant_id, customer_id, as_of, horizon_days, normalized_label,
                 churn_type, normalized_outcome, observed, label_policy_version),
            )
        except sqlite3.IntegrityError:
            raise DataFoundationError("contract_conflict") from None


def store_prediction(
    path: str | Path,
    principal: ReadPrincipal,
    prediction: dict[str, Any],
) -> str:
    required = {
        "prediction_id", "prediction_run_id", "customer_id", "as_of", "generated_at", "status",
        "p_churn_7d", "p_churn_14d", "p_churn_30d", "feature_version", "model_version",
        "calibration_version", "reliability_status", "data_freshness_status",
    }
    if not isinstance(prediction, dict) or not required.issubset(prediction):
        raise DataFoundationError("invalid_contract")
    prediction_id = _validate_id(prediction["prediction_id"])
    run_id = _validate_id(prediction["prediction_run_id"])
    customer_id = _validate_id(prediction["customer_id"])
    as_of = normalize_timestamp(prediction["as_of"])
    generated_at = normalize_timestamp(prediction["generated_at"])
    status = prediction["status"]
    reliability = prediction["reliability_status"]
    freshness = prediction["data_freshness_status"]
    if status not in PREDICTION_STATUSES or reliability not in RELIABILITY_STATUSES or freshness not in FRESHNESS_STATUSES:
        raise DataFoundationError("invalid_contract")
    probabilities = [prediction[f"p_churn_{horizon}d"] for horizon in (7, 14, 30)]
    if status == "scored":
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in probabilities):
            raise DataFoundationError("invalid_contract")
        if not (0 <= probabilities[0] <= probabilities[1] <= probabilities[2] <= 1):
            raise DataFoundationError("invalid_contract")
    elif any(value is not None for value in probabilities):
        raise DataFoundationError("invalid_contract")
    feature_version = _validate_id(prediction["feature_version"])
    model_version = _validate_id(prediction["model_version"])
    calibration_version = _validate_id(prediction["calibration_version"])
    label_policy = prediction.get("label_policy_version")
    label_policy = _validate_id(label_policy) if label_policy is not None else None
    reasons = prediction.get("reliability_reasons", [])
    explanations = prediction.get("explanations_by_horizon", {})
    _check_reliability_reasons(reasons)
    if not isinstance(explanations, dict):
        raise DataFoundationError("invalid_contract")
    _check_feature_tree(
        explanations,
        allow_billing="billing_valuation" in principal.authorized_purposes,
    )
    input_data_as_of = prediction.get("input_data_as_of")
    input_data_as_of = normalize_timestamp(input_data_as_of) if input_data_as_of is not None else None
    if input_data_as_of is not None and input_data_as_of > as_of:
        raise DataFoundationError("invalid_contract")
    feature_snapshot_id = prediction.get("feature_snapshot_id")
    if feature_snapshot_id is not None:
        feature_snapshot_id = _validate_id(feature_snapshot_id)
    with _db(path) as connection:
        _assert_customer(connection, principal, customer_id)
        if feature_snapshot_id is not None:
            snapshot = connection.execute(
                "SELECT customer_id, as_of, feature_version FROM feature_snapshots "
                "WHERE tenant_id = ? AND feature_snapshot_id = ?",
                (principal.tenant_id, feature_snapshot_id),
            ).fetchone()
            if (snapshot is None or snapshot["customer_id"] != customer_id
                    or snapshot["as_of"] != as_of or snapshot["feature_version"] != feature_version):
                raise DataFoundationError("invalid_contract")
        try:
            connection.execute(
                "INSERT INTO predictions(tenant_id, prediction_id, prediction_run_id, customer_id, as_of, generated_at, "
                "status, p_churn_7d, p_churn_14d, p_churn_30d, feature_snapshot_id, feature_version, model_version, "
                "calibration_version, label_policy_version, reliability_status, reliability_reasons_json, "
                "data_freshness_status, input_data_as_of, explanations_by_horizon_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (principal.tenant_id, prediction_id, run_id, customer_id, as_of, generated_at, status,
                 *probabilities, feature_snapshot_id, feature_version, model_version, calibration_version,
                 label_policy, reliability, json.dumps(reasons, separators=(",", ":")), freshness,
                 input_data_as_of, json.dumps(explanations, separators=(",", ":"), allow_nan=False)),
            )
        except sqlite3.IntegrityError:
            raise DataFoundationError("contract_conflict") from None
    return prediction_id


def get_integration_health(
    path: str | Path,
    principal: IntegrationPrincipal,
) -> list[dict[str, Any]]:
    with _db(path) as connection:
        _assert_principal(connection, principal)
        rows = connection.execute(
        "SELECT tenant_id, source, authorized_purposes_json, schema_version, mapping_version, created_at, "
            "last_successful_ingestion_at, last_failure_at, last_failure_code "
            "FROM integrations WHERE tenant_id = ? AND integration_id = ? ORDER BY source",
            (principal.tenant_id, principal.integration_id),
        ).fetchall()
    result = []
    for row in rows:
        success = row["last_successful_ingestion_at"]
        failure = row["last_failure_at"]
        if not success and not failure:
            state = "unknown"
        elif failure and (not success or failure > success):
            state = "degraded"
        else:
            state = "observed"
        result.append({
            "tenant_id": row["tenant_id"], "source": row["source"],
            "schema_version": row["schema_version"], "mapping_version": row["mapping_version"],
            "authorized_purposes": json.loads(row["authorized_purposes_json"]),
            "last_successful_ingestion_at": success, "last_failure_at": failure,
            "last_failure_code": row["last_failure_code"], "availability_status": state,
            "freshness_status": "unknown",
        })
    return result


def get_tenant_integration_health(
    path: str | Path,
    principal: ServicePrincipal,
) -> list[dict[str, Any]]:
    """Return health only for exact sources granted to an internal Admin/Operator."""
    if not isinstance(principal, ServicePrincipal) or principal.role not in {"admin", "operator"}:
        raise DataFoundationError("unauthorized")
    _require_purposes(principal, "integration_health")
    with _db(path) as connection:
        _assert_service_principal(connection, principal)
        placeholders = ",".join("?" for _ in principal.authorized_sources)
        rows = connection.execute(
            "SELECT tenant_id, source, authorized_purposes_json, schema_version, mapping_version, created_at, "
            "last_successful_ingestion_at, last_failure_at, last_failure_code "
            f"FROM integrations WHERE tenant_id = ? AND source IN ({placeholders}) ORDER BY source",
            (principal.tenant_id, *principal.authorized_sources),
        ).fetchall()
    result = []
    for row in rows:
        success = row["last_successful_ingestion_at"]
        failure = row["last_failure_at"]
        if not success and not failure:
            state = "unknown"
        elif failure and (not success or failure > success):
            state = "degraded"
        else:
            state = "observed"
        result.append({
            "tenant_id": row["tenant_id"], "source": row["source"],
            "schema_version": row["schema_version"], "mapping_version": row["mapping_version"],
            "authorized_purposes": json.loads(row["authorized_purposes_json"]),
            "last_successful_ingestion_at": success, "last_failure_at": failure,
            "last_failure_code": row["last_failure_code"], "availability_status": state,
            "freshness_status": "unknown",
        })
    return result
