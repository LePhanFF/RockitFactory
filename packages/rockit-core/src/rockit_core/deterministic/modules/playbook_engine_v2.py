# modules/playbook_engine_v2.py
"""
Enhanced Playbook Engine v2: Includes acceptance_test and balance_classification.

Generates conditional playbooks based on:
1. Day type classification (Neutral Range, Balance, Trend Up/Down)
2. Acceptance/rejection signals (from acceptance_test module)
3. Balance sub-type (P, b, neutral - from balance_classification module)
4. CRI readiness and permissions

CORRECTED LOGIC:
- P-Type Balance: FADE VAH (SHORT), target VAL area
- b-Type Balance: FADE VAL (LONG), target VAH area
- Trend Day with rejection: REVERSION playbook
- Trend Day with acceptance: CONTINUATION playbook
"""


def generate_playbook(day_type, trend_strength, cri_readiness,
                      acceptance_test=None, balance_classification=None,
                      current_time="11:45", **kwargs):
    """
    Main entry point: Generate trade setup with NEW modules.

    Args:
        day_type: str ("Neutral Range", "Balance", "Trend Up", "Trend Down", ...)
        trend_strength: str ("Weak", "Moderate", "Strong", "Super")
        cri_readiness: dict (overall_status, permission, terrain, etc.)
        acceptance_test: dict (breakout_direction, rejection_confidence, pullback_type)
        balance_classification: dict (balance_type, dominant_bias, playbook_action)
        current_time: str ("HH:MM")

    Returns:
        dict: {
            "matched_playbook": str,
            "direction": str ("LONG", "SHORT", "NONE"),
            "entry": str or float,
            "stop": str or float,
            "target": str or float,
            "size": str ("3/3", "2/3", "1/3"),
            "rationale": list of str,
            "permission": str
        }
    """

    # Permission check (universal)
    permission = cri_readiness.get('permission', {})
    aggression = permission.get('aggression', 'No entry')
    size_cap = permission.get('size_cap', 'Flat')

    if aggression == "No entry":
        return _standby_setup("CRI permission denied (No entry)")

    # Route to appropriate playbook
    if day_type == "Balance":
        return _balance_day_playbook(
            trend_strength, balance_classification, size_cap, permission
        )

    elif day_type == "Trend Up":
        return _trend_up_playbook(
            trend_strength, acceptance_test, size_cap, permission
        )

    elif day_type == "Trend Down":
        return _trend_down_playbook(
            trend_strength, acceptance_test, size_cap, permission
        )

    elif day_type in ["Neutral Range", "Open Auction", "Open Drive"]:
        return _neutral_range_playbook(
            day_type, trend_strength, acceptance_test, size_cap, permission
        )

    else:
        return _standby_setup(f"Unknown day type: {day_type}")


def _balance_day_playbook(trend_strength, balance_classification, size_cap, permission):
    """
    Balance Day Playbooks: P-type, b-type, or neutral.

    CORRECTED LOGIC:
    - P-Type (upper rejected, lower accepted): FADE VAH (SHORT)
    - b-Type (lower rejected, upper accepted): FADE VAL (LONG)
    - Neutral: Wait for confirmation
    """

    if balance_classification is None:
        return _standby_setup("Balance classification not available yet")

    balance_type = balance_classification.get('balance_type', 'neutral')
    confidence = balance_classification.get('confidence', 0)
    playbook_action = balance_classification.get('playbook_action', 'WAIT_DUAL_SIDED')

    # Determine size based on trend_strength
    if trend_strength == "Weak":
        size = "1/3"  # Probe on weak days
    elif trend_strength == "Moderate":
        size = "2/3"
    else:
        size = "3/3"

    # P-Type: Upper REJECTED, Lower ACCEPTED → FADE VAH (SHORT)
    if balance_type == "P" and confidence > 0.70:
        return {
            "matched_playbook": "P-Type Balance - Fade VAH Short",
            "direction": "SHORT",
            "entry": "VAH (rejected level)",
            "stop": "VAH + 10pts (above rejection)",
            "target": "VAL area (accepted support)",
            "target_1": "Prior POC",
            "target_2": "VAL area",
            "size": size,
            "rationale": [
                "Upper extreme (VAH) REJECTED - quick pullback observed",
                "Lower extreme (VAL) ACCEPTED - support holding",
                f"Confidence: {confidence:.0%}",
                f"Size: {size} ({trend_strength} trend)"
            ],
            "permission": "TRADE" if aggression != "No entry" else "STANDBY"
        }

    # b-Type: Lower REJECTED, Upper ACCEPTED → FADE VAL (LONG)
    elif balance_type == "b" and confidence > 0.70:
        return {
            "matched_playbook": "b-Type Balance - Fade VAL Long",
            "direction": "LONG",
            "entry": "VAL (rejected level)",
            "stop": "VAL - 10pts (below rejection)",
            "target": "VAH area (accepted resistance)",
            "target_1": "Prior POC",
            "target_2": "VAH area",
            "size": size,
            "rationale": [
                "Lower extreme (VAL) REJECTED - quick pullback observed",
                "Upper extreme (VAH) ACCEPTED - resistance holding",
                f"Confidence: {confidence:.0%}",
                f"Size: {size} ({trend_strength} trend)"
            ],
            "permission": "TRADE" if aggression != "No entry" else "STANDBY"
        }

    # Neutral Balance: Both probes tested
    elif balance_type == "neutral":
        return _standby_setup(
            f"Neutral balance day - waiting for clearer P or b signal (confidence: {confidence:.0%})"
        )

    else:
        return _standby_setup(f"Balance day unclear - confidence too low ({confidence:.0%})")


