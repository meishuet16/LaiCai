"""Streaming stochastic SaaS lifecycle generator.

Latent account state is held only while an account is generated. It is never
written to the dataset. Observable outcomes are expressed as canonical events.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import shutil
from collections import Counter
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import SyntheticConfig


TENANT_ARCHETYPES = (
    ("analytics", "B2B Analytics SaaS", 1.00, 0.75),
    ("projects", "Project Management SaaS", 1.15, 0.90),
    ("developer", "Developer SaaS", 0.80, 1.45),
    ("productivity", "Business Productivity SaaS", 0.90, 1.10),
)
PLAN_TIERS = (
    ("starter", 2900), ("standard", 7900), ("growth", 15900),
    ("business", 34900), ("enterprise", 89900),
)
CURRENCIES = ("MYR", "USD", "SGD")
FEATURES = ("dashboard", "reports", "automation", "api", "collaboration", "integrations")
SEGMENTS = ("startup", "small_business", "mid_market", "enterprise")
INDUSTRIES = ("technology", "services", "commerce", "education", "finance")
REGIONS = ("apac", "north_america", "europe")
CHANNELS = ("organic", "partner", "paid", "referral", "sales")

CUSTOMER_FIELDS = (
    "tenant_id", "customer_id", "account_created_at", "customer_segment",
    "company_size_category", "industry_category", "region_category",
    "acquisition_channel", "onboarding_cohort", "initial_plan_tier",
    "simulated_account_type", "dataset_type",
)
IDENTITY_FIELDS = ("tenant_id", "customer_id", "source", "source_category", "external_customer_id")
PLAN_FIELDS = (
    "tenant_id", "plan_id", "plan_tier", "billing_interval", "billing_interval_count",
    "amount_minor", "currency", "effective_at", "entitlements_json",
)
EVENT_FIELDS = (
    "tenant_id", "source", "source_category", "source_event_id", "external_customer_id",
    "customer_id", "event_type", "occurred_at", "source_available_at", "received_at",
    "attributes_json", "schema_version",
)
COVERAGE_FIELDS = (
    "tenant_id", "source", "source_category", "scope_type", "scope_id", "period_start",
    "period_end", "coverage_status", "coverage_completeness", "last_trustworthy_observed_at",
    "supports_verified_negative",
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _at_noon(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, 12, tzinfo=timezone.utc)


def _month_starts(start: date, end: date) -> Iterator[date]:
    current = date(start.year, start.month, 1)
    while current <= end:
        yield current
        current = date(current.year + (current.month == 12), 1 if current.month == 12 else current.month + 1, 1)


def _next_month(value: date) -> date:
    return date(value.year + (value.month == 12), 1 if value.month == 12 else value.month + 1, 1)


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))


def _account_rng(seed: int, tenant_id: str, index: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{tenant_id}|{index}".encode("ascii")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _dataset_id(config: SyntheticConfig) -> str:
    encoded = json.dumps(config.stable_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"synthetic-saas-v1-{config.profile}-s{config.seed}-{hashlib.sha256(encoded).hexdigest()[:12]}"


def _sources(tenant_id: str) -> dict[str, str]:
    return {category: f"{tenant_id}-synthetic-{category}-v1" for category in ("usage", "billing", "subscription")}


class _EventWriter:
    def __init__(self, writers: dict[str, csv.DictWriter], counts: Counter[str]):
        self.writers = writers
        self.counts = counts

    def write(
        self, *, tenant_id: str, category: str, source: str, event_id: str,
        external_customer_id: str, customer_id: str, event_type: str,
        occurred_at: datetime, attributes: dict[str, Any], rng: random.Random,
        late: bool = False,
    ) -> None:
        availability_delay = rng.randint(35, 45) if late else rng.choice((0, 0, 0, 1, 1, 2))
        available = occurred_at + timedelta(days=availability_delay, minutes=rng.randint(0, 180))
        received = available + timedelta(minutes=rng.randint(0, 240))
        row = {
            "tenant_id": tenant_id,
            "source": source,
            "source_category": category,
            "source_event_id": event_id,
            "external_customer_id": external_customer_id,
            "customer_id": customer_id,
            "event_type": event_type,
            "occurred_at": _iso(occurred_at),
            "source_available_at": _iso(available),
            "received_at": _iso(received),
            "attributes_json": json.dumps(attributes, sort_keys=True, separators=(",", ":")),
            "schema_version": "1.0",
        }
        self.writers[category].writerow(row)
        self.writers["canonical"].writerow(row)
        self.counts[f"{category}_events"] += 1
        self.counts["canonical_events"] += 1
        if late:
            self.counts["late_arriving_events"] += 1


def _open_csv(stack: ExitStack, path: Path, fields: tuple[str, ...]) -> csv.DictWriter:
    stream = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    return writer


def _plan_catalog(tenant_ids: list[str], start: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    intervals = (("month", 1), ("quarter", 1), ("year", 1))
    for tenant_index, tenant_id in enumerate(tenant_ids):
        currency = CURRENCIES[tenant_index % len(CURRENCIES)]
        for tier_index, (tier, monthly_minor) in enumerate(PLAN_TIERS):
            interval, count = intervals[(tenant_index + tier_index) % len(intervals)]
            multiplier = {"month": 1, "quarter": 3, "year": 12}[interval]
            discount_factor = {"month": 1.0, "quarter": 0.96, "year": 0.86}[interval]
            rows.append({
                "tenant_id": tenant_id,
                "plan_id": f"{tenant_id}-{tier}-{interval}-v1",
                "plan_tier": tier,
                "billing_interval": interval,
                "billing_interval_count": count,
                "amount_minor": round(monthly_minor * multiplier * discount_factor),
                "currency": currency,
                "effective_at": _iso(_at_noon(start)),
                "entitlements_json": json.dumps({"feature_bundle": tier}, separators=(",", ":")),
            })
    return rows


def _write_label_fixtures(path: Path) -> None:
    payload = {
        "policy": "effective-account-churn-v1",
        "disclosure": "Independent synthetic oracle fixtures; not production labels or model features.",
        "fixtures": [
            {"case": "churn_day_5", "labels": {"7": "1", "14": "1", "30": "1"}},
            {"case": "churn_day_10", "labels": {"7": "0", "14": "1", "30": "1"}},
            {"case": "churn_day_20", "labels": {"7": "0", "14": "0", "30": "1"}},
            {"case": "retained_30d", "labels": {"7": "0", "14": "0", "30": "0"}},
            {"case": "censored_day_10", "labels": {"7": "0", "14": "unknown", "30": "unknown"}},
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_adversarial_fixtures(path: Path) -> None:
    payload = {
        "dataset_type": "synthetic_adversarial_test_fixtures",
        "must_remain_separate_from_valid_population": True,
        "fixtures": [
            {"case": "invalid_tenant_context", "expected_error": "unauthorized"},
            {"case": "unknown_source", "expected_error": "source_not_authorized"},
            {"case": "unauthorized_event_category", "expected_error": "event_category_not_authorized"},
            {"case": "duplicate_event_key", "expected_result": "duplicate"},
            {"case": "conflicting_duplicate_payload", "expected_error": "idempotency_conflict"},
            {"case": "subscription_owner_conflict", "expected_error": "contract_conflict"},
            {"case": "unsupported_event_type", "expected_error": "invalid_event"},
            {"case": "invalid_date", "expected_error": "invalid_event"},
            {"case": "invalid_currency", "expected_error": "invalid_event"},
            {"case": "negative_payment_amount", "expected_error": "invalid_event"},
            {"case": "forbidden_sensitive_field", "expected_error": "invalid_event"},
            {"case": "event_after_cutoff", "expected_result": "excluded_from_as_of_read"},
            {"case": "restricted_model_write", "expected_error": "purpose_not_authorized"}
        ]
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_documentation(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)
    documents = {
        "data_dictionary.md": """# Synthetic SaaS data dictionary

