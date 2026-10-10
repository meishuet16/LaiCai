"""
enums.py — All canonical enum values for the Decision Engine.

These MUST match the shared contracts exactly.
Never add undocumented route values (e.g. "Urgent", "Scheduled").
Ref: RetainIQ_v2_Complete_Requirements.md §7.2, §4.2
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Prediction input enums (from Member 2 / prediction_contract.md)
# ---------------------------------------------------------------------------

class PredictionStatus(str, Enum):
    SCORED              = "scored"
    ABSTAINED           = "abstained"
    KNOWN_CANCELLATION  = "known_cancellation"
    NOT_ELIGIBLE        = "not_eligible"


class ReliabilityStatus(str, Enum):
    SUFFICIENT_EVIDENCE   = "sufficient_evidence"
    LIMITED_EVIDENCE      = "limited_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class DataFreshnessStatus(str, Enum):
    FRESH           = "fresh"
    PARTIALLY_STALE = "partially_stale"
    STALE           = "stale"
    UNKNOWN         = "unknown"


class UncertaintyStatus(str, Enum):
    NOT_QUANTIFIED = "not_quantified"


# ---------------------------------------------------------------------------
# MRR input enums (from Member 1 / mrr_contract.md)
# ---------------------------------------------------------------------------

class MRRCompleteness(str, Enum):
    COMPLETE = "complete"
    PARTIAL  = "partial"
    MISSING  = "missing"


# ---------------------------------------------------------------------------
# Decision Engine output enums
# Ref: §7.2 — exactly 3 operational routes + 2 nonpredictive states
# ---------------------------------------------------------------------------

class RouteEnum(str, Enum):
    # Operational routes
    PRIORITY_REVIEW = "PRIORITY_REVIEW"
    HUMAN_REVIEW    = "HUMAN_REVIEW"
    OBSERVE         = "OBSERVE"
    # Nonpredictive states (not ranked, not scored)
    KNOWN_CANCELLATION = "KNOWN_CANCELLATION"
    NOT_ELIGIBLE       = "NOT_ELIGIBLE"


# ---------------------------------------------------------------------------
# Decision case lifecycle states
# Ref: §7.7 — append-only state machine
# ---------------------------------------------------------------------------

class CaseStatus(str, Enum):
    PROPOSED         = "PROPOSED"
    HUMAN_REVIEWED   = "HUMAN_REVIEWED"
    ASSIGNED         = "ASSIGNED"
    EXECUTED         = "EXECUTED"
    FOLLOW_UP_DUE    = "FOLLOW_UP_DUE"
    CLOSED           = "CLOSED"
    CLOSED_NO_ACTION = "CLOSED_NO_ACTION"
    REJECTED         = "REJECTED"


# ---------------------------------------------------------------------------
# Human decision types
# Ref: §7.7
# ---------------------------------------------------------------------------

class HumanDecisionType(str, Enum):
    APPROVE         = "APPROVE"
    MODIFY          = "MODIFY"
    REJECT          = "REJECT"
    NO_INTERVENTION = "NO_INTERVENTION"
    DEFER           = "DEFER"          # optional


# ---------------------------------------------------------------------------
# Action codes
# Ref: §7.4 — only operational actions exposed for live proposals
# ---------------------------------------------------------------------------

class ActionCode(str, Enum):
    ACCOUNT_CHECK_IN         = "ACCOUNT_CHECK_IN"       # operational
    PAYMENT_RECOVERY         = "PAYMENT_RECOVERY"       # operational
    DATA_INVESTIGATION       = "DATA_INVESTIGATION"     # operational
    NO_INTERVENTION          = "NO_INTERVENTION"        # operational
    PRODUCT_WALKTHROUGH      = "PRODUCT_WALKTHROUGH"    # conditional
    TECH_SUPPORT_ESCALATION  = "TECH_SUPPORT_ESCALATION"  # disabled
    PLAN_REVIEW              = "PLAN_REVIEW"            # simulation_only
    PAUSE                    = "PAUSE"                  # simulation_only
    DOWNGRADE                = "DOWNGRADE"              # simulation_only
    CONDITIONAL_DISCOUNT     = "CONDITIONAL_DISCOUNT"   # simulation_only


class ActionMode(str, Enum):
    OPERATIONAL     = "operational"
    CONDITIONAL     = "conditional"
    SIMULATION_ONLY = "simulation_only"
    DISABLED        = "disabled"


# ---------------------------------------------------------------------------
# Outcome observation states
# Ref: §7.7
# ---------------------------------------------------------------------------

class ObservedStatus(str, Enum):
    ACTIVE              = "active"
    CHURNED             = "churned"
    PENDING_CANCELLATION = "pending_cancellation"
    DOWNGRADED          = "downgraded"
    UNKNOWN             = "unknown"   # NOT a successful retention


# ---------------------------------------------------------------------------
# ROI / scenario label
# Ref: §7.6 — always SCENARIO_ONLY in MVP
# ---------------------------------------------------------------------------

class ScenarioLabel(str, Enum):
    SCENARIO_ONLY            = "SCENARIO_ONLY"
    OBSERVED_OUTCOME         = "OBSERVED_OUTCOME"
    VALIDATED_INCREMENTAL_ROI = "VALIDATED_INCREMENTAL_ROI"  # unavailable MVP


# Aliases for harness compatibility
Route = RouteEnum
HumanDecision = HumanDecisionType

