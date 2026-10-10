"""Configuration and profile defaults for the synthetic SaaS generator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


PROFILE_DEFAULTS = {
    "quick": {"account_count": 200, "tenant_count": 4},
    "standard": {"account_count": 3000, "tenant_count": 4},
    "full": {"account_count": 20000, "tenant_count": 4},
    "stress": {"account_count": 50000, "tenant_count": 8},
}


@dataclass(frozen=True)
class SyntheticConfig:
    profile: str
    seed: int = 2026
    account_count: int = 200
    tenant_count: int = 4
    start_date: str = "2024-10-01"
    end_date: str = "2026-10-01"
    event_density: float = 1.0
    usage_frequency: float = 1.0
    source_outage_frequency: float = 0.025
    billing_failure_frequency: float = 0.08
    churn_hazard_multiplier: float = 1.0
    generator_version: str = "synthetic-saas-v1.2"
    generator_build_revision: str = "r9"
    target_policy_version: str = "effective-account-churn-v1.2"

    @classmethod
    def from_profile(cls, profile: str, **overrides: Any) -> "SyntheticConfig":
        normalized = profile.lower()
        if normalized not in PROFILE_DEFAULTS:
            raise ValueError(f"unsupported profile: {profile}")
        values = {"profile": normalized, **PROFILE_DEFAULTS[normalized], **overrides}
        config = cls(**values)
        config.validate()
        return config

    def validate(self) -> None:
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("start_date and end_date must be ISO dates") from exc
        if end <= start:
            raise ValueError("end_date must be after start_date (exclusive)")
        if self.account_count < 1 or self.account_count > 250000:
            raise ValueError("account_count must be between 1 and 250000")
        if self.tenant_count < 1 or self.tenant_count > self.account_count:
            raise ValueError("tenant_count must be between 1 and account_count")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        for name in ("event_density", "usage_frequency", "churn_hazard_multiplier"):
            if not 0 < getattr(self, name) <= 10:
                raise ValueError(f"{name} must be greater than 0 and at most 10")
        for name in ("source_outage_frequency", "billing_failure_frequency"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be between 0 and 1")

    def stable_dict(self) -> dict[str, Any]:
        return asdict(self)