All timestamps are UTC ISO 8601 values. Money uses integer minor units with an ISO 4217 currency.

- `customers.csv`: one synthetic paying account per row.
- `customer_identities.csv`: exact tenant/source external-to-canonical identity maps.
- `plan_catalog.csv`: tenant-scoped, dated plan definitions.
- `*_events.csv`: category-specific canonical import rows.
- `canonical_events.csv`: the union used by the synthetic canonical adapter.
- `observation_coverage.csv`: source periods; only `complete` periods support verified negatives.
- `label_oracle_fixtures.json`: isolated label-policy examples, never training rows.
- `adversarial_fixtures.json`: rejection expectations, never valid population rows.
""",
        "generation_methodology.md": """# Generation methodology

The generator derives a stable random stream per account from the configured seed. Private latent engagement, volatility, product fit, billing reliability, price sensitivity, seasonality, recovery, and renewal tendencies evolve through a stochastic monthly process. A discrete-time hazard combines current state and random shocks. Only observable canonical lifecycle events are exported; latent factors and hazards are discarded.
""",
        "synthetic_label_policy.md": """# Synthetic label policy

The lifecycle ledger is authoritative. Effective loss of the final paid entitlement is account churn. A request is known cancellation and a payment failure alone is not churn. For cutoff `t`, positives occur only when effective account churn is in `(t,t+h]`; negatives need complete coverage through `t+h`; otherwise the label is `unknown`. Member 2 owns production materialization.
""",
        "dataset_isolation.md": """# Dataset isolation