def _trend_up_playbook(trend_strength, acceptance_test, size_cap, permission):
    """
    Trend Up Playbooks: Follow if accepted, revert if rejected.

    WITH ACCEPTANCE_TEST:
    - ACCEPTED (holding): Continue uptrend → IBH retest long
    - REJECTED (fast pullback): Revert down → SHORT fade setup
    """

    if acceptance_test is None:
        # Fallback to mechanical trend confirmation
        if trend_strength in ["Strong", "Super"]:
            return {
                "matched_playbook": "Trend Up - IBH Retest (Mechanical)",
                "direction": "LONG",
                "entry": "IBH + 5pts",
                "stop": "IBL - 5pts",
                "target": "2x IB extension",
                "size": _size_by_strength(trend_strength),
                "rationale": ["Strong trend strength", "No early acceptance signal"]
            }
        else:
            return _standby_setup("Weak trend - waiting for acceptance confirmation")

    rejection_conf = acceptance_test.get('rejection_confidence', 0)
    acceptance_conf = acceptance_test.get('acceptance_confidence', 0)
    pullback_type = acceptance_test.get('pullback_type', 'none')

    # ACCEPTED: Price holding → Continue trend
    if acceptance_conf > 0.75 and pullback_type == "holding":
        return {
            "matched_playbook": "Trend Up - Continuation (Acceptance Confirmed)",
            "direction": "LONG",
            "entry": "IBH + 5pts (from pullback high)",
            "stop": "IBL - 5pts",
            "target": f"{_size_by_strength(trend_strength)} size",
            "size": _size_by_strength(trend_strength),
            "rationale": [
                "Uptrend breakout ACCEPTED - price holding above IBH",
                "Pullback type: holding (not fast rejection)",
                f"Acceptance confidence: {acceptance_conf:.0%}",
                "Continue trend on next pullback to IBH"
            ]
        }

    # REJECTED: Fast pullback → Revert to reversion setup
    elif rejection_conf > 0.75 and pullback_type in ["fast_rejection", "hesitant_reclaim"]:
        if trend_strength == "Weak":
            # Weak trend + rejected = HIGH probability reversion
            return {
                "matched_playbook": "Weak Trend Up - Reversal Short (Fast Rejection)",
                "direction": "SHORT",
                "entry": "IBH + 5pts (fade the high)",
                "stop": "IBH + 15pts (above rejection)",
                "target": "VAL area (first target) or POC (extended)",
                "size": "2/3" if trend_strength == "Weak" else "2/3",
                "rationale": [
                    "Uptrend breakout REJECTED - fast pullback detected",
                    f"Pullback type: {pullback_type}",
                    f"Rejection confidence: {rejection_conf:.0%}",
                    "Weak trend strength = 73% reversion probability",
                    "FADE the high, expect mean reversion"
                ]
            }
        else:
            # Moderate+ trend with rejection = unclear, stand down
            return _standby_setup(
                f"Moderate/strong trend with rejection signal - unclear ({rejection_conf:.0%})"
            )

    else:
        return _standby_setup(
            f"Trend Up - acceptance unclear (Accept: {acceptance_conf:.0%}, Reject: {rejection_conf:.0%})"
        )


