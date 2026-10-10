"""Canonical, validated Part 2 prediction payload.

This module defines transport and persistence semantics only. It does not train
models, calculate probabilities, or infer intervention effects.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


NonEmptyId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Horizon = Literal["7", "14", "30"]
ExplanationAttribution = dict[str, Any]


class PredictionStatus(str, Enum):
    """Lifecycle state of a forecast snapshot."""

    SCORED = "scored"
    ABSTAINED = "abstained"
    KNOWN_CANCELLATION = "known_cancellation"
    NOT_ELIGIBLE = "not_eligible"


class ReliabilityStatus(str, Enum):
    """Applicability/data-quality status, not a confidence percentage."""

    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    LIMITED_EVIDENCE = "limited_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class FreshnessStatus(str, Enum):
    """Status of the source data used for the snapshot."""

    FRESH = "fresh"
    PARTIALLY_STALE = "partially_stale"
    STALE = "stale"
    UNKNOWN = "unknown"


class UncertaintyStatus(str, Enum):
    """Supported uncertainty state until validated intervals exist."""

    NOT_QUANTIFIED = "not_quantified"


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Reliability(_ContractModel):
    status: ReliabilityStatus
    reasons: list[str] = Field(default_factory=list)


class DataFreshness(_ContractModel):
    status: FreshnessStatus
    input_data_as_of: AwareDatetime | None = None
    stale_sources: list[str] = Field(default_factory=list)


class Uncertainty(_ContractModel):
    """Explicitly non-quantified uncertainty contract.

    The restrictive literals intentionally reject unsupported numerical
    confidence or interval payloads until they are defensibly validated.
    """

    status: Literal["not_quantified"] = "not_quantified"
    method: Literal["none"] = "none"
    intervals: None = None


class PredictionOutput(_ContractModel):
    """Canonical immutable account-level prediction snapshot.

    ``prediction_id`` identifies this account forecast snapshot. The separate
    ``prediction_run_id`` identifies the inference batch/job that produced it.
    Persistence is responsible for enforcing uniqueness and tenant scoping.
    """

    tenant_id: NonEmptyId
    customer_id: NonEmptyId
    prediction_id: NonEmptyId
    prediction_run_id: NonEmptyId
    as_of: AwareDatetime
    generated_at: AwareDatetime
    status: PredictionStatus
    p_churn_7d: float | None = Field(default=None, ge=0.0, le=1.0)
    p_churn_14d: float | None = Field(default=None, ge=0.0, le=1.0)
    p_churn_30d: float | None = Field(default=None, ge=0.0, le=1.0)
    feature_version: NonEmptyId
    model_version: NonEmptyId
    calibration_version: NonEmptyId
    label_policy_version: NonEmptyId
    reliability: Reliability
    data_freshness: DataFreshness
    uncertainty: Uncertainty
    explanations_by_horizon: dict[Horizon, list[ExplanationAttribution]] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_prediction_contract(self) -> Self:
        if self.prediction_id == self.prediction_run_id:
            raise ValueError(
                "prediction_id and prediction_run_id must remain distinct identities"
            )

        probabilities = (
            self.p_churn_7d,
            self.p_churn_14d,
            self.p_churn_30d,
        )

        if self.status is PredictionStatus.SCORED:
            if any(probability is None for probability in probabilities):
                raise ValueError(
                    "scored predictions require p_churn_7d, p_churn_14d, and p_churn_30d"
                )
            p7, p14, p30 = probabilities
            assert p7 is not None and p14 is not None and p30 is not None
            if not p7 <= p14 <= p30:
                raise ValueError(
                    "scored probabilities must satisfy p_churn_7d <= "
                    "p_churn_14d <= p_churn_30d"
                )
        elif any(probability is not None for probability in probabilities):
            raise ValueError(
                "abstained, known_cancellation, and not_eligible predictions "
                "must have null churn probabilities"
            )

        return self


__all__ = [
    "DataFreshness",
    "ExplanationAttribution",
    "FreshnessStatus",
    "PredictionOutput",
    "PredictionStatus",
    "Reliability",
    "ReliabilityStatus",
    "Uncertainty",
    "UncertaintyStatus",
]