This family is `synthetic_saas` and carries `SYNTHETIC SAAS DEMO` provenance. It has its own dataset ID, target policy, split proposal, source namespaces, and future model artifact namespace. KKBox records, targets, metrics, and model artifacts must never be pooled with it.
""",
        "reproduction_instructions.md": """# Reproduction

Run `python -m retaniq.synthetic generate --profile <quick|standard|full> --seed 2026`. Use the same configuration and seed in a new output root to reproduce logical file hashes. Run `validate`, then use `import --db <new.sqlite3> --verify-idempotency` to exercise canonical ingestion.
""",
    }
    for name, content in documents.items():
        (path / name).write_text(content.strip() + "\n", encoding="utf-8")


def generate_dataset(config: SyntheticConfig, output_root: Path | str) -> dict[str, Any]:
    """Generate a linked dataset family using bounded per-account state."""
    config.validate()
    root = Path(output_root).expanduser().resolve()
    dataset_id = _dataset_id(config)
    profile_root = root / config.profile
    destination = profile_root / dataset_id
    staging = profile_root / f".{dataset_id}.staging-{os.getpid()}"
    if destination.exists():
        raise FileExistsError(f"dataset already exists: {destination}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=False)

    start = date.fromisoformat(config.start_date)
    end = date.fromisoformat(config.end_date)
    months = list(_month_starts(start, end))
    tenant_ids = [f"tenant-{index + 1:02d}" for index in range(config.tenant_count)]
    plans = _plan_catalog(tenant_ids, start)
    plans_by_tenant: dict[str, list[dict[str, Any]]] = {
        tenant_id: [row for row in plans if row["tenant_id"] == tenant_id] for tenant_id in tenant_ids
    }
    counts: Counter[str] = Counter()
    scenarios: Counter[str] = Counter()
    tenant_counts: Counter[str] = Counter()
    plan_counts: Counter[str] = Counter()
    interval_counts: Counter[str] = Counter()
    churn_types: Counter[str] = Counter()

    try:
        with ExitStack() as stack:
            writers = {
                "customers": _open_csv(stack, staging / "customers.csv", CUSTOMER_FIELDS),
                "identities": _open_csv(stack, staging / "customer_identities.csv", IDENTITY_FIELDS),
                "plans": _open_csv(stack, staging / "plan_catalog.csv", PLAN_FIELDS),
                "subscription": _open_csv(stack, staging / "subscription_events.csv", EVENT_FIELDS),
                "billing": _open_csv(stack, staging / "billing_events.csv", EVENT_FIELDS),
                "usage": _open_csv(stack, staging / "usage_events.csv", EVENT_FIELDS),
                "canonical": _open_csv(stack, staging / "canonical_events.csv", EVENT_FIELDS),
                "coverage": _open_csv(stack, staging / "observation_coverage.csv", COVERAGE_FIELDS),
            }
            for plan in plans:
                writers["plans"].writerow(plan)
            counts["plans"] = len(plans)
            event_writer = _EventWriter(writers, counts)

            for tenant_index, tenant_id in enumerate(tenant_ids):
                archetype = TENANT_ARCHETYPES[tenant_index % len(TENANT_ARCHETYPES)]
                source_map = _sources(tenant_id)
                coverage_rng = _account_rng(config.seed, tenant_id, -1)
                outage_periods: set[tuple[str, str]] = set()
                for month in months:
                    period_end = min(end, _next_month(month) - timedelta(days=1))
                    for category, source in source_map.items():
                        outage = coverage_rng.random() < config.source_outage_frequency
                        completeness = 0.0 if outage else round(coverage_rng.uniform(0.82, 1.0), 3)
                        status = "outage" if outage else ("partial" if completeness < 0.95 else "complete")
                        observed = _at_noon(period_end) if not outage else _at_noon(month) - timedelta(seconds=1)
                        writers["coverage"].writerow({
                            "tenant_id": tenant_id, "source": source, "source_category": category,
                            "scope_type": "tenant", "scope_id": tenant_id,
                            "period_start": _iso(_at_noon(month)), "period_end": _iso(_at_noon(period_end)),
                            "coverage_status": status, "coverage_completeness": completeness,
                            "last_trustworthy_observed_at": _iso(observed),
                            "supports_verified_negative": "true" if status == "complete" else "false",
                        })
                        counts["observation_coverage"] += 1
                        if outage:
                            outage_periods.add((category, month.strftime("%Y%m")))
                            scenarios[f"{category}_source_outage"] += 1

                def source_is_out(category: str, occurred_at: datetime) -> bool:
                    return (category, occurred_at.strftime("%Y%m")) in outage_periods

                account_indexes = range(tenant_index, config.account_count, config.tenant_count)
                for account_index in account_indexes:
                    rng = _account_rng(config.seed, tenant_id, account_index)
                    customer_id = f"{tenant_id}-customer-{account_index + 1:06d}"
                    total_days = max(0, (end - start).days)
                    if account_index % 20 == 0 and total_days > 45:
                        created_date = end - timedelta(days=rng.randint(0, 45))
                        scenarios["short_history"] += 1
                        scenarios["incomplete_outcome_observation"] += 1
                    else:
                        max_offset = max(0, min(total_days, int(total_days * 0.70)))
                        created_date = start + timedelta(days=rng.randint(0, max_offset))
                    created_at = _at_noon(created_date)
                    selected_plan = rng.choice(plans_by_tenant[tenant_id])
                    segment = rng.choices(SEGMENTS, weights=(30, 36, 25, 9))[0]
                    writers["customers"].writerow({
                        "tenant_id": tenant_id, "customer_id": customer_id,
                        "account_created_at": _iso(created_at), "customer_segment": segment,
                        "company_size_category": segment, "industry_category": rng.choice(INDUSTRIES),
                        "region_category": rng.choice(REGIONS), "acquisition_channel": rng.choice(CHANNELS),
                        "onboarding_cohort": created_date.strftime("%Y-%m"),
                        "initial_plan_tier": selected_plan["plan_tier"],
                        "simulated_account_type": archetype[1], "dataset_type": "synthetic_saas",
                    })
                    counts["customers"] += 1
                    tenant_counts[tenant_id] += 1
                    plan_counts[selected_plan["plan_tier"]] += 1
                    interval_counts[selected_plan["billing_interval"]] += 1
                    external_ids: dict[str, str] = {}
                    for category, source in source_map.items():
                        external = f"ext-{category}-{customer_id}"
                        external_ids[category] = external
                        writers["identities"].writerow({
                            "tenant_id": tenant_id, "customer_id": customer_id, "source": source,
                            "source_category": category, "external_customer_id": external,
                        })
                        counts["customer_identities"] += 1

                    baseline = rng.lognormvariate(math.log(6.0 * archetype[2]), 0.60)
                    volatility = rng.uniform(0.08, 0.65) * archetype[3]
                    price_sensitivity = rng.uniform(-0.8, 1.2)
                    billing_reliability = rng.uniform(0.55, 0.995)
                    product_fit = rng.uniform(-1.2, 1.4)
                    renewal_tendency = rng.uniform(-1.0, 1.2)
                    recovery_propensity = rng.uniform(0.25, 0.95)
                    seasonal_strength = rng.uniform(0.0, 0.55)
                    engagement = max(0.05, rng.lognormvariate(math.log(max(0.2, baseline)), 0.20))
                    multi_subscription = rng.random() < 0.08 and (end - created_date).days >= 45
                    missing_valuation = rng.random() < 0.025
                    sparse_telemetry = rng.random() < 0.06
                    if multi_subscription:
                        scenarios["multiple_subscriptions"] += 1
                    if missing_valuation:
                        scenarios["missing_mrr"] += 1
                    if sparse_telemetry:
                        scenarios["incomplete_telemetry"] += 1
                    if baseline < 4:
                        scenarios["long_stable_low_usage"] += 1
                    if product_fit > 0.45 and billing_reliability > 0.90:
                        scenarios["healthy_stable"] += 1
                    if seasonal_strength > 0.35:
                        scenarios["seasonal_usage"] += 1
                    if volatility > 0.55:
                        scenarios["volatile_usage"] += 1
                    if price_sensitivity > 0.70:
                        scenarios["price_sensitive"] += 1
                    if selected_plan["plan_tier"] in {"business", "enterprise"} and sparse_telemetry:
                        scenarios["high_value_limited_telemetry"] += 1

                    subscription_ids = [f"sub-{customer_id}-01"]
                    if multi_subscription:
                        subscription_ids.append(f"sub-{customer_id}-02")
                    active_subscriptions = set(subscription_ids)
                    for sub_index, subscription_id in enumerate(subscription_ids):
                        sub_start = created_at + timedelta(days=30 * sub_index)
                        amount = None if missing_valuation and sub_index == 0 else int(selected_plan["amount_minor"])
                        attrs: dict[str, Any] = {
                            "subscription_id": subscription_id, "status": "active",
                            "plan_id": selected_plan["plan_id"], "started_at": _iso(sub_start),
                            "current_period_end": _iso(sub_start + timedelta(days=30)),
                            "billing_interval": selected_plan["billing_interval"], "billing_interval_count": 1,
                        }
                        if amount is not None:
                            attrs.update(amount_minor=amount, discount_minor=0, currency=selected_plan["currency"])
                        event_writer.write(
                            tenant_id=tenant_id, category="subscription", source=source_map["subscription"],
                            event_id=f"evt-{customer_id}-sub-create-{sub_index + 1}",
                            external_customer_id=external_ids["subscription"], customer_id=customer_id,
                            event_type="subscription_created", occurred_at=sub_start, attributes=attrs, rng=rng,
                            late=source_is_out("subscription", sub_start),
                        )
                        counts["subscriptions"] += 1

                    failed_streak = 0
                    churned_at: datetime | None = None
                    last_month_engagement = engagement
                    eligible_months = [month for month in months if month >= date(created_date.year, created_date.month, 1)]
                    for month_index, month in enumerate(eligible_months):
                        event_time = _at_noon(month) + timedelta(days=min(14, rng.randint(0, 14)))
                        if event_time.date() < created_date:
                            event_time = created_at
                        if event_time.date() > end or not active_subscriptions:
                            break
                        seasonal = math.sin((month.month - 1) / 12 * 2 * math.pi) * seasonal_strength
                        external_shock = rng.gauss(0, 0.20)
                        if rng.random() < 0.035:
                            external_shock += rng.choice((-1.25, 1.15))
                        drift = rng.gauss(0, volatility) + seasonal + external_shock + 0.08 * product_fit
                        engagement = max(0.0, engagement * math.exp(drift * 0.18))
                        quantity = max(0, round(engagement * rng.uniform(0.65, 1.35) * config.usage_frequency))
                        if sparse_telemetry and rng.random() < 0.45:
                            quantity = 0
                        if quantity > 0 and rng.random() <= min(1.0, config.event_density):
                            event_writer.write(
                                tenant_id=tenant_id, category="usage", source=source_map["usage"],
                                event_id=f"evt-{customer_id}-usage-{month.strftime('%Y%m')}",
                                external_customer_id=external_ids["usage"], customer_id=customer_id,
                                event_type="usage_aggregate_updated", occurred_at=event_time,
                                attributes={"feature": rng.choice(FEATURES), "quantity": quantity, "unit": "sessions"},
                                rng=rng, late=source_is_out("usage", event_time) or rng.random() < 0.035,
                            )
                        if quantity >= max(12, baseline * 1.8):
                            scenarios["usage_burst"] += 1
                        if last_month_engagement > baseline * 0.9 and engagement < baseline * 0.55:
                            scenarios["strong_usage_decline"] += 1

                        due_every = {"month": 1, "quarter": 3, "year": 12}[selected_plan["billing_interval"]]
                        if month_index % due_every != 0:
                            last_month_engagement = engagement
                            continue
                        billing_failed = rng.random() > billing_reliability or rng.random() < config.billing_failure_frequency
                        primary_sub = sorted(active_subscriptions)[0]
                        amount = None if missing_valuation else int(selected_plan["amount_minor"])
                        billing_attrs: dict[str, Any] = {"subscription_id": primary_sub}
                        if amount is not None:
                            billing_attrs.update(amount_minor=amount, currency=selected_plan["currency"])
                        if billing_failed:
                            failed_streak += 1
                            scenarios["billing_failures"] += 1
                            event_writer.write(
                                tenant_id=tenant_id, category="billing", source=source_map["billing"],
                                event_id=f"evt-{customer_id}-bill-fail-{month.strftime('%Y%m')}",
                                external_customer_id=external_ids["billing"], customer_id=customer_id,
                                event_type="invoice_payment_failed", occurred_at=event_time + timedelta(hours=2),
                                attributes=billing_attrs, rng=rng,
                                late=source_is_out("billing", event_time),
                            )
                            if rng.random() < recovery_propensity:
                                failed_streak = 0
                                scenarios["payment_recovery"] += 1
                                event_writer.write(
                                    tenant_id=tenant_id, category="billing", source=source_map["billing"],
                                    event_id=f"evt-{customer_id}-bill-recover-{month.strftime('%Y%m')}",
                                    external_customer_id=external_ids["billing"], customer_id=customer_id,
                                    event_type="invoice_paid", occurred_at=event_time + timedelta(days=rng.randint(1, 6)),
                                    attributes=billing_attrs, rng=rng,
                                    late=source_is_out("billing", event_time),
                                )
                        else:
                            failed_streak = 0
                            event_writer.write(
                                tenant_id=tenant_id, category="billing", source=source_map["billing"],
                                event_id=f"evt-{customer_id}-bill-paid-{month.strftime('%Y%m')}",
                                external_customer_id=external_ids["billing"], customer_id=customer_id,
                                event_type="invoice_paid", occurred_at=event_time + timedelta(hours=2),
                                attributes=billing_attrs, rng=rng,
                                late=source_is_out("billing", event_time),
                            )

                        if month_index > 1 and rng.random() < 0.018:
                            new_plan = rng.choice(plans_by_tenant[tenant_id])
                            event_writer.write(
                                tenant_id=tenant_id, category="subscription", source=source_map["subscription"],
                                event_id=f"evt-{customer_id}-plan-{month.strftime('%Y%m')}",
                                external_customer_id=external_ids["subscription"], customer_id=customer_id,
                                event_type="subscription_updated", occurred_at=event_time + timedelta(days=1),
                                attributes={"subscription_id": primary_sub, "plan_id": new_plan["plan_id"],
                                            "amount_minor": int(new_plan["amount_minor"]), "discount_minor": 0,
                                            "currency": new_plan["currency"]}, rng=rng,
                                late=source_is_out("subscription", event_time),
                            )
                            scenarios["plan_changes"] += 1

                        tenure_months = month_index + 1
                        engagement_signal = math.log1p(engagement) - math.log1p(max(0.1, baseline))
                        hazard_logit = (
                            -4.0 - 0.45 * product_fit - 0.30 * renewal_tendency
                            - 0.65 * engagement_signal + 0.72 * failed_streak
                            + 0.22 * price_sensitivity + (0.28 if tenure_months < 4 else -0.12)
                            + rng.gauss(0, 0.85)
                        )
                        hazard = min(0.35, _sigmoid(hazard_logit) * config.churn_hazard_multiplier)
                        if month_index > 1 and rng.random() < hazard:
                            voluntary = failed_streak == 0 and rng.random() < 0.68
                            churn_type = "voluntary" if voluntary else ("involuntary" if failed_streak else "non_renewal")
                            effective_at = min(_at_noon(end), event_time + timedelta(days=rng.randint(5, 25)))
                            target_subscriptions = sorted(active_subscriptions)
                            if multi_subscription and rng.random() < 0.55:
                                target_subscriptions = target_subscriptions[:1]
                                scenarios["partial_subscription_termination"] += 1
                            if voluntary:
                                requested_at = max(event_time, effective_at - timedelta(days=rng.randint(2, 14)))
                                for sub_id in target_subscriptions:
                                    event_writer.write(
                                        tenant_id=tenant_id, category="subscription", source=source_map["subscription"],
                                        event_id=f"evt-{customer_id}-cancel-request-{sub_id[-2:]}-{month.strftime('%Y%m')}",
                                        external_customer_id=external_ids["subscription"], customer_id=customer_id,
                                        event_type="cancellation_requested", occurred_at=requested_at,
                                        attributes={"subscription_id": sub_id, "current_period_end": _iso(effective_at)}, rng=rng,
                                        late=source_is_out("subscription", requested_at),
                                    )
                                scenarios["known_cancellations"] += 1
                            effective_type = {
                                "voluntary": "subscription_cancelled_effective",
                                "non_renewal": "subscription_non_renewed_effective",
                                "involuntary": "subscription_involuntary_terminated",
                            }[churn_type]
                            for sub_id in target_subscriptions:
                                event_writer.write(
                                    tenant_id=tenant_id, category="subscription", source=source_map["subscription"],
                                    event_id=f"evt-{customer_id}-effective-{sub_id[-2:]}-{month.strftime('%Y%m')}",
                                    external_customer_id=external_ids["subscription"], customer_id=customer_id,
                                    event_type=effective_type, occurred_at=effective_at,
                                    attributes={"subscription_id": sub_id}, rng=rng,
                                    late=source_is_out("subscription", effective_at),
                                )
                                active_subscriptions.discard(sub_id)
                            if not active_subscriptions:
                                churned_at = effective_at
                                scenarios["effective_account_churn"] += 1
                                scenarios[f"effective_{churn_type}_churn"] += 1
                                churn_types[churn_type] += 1
                                if quantity > baseline * 1.15:
                                    scenarios["high_usage_before_churn"] += 1
                                break
                        elif engagement < baseline * 0.55:
                            scenarios["usage_decline_without_churn"] += 1
                        last_month_engagement = engagement

                    if churned_at and (end - churned_at.date()).days >= 45 and rng.random() < 0.12:
                        reactivation_at = churned_at + timedelta(days=rng.randint(30, 90))
                        if reactivation_at.date() <= end:
                            reactivation_sub = f"sub-{customer_id}-reactivated-01"
                            attrs = {
                                "subscription_id": reactivation_sub, "status": "active",
                                "plan_id": selected_plan["plan_id"], "started_at": _iso(reactivation_at),
                                "current_period_end": _iso(reactivation_at + timedelta(days=30)),
                                "billing_interval": selected_plan["billing_interval"], "billing_interval_count": 1,
                                "amount_minor": int(selected_plan["amount_minor"]), "discount_minor": 0,
                                "currency": selected_plan["currency"],
                            }
                            event_writer.write(
                                tenant_id=tenant_id, category="subscription", source=source_map["subscription"],
                                event_id=f"evt-{customer_id}-reactivation", external_customer_id=external_ids["subscription"],
                                customer_id=customer_id, event_type="subscription_created",
                                occurred_at=reactivation_at, attributes=attrs, rng=rng,
                                late=source_is_out("subscription", reactivation_at),
                            )
                            counts["subscriptions"] += 1
                            scenarios["reactivations"] += 1

            counts["tenants"] = len(tenant_ids)

        _write_label_fixtures(staging / "label_oracle_fixtures.json")
        _write_adversarial_fixtures(staging / "adversarial_fixtures.json")
        _write_documentation(staging / "documentation")
        scenarios["late_arriving_events"] = counts["late_arriving_events"]
        scenario_payload = {
            "overlap_allowed": True,
            "accounts_by_tenant": dict(sorted(tenant_counts.items())),
            "accounts_by_plan_tier": dict(sorted(plan_counts.items())),
            "accounts_by_billing_interval": dict(sorted(interval_counts.items())),
            "scenario_counts": dict(sorted(scenarios.items())),
            "churn_outcomes": dict(sorted(churn_types.items())),
            "event_volumes": {key: counts[key] for key in ("usage_events", "billing_events", "subscription_events")},
        }
        (staging / "scenario_coverage.json").write_text(
            json.dumps(scenario_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        quality = {
            "status": "PENDING_VALIDATION",
            "dataset_type": "synthetic_saas",
            "direct_target_fields_exported": False,
            "latent_state_exported": False,
            "right_censored_accounts": scenarios["incomplete_outcome_observation"],
            "notes": ["Label materialization remains owned by Member 2."],
        }
        (staging / "quality_report.json").write_text(
            json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        split_manifest = {
            "strategy": "chronological_cutoff_windows",
            "training": {"end": "2025-09-30", "label_maturity_through": "2025-10-30"},
            "development": {"start": "2025-10-01", "end": "2026-02-28", "embargo_days": 30},
            "calibration": {"start": "2026-03-01", "end": "2026-05-31", "embargo_days": 30},
            "untouched_test": {"start": "2026-06-01", "end": "2026-08-31", "mature_through": "2026-09-30"},
            "warning": "Adjust windows for overridden simulation dates; never randomly split account cutoffs.",
        }
        (staging / "split_manifest.json").write_text(
            json.dumps(split_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

        hash_targets = sorted(path for path in staging.rglob("*") if path.is_file() and path.name != "dataset_manifest.json")
        file_hashes = {path.relative_to(staging).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in hash_targets}
        file_sizes = {path.relative_to(staging).as_posix(): path.stat().st_size for path in hash_targets}
        manifest = {
            "dataset_id": dataset_id,
            "dataset_family": "retainiq_synthetic_saas",
            "dataset_version": "1.0.0",
            "dataset_type": "synthetic_saas",
            "target_policy_version": config.target_policy_version,
            "generator_code_version": config.generator_version,
            "random_seed": config.seed,
            "profile": config.profile,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "tenant_count": len(tenant_ids),
            "account_count": counts["customers"],
            "actual_counts": dict(sorted(counts.items())),
            "actual_scenario_coverage": dict(sorted(scenarios.items())),
            "actual_churn_outcomes": dict(sorted(churn_types.items())),
            "file_hashes": file_hashes,
            "file_sizes_bytes": file_sizes,
            "split_manifest_reference": "split_manifest.json",
            "synthetic_data_disclosure": "SYNTHETIC SAAS DEMO",
            "no_real_customer_data": True,
            "track": "synthetic_saas",
            "real_kkbox_benchmark_status": "NOT_VALIDATED",
            "configuration": config.stable_dict(),
        }
        (staging / "dataset_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        profile_root.mkdir(parents=True, exist_ok=True)
        staging.replace(destination)
        returned = dict(manifest)
        returned["dataset_path"] = str(destination)
        return returned
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