def _trend_down_playbook(trend_strength, acceptance_test, size_cap, permission):
    """
    Trend Down Playbooks: Mirror of Trend Up.

    ACCEPTED (holding): Continue downtrend → IBL retest short
    REJECTED (fast pullback): Revert up → LONG fade setup
    """

    if acceptance_test is None:
        if trend_strength in ["Strong", "Super"]:
            return {
                "matched_playbook": "Trend Down - IBL Retest (Mechanical)",
                "direction": "SHORT",
                "entry": "IBL - 5pts",
                "stop": "IBH + 5pts",
                "target": "2x IB extension",
                "size": _size_by_strength(trend_strength)
            }
        else:
            return _standby_setup("Weak trend - waiting for acceptance confirmation")

    rejection_conf = acceptance_test.get('rejection_confidence', 0)
    acceptance_conf = acceptance_test.get('acceptance_confidence', 0)
    pullback_type = acceptance_test.get('pullback_type', 'none')

    # ACCEPTED: Price holding → Continue trend
    if acceptance_conf > 0.75 and pullback_type == "holding":
        return {
            "matched_playbook": "Trend Down - Continuation (Acceptance Confirmed)",
            "direction": "SHORT",
            "entry": "IBL - 5pts (from pullback low)",
            "stop": "IBH + 5pts",
            "target": f"{_size_by_strength(trend_strength)} size",
            "size": _size_by_strength(trend_strength),
            "rationale": [
                "Downtrend breakdown ACCEPTED - price holding below IBL",
                "Pullback type: holding (not fast rejection)",
                f"Acceptance confidence: {acceptance_conf:.0%}",
                "Continue trend on next pullback to IBL"
            ]
        }

    # REJECTED: Fast pullback → Revert to reversion setup
    elif rejection_conf > 0.75 and pullback_type in ["fast_rejection", "hesitant_reclaim"]:
        if trend_strength == "Weak":
            return {
                "matched_playbook": "Weak Trend Down - Reversal Long (Fast Rejection)",
                "direction": "LONG",
                "entry": "IBL - 5pts (fade the low)",
                "stop": "IBL - 15pts (below rejection)",
                "target": "VAH area (first target) or POC (extended)",
                "size": "2/3",
                "rationale": [
                    "Downtrend breakdown REJECTED - fast pullback detected",
                    f"Pullback type: {pullback_type}",
                    f"Rejection confidence: {rejection_conf:.0%}",
                    "Weak trend strength = 73% reversion probability",
                    "FADE the low, expect mean reversion"
                ]
            }
        else:
            return _standby_setup(
                f"Moderate/strong trend with rejection signal - unclear ({rejection_conf:.0%})"
            )

    else:
        return _standby_setup(
            f"Trend Down - acceptance unclear (Accept: {acceptance_conf:.0%}, Reject: {rejection_conf:.0%})"
        )


def _neutral_range_playbook(day_type, trend_strength, acceptance_test, size_cap, permission):
    """
    Neutral Range / Non-Trending Days: Fade extremes.

    Short VAH, Long VAL - mean reversion trades.
    """

    return {
        "matched_playbook": "Neutral Range - Value Area Fade",
        "direction": "DUAL_SIDED",
        "setup_1": {
            "direction": "SHORT",
            "entry": "VAH (rejection at upper extreme)",
            "stop": "VAH + 10pts",
            "target": "POC",
            "size": "1/3"
        },
        "setup_2": {
            "direction": "LONG",
            "entry": "VAL (rejection at lower extreme)",
            "stop": "VAL - 10pts",
            "target": "POC",
            "size": "1/3"
        },
        "rationale": [
            f"Day type: {day_type} (non-trending)",
            "Playbook: Value area reclamation (mean reversion)",
            "Fade extremes, target POC",
            "Size: 1/3 probes (non-aggressive)"
        ]
    }


def _size_by_strength(trend_strength):
    """Map trend strength to position size."""
    mapping = {
        "Weak": "1/3",
        "Moderate": "2/3",
        "Strong": "3/3",
        "Super": "3/3"
    }
    return mapping.get(trend_strength, "1/3")


def _standby_setup(reason="No clear setup"):
    """Generate standby (observe only) setup."""
    return {
        "matched_playbook": "Standby",
        "direction": "NONE",
        "entry": None,
        "stop": None,
        "target": None,
        "size": "0/3",
        "rationale": [reason],
        "permission": "OBSERVE_ONLY"
    }
