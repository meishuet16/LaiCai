"""Source-backed stochastic generator for Synthetic SaaS v1.2."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import random
import shutil
from array import array
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path
from typing import Any

from .config import SyntheticConfig
from .generator import add_billing_period


TENANT_ARCHETYPES = (
    ("analytics", "B2B Analytics SaaS", 0.94, 0.72),
    ("projects", "Project Management SaaS", 1.08, 0.86),
    ("developer", "Developer SaaS", 0.78, 1.24),
    ("productivity", "Business Productivity SaaS", 1.00, 0.98),
)
PLAN_TIERS = (("starter", 2900), ("standard", 7900), ("growth", 15900), ("business", 34900), ("enterprise", 89900))
CURRENCIES = ("MYR", "USD", "SGD")
FEATURES = ("dashboard", "reports", "automation", "api", "collaboration", "integrations")
SEGMENTS = ("startup", "small_business", "mid_market", "enterprise")
INDUSTRIES = ("technology", "services", "commerce", "education", "finance")
REGIONS = ("apac", "north_america", "europe")
CHANNELS = ("organic", "partner", "paid", "referral", "sales")
OBSERVATION_POLICY = "customer-source-weekly-v1"

CUSTOMER_FIELDS = (
    "tenant_id", "customer_id", "account_created_at", "customer_segment",
    "company_size_category", "industry_category", "region_category",
    "acquisition_channel", "onboarding_cohort", "initial_plan_tier",
    "tenant_product_category", "dataset_type",
)
TENANT_FIELDS = ("tenant_id", "product_category", "product_name", "currency", "dataset_type")
IDENTITY_FIELDS = ("tenant_id", "customer_id", "source", "source_category", "external_customer_id")
PLAN_FIELDS = (
    "tenant_id", "plan_id", "plan_tier", "billing_interval", "billing_interval_count",
    "amount_minor", "currency", "effective_at", "entitlements_json",
)
EVENT_FIELDS = (
    "tenant_id", "source", "source_category", "source_event_id", "external_customer_id",
    "customer_id", "event_type", "occurred_at", "source_available_at", "simulated_received_at",
    "attributes_json", "schema_version",
)
COVERAGE_FIELDS = (
    "tenant_id", "customer_id", "source", "source_category", "covered_from", "covered_through",
    "coverage_status", "coverage_completeness", "coverage_available_at", "observation_policy_version",
)
CHURN_FIELDS = (
    "tenant_id", "customer_id", "episode_number", "churn_effective_at", "churn_type",
    "source_event_id", "subscriptions_ended_at_loss",
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _midnight(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _weeks(start: date, end: date) -> list[date]:
    current = _week_start(start)
    result: list[date] = []
    while current < end:
        result.append(current)
        current += timedelta(days=7)
    return result


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))


def _account_rng(seed: int, profile: str, tenant_id: str, index: int) -> random.Random:
    identity = f"synthetic-saas-v1.2|{profile}|{seed}|{tenant_id}|{index}"
    digest = hashlib.sha256(identity.encode("ascii")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _dataset_id(config: SyntheticConfig) -> str:
    encoded = json.dumps(config.stable_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:12]
    return f"synthetic-saas-v1-2-{config.profile}-s{config.seed}-{digest}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sources(tenant_id: str) -> dict[str, str]:
    return {category: f"{tenant_id}-synthetic-{category}-v1-2" for category in ("usage", "billing", "subscription")}


def _poisson(rng: random.Random, mean: float) -> int:
    if mean <= 0:
        return 0
    mean = min(mean, 20.0)
    threshold = math.exp(-mean)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return max(0, count - 1)


def _plan_catalog(tenant_ids: list[str], start: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    intervals = (("month", 1), ("month", 2), ("quarter", 1), ("quarter", 2), ("year", 1))
    for tenant_index, tenant_id in enumerate(tenant_ids):
        currency = CURRENCIES[tenant_index % len(CURRENCIES)]
        for tier_index, (tier, monthly_minor) in enumerate(PLAN_TIERS):
            interval, count = intervals[(tenant_index + tier_index) % len(intervals)]
            period_months = {"month": 1, "quarter": 3, "year": 12}[interval] * count
            discount_factor = {"month": 1.0, "quarter": 0.965, "year": 0.88}[interval]
            rows.append({
                "tenant_id": tenant_id,
                "plan_id": f"{tenant_id}-{tier}-{interval}-{count}-v1-2",
                "plan_tier": tier,
                "billing_interval": interval,
                "billing_interval_count": count,
                "amount_minor": round(monthly_minor * period_months * discount_factor),
                "currency": currency,
                "effective_at": _iso(_midnight(start)),
                "entitlements_json": json.dumps({"feature_bundle": tier}, separators=(",", ":")),
            })
    return rows


def _open_csv(stack: ExitStack, path: Path, fields: tuple[str, ...]) -> csv.DictWriter:
    stream = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    return writer


def _open_gzip_csv(stack: ExitStack, path: Path, fields: tuple[str, ...]) -> csv.DictWriter:
    raw = stack.enter_context(path.open("wb"))
    compressed = stack.enter_context(gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0))
    stream = stack.enter_context(io.TextIOWrapper(compressed, encoding="utf-8", newline=""))
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    return writer


class _EventWriter:
    def __init__(self, writers: dict[str, csv.DictWriter], counts: Counter[str]):
        self.writers = writers
        self.counts = counts
        self.current_account: tuple[str, str] | None = None
        self.max_available: dict[tuple[str, date], datetime] = {}

    def begin_account(self, tenant_id: str, customer_id: str) -> None:
        """Bound availability bookkeeping to the account currently being emitted."""
        self.current_account = (tenant_id, customer_id)
        self.max_available.clear()

    def write(
        self, *, tenant_id: str, category: str, source: str, event_id: str,
        external_customer_id: str, customer_id: str, event_type: str,
        occurred_at: datetime, attributes: dict[str, Any], rng: random.Random,
        late_days: int = 0, extra_delay_days: int = 0,
    ) -> dict[str, Any]:
        if self.current_account != (tenant_id, customer_id):
            raise ValueError("event writer account context was not initialized")
        if late_days:
            available = occurred_at + timedelta(days=late_days, minutes=rng.randint(0, 360))
            self.counts["late_arriving_events"] += 1
        else:
            available = occurred_at + timedelta(days=extra_delay_days, minutes=rng.randint(0, 90))
        simulated_received = available + timedelta(minutes=rng.randint(1, 180))
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
            "simulated_received_at": _iso(simulated_received),
            "attributes_json": json.dumps(attributes, sort_keys=True, separators=(",", ":")),
            "schema_version": "1.0",
        }
        self.writers[category].writerow(row)
        self.writers["canonical"].writerow(row)
        self.counts[f"{category}_events"] += 1
        self.counts["canonical_events"] += 1
        if extra_delay_days:
            self.counts["outage_delayed_events"] += 1
        week = _week_start(occurred_at.date())
        key = (category, week)
        self.max_available[key] = max(self.max_available.get(key, available), available)
        return row


def _create_subscription(
    *, tenant_id: str, customer_id: str, external_id: str, billing_external_id: str,
    source: str, billing_source: str, sub_index: int,
    start_at: datetime, plan: dict[str, Any], plans: list[dict[str, Any]], rng: random.Random,
    writer: _EventWriter, event_rng: random.Random, end_at: datetime, missing_mrr: bool,
    discount_rate: float, risk: dict[str, float], behavior: list[tuple[date, int]],
    source_outages: set[date], late_event_rate: float,
) -> tuple[list[tuple[datetime, datetime]], list[tuple[datetime, str, str]], dict[str, Any]]:
    """Create one append-only subscription episode; return its paid intervals and events."""
    subscription_id = f"sub-{customer_id}-{sub_index:02d}"
    current_plan = dict(plan)
    interval = current_plan["billing_interval"]
    interval_count = int(current_plan["billing_interval_count"])
    gross = int(current_plan["amount_minor"])
    discount = round(gross * discount_rate)
    currency = current_plan["currency"]
    initial_end = datetime.fromisoformat(add_billing_period(_iso(start_at), interval, interval_count).replace("Z", "+00:00"))
    first_attrs: dict[str, Any] = {
        "subscription_id": subscription_id,
        "status": "active",
        "plan_id": current_plan["plan_id"],
        "started_at": _iso(start_at),
        "current_period_end": _iso(initial_end),
        "billing_interval": interval,
        "billing_interval_count": interval_count,
    }
    if not missing_mrr:
        first_attrs.update(amount_minor=gross, discount_minor=discount, currency=currency)
    end_event_id = ""
    def emit(event_type: str, event_time: datetime, suffix: str, attributes: dict[str, Any], *, billing: bool = False) -> None:
        event_category = "billing" if billing else "subscription"
        event_source = billing_source if billing else source
        event_external_id = billing_external_id if billing else external_id
        delay = 2 if _week_start(event_time.date()) in source_outages and not billing else 0
        late = 0
        if event_category in {"billing"} and event_rng.random() < late_event_rate:
            late = event_rng.randint(35, 45)
        if event_category == "subscription" and event_rng.random() < late_event_rate / 20:
            late = event_rng.randint(1, 3)
        row = writer.write(
            tenant_id=tenant_id, category=event_category, source=event_source, event_id=f"evt-{customer_id}-{suffix}",
            external_customer_id=event_external_id, customer_id=customer_id, event_type=event_type,
            occurred_at=event_time, attributes=attributes, rng=event_rng,
            late_days=late, extra_delay_days=delay,
        )

    emit("subscription_created", start_at, f"sub-create-{sub_index:02d}", first_attrs)
    periods: list[tuple[datetime, datetime]] = []
    cycle_start = start_at
    cycle_number = 1
    period_end = initial_end
    failure_streak = 0
    end_type = ""
    while period_end < end_at:
        due = period_end
        prior = [sessions for day, sessions in behavior if due.date() - timedelta(days=30) <= day < due.date()]
        prior_mean = sum(prior) / 30 if prior else 0.0
        reference = max(0.1, risk["baseline_sessions"] / 30)
        decline = max(-1.5, min(2.0, math.log((prior_mean + 0.05) / reference)))
        tenure_months = max(1, (due.year - start_at.year) * 12 + due.month - start_at.month)
        cancellation_logit = (
            -5.05 - 0.85 * risk["product_fit"] + 0.35 * risk["price_sensitivity"]
            - 0.45 * decline + 0.45 * failure_streak
            + (0.35 if tenure_months < 3 else -0.08)
            + event_rng.gauss(0, 0.70)
        )
        cancel = event_rng.random() < min(0.12, _sigmoid(cancellation_logit))
        payment_failed = event_rng.random() > risk["billing_reliability"] or event_rng.random() < risk["billing_failure_frequency"]
        billing_attrs: dict[str, Any] = {"subscription_id": subscription_id}
        if not missing_mrr:
            billing_attrs.update(amount_minor=gross - discount, currency=currency)

        if payment_failed:
            failure_streak += 1
            emit("invoice_payment_failed", due, f"bill-fail-{sub_index:02d}-{cycle_number:03d}", billing_attrs, billing=True)
            recovery_mode = _payment_recovery_mode(event_rng, risk["recovery_propensity"])
            if recovery_mode in {"immediate_recovery", "late_recovery"}:
                if recovery_mode == "late_recovery":
                    emit("subscription_updated", due, f"sub-pastdue-{sub_index:02d}-{cycle_number:03d}",
                         {"subscription_id": subscription_id, "status": "past_due"})
                    for retry_number, retry_day in enumerate((2, 4), start=1):
                        emit(
                            "invoice_payment_failed", due + timedelta(days=retry_day),
                            f"bill-retry-{sub_index:02d}-{cycle_number:03d}-{retry_number:02d}",
                            billing_attrs, billing=True,
                        )
                    recovered_at = due + timedelta(days=event_rng.randint(5, 6))
                else:
                    recovered_at = due + timedelta(days=event_rng.randint(1, 6))
                emit("invoice_paid", recovered_at, f"bill-recover-{sub_index:02d}-{cycle_number:03d}", billing_attrs, billing=True)
                failure_streak = max(0, failure_streak - 1)
                next_end = datetime.fromisoformat(
                    add_billing_period(_iso(due), interval, interval_count).replace("Z", "+00:00"),
                )
                renewal_attrs = {
                    "subscription_id": subscription_id, "status": "active", "current_period_end": _iso(next_end),
                    "billing_interval": interval, "billing_interval_count": interval_count,
                    "plan_id": current_plan["plan_id"],
                }
                if not missing_mrr:
                    renewal_attrs.update(amount_minor=gross, discount_minor=discount, currency=currency)
                emit("subscription_updated", recovered_at, f"sub-recovered-{sub_index:02d}-{cycle_number:03d}", renewal_attrs)
                periods.append((cycle_start, next_end))
                period_end = next_end
                cycle_start = due
                cycle_number += 1
                continue
            past_due_attrs = {"subscription_id": subscription_id, "status": "past_due"}
            emit("subscription_updated", due, f"sub-pastdue-{sub_index:02d}-{cycle_number:03d}", past_due_attrs)
            for retry_number, retry_day in enumerate((2, 4), start=1):
                emit(
                    "invoice_payment_failed", due + timedelta(days=retry_day),
                    f"bill-retry-{sub_index:02d}-{cycle_number:03d}-{retry_number:02d}",
                    billing_attrs, billing=True,
                )
            effective_at = due + timedelta(days=7)
            if effective_at < end_at:
                emit(
                    "subscription_involuntary_terminated", effective_at,
                    f"sub-involuntary-{sub_index:02d}-{cycle_number:03d}", {"subscription_id": subscription_id},
                )
                end_event_id = f"evt-{customer_id}-sub-involuntary-{sub_index:02d}-{cycle_number:03d}"
                periods.append((cycle_start, effective_at))
                end_type = "involuntary"
            else:
                periods.append((cycle_start, end_at))
            break

        emit("invoice_paid", due, f"bill-paid-{sub_index:02d}-{cycle_number:03d}", billing_attrs, billing=True)
        if cancel:
            voluntary = event_rng.random() < 0.72
            if voluntary:
                lead = timedelta(days=event_rng.randint(1, 45))
                request_at = max(cycle_start, due - lead)
                emit(
                    "cancellation_requested", request_at,
                    f"cancel-request-{sub_index:02d}-{cycle_number:03d}",
                    {"subscription_id": subscription_id, "current_period_end": _iso(due)},
                )
                end_type = "voluntary"
                effective_type = "subscription_cancelled_effective"
            else:
                end_type = "non_renewal"
                effective_type = "subscription_non_renewed_effective"
            emit(effective_type, due, f"sub-effective-{sub_index:02d}-{cycle_number:03d}", {"subscription_id": subscription_id})
            end_event_id = f"evt-{customer_id}-sub-effective-{sub_index:02d}-{cycle_number:03d}"
            periods.append((cycle_start, due))
            break

        if event_rng.random() < 0.025:
            current_plan = dict(event_rng.choice(plans))
            interval = current_plan["billing_interval"]
            interval_count = int(current_plan["billing_interval_count"])
            gross = int(current_plan["amount_minor"])
            discount = round(gross * discount_rate)
            currency = current_plan["currency"]
        next_end = datetime.fromisoformat(add_billing_period(_iso(due), interval, interval_count).replace("Z", "+00:00"))
        renewal_attrs = {
            "subscription_id": subscription_id, "status": "active", "plan_id": current_plan["plan_id"],
            "current_period_end": _iso(next_end), "billing_interval": interval,
            "billing_interval_count": interval_count,
        }
        if not missing_mrr:
            renewal_attrs.update(amount_minor=gross, discount_minor=discount, currency=currency)
        emit("subscription_updated", due, f"sub-renewal-{sub_index:02d}-{cycle_number:03d}", renewal_attrs)
        periods.append((cycle_start, next_end))
        period_end = next_end
        cycle_start = due
        cycle_number += 1

    if not periods or periods[-1][1] < end_at and not end_type:
        periods.append((cycle_start, end_at))
    if not periods:
        periods.append((start_at, end_at))
    lifecycle = {
        "subscription_id": subscription_id,
        "started_at": start_at,
        "ended_at": periods[-1][1] if end_type else None,
        "end_type": end_type,
        "end_event_id": end_event_id,
        "periods": periods,
    }
    return periods, [], lifecycle


def _payment_recovery_mode(event_rng: random.Random, recovery_propensity: float) -> str:
    """Allow a failed charge to recover immediately, recover during dunning, or terminate."""
    if event_rng.random() < recovery_propensity:
        return "immediate_recovery"
    late_recovery_probability = 0.05 + 0.16 * recovery_propensity
    if event_rng.random() < late_recovery_probability:
        return "late_recovery"
    return "termination"


def _is_active(day: date, lifecycles: list[dict[str, Any]]) -> bool:
    instant = _midnight(day)
    return any(start <= instant < end for item in lifecycles for start, end in item["periods"])


def _account_churn_episodes(lifecycles: list[dict[str, Any]]) -> list[tuple[datetime, str, str, int, str]]:
    changes: list[tuple[datetime, int, str, str, str]] = []
    for lifecycle in lifecycles:
        start = lifecycle["started_at"]
        end = lifecycle["ended_at"]
        changes.append((start, 1, lifecycle["subscription_id"], "", ""))
        if end is not None:
            changes.append((end, -1, lifecycle["subscription_id"], lifecycle["end_type"], lifecycle["end_event_id"]))
    changes.sort(key=lambda item: (item[0], item[1]))
    active = 0
    episodes: list[tuple[datetime, str, str, int, str]] = []
    episode = 0
    for at, same_time_changes in groupby(changes, key=lambda item: item[0]):
        transitions = list(same_time_changes)
        prior = active
        active += sum(delta for _, delta, *_ in transitions)
        if prior > 0 and active == 0:
            _, _, subscription_id, end_type, end_event_id = next(
                transition for transition in reversed(transitions) if transition[1] < 0
            )
            episode += 1
            episodes.append((at, end_type or "non_renewal", subscription_id, episode, end_event_id))
    return episodes


def _write_static_fixtures(dataset: Path, dataset_id: str, target_policy: str) -> None:
    (dataset / "label_oracle_fixtures.json").write_text(json.dumps({
        "dataset_id": dataset_id,
        "target_policy_version": target_policy,
        "purpose": "independent test fixtures only; never a production label table or model feature",
        "cases": [
            {"case": "final_entitlement_loss_day_5", "expected": {"7": "1", "14": "1", "30": "1"}},
            {"case": "final_entitlement_loss_day_10", "expected": {"7": "0", "14": "1", "30": "1"}},
            {"case": "final_entitlement_loss_day_20", "expected": {"7": "0", "14": "0", "30": "1"}},
            {"case": "complete_retention", "expected": {"7": "0", "14": "0", "30": "0"}},
            {"case": "outcome_coverage_gap", "expected": {"7": "0", "14": "unknown", "30": "unknown"}},
            {"case": "partial_subscription_end", "expected": {"7": "0", "14": "0", "30": "0"}},
            {"case": "reactivation_after_churn", "expected": {"7": "1", "14": "1", "30": "1"}},
        ],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (dataset / "adversarial_fixtures.json").write_text(json.dumps({
        "dataset_type": "synthetic_adversarial_test_fixtures",
        "must_remain_separate_from_valid_population": True,
        "fixtures": [
            {"case": "invalid_tenant_context", "expected_error": "unauthorized"},
            {"case": "unauthorized_source", "expected_error": "source_not_authorized"},
            {"case": "unauthorized_event_category", "expected_error": "event_category_not_authorized"},
            {"case": "duplicate_event_key", "expected_result": "duplicate"},
            {"case": "conflicting_duplicate_payload", "expected_error": "idempotency_conflict"},
            {"case": "subscription_owner_conflict", "expected_error": "contract_conflict"},
            {"case": "future_subscription_start", "expected_result": "not_eligible_before_start"},
            {"case": "late_event", "expected_result": "excluded_until_available"},
        ],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_documentation(dataset: Path, config: SyntheticConfig) -> None:
    doc = dataset / "documentation"
    doc.mkdir(parents=True, exist_ok=False)
    documents = {
        "data_dictionary.md": """# Synthetic SaaS v1.2 data dictionary

