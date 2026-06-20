"""
Module 2: Severity Categorization Matrix
Evaluates each detected violation and assigns a risk severity tier.

Tier derivation is grounded in the compliance policy:
- CRITICAL SAFETY NOTICE → CRITICAL tier (Unauthorized Intervention, Forklift Overload)
- WARNING → HIGH tier (Safe Walkway Violation, Opened Panel Cover)

Within each policy-signal tier, contextual factors (confidence, personnel proximity)
further modulate whether a detection is LOW/MED vs the policy-maximum tier.
"""

from typing import Literal

SeverityTier = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Policy-grounded severity mapping
# Derived from Section 3.3.2 (WARNING), Section 4.3.2 (CRITICAL SAFETY NOTICE),
# Section 5.2.2 (WARNING), Section 6.3.2 (CRITICAL SAFETY NOTICE)
POLICY_SEVERITY_MAP: dict[int, dict] = {
    0: {
        # Safe Walkway Violation — Section 3.3.2
        # "WARNING" callout: highest-frequency behavior, forklift/machinery proximity risk
        "signal": "WARNING",
        "max_tier": "HIGH",
        "rationale": (
            "Safe Walkway Violation flagged as WARNING in Section 3.3.2. "
            "Highest-frequency unsafe behavior; places personnel near forklift/machinery hazards."
        ),
    },
    1: {
        # Unauthorized Intervention — Section 4.3.2
        # "CRITICAL SAFETY NOTICE": direct equipment interaction without authorization
        "signal": "CRITICAL SAFETY NOTICE",
        "max_tier": "CRITICAL",
        "rationale": (
            "Unauthorized Intervention flagged as CRITICAL SAFETY NOTICE in Section 4.3.2. "
            "Direct unauthorized equipment interaction; immediate injury risk."
        ),
    },
    2: {
        # Opened Panel Cover — Section 5.2.2
        # "WARNING": state-based condition, no immediate personnel exposure required
        "signal": "WARNING",
        "max_tier": "HIGH",
        "rationale": (
            "Opened Panel Cover flagged as WARNING in Section 5.2.2. "
            "State-based hazard; alert generated regardless of personnel proximity."
        ),
    },
    3: {
        # Carrying Overload with Forklift — Section 6.3.2
        # "CRITICAL SAFETY NOTICE": vehicle instability, direct injury risk
        "signal": "CRITICAL SAFETY NOTICE",
        "max_tier": "CRITICAL",
        "rationale": (
            "Forklift Overload flagged as CRITICAL SAFETY NOTICE in Section 6.3.2. "
            "Vehicle instability; direct injury risk to operator and nearby personnel."
        ),
    },
}


def assign_severity(detection: dict) -> dict:
    """
    Assign severity tier to a detection record.

    Logic:
    1. Look up policy-grounded max tier for this class_id.
    2. Modulate downward based on confidence and contextual signals:
       - confidence >= 0.85 → assign max tier
       - 0.70 <= confidence < 0.85 → one tier below max
       - confidence < 0.70 → two tiers below max (floored at LOW)
    3. Special case: class_id=2 (Opened Panel Cover) is state-based,
       so lower confidence → MEDIUM rather than HIGH (no immediate personnel needed).

    Returns the detection dict augmented with severity fields.
    """
    tier_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    class_id = detection.get("class_id", -1)
    confidence = detection.get("confidence", 0.5)

    policy_info = POLICY_SEVERITY_MAP.get(class_id, {
        "signal": "WARNING",
        "max_tier": "HIGH",
        "rationale": "Unknown class; defaulting to HIGH.",
    })

    max_tier = policy_info["max_tier"]
    max_idx = tier_order.index(max_tier)

    # Confidence-based modulation
    if confidence >= 0.85:
        tier_idx = max_idx
    elif confidence >= 0.70:
        tier_idx = max(0, max_idx - 1)
    else:
        tier_idx = max(0, max_idx - 2)

    # Opened Panel Cover (class 2): it's a state-based condition.
    # Policy says alert regardless of personnel proximity, but
    # low-confidence detections should be MED not HIGH to avoid false alarms.
    if class_id == 2 and confidence < 0.75:
        tier_idx = min(tier_idx, tier_order.index("MEDIUM"))

    severity = tier_order[tier_idx]

    return {
        **detection,
        "severity": severity,
        "severity_signal": policy_info["signal"],
        "severity_rationale": policy_info["rationale"],
    }


def assign_severity_batch(detections: list[dict]) -> list[dict]:
    """Assign severity to a list of detection records."""
    return [assign_severity(d) for d in detections]
