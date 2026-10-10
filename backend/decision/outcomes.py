"""
outcomes.py — Outcome observation recording at 7, 14, and 30-day horizons (§7.7).

RULES (§7.7):
  1. Follow-up Horizons: Explicitly at 7, 14, and 30 days after anchor.
  2. Observed states: ACTIVE, CHURNED, PENDING_CANCELLATION, DOWNGRADED, UNKNOWN.
  3. Evidence Integrity: UNKNOWN / incomplete observation is NOT a successful retention outcome.
  4. Causal Guardrail: Active observation alone does NOT prove intervention effectiveness.
     Response note must strictly reflect: 'active_is_not_proof_of_retention_effectiveness'.
"""

from __future__ import annotations
from datetime import datetime, timezone
import uuid

from .enums import ObservedStatus
from .models import HistoryEvent, OutcomeObservationRequest, OutcomeObservationResponse


class OutcomeError(Exception):
    """Domain error in outcome observation recording."""
    pass


def record_outcome_observation(
    case_id: str,
    request: OutcomeObservationRequest,
) -> tuple[OutcomeObservationResponse, HistoryEvent]:
    """
    Validate and record an outcome observation event.

    Args:
        case_id: Decision case identifier.
        request: Validated observation payload.

    Returns:
        (OutcomeObservationResponse, HistoryEvent to append to audit history)
    """
    if request.horizon_days not in (7, 14, 30):
        raise OutcomeError(f"horizon_days must be 7, 14, or 30; received {request.horizon_days}")

    valid_coverages = ("complete", "partial", "unknown")
    if request.observation_coverage not in valid_coverages:
        raise OutcomeError(
            f"observation_coverage must be one of {valid_coverages}; received {request.observation_coverage}"
        )

    now = datetime.now(timezone.utc)
    obs_id = f"obs_{uuid.uuid4().hex[:8]}"

    # §7.7 Guardrail note
    note = "active_is_not_proof_of_retention_effectiveness"
    if request.observed_status == ObservedStatus.UNKNOWN or request.observation_coverage == "unknown":
        note = "unknown_status_or_coverage_is_not_a_successful_retention_outcome"

    response = OutcomeObservationResponse(
        observation_id=obs_id,
        case_id=case_id,
        horizon_days=request.horizon_days,
        observed_status=request.observed_status,
        observation_coverage=request.observation_coverage,
        observed_at=now,
        note=note,
    )

    history_event = HistoryEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        case_id=case_id,
        event_type="OUTCOME_OBSERVED",
        occurred_at=now,
        actor="system",
        details={
            "observation_id": obs_id,
            "horizon_days": request.horizon_days,
            "observed_status": request.observed_status.value,
            "observation_coverage": request.observation_coverage,
            "source_ref": request.source_ref,
            "follow_up_anchor": request.follow_up_anchor.isoformat(),
        },
    )

    return response, history_event