All timestamps are UTC. Account and source identity tables contain generated IDs only. `canonical_events.csv` is the union of the category event files. `simulated_received_at` records the source-side synthetic arrival time; the canonical importer records actual local receipt time.

`usage_aggregate_updated` rows are daily session counts for the completed UTC window `[occurred_at - 24 hours, occurred_at)`. `occurred_at` is the UTC midnight at the window end. `quantity` counts sessions only in that window; one row is not one session. The `feature` field is the predominant feature for that day's aggregate and does not partition or duplicate the session quantity. No `session_started` or `feature_used` rows are emitted in v1.2.

`observation_coverage.csv.gz` stores tenant/customer/source/category intervals with exclusive `covered_through`, status, completeness, availability, and policy version. Absence of a usage row is zero only when the complete usage interval is visible as of the feature cutoff. Partial, outage, delayed, missing-backfill, and censored intervals stay unknown. Subscription-outcome coverage is independent of usage coverage. Weekly cutoffs occur Monday at 12:00Z; rolling features end at that date's 00:00Z, the last completed UTC day.

`subscription_events.csv` is the append-only lifecycle ledger. `subscription_updated` records the full dated interval/count/plan/price state on renewals and contract changes. Effective end events mean that one subscription ended; account churn occurs only when the final paid entitlement ends. A later `subscription_created` after an account-level churn begins a new episode.

