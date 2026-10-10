"""Append-only reconciliation of frozen predictions with observed outcomes.

This module is the Part 4 feedback boundary owned by Member 2.  It consumes
canonical :class:`PredictionOutput` snapshots and the existing
:class:`ChurnLabel` builder output.  It does not create a new churn definition,
mutate predictions, persist to a database, estimate intervention effects, or
trigger model training.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json
from typing import Iterable, Literal, Sequence

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .contracts import PredictionOutput, PredictionStatus
from .label_builder import (
    ChurnLabel,
    LabelReasonCode,
    LabelStatus,
    SUPPORTED_HORIZONS,
)


class FeedbackStatus(str, Enum):
    """Maturity of one prediction-as-of/horizon outcome."""

    PENDING = "PENDING"
    MATURE_POSITIVE = "MATURE_POSITIVE"
    MATURE_NEGATIVE = "MATURE_NEGATIVE"
    INCOMPLETE = "INCOMPLETE"
    INELIGIBLE = "INELIGIBLE"


class FeedbackProvenanceStatus(str, Enum):
    AUTHORIZED_REAL = "authorized_real"
    SYNTHETIC_TEST_ONLY = "synthetic_test_only"
    UNVERIFIED = "unverified"


class OutcomeReasonCode(str, Enum):
    HORIZON_NOT_MATURE = "horizon_not_mature"
    POSITIVE_OUTCOME_VERIFIED = "positive_outcome_verified"
    NEGATIVE_FULL_HORIZON_VERIFIED = "negative_full_horizon_verified"
    OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF = (
        "outcome_not_available_by_evaluation_cutoff"
    )
    OUTCOME_COVERAGE_INCOMPLETE = "outcome_coverage_incomplete"
    UNKNOWN_OUTCOME = "unknown_outcome"
    UNVERIFIED_PROVENANCE = "unverified_provenance"
    CONFLICTING_OUTCOME_EVIDENCE = "conflicting_outcome_evidence"
    UNRESOLVED_MULTI_SUBSCRIPTION_POLICY = (
        "unresolved_multi_subscription_policy"
    )
    KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF = (
        "known_cancellation_at_prediction_cutoff"
    )
    NOT_ELIGIBLE_AT_PREDICTION_CUTOFF = "not_eligible_at_prediction_cutoff"
    ALREADY_TERMINATED_AT_PREDICTION_CUTOFF = (
        "already_terminated_at_prediction_cutoff"
    )
    EXCLUDED_BY_LABEL_POLICY = "excluded_by_label_policy"
    UNSUPPORTED_BY_LABEL_POLICY = "unsupported_by_label_policy"
    SOURCE_CORRECTION = "source_correction"
    NEW_OBSERVATION_REVISION = "new_observation_revision"
    SYNTHETIC_FEEDBACK_NOT_AUTHORIZED_FOR_LEARNING = (
        "synthetic_feedback_not_authorized_for_learning"
    )
    LEARNING_OUTCOME_NOT_MATURE = "learning_outcome_not_mature"
    LEARNING_OUTCOME_RECORDED_AFTER_CUTOFF = (
        "learning_outcome_recorded_after_cutoff"
    )
    LEARNING_POLICY_MISMATCH = "learning_policy_mismatch"
    LEARNING_PROVENANCE_INSUFFICIENT = "learning_provenance_insufficient"
    LEARNING_COVERAGE_INSUFFICIENT = "learning_coverage_insufficient"
    LEARNING_UNRESOLVED_POLICY = "learning_unresolved_policy"
    ACTION_CAUSALITY_NOT_ESTABLISHED = "action_causality_not_established"


class ActionApprovalState(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    NOT_RECORDED = "not_recorded"


class InterventionExposureStatus(str, Enum):
    NONE = "none"
    KNOWN = "known"
    UNKNOWN = "unknown"


class LearningEligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class _FeedbackModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OutcomeEvidence(_FeedbackModel):
    """Explicit evidence supplied by the canonical source adapter.

    ``source_available_at`` is deliberately optional.  Missing availability is
    not treated as historical proof; it prevents a mature status when the
    evidence cannot be placed before the requested evaluation cutoff.
    """

    provenance_status: FeedbackProvenanceStatus
    source_evidence_refs: tuple[str, ...] = ()
    source_available_at: AwareDatetime | None = None
    observed_from: AwareDatetime
    observed_through: AwareDatetime
    complete_through: AwareDatetime | None = None
    verified: bool = False
    coverage_complete: bool = False
    conflicting_evidence: bool = False
    unresolved_multi_subscription_policy: bool = False
    intervention_exposure: InterventionExposureStatus = (
        InterventionExposureStatus.UNKNOWN
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> "OutcomeEvidence":
        if self.observed_through < self.observed_from:
            raise ValueError("observed_through must not precede observed_from")
        if self.complete_through is not None and self.complete_through < self.observed_from:
            raise ValueError("complete_through must not precede observed_from")
        if self.provenance_status is FeedbackProvenanceStatus.AUTHORIZED_REAL and not self.verified:
            raise ValueError("authorized real evidence must be verified")
        if self.source_available_at is not None and self.source_available_at < self.observed_from:
            raise ValueError("source_available_at must not precede observed_from")
        return self


class FeedbackReconciliationRequest(_FeedbackModel):
    """One deterministic append-only reconciliation request."""

    feedback_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    prediction_run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    prediction_as_of: AwareDatetime
    horizon_days: int
    churn_label: ChurnLabel
    evaluation_as_of: AwareDatetime
    evidence: OutcomeEvidence
    reconciliation_policy_version: str = Field(min_length=1)
    reconciled_at: AwareDatetime
    supersedes_feedback_id: str | None = Field(default=None, min_length=1)
    correction_reason: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> "FeedbackReconciliationRequest":
        if self.horizon_days not in SUPPORTED_HORIZONS:
            raise ValueError("horizon_days must be one of 7, 14, or 30")
        if self.prediction_as_of != self.churn_label.as_of:
            raise ValueError("prediction_as_of must match churn_label.as_of")
        if self.horizon_days != self.churn_label.horizon_days:
            raise ValueError("horizon_days must match churn_label.horizon_days")
        if self.tenant_id != self.churn_label.tenant_id:
            raise ValueError("tenant_id must match churn_label.tenant_id")
        if self.customer_id != self.churn_label.customer_id:
            raise ValueError("customer_id must match churn_label.customer_id")
        if self.evaluation_as_of < self.prediction_as_of:
            raise ValueError("evaluation_as_of must not precede prediction_as_of")
        if self.supersedes_feedback_id and not (self.correction_reason or "").strip():
            raise ValueError("correction_reason is required for a source correction")
        return self


class PredictionFeedback(_FeedbackModel):
    """Immutable, serializable outcome feedback for one prediction horizon.

    ``prediction_snapshot`` is the original canonical object, copied into the
    record at reconciliation time.  Outcome fields are append-only metadata;
    they never rewrite that nested prediction.
    """

    feedback_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    supersedes_feedback_id: str | None = Field(default=None, min_length=1)
    revision_reason: str | None = None
    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    prediction_run_id: str = Field(min_length=1)
    prediction_as_of: AwareDatetime
    horizon_days: int
    prediction_snapshot: PredictionOutput
    model_version: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    calibration_version: str = Field(min_length=1)
    label_policy_version: str = Field(min_length=1)
    churn_label: ChurnLabel
    feedback_status: FeedbackStatus
    label: Literal[0, 1] | None = None
    churn_effective_at: AwareDatetime | None = None
    evaluation_as_of: AwareDatetime
    outcome_observed_through: AwareDatetime
    outcome_coverage: OutcomeEvidence
    source_evidence_refs: tuple[str, ...] = ()
    reconciliation_policy_version: str = Field(min_length=1)
    reconciliation_timestamp: AwareDatetime
    reason_codes: tuple[OutcomeReasonCode, ...] = ()
    provenance_status: FeedbackProvenanceStatus
    synthetic_test_only: bool
    input_fingerprint: str = Field(min_length=64, max_length=64)

    @property
    def outcome_status(self) -> FeedbackStatus:
        """Compatibility alias for callers using outcome terminology."""

        return self.feedback_status

    @model_validator(mode="after")
    def validate_identity_and_state(self) -> "PredictionFeedback":
        if self.horizon_days not in SUPPORTED_HORIZONS:
            raise ValueError("horizon_days must be one of 7, 14, or 30")
        if self.prediction_id != self.prediction_snapshot.prediction_id:
            raise ValueError("prediction_id must match the frozen prediction snapshot")
        if self.prediction_run_id != self.prediction_snapshot.prediction_run_id:
            raise ValueError("prediction_run_id must match the frozen prediction snapshot")
        if self.tenant_id != self.prediction_snapshot.tenant_id:
            raise ValueError("tenant_id must match the frozen prediction snapshot")
        if self.customer_id != self.prediction_snapshot.customer_id:
            raise ValueError("customer_id must match the frozen prediction snapshot")
        if self.prediction_as_of != self.prediction_snapshot.as_of:
            raise ValueError("prediction_as_of must match the frozen prediction snapshot")
        if self.model_version != self.prediction_snapshot.model_version:
            raise ValueError("model_version must match the frozen prediction snapshot")
        if self.feature_version != self.prediction_snapshot.feature_version:
            raise ValueError("feature_version must match the frozen prediction snapshot")
        if self.calibration_version != self.prediction_snapshot.calibration_version:
            raise ValueError("calibration_version must match the frozen prediction snapshot")
        if self.label_policy_version != self.prediction_snapshot.label_policy_version:
            raise ValueError("label_policy_version must match the frozen prediction snapshot")
        if self.prediction_as_of != self.churn_label.as_of:
            raise ValueError("prediction_as_of must match the churn label")
        if self.horizon_days != self.churn_label.horizon_days:
            raise ValueError("horizon_days must match the churn label")
        if self.evaluation_as_of < self.prediction_as_of:
            raise ValueError("evaluation_as_of must not precede prediction_as_of")
        if self.reconciliation_timestamp < self.prediction_as_of:
            raise ValueError("reconciliation_timestamp must not precede prediction_as_of")
        if self.label is not None:
            if self.feedback_status is FeedbackStatus.MATURE_POSITIVE and self.label != 1:
                raise ValueError("mature positive feedback requires label=1")
            if self.feedback_status is FeedbackStatus.MATURE_NEGATIVE and self.label != 0:
                raise ValueError("mature negative feedback requires label=0")
        elif self.feedback_status in {
            FeedbackStatus.MATURE_POSITIVE,
            FeedbackStatus.MATURE_NEGATIVE,
        }:
            raise ValueError("mature feedback requires a concrete label")
        if self.feedback_status is FeedbackStatus.MATURE_POSITIVE and self.churn_effective_at is None:
            raise ValueError("mature positive feedback requires churn_effective_at")
        if self.feedback_status is not FeedbackStatus.MATURE_POSITIVE and self.churn_effective_at is not None:
            raise ValueError("only mature positive feedback may contain churn_effective_at")
        if self.provenance_status is FeedbackProvenanceStatus.SYNTHETIC_TEST_ONLY and not self.synthetic_test_only:
            raise ValueError("synthetic provenance requires synthetic_test_only")
        if self.provenance_status is FeedbackProvenanceStatus.AUTHORIZED_REAL and self.synthetic_test_only:
            raise ValueError("authorized real feedback cannot be synthetic_test_only")
        return self

    def original_prediction(self) -> PredictionOutput:
        """Return a deep copy so callers cannot mutate the ledger snapshot."""

        return deepcopy(self.prediction_snapshot)


class LearningEligibilityResult(_FeedbackModel):
    status: LearningEligibilityStatus
    feedback_id: str = Field(min_length=1)
    training_cutoff: AwareDatetime
    reason_codes: tuple[OutcomeReasonCode, ...] = ()
    explanation: str = Field(min_length=1)

    @property
    def admissible(self) -> bool:
        return self.status is LearningEligibilityStatus.ELIGIBLE


class ActionFeedbackCompatibilityRecord(_FeedbackModel):
    """Read-only handoff shape for Part 3 action history.

    This is not a decision or causal-outcome record.  The false literal is
    intentional: observed churn/retention is never asserted to be caused by an
    intervention here.
    """

    tenant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    prediction_id: str = Field(min_length=1)
    action_id: str | None = Field(default=None, min_length=1)
    action_type: str = Field(min_length=1)
    approval_state: ActionApprovalState
    actual_execution_at: AwareDatetime | None = None
    outcome_observation_at: AwareDatetime | None = None
    evidence_refs: tuple[str, ...] = ()
    intervention_exposure: InterventionExposureStatus = (
        InterventionExposureStatus.UNKNOWN
    )
    causal_effect_established: Literal[False] = False


class UnknownPredictionError(ValueError):
    """Raised when feedback references no registered immutable prediction."""


class FeedbackScopeError(ValueError):
    """Raised when feedback crosses tenant or customer boundaries."""


class ConflictingFeedbackError(ValueError):
    """Raised when a feedback identifier is reused with different inputs."""


def _unique_reasons(values: Iterable[OutcomeReasonCode]) -> tuple[OutcomeReasonCode, ...]:
    return tuple(dict.fromkeys(values))


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _request_fingerprint(request: FeedbackReconciliationRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"reconciled_at"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _maturity_blockers(
    label: ChurnLabel,
    evidence: OutcomeEvidence,
    evaluation_as_of: datetime,
) -> tuple[OutcomeReasonCode, ...]:
    reasons: list[OutcomeReasonCode] = []
    if label.evaluation_as_of > evaluation_as_of or label.label_generated_at > evaluation_as_of:
        reasons.append(OutcomeReasonCode.OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF)
    if evidence.source_available_at is None or evidence.source_available_at > evaluation_as_of:
        reasons.append(OutcomeReasonCode.OUTCOME_NOT_AVAILABLE_BY_EVALUATION_CUTOFF)
    if evidence.provenance_status is FeedbackProvenanceStatus.UNVERIFIED or not evidence.verified:
        reasons.append(OutcomeReasonCode.UNVERIFIED_PROVENANCE)
    if not evidence.source_evidence_refs and not label.source_evidence_refs:
        reasons.append(OutcomeReasonCode.OUTCOME_COVERAGE_INCOMPLETE)
    if evidence.conflicting_evidence:
        reasons.append(OutcomeReasonCode.CONFLICTING_OUTCOME_EVIDENCE)
    if evidence.unresolved_multi_subscription_policy:
        reasons.append(OutcomeReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY)
    return _unique_reasons(reasons)


def _reconcile_label(
    prediction: PredictionOutput,
    label: ChurnLabel,
    evidence: OutcomeEvidence,
    evaluation_as_of: datetime,
) -> tuple[FeedbackStatus, Literal[0, 1] | None, tuple[OutcomeReasonCode, ...]]:
    """Map one existing ChurnLabel without defining a second churn policy."""

    horizon_end = label.as_of + timedelta(days=int(label.horizon_days))
    horizon_mature = evaluation_as_of >= horizon_end

    if prediction.status is PredictionStatus.KNOWN_CANCELLATION:
        return (
            FeedbackStatus.INELIGIBLE,
            None,
            (OutcomeReasonCode.KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF,),
        )
    if prediction.status is PredictionStatus.NOT_ELIGIBLE:
        return (
            FeedbackStatus.INELIGIBLE,
            None,
            (OutcomeReasonCode.NOT_ELIGIBLE_AT_PREDICTION_CUTOFF,),
        )
    if label.label_status is LabelStatus.EXCLUDED:
        reasons = [OutcomeReasonCode.EXCLUDED_BY_LABEL_POLICY]
        if LabelReasonCode.KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF in label.reason_codes:
            reasons.append(OutcomeReasonCode.KNOWN_CANCELLATION_AT_PREDICTION_CUTOFF)
        if LabelReasonCode.ALREADY_TERMINATED_AT_PREDICTION_CUTOFF in label.reason_codes:
            reasons.append(OutcomeReasonCode.ALREADY_TERMINATED_AT_PREDICTION_CUTOFF)
        return FeedbackStatus.INELIGIBLE, None, _unique_reasons(reasons)

    blockers = _maturity_blockers(label, evidence, evaluation_as_of)
    if blockers:
        hard_blockers = {
            OutcomeReasonCode.CONFLICTING_OUTCOME_EVIDENCE,
            OutcomeReasonCode.UNRESOLVED_MULTI_SUBSCRIPTION_POLICY,
            OutcomeReasonCode.UNVERIFIED_PROVENANCE,
        }
        if any(reason in hard_blockers for reason in blockers):
            return FeedbackStatus.INCOMPLETE, None, blockers
        if horizon_mature:
            return FeedbackStatus.INCOMPLETE, None, blockers
        return (
            FeedbackStatus.PENDING,
            None,
            _unique_reasons((*blockers, OutcomeReasonCode.HORIZON_NOT_MATURE)),
        )

    if label.label_status is LabelStatus.POSITIVE and label.label == 1:
        if label.churn_effective_at is None:
            return FeedbackStatus.INCOMPLETE, None, (OutcomeReasonCode.OUTCOME_COVERAGE_INCOMPLETE,)
        if evidence.observed_through < label.churn_effective_at:
            return FeedbackStatus.INCOMPLETE, None, (OutcomeReasonCode.OUTCOME_COVERAGE_INCOMPLETE,)
        return (
            FeedbackStatus.MATURE_POSITIVE,
            1,
            (OutcomeReasonCode.POSITIVE_OUTCOME_VERIFIED,),
        )

    if label.label_status is LabelStatus.NEGATIVE and label.label == 0:
        if not horizon_mature:
            return FeedbackStatus.PENDING, None, (OutcomeReasonCode.HORIZON_NOT_MATURE,)
        if not evidence.coverage_complete or evidence.observed_through < horizon_end:
            return FeedbackStatus.INCOMPLETE, None, (OutcomeReasonCode.OUTCOME_COVERAGE_INCOMPLETE,)
        if evidence.complete_through is not None and evidence.complete_through < horizon_end:
            return FeedbackStatus.INCOMPLETE, None, (OutcomeReasonCode.OUTCOME_COVERAGE_INCOMPLETE,)
        return (
            FeedbackStatus.MATURE_NEGATIVE,
            0,
            (OutcomeReasonCode.NEGATIVE_FULL_HORIZON_VERIFIED,),
        )

    if label.label_status is LabelStatus.UNSUPPORTED:
        return FeedbackStatus.INCOMPLETE, None, (OutcomeReasonCode.UNSUPPORTED_BY_LABEL_POLICY,)
    if label.label_status is LabelStatus.UNKNOWN:
        return (
            FeedbackStatus.PENDING if not horizon_mature else FeedbackStatus.INCOMPLETE,
            None,
            (OutcomeReasonCode.HORIZON_NOT_MATURE if not horizon_mature else OutcomeReasonCode.UNKNOWN_OUTCOME,),
        )
    return FeedbackStatus.INCOMPLETE, None, (OutcomeReasonCode.UNKNOWN_OUTCOME,)


def _build_feedback(
    prediction: PredictionOutput,
    request: FeedbackReconciliationRequest,
    *,
    revision_number: int,
    extra_reasons: Sequence[OutcomeReasonCode] = (),
) -> PredictionFeedback:
    status, label_value, reasons = _reconcile_label(
        prediction,
        request.churn_label,
        request.evidence,
        request.evaluation_as_of,
    )
    source_refs = tuple(
        dict.fromkeys(
            (*request.churn_label.source_evidence_refs, *request.evidence.source_evidence_refs)
        )
    )
    return PredictionFeedback(
        feedback_id=request.feedback_id,
        revision_number=revision_number,
        supersedes_feedback_id=request.supersedes_feedback_id,
        revision_reason=request.correction_reason,
        tenant_id=prediction.tenant_id,
        customer_id=prediction.customer_id,
        prediction_id=prediction.prediction_id,
        prediction_run_id=prediction.prediction_run_id,
        prediction_as_of=prediction.as_of,
        horizon_days=request.horizon_days,
        prediction_snapshot=deepcopy(prediction),
        model_version=prediction.model_version,
        feature_version=prediction.feature_version,
        calibration_version=prediction.calibration_version,
        label_policy_version=prediction.label_policy_version,
        churn_label=request.churn_label,
        feedback_status=status,
        label=label_value,
        churn_effective_at=(
            request.churn_label.churn_effective_at
            if status is FeedbackStatus.MATURE_POSITIVE
            else None
        ),
        evaluation_as_of=request.evaluation_as_of,
        outcome_observed_through=request.evidence.observed_through,
        outcome_coverage=request.evidence,
        source_evidence_refs=source_refs,
        reconciliation_policy_version=request.reconciliation_policy_version,
        reconciliation_timestamp=request.reconciled_at,
        reason_codes=_unique_reasons((*reasons, *extra_reasons)),
        provenance_status=request.evidence.provenance_status,
        synthetic_test_only=(
            request.evidence.provenance_status
            is FeedbackProvenanceStatus.SYNTHETIC_TEST_ONLY
        ),
        input_fingerprint=_request_fingerprint(request),
    )


class InMemoryOutcomeReconciliationStore:
    """Synthetic/test ledger with immutable prediction registration.

    A production adapter can implement the same operations with append-only
    storage.  This class intentionally does not provide database or queue
    behavior.
    """

    def __init__(self, predictions: Iterable[PredictionOutput] = ()) -> None:
        self._predictions: dict[tuple[str, str], PredictionOutput] = {}
        self._feedback: dict[str, PredictionFeedback] = {}
        self._revisions: dict[tuple[str, str, str, int], list[str]] = {}
        for prediction in predictions:
            self.register_prediction(prediction)

    def register_prediction(self, prediction: PredictionOutput) -> None:
        key = (prediction.tenant_id, prediction.prediction_id)
        existing = self._predictions.get(key)
        if existing is not None and existing.model_dump(mode="json") != prediction.model_dump(mode="json"):
            raise ValueError("prediction_id is immutable and cannot be registered with different content")
        if existing is None:
            self._predictions[key] = deepcopy(prediction)

    def prediction_for(self, tenant_id: str, prediction_id: str) -> PredictionOutput:
        prediction = self._predictions.get((tenant_id, prediction_id))
        if prediction is not None:
            return deepcopy(prediction)
        if any(existing_id == prediction_id for _, existing_id in self._predictions):
            raise FeedbackScopeError("prediction_id belongs to a different tenant")
        raise UnknownPredictionError("prediction_id is not registered")

    def reconcile(self, request: FeedbackReconciliationRequest) -> PredictionFeedback:
        prediction = self.prediction_for(request.tenant_id, request.prediction_id)
        if request.customer_id != prediction.customer_id:
            raise FeedbackScopeError("customer_id does not match the registered prediction")
        if request.prediction_run_id != prediction.prediction_run_id:
            raise ValueError("prediction_run_id does not match the registered prediction")
        if request.prediction_as_of != prediction.as_of:
            raise ValueError("prediction_as_of does not match the registered prediction")

        fingerprint = _request_fingerprint(request)
        existing = self._feedback.get(request.feedback_id)
        if existing is not None:
            if existing.input_fingerprint == fingerprint:
                return existing.model_copy(deep=True)
            raise ConflictingFeedbackError(
                "feedback_id already exists with different reconciliation inputs"
            )

        revision_key = (
            prediction.tenant_id,
            prediction.customer_id,
            prediction.prediction_id,
            request.horizon_days,
        )
        previous_ids = self._revisions.get(revision_key, [])
        revision_number = len(previous_ids) + 1
        extra_reasons: tuple[OutcomeReasonCode, ...] = ()
        if request.supersedes_feedback_id is not None:
            previous = self._feedback.get(request.supersedes_feedback_id)
            if previous is None:
                raise ValueError("supersedes_feedback_id must reference existing feedback")
            if (
                previous.prediction_id != prediction.prediction_id
                or previous.tenant_id != prediction.tenant_id
                or previous.customer_id != prediction.customer_id
                or previous.horizon_days != request.horizon_days
            ):
                raise FeedbackScopeError("source correction crosses feedback identity scope")
            extra_reasons = (OutcomeReasonCode.SOURCE_CORRECTION,)
        elif previous_ids:
            extra_reasons = (OutcomeReasonCode.NEW_OBSERVATION_REVISION,)

        feedback = _build_feedback(
            prediction,
            request,
            revision_number=revision_number,
            extra_reasons=extra_reasons,
        )
        self._feedback[feedback.feedback_id] = feedback
        self._revisions.setdefault(revision_key, []).append(feedback.feedback_id)
        return feedback.model_copy(deep=True)

    def feedback_for(self, feedback_id: str) -> PredictionFeedback:
        try:
            return self._feedback[feedback_id].model_copy(deep=True)
        except KeyError as exc:
            raise KeyError("unknown feedback_id") from exc

    def history_for(
        self, tenant_id: str, prediction_id: str, horizon_days: int
    ) -> tuple[PredictionFeedback, ...]:
        ids = self._revisions.get(
            (tenant_id, self.prediction_for(tenant_id, prediction_id).customer_id, prediction_id, horizon_days),
            [],
        )
        return tuple(self._feedback[item].model_copy(deep=True) for item in ids)

    def latest_feedback_as_of(
        self,
        tenant_id: str,
        prediction_id: str,
        horizon_days: int,
        view_as_of: datetime,
    ) -> PredictionFeedback | None:
        if not _is_aware(view_as_of):
            raise ValueError("view_as_of must be timezone-aware")
        history = self.history_for(tenant_id, prediction_id, horizon_days)
        visible = [
            item
            for item in history
            if item.reconciliation_timestamp <= view_as_of
            and item.evaluation_as_of <= view_as_of
        ]
        if not visible:
            return None
        return max(visible, key=lambda item: item.revision_number).model_copy(deep=True)

    def all_feedback(self) -> tuple[PredictionFeedback, ...]:
        return tuple(item.model_copy(deep=True) for item in self._feedback.values())


def assess_learning_eligibility(
    feedback: PredictionFeedback,
    *,
    training_cutoff: datetime,
    expected_label_policy_version: str | None = None,
) -> LearningEligibilityResult:
    """Check admissibility only; never start training or promote a model."""

    if not _is_aware(training_cutoff):
        raise ValueError("training_cutoff must be timezone-aware")
    reasons: list[OutcomeReasonCode] = []
    if feedback.feedback_status not in {
        FeedbackStatus.MATURE_POSITIVE,
        FeedbackStatus.MATURE_NEGATIVE,
    }:
        reasons.append(OutcomeReasonCode.LEARNING_OUTCOME_NOT_MATURE)
    if feedback.prediction_snapshot.status in {
        PredictionStatus.KNOWN_CANCELLATION,
        PredictionStatus.NOT_ELIGIBLE,
    }:
        reasons.append(OutcomeReasonCode.NOT_ELIGIBLE_AT_PREDICTION_CUTOFF)
    if feedback.provenance_status is not FeedbackProvenanceStatus.AUTHORIZED_REAL:
        reasons.append(OutcomeReasonCode.LEARNING_PROVENANCE_INSUFFICIENT)
        if feedback.synthetic_test_only:
            reasons.append(OutcomeReasonCode.SYNTHETIC_FEEDBACK_NOT_AUTHORIZED_FOR_LEARNING)
    if expected_label_policy_version is not None:
        if feedback.churn_label.label_policy_version != expected_label_policy_version:
            reasons.append(OutcomeReasonCode.LEARNING_POLICY_MISMATCH)
        if feedback.prediction_snapshot.label_policy_version != expected_label_policy_version:
            reasons.append(OutcomeReasonCode.LEARNING_POLICY_MISMATCH)
    elif feedback.prediction_snapshot.label_policy_version != feedback.churn_label.label_policy_version:
        reasons.append(OutcomeReasonCode.LEARNING_POLICY_MISMATCH)
    if feedback.outcome_coverage.unresolved_multi_subscription_policy:
        reasons.append(OutcomeReasonCode.LEARNING_UNRESOLVED_POLICY)
    if feedback.outcome_coverage.conflicting_evidence:
        reasons.append(OutcomeReasonCode.CONFLICTING_OUTCOME_EVIDENCE)
    if not feedback.outcome_coverage.verified or not feedback.source_evidence_refs:
        reasons.append(OutcomeReasonCode.LEARNING_COVERAGE_INSUFFICIENT)
    if feedback.outcome_coverage.source_available_at is None or feedback.outcome_coverage.source_available_at > training_cutoff:
        reasons.append(OutcomeReasonCode.LEARNING_OUTCOME_RECORDED_AFTER_CUTOFF)
    if feedback.evaluation_as_of > training_cutoff or feedback.reconciliation_timestamp > training_cutoff:
        reasons.append(OutcomeReasonCode.LEARNING_OUTCOME_RECORDED_AFTER_CUTOFF)
    if feedback.prediction_as_of > training_cutoff:
        reasons.append(OutcomeReasonCode.LEARNING_OUTCOME_RECORDED_AFTER_CUTOFF)

    unique = _unique_reasons(reasons)
    if unique:
        return LearningEligibilityResult(
            status=LearningEligibilityStatus.INELIGIBLE,
            feedback_id=feedback.feedback_id,
            training_cutoff=training_cutoff,
            reason_codes=unique,
            explanation="Feedback is not admissible for supervised learning at this cutoff.",
        )
    return LearningEligibilityResult(
        status=LearningEligibilityStatus.ELIGIBLE,
        feedback_id=feedback.feedback_id,
        training_cutoff=training_cutoff,
        reason_codes=(),
        explanation="Verified mature feedback is admissible for supervised learning at this cutoff.",
    )


def feedback_labels_for_historical_evaluation(
    feedback: Sequence[PredictionFeedback],
    *,
    evaluation_as_of: datetime,
) -> tuple[ChurnLabel, ...]:
    """Expose mature labels to the existing evaluator without new metrics."""

    if not _is_aware(evaluation_as_of):
        raise ValueError("evaluation_as_of must be timezone-aware")
    selected: dict[tuple[str, str, datetime, int], PredictionFeedback] = {}
    for item in feedback:
        if item.reconciliation_timestamp > evaluation_as_of or item.evaluation_as_of > evaluation_as_of:
            continue
        if item.feedback_status not in {
            FeedbackStatus.MATURE_POSITIVE,
            FeedbackStatus.MATURE_NEGATIVE,
        }:
            continue
        key = (item.tenant_id, item.customer_id, item.prediction_as_of, item.horizon_days)
        previous = selected.get(key)
        if previous is None or item.revision_number > previous.revision_number:
            selected[key] = item
    return tuple(
        selected[key].churn_label
        for key in sorted(selected, key=lambda value: (value[0], value[1], value[2], value[3]))
    )


__all__ = [
    "ActionApprovalState",
    "ActionFeedbackCompatibilityRecord",
    "ConflictingFeedbackError",
    "FeedbackProvenanceStatus",
    "FeedbackReconciliationRequest",
    "FeedbackScopeError",
    "FeedbackStatus",
    "InMemoryOutcomeReconciliationStore",
    "InterventionExposureStatus",
    "LearningEligibilityResult",
    "LearningEligibilityStatus",
    "OutcomeEvidence",
    "OutcomeReasonCode",
    "PredictionFeedback",
    "UnknownPredictionError",
    "assess_learning_eligibility",
    "feedback_labels_for_historical_evaluation",
]