`effective_churn.csv` is a source-ledger-derived audit file, not a feature or precomputed training-label table. Scenario reports count source-verifiable accounts and events. Adversarial fixtures are separate from the ordinary population.
""",
        "generation_methodology.md": f"""# Synthetic SaaS v1.2 generation methodology

Default simulation window: `{config.start_date}T00:00:00Z` through `{config.end_date}T00:00:00Z` (exclusive end). Randomness uses stable per-profile, per-tenant, per-account streams derived from the configured seed. QUICK, STANDARD, and FULL therefore represent independent populations.

Daily usage activity evolves with personal baseline, weekday rhythm, seasonal/project cycles, gradual change, temporary shocks, volatility, and recovery. Usage behavior is generated before lifecycle outcomes. Renewal and termination are probabilistic conditional on changing behavior, pricing, tenure, payment reliability, and independent shocks; identical visible patterns can have different outcomes. Latent parameters and hazard values are never exported.

Source availability, source-side simulated receipt, canonical local import receipt, and interval coverage availability are separate timestamps. Usage/billing late arrivals and category-specific outages are represented explicitly. Coverage and scenario counts are computed from emitted source records.
""",
        "synthetic_label_policy.md": """# Synthetic label policy

The lifecycle event ledger is authoritative. A positive horizon requires source-backed loss of the account's final paid entitlement in `(as_of, as_of + horizon]`, available by the horizon end plus an eight-day maturity lag. The lag allows weekly source-coverage evidence and bounded source delays to mature. A partial subscription end is not account churn. Known cancellation at the cutoff is excluded from the prospective population. A negative requires subscription outcome coverage through the full horizon, available by maturity. Missing/censored outcome windows remain `unknown`. Reactivation starts a later risk episode and never deletes an earlier churn event. Feature sufficiency is audited separately from labels; missing usage does not erase a valid subscription outcome. Member 2 owns the production point-in-time feature builder and label builder.
""",
        "dataset_isolation.md": """# Dataset isolation

This artifact is the `synthetic_saas` track with target policy `effective_account_churn_7_14_30`. Each database stores one immutable dataset ID, manifest digest, generator version, and target-policy version. Import rejects another identity before provisioning rows. Dataset-scoped model/evaluation artifacts belong under a path containing the exact dataset ID. KKBox source files, targets, databases, and model artifacts are not used by this generator.
""",
        "reproduction_instructions.md": """# Reproduction

From the repository root run `python -m retaniq.synthetic generate --profile quick --seed 2026`, then `python -m retaniq.synthetic validate --profile quick`. Repeat with `standard` and `full`. Output defaults to `%USERPROFILE%\\RetainIQ-private\\synthetic_saas_v1_2`. Import each dataset into a separate database whose file name includes its manifest dataset ID. Run the Member 2 smoke command in `docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md` after provisioning a reader principal.
""",
    }
    for name, content in documents.items():
        (doc / name).write_text(content.strip() + "\n", encoding="utf-8")


def _simulate_behavior(
    *, rng: random.Random, tenant_index: int, created: date, end: date,
    usage_frequency: float, feature_change_chance: float,
) -> tuple[list[tuple[date, int]], dict[str, Any]]:
    archetype = TENANT_ARCHETYPES[tenant_index % len(TENANT_ARCHETYPES)]
    low_frequency = rng.random() < 0.14
    baseline = rng.lognormvariate(math.log(1.8 if low_frequency else 9.5 * archetype[2]), 0.38 if low_frequency else 0.62)
    volatility = rng.uniform(0.06, 0.42) * archetype[3]
    season_strength = rng.uniform(0.0, 0.42)
    season_phase = rng.random() * math.tau
    behavior = rng.choices(
        ("stable", "decline_recovery", "decline", "improving", "volatile", "cold_start"),
        weights=(36, 14, 12, 12, 12, 14), k=1,
    )[0]
    span = max(1, (end - created).days)
    trend_start = rng.randint(max(10, int(span * 0.18)), max(10, int(span * 0.72))) if span > 24 else 0
    decline_length = rng.randint(30, 100)
    recovery_start = trend_start + decline_length
    recovery_length = rng.randint(25, 75)
    feature_start = rng.choice(FEATURES)
    feature_later = rng.choice(tuple(feature for feature in FEATURES if feature != feature_start))
    feature_change = rng.random() < feature_change_chance
    feature_change_day = rng.randint(max(1, span // 4), max(2, 3 * span // 4)) if span > 10 else span
    engagement_log = rng.gauss(0, 0.12)
    daily: list[tuple[date, int]] = []
    features: list[str] = []
    for offset in range(span):
        day = created + timedelta(days=offset)
        if behavior == "decline_recovery" and trend_start <= offset < recovery_start:
            trend = -0.0042
        elif behavior == "decline_recovery" and recovery_start <= offset < recovery_start + recovery_length:
            trend = 0.0048
        elif behavior == "decline" and trend_start <= offset < trend_start + decline_length:
            trend = -0.0038
        elif behavior == "improving" and trend_start <= offset < trend_start + decline_length:
            trend = 0.0030
        else:
            trend = 0.0
        shock = rng.gauss(0, 0.008 + volatility * 0.018)
        engagement_log = max(-2.2, min(1.7, engagement_log + trend - 0.0012 * engagement_log + shock))
        weekday = (archetype[3] if day.weekday() < 5 else max(0.18, 1.35 - archetype[3]))
        seasonal = 1 + season_strength * math.sin(math.tau * day.timetuple().tm_yday / 365.25 + season_phase)
        workload = 1 + 0.12 * math.sin(math.tau * offset / 30.4 + season_phase / 2)
        intensity = max(0.01, baseline / 30 * math.exp(engagement_log) * weekday * seasonal * workload * usage_frequency)
        sessions = _poisson(rng, intensity)
        if rng.random() < 0.018:
            sessions += 1 + _poisson(rng, min(5.0, intensity * 2.4 + 1.0))
        daily.append((day, sessions))
        features.append(feature_later if feature_change and offset >= feature_change_day else feature_start)
    risk = {
        "baseline_sessions": baseline,
        "volatility": volatility,
        "product_fit": rng.uniform(-1.3, 1.4),
        "price_sensitivity": rng.uniform(-0.8, 1.2),
        "billing_reliability": rng.uniform(0.72, 0.995),
        "billing_failure_frequency": rng.uniform(0.0, 0.12),
        "recovery_propensity": rng.uniform(0.28, 0.94),
        "behavior": behavior,
        "feature_start": feature_start,
        "feature_later": feature_later,
        "feature_change_day": feature_change_day,
        "features": features,
    }
    return daily, risk


def _write_coverage_for_account(
    *, writer: csv.DictWriter, tenant_id: str, customer_id: str, created: date, start: date, end: date,
    source_map: dict[str, str], week_starts: list[date], outage_weeks: dict[str, set[date]],
    missing_usage_weeks: set[date], missing_subscription_weeks: set[date],
    lifecycles: list[dict[str, Any]], event_writer: _EventWriter, rng: random.Random,
    counts: Counter[str], tenant_outage_delay: dict[tuple[str, str, date], int],
) -> None:
    start_dt = _midnight(start)
    end_dt = _midnight(end)
    if created > start:
        unavailable_from = start_dt
        not_created_to = _midnight(created)
        for category, source in source_map.items():
            writer.writerow({
                "tenant_id": tenant_id, "customer_id": customer_id, "source": source,
                "source_category": category, "covered_from": _iso(unavailable_from),
                "covered_through": _iso(not_created_to), "coverage_status": "not_created",
                "coverage_completeness": 0.0, "coverage_available_at": _iso(not_created_to),
                "observation_policy_version": OBSERVATION_POLICY,
            })
            counts["observation_coverage"] += 1
    created_dt = _midnight(created)
    for week in week_starts:
        week_end = _midnight(week + timedelta(days=7))
        left = max(start_dt, created_dt, _midnight(week))
        right = min(end_dt, week_end)
        if left >= right:
            continue
        week_complete = week + timedelta(days=7) <= end
        for category, source in source_map.items():
            status = "complete"
            completeness = 1.0
            if category == "usage" and not any(
                sub_start < right and sub_end > left
                for lifecycle in lifecycles for sub_start, sub_end in lifecycle["periods"]
            ):
                status = "entitlement_ended"
            if week in outage_weeks[category]:
                status = "outage"
                completeness = 0.0
            elif category == "usage" and week in missing_usage_weeks:
                status = "missing_historical_backfill" if week <= created + timedelta(days=56) else "partial"
                completeness = round(rng.uniform(0.25, 0.78), 3)
            elif category == "subscription" and week in missing_subscription_weeks:
                status = "partial"
                completeness = round(rng.uniform(0.45, 0.84), 3)
            event_available = event_writer.max_available.get((category, week))
            report_at = week_end + timedelta(hours=12)
            if status == "complete" and event_available is not None and event_available > report_at:
                status = "delayed"
            if not week_complete:
                status = "censored"
            available_at = max(right, report_at if week_complete else right)
            if status == "outage":
                available_at = max(right, week_end + timedelta(days=tenant_outage_delay.get((tenant_id, category, week), 2)))
            elif status == "delayed" and event_available is not None:
                available_at = max(available_at, event_available)
            writer.writerow({
                "tenant_id": tenant_id, "customer_id": customer_id, "source": source,
                "source_category": category, "covered_from": _iso(left), "covered_through": _iso(right),
                "coverage_status": status, "coverage_completeness": completeness,
                "coverage_available_at": _iso(available_at), "observation_policy_version": OBSERVATION_POLICY,
            })
            counts["observation_coverage"] += 1
            counts[f"coverage_{status}"] += 1


def generate_dataset(config: SyntheticConfig, output_root: Path | str) -> dict[str, Any]:
    """Generate deterministic, bounded-memory v1.2 source exports."""
    config.validate()
    root = Path(output_root).expanduser().resolve()
    dataset_id = _dataset_id(config)
    profile_root = root / config.profile
    destination = profile_root / dataset_id
    staging = profile_root / f".{dataset_id}.staging-{os.getpid()}"
    if destination.exists():
        raise FileExistsError(f"dataset already exists: {destination}")
    if staging.exists():
        raise FileExistsError(f"staging directory already exists: {staging}")
    staging.mkdir(parents=True, exist_ok=False)
    start = date.fromisoformat(config.start_date)
    end = date.fromisoformat(config.end_date)
    end_at = _midnight(end)
    week_starts = _weeks(start, end)
    tenant_ids = [f"tenant-{index + 1:02d}" for index in range(config.tenant_count)]
    plans = _plan_catalog(tenant_ids, start)
    plans_by_tenant: dict[str, list[dict[str, Any]]] = {
        tenant_id: [row for row in plans if row["tenant_id"] == tenant_id] for tenant_id in tenant_ids
    }
    counts: Counter[str] = Counter()
    tenant_accounts: Counter[str] = Counter()
    plan_accounts: Counter[str] = Counter()
    interval_accounts: Counter[str] = Counter()
    scenario_accounts: dict[str, set[str]] = defaultdict(set)
    scenario_events: Counter[str] = Counter()
    source_outages: dict[str, dict[str, set[date]]] = {}
    outage_delays: dict[tuple[str, str, date], int] = {}

    try:
        with ExitStack() as stack:
            writers = {
                "customers": _open_csv(stack, staging / "customers.csv", CUSTOMER_FIELDS),
                "tenants": _open_csv(stack, staging / "tenants.csv", TENANT_FIELDS),
                "identities": _open_csv(stack, staging / "customer_identities.csv", IDENTITY_FIELDS),
                "plans": _open_csv(stack, staging / "plan_catalog.csv", PLAN_FIELDS),
                "subscription": _open_csv(stack, staging / "subscription_events.csv", EVENT_FIELDS),
                "billing": _open_csv(stack, staging / "billing_events.csv", EVENT_FIELDS),
                "usage": _open_csv(stack, staging / "usage_events.csv", EVENT_FIELDS),
                "canonical": _open_csv(stack, staging / "canonical_events.csv", EVENT_FIELDS),
                "coverage": _open_gzip_csv(stack, staging / "observation_coverage.csv.gz", COVERAGE_FIELDS),
                "churn": _open_csv(stack, staging / "effective_churn.csv", CHURN_FIELDS),
            }
            for tenant_index, tenant_id in enumerate(tenant_ids):
                archetype = TENANT_ARCHETYPES[tenant_index % len(TENANT_ARCHETYPES)]
                currency = CURRENCIES[tenant_index % len(CURRENCIES)]
                writers["tenants"].writerow({
                    "tenant_id": tenant_id, "product_category": archetype[0], "product_name": archetype[1],
                    "currency": currency, "dataset_type": "synthetic_saas",
                })
                counts["tenants"] += 1
                outage_rng = _account_rng(config.seed, config.profile, tenant_id, -1)
                outage_weeks = {
                    category: {week for week in week_starts if outage_rng.random() < config.source_outage_frequency}
                    for category in ("usage", "billing", "subscription")
                }
                source_outages[tenant_id] = outage_weeks
                for category, weeks in outage_weeks.items():
                    for week in weeks:
                        outage_delays[(tenant_id, category, week)] = outage_rng.randint(1, 3)
                        scenario_accounts[f"tenant_outage_{category}"].update(
                            f"{tenant_id}-customer-{index + 1:06d}"
                            for index in range(tenant_index, config.account_count, config.tenant_count)
                        )
                        scenario_events[f"tenant_outage_{category}"] += 1

            for plan in plans:
                writers["plans"].writerow(plan)
            counts["plans"] = len(plans)
            event_writer = _EventWriter(writers, counts)
            for tenant_index, tenant_id in enumerate(tenant_ids):
                source_map = _sources(tenant_id)
                for account_index in range(tenant_index, config.account_count, config.tenant_count):
                    rng = _account_rng(config.seed, config.profile, tenant_id, account_index)
                    customer_id = f"{tenant_id}-customer-{account_index + 1:06d}"
                    event_writer.begin_account(tenant_id, customer_id)
                    span = (end - start).days
                    max_offset = max(0, span - 1)
                    created = start + timedelta(days=rng.randint(0, max_offset))
                    created_at = _midnight(created)
                    segment = rng.choices(SEGMENTS, weights=(30, 36, 25, 9), k=1)[0]
                    initial_plan = dict(rng.choice(plans_by_tenant[tenant_id]))
                    missing_mrr = rng.random() < 0.026
                    missing_telemetry = rng.random() < 0.055
                    missing_usage_weeks: set[date] = set()
                    if missing_telemetry:
                        available_weeks = [week for week in week_starts if week >= created]
                        if available_weeks:
                            missing_start = rng.randrange(len(available_weeks))
                            missing_length = rng.randint(1, min(10, len(available_weeks) - missing_start))
                            missing_usage_weeks.update(available_weeks[missing_start:missing_start + missing_length])
                    missing_subscription_weeks: set[date] = set()
                    if rng.random() < 0.035:
                        available_weeks = [week for week in week_starts if week >= created]
                        if available_weeks:
                            missing_start = rng.randrange(len(available_weeks))
                            missing_length = rng.randint(1, min(5, len(available_weeks) - missing_start))
                            missing_subscription_weeks.update(available_weeks[missing_start:missing_start + missing_length])
                    writers["customers"].writerow({
                        "tenant_id": tenant_id, "customer_id": customer_id,
                        "account_created_at": _iso(created_at), "customer_segment": segment,
                        "company_size_category": segment, "industry_category": rng.choice(INDUSTRIES),
                        "region_category": rng.choice(REGIONS), "acquisition_channel": rng.choice(CHANNELS),
                        "onboarding_cohort": created.strftime("%Y-%m"), "initial_plan_tier": initial_plan["plan_tier"],
                        "tenant_product_category": TENANT_ARCHETYPES[tenant_index % len(TENANT_ARCHETYPES)][0],
                        "dataset_type": "synthetic_saas",
                    })
                    counts["customers"] += 1
                    tenant_accounts[tenant_id] += 1
                    plan_accounts[initial_plan["plan_tier"]] += 1
                    interval_accounts[f"{initial_plan['billing_interval']}:{initial_plan['billing_interval_count']}"] += 1
                    identity_sources: dict[str, str] = {}
                    for category, source in source_map.items():
                        external = f"ext-{category}-{customer_id}"
                        identity_sources[category] = external
                        writers["identities"].writerow({
                            "tenant_id": tenant_id, "customer_id": customer_id, "source": source,
                            "source_category": category, "external_customer_id": external,
                        })
                        counts["customer_identities"] += 1

                    daily, risk = _simulate_behavior(
                        rng=rng, tenant_index=tenant_index, created=created, end=end,
                        usage_frequency=config.usage_frequency, feature_change_chance=0.28,
                    )
                    usage_rng = _account_rng(config.seed + 101, config.profile, tenant_id, account_index)
                    bill_rng = _account_rng(config.seed + 202, config.profile, tenant_id, account_index)
                    sub_rng = _account_rng(config.seed + 303, config.profile, tenant_id, account_index)
                    telemetry_rng = _account_rng(config.seed + 404, config.profile, tenant_id, account_index)
                    event_start_count = counts["subscription_events"]
                    multi = rng.random() < 0.075 and (end - created).days > 120
                    sub_specs = [(created_at, initial_plan)]
                    if multi:
                        second_start = created_at + timedelta(days=rng.randint(20, 60))
                        if second_start < end_at:
                            other_plans = [p for p in plans_by_tenant[tenant_id] if p["plan_id"] != initial_plan["plan_id"]]
                            sub_specs.append((second_start, dict(rng.choice(other_plans))))

                    lifecycles: list[dict[str, Any]] = []
                    for sub_index, (sub_start, plan) in enumerate(sub_specs, start=1):
                        _, _, lifecycle = _create_subscription(
                            tenant_id=tenant_id, customer_id=customer_id,
                            external_id=identity_sources["subscription"], source=source_map["subscription"],
                            billing_external_id=identity_sources["billing"],
                            billing_source=source_map["billing"],
                            sub_index=sub_index, start_at=sub_start, plan=plan,
                            plans=plans_by_tenant[tenant_id], rng=rng, writer=event_writer,
                            event_rng=sub_rng, end_at=end_at, missing_mrr=missing_mrr,
                            discount_rate=(rng.uniform(0.02, 0.20) if rng.random() < 0.17 else 0.0),
                            risk=risk, behavior=daily, source_outages=source_outages[tenant_id]["subscription"],
                            late_event_rate=0.004,
                        )
                        lifecycles.append(lifecycle)
                    churns = _account_churn_episodes(lifecycles)
                    if churns:
                        first_loss = churns[0][0]
                        if first_loss + timedelta(days=45) < end_at and rng.random() < 0.13:
                            reactivate_at = first_loss + timedelta(days=rng.randint(30, 90))
                            if reactivate_at < end_at:
                                reactivation_plan = dict(rng.choice(plans_by_tenant[tenant_id]))
                                _, _, lifecycle = _create_subscription(
                                    tenant_id=tenant_id, customer_id=customer_id,
                                    external_id=identity_sources["subscription"], source=source_map["subscription"],
                                    billing_external_id=identity_sources["billing"],
                                    billing_source=source_map["billing"],
                                    sub_index=len(lifecycles) + 1, start_at=reactivate_at,
                                    plan=reactivation_plan, plans=plans_by_tenant[tenant_id], rng=rng,
                                    writer=event_writer, event_rng=sub_rng, end_at=end_at,
                                    missing_mrr=missing_mrr, discount_rate=0.0, risk=risk,
                                    behavior=daily, source_outages=source_outages[tenant_id]["subscription"],
                                    late_event_rate=0.004,
                                )
                                lifecycles.append(lifecycle)
                                counts["reactivations"] += 1

                    churns = _account_churn_episodes(lifecycles)
                    account_churn_rows = []
                    for at, churn_type, source_event_id, episode, end_event_id in churns:
                        account_churn_rows.append({
                            "tenant_id": tenant_id, "customer_id": customer_id, "episode_number": episode,
                            "churn_effective_at": _iso(at), "churn_type": churn_type,
                            "source_event_id": end_event_id,
                            "subscriptions_ended_at_loss": sum(
                                1 for item in lifecycles if item["ended_at"] == at
                            ),
                        })
                    for churn_row in account_churn_rows:
                        writers["churn"].writerow(churn_row)
                    counts["effective_account_churn_episodes"] += len(churns)
                    counts["subscriptions"] += len(lifecycles)

                    active_days = 0
                    account_usage_events = 0
                    for day, sessions in daily:
                        if sessions <= 0 or not _is_active(day, lifecycles):
                            continue
                        week = _week_start(day)
                        if week in source_outages[tenant_id]["usage"] or week in missing_usage_weeks:
                            continue
                        if usage_rng.random() > min(1.0, config.event_density):
                            continue
                        if week in source_outages[tenant_id]["usage"]:
                            continue
                        occurred_at = _midnight(day + timedelta(days=1))
                        late_days = usage_rng.randint(35, 45) if usage_rng.random() < 0.004 else 0
                        feature = risk["features"][(day - created).days]
                        event = event_writer.write(
                            tenant_id=tenant_id, category="usage", source=source_map["usage"],
                            event_id=f"evt-{customer_id}-usage-{day:%Y%m%d}",
                            external_customer_id=identity_sources["usage"], customer_id=customer_id,
                            event_type="usage_aggregate_updated", occurred_at=occurred_at,
                            attributes={"feature": feature, "quantity": sessions, "unit": "sessions"},
                            rng=usage_rng, late_days=late_days,
                        )
                        counts["usage_active_days"] += 1
                        counts["usage_sessions"] += sessions
                        account_usage_events += 1
                        active_days += 1
                        if late_days:
                            scenario_accounts["delayed_usage_events"].add(customer_id)
                            scenario_events["delayed_usage_events"] += 1
                    counts["account_usage_event_rows"] += account_usage_events

                    _write_coverage_for_account(
                        writer=writers["coverage"], tenant_id=tenant_id, customer_id=customer_id,
                        created=created, start=start, end=end, source_map=source_map, week_starts=week_starts,
                        outage_weeks=source_outages[tenant_id], missing_usage_weeks=missing_usage_weeks,
                        missing_subscription_weeks=missing_subscription_weeks, lifecycles=lifecycles,
                        event_writer=event_writer, rng=telemetry_rng, counts=counts,
                        tenant_outage_delay=outage_delays,
                    )
                    episode_types = {row["churn_type"] for row in account_churn_rows}
                    if active_days >= max(8, (end - created).days // 12) and not episode_types:
                        scenario_accounts["source_observed_retention"].add(customer_id)
                    if episode_types:
                        scenario_accounts["source_observed_churn"].add(customer_id)
                    if account_usage_events >= 10 and episode_types:
                        scenario_accounts["usage_evidence_before_or_during_churn"].add(customer_id)
                    if account_usage_events < 8 and not episode_types:
                        scenario_accounts["sparse_usage_with_retention"].add(customer_id)
                    if missing_telemetry:
                        scenario_accounts["account_specific_missing_telemetry"].add(customer_id)
                    if missing_mrr:
                        scenario_accounts["missing_mrr"].add(customer_id)
                    if multi:
                        scenario_accounts["multiple_subscriptions"].add(customer_id)
                    if churns:
                        scenario_accounts["effective_account_churn"].add(customer_id)
                        scenario_events["effective_account_churn"] += len(churns)
                    if len(lifecycles) > 1:
                        scenario_accounts["reactivated_or_multiple_subscriptions"].add(customer_id)
                    if risk["behavior"] == "decline_recovery" and account_usage_events:
                        scenario_accounts["decline_recovery_behavior_proxy"].add(customer_id)

            counts["subscriptions"] = max(counts["subscriptions"], 0)
            counts["scenario_accounts"] = sum(tenant_accounts.values())
            tenant_distributions = {key: int(value) for key, value in sorted(tenant_accounts.items())}
            plan_distributions = {key: int(value) for key, value in sorted(plan_accounts.items())}
            interval_distributions = {key: int(value) for key, value in sorted(interval_accounts.items())}
            for scenario in (
                "source_observed_retention", "source_observed_churn", "usage_evidence_before_or_during_churn",
                "sparse_usage_with_retention", "account_specific_missing_telemetry", "missing_mrr",
                "multiple_subscriptions", "effective_account_churn", "reactivated_or_multiple_subscriptions",
                "decline_recovery_behavior_proxy", "delayed_usage_events",
            ):
                scenario_accounts.setdefault(scenario, set())
            scenario_rules = {
                "source_observed_retention": "Customer has emitted daily usage aggregates and has no effective account-loss event in the exported lifecycle ledger.",
                "source_observed_churn": "At least one source-backed final-entitlement loss is listed in effective_churn.csv.",
                "usage_evidence_before_or_during_churn": "Customer has at least ten daily aggregates and a source-backed effective account-loss episode.",
                "sparse_usage_with_retention": "Customer has fewer than eight daily usage aggregate rows and no source-backed effective account-loss episode.",
                "account_specific_missing_telemetry": "Customer has a non-complete usage coverage interval in the source coverage ledger.",
                "missing_mrr": "A created subscription event omits amount and currency fields.",
                "multiple_subscriptions": "At least two distinct subscription IDs were created for the same account.",
                "effective_account_churn": "At least one source-backed final-entitlement loss was independently written to effective_churn.csv.",
                "reactivated_or_multiple_subscriptions": "Customer has more than one subscription lifecycle; this proxy does not alone prove reactivation.",
                "decline_recovery_behavior_proxy": "Generator state indicated a decline-and-recovery path; source-level trend verification is pending.",
                "delayed_usage_events": "Usage event has source_available_at more than 30 days after occurred_at.",
            }
            scenario_rows = []
            for name, rule in sorted(scenario_rules.items()):
                accounts = scenario_accounts[name]
                tenants = Counter(customer.split("-customer-")[0] for customer in accounts)
                scenario_rows.append({
                    "scenario_name": name,
                    "detection_rule": rule,
                    "source_evidence": "customer_id, canonical_events.csv, effective_churn.csv, or observation_coverage.csv.gz",
                    "distinct_account_count": len(accounts),
                    "event_count": int(scenario_events[name]),
                    "tenant_distribution": dict(sorted(tenants.items())),
                    "cohort_distribution": {},
                    "verification_status": "SOURCE_PROXY" if "proxy" in name or "or_multiple" in name else "SOURCE_VERIFIED",
                })
            scenario_payload = {
                "dataset_id": dataset_id,
                "overlap_allowed": True,
                "accounts_by_tenant": tenant_distributions,
                "accounts_by_plan_tier": plan_distributions,
                "accounts_by_billing_interval": interval_distributions,
                "scenarios": scenario_rows,
                "event_volumes": {
                    "usage_events": counts["usage_events"], "billing_events": counts["billing_events"],
                    "subscription_events": counts["subscription_events"], "canonical_events": counts["canonical_events"],
                },
            }
            counts["accounts"] = counts["customers"]
            counts["effective_churn_episodes"] = counts["effective_account_churn_episodes"]
            (staging / "scenario_coverage.json").write_text(
                json.dumps(scenario_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
            )
            _write_static_fixtures(staging, dataset_id, config.target_policy_version)
            _write_documentation(staging, config)

        split_manifest = {
            "dataset_id": dataset_id,
            "target_policy_version": config.target_policy_version,
            "strategy": "chronological_weekly_account_cutoffs_with_mature_horizon_embargo",
            "cohort_readiness": "READY" if (config.start_date == "2024-10-01" and config.end_date == "2026-10-01") else "NOT_READY_CUSTOM_WINDOW",
            "sampling_policy": {
                "frequency": "weekly",
                "cutoff_utc": "Monday 12:00:00Z",
                "warmup_days": 63,
                "usage_windows": "Completed UTC days ending at cutoff-date 00:00Z; features are known at the Monday 12:00Z cutoff.",
                "personal_baseline": "Earlier non-overlapping 28-day window [cutoff-date-58d, cutoff-date-30d).",
                "key": ["dataset_id", "tenant_id", "customer_id", "as_of", "horizon_days"],
                "grouping": "account and risk episode; correlated cutoffs are not independent accounts",
            },
            "label_maturity_lag_days": 8,
            "maximum_horizon_days": 30,
            "stages": {
                "train": {"cutoff_start": "2024-10-01", "cutoff_end": "2025-08-24", "mature_before": "2025-10-01"},
                "development": {"cutoff_start": "2025-10-01", "cutoff_end": "2026-01-25", "mature_before": "2026-03-01"},
                "calibration": {"cutoff_start": "2026-03-01", "cutoff_end": "2026-04-26", "mature_before": "2026-06-01"},
                "untouched_test": {"cutoff_start": "2026-06-01", "cutoff_end": "2026-08-24", "mature_before": "2026-10-01"},
            },
            "test_policy": "Do not use the untouched test for fitting, tuning, calibration, or generator adjustment.",
        }
        (staging / "split_manifest.json").write_text(
            json.dumps(split_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        _write_churn_file_rows = counts["effective_churn_episodes"]
        quality = {
            "status": "PENDING_INDEPENDENT_VALIDATION",
            "dataset_type": "synthetic_saas",
            "dataset_id": dataset_id,
            "direct_target_fields_exported": False,
            "latent_state_exported": False,
            "daily_usage_semantics": "completed_utc_day_window_end_timestamp",
            "source_coverage_policy": OBSERVATION_POLICY,
            "source_backed_churn_episodes": _write_churn_file_rows,
            "notes": ["Label construction remains owned by Member 2.", "Generator status is not a model-readiness or real-world validation claim."],
        }
        (staging / "quality_report.json").write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        count_payload = dict(sorted((key, int(value)) for key, value in counts.items()))
        file_targets = sorted(
            path for path in staging.rglob("*")
            if path.is_file() and path.name != "dataset_manifest.json"
        )
        file_hashes = {path.relative_to(staging).as_posix(): _sha256_file(path) for path in file_targets}
        file_sizes = {path.relative_to(staging).as_posix(): path.stat().st_size for path in file_targets}
        manifest = {
            "dataset_id": dataset_id,
            "dataset_family": "retainiq_synthetic_saas",
            "dataset_version": "1.2.0",
            "dataset_type": "synthetic_saas",
            "target_policy_version": config.target_policy_version,
            "generator_code_version": config.generator_version,
            "generator_build_revision": config.generator_build_revision,
            "random_seed": config.seed,
            "profile": config.profile,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "end_date_exclusive": True,
            "tenant_count": config.tenant_count,
            "account_count": counts["customers"],
            "actual_counts": count_payload,
            "scenario_counts": {row["scenario_name"]: row["distinct_account_count"] for row in scenario_rows},
            "file_hashes": file_hashes,
            "file_sizes_bytes": file_sizes,
            "split_manifest_reference": "split_manifest.json",
            "usage_window_convention": {
                "event_type": "usage_aggregate_updated",
                "unit": "sessions",
                "window": "[occurred_at - 24 hours, occurred_at)",
                "occurred_at": "completed UTC day end at midnight",
                "source_available_at": "at or after occurred_at",
                "double_counting": "only daily aggregate quantity contributes to session totals",
            },
            "synthetic_data_disclosure": "SYNTHETIC SAAS DEMO",
            "no_real_customer_data": True,
            "track": "synthetic_saas",
            "target": "effective_account_churn_7_14_30",
            "real_kkbox_benchmark_status": "NOT_VALIDATED",
            "configuration": config.stable_dict(),
        }
        (staging / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        from .v12_validation import validate_v12_dataset
        first_validation = validate_v12_dataset(staging)
        if first_validation["status"] != "PASS":
            errors = "; ".join(first_validation.get("errors", [])[:8])
            raise ValueError(f"independent v1.2 validation failed: {errors}")
        scenario_payload["scenarios"] = first_validation["source_scenarios"]
        scenario_payload["audit_method"] = "Independent source-record audit; latent generator state is not counted as observed evidence."
        scenario_payload["usage_density_by_tenant"] = first_validation["usage_density_by_tenant"]
        scenario_payload["usage_density_by_cohort"] = first_validation["usage_density_by_cohort"]
        scenario_payload["usage_rhythm_by_tenant"] = first_validation["usage_rhythm_by_tenant"]
        scenario_payload["feature_history_by_tenant"] = first_validation["feature_history_by_tenant"]
        scenario_payload["feature_history_by_cohort"] = first_validation["feature_history_by_cohort"]
        scenario_payload["behavior_by_tenant"] = first_validation["behavior_by_tenant"]
        scenario_payload["behavior_by_cohort"] = first_validation["behavior_by_cohort"]
        scenario_payload["coverage_by_tenant"] = first_validation["coverage_by_tenant"]
        scenario_payload["coverage_by_cohort"] = first_validation["coverage_by_cohort"]
        scenario_payload["behavior_windows"] = first_validation["behavior_windows"]
        (staging / "scenario_coverage.json").write_text(
            json.dumps(scenario_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        split_manifest["cohort_label_audit"] = first_validation["cohort_label_audit"]
        (staging / "split_manifest.json").write_text(
            json.dumps(split_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        quality.update({
            "status": "PASS",
            "validation_scope": "source_export_integrity_only",
            "independent_validation_counts": first_validation["measured_counts"],
            "chronological_splits": split_manifest["cohort_readiness"],
            "cohort_label_audit": first_validation["cohort_label_audit"],
            "usage_density_by_tenant": first_validation["usage_density_by_tenant"],
            "usage_density_by_cohort": first_validation["usage_density_by_cohort"],
            "usage_rhythm_by_tenant": first_validation["usage_rhythm_by_tenant"],
            "feature_history_by_tenant": first_validation["feature_history_by_tenant"],
            "feature_history_by_cohort": first_validation["feature_history_by_cohort"],
            "behavior_by_tenant": first_validation["behavior_by_tenant"],
            "behavior_by_cohort": first_validation["behavior_by_cohort"],
            "behavior_windows": first_validation["behavior_windows"],
            "source_scenario_counts": {
                row["scenario_name"]: row["distinct_account_count"]
                for row in first_validation["source_scenarios"]
            },
        })
        (staging / "quality_report.json").write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        file_targets = sorted(
            path for path in staging.rglob("*")
            if path.is_file() and path.name != "dataset_manifest.json"
        )
        manifest["file_hashes"] = {path.relative_to(staging).as_posix(): _sha256_file(path) for path in file_targets}
        manifest["file_sizes_bytes"] = {path.relative_to(staging).as_posix(): path.stat().st_size for path in file_targets}
        manifest["scenario_counts"] = {
            row["scenario_name"]: row["distinct_account_count"]
            for row in first_validation["source_scenarios"]
        }
        (staging / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        final_validation = validate_v12_dataset(staging)
        if final_validation["status"] != "PASS":
            errors = "; ".join(final_validation.get("errors", [])[:8])
            raise ValueError(f"final v1.2 validation failed: {errors}")
        profile_root.mkdir(parents=True, exist_ok=True)
        staging.replace(destination)
        returned = dict(manifest)
        returned["dataset_path"] = str(destination)
        returned["validation"] = final_validation
        return returned
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
