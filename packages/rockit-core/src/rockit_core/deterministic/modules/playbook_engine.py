# modules/playbook_engine.py
"""
Playbook Engine: Trade setup generation based on market structure.
Matches day_type + trend_strength + DPOC regime → playbook section → generates setups.

Implements 10 fundamental playbooks covering all market conditions:
1. Super Trend Day Bull - Sustained bullish momentum
2. Super Trend Day Bear - Sustained bearish momentum
3. Fading Trend Long - Countertrend entry on trend exhaustion
4. Fading Trend Short - Countertrend entry on trend exhaustion
5. Balance Day Long - Value reclaim in balanced markets
6. Balance Day Short - Rejection in balanced markets
7. Open Drive Bull - Initial breakout momentum
8. Open Drive Bear - Initial breakdown momentum
9. Reversional Pattern - Reversal setup (double distribution, potential BPR)
10. Standby - No clear setup (observe only)
"""


def generate_playbook_setup(snapshot, inference_result, cri_result):
    """
    Main entry point: Generate trade setup from market snapshot.

    Args:
        snapshot (dict): Full market snapshot from orchestrator
        inference_result (dict): Decision engine output (day_type, bias, confidence, trend_strength)
        cri_result (dict): CRI readiness output (overall_status, terrain, identity, permission)

    Returns:
        dict: Playbook setup with bullish_setup, bearish_setup, matched_playbook, rationale
    """
    # Extract key signals
    day_type = inference_result.get('day_type', 'Neutral Range')
    trend_strength = inference_result.get('trend_strength', 'Weak')
    bias = inference_result.get('bias', 'Flat')
    confidence = inference_result.get('confidence', 0)

    intraday = snapshot.get('intraday', {})
    dpoc_regime = intraday.get('dpoc_migration', {}).get('dpoc_regime', 'transitional_unclear')
    ib_data = intraday.get('ib', {})
    volume_profile = intraday.get('volume_profile', {})

    # Permission check
    permission = cri_result.get('permission', {})
    aggression = permission.get('aggression', 'No entry')
    size_cap = permission.get('size_cap', 'Flat')

    # If permission is "No entry", return standby
    if aggression == "No entry":
        return _generate_standby_setup(snapshot, "Permission denied (CRI: No entry)")

    # Match to playbook
    matched_playbook, bullish_setup, bearish_setup, rationale = _match_playbook(
        day_type, trend_strength, bias, confidence, dpoc_regime, aggression, ib_data, volume_profile
    )

    return {
        "matched_playbook": matched_playbook,
        "bullish_setup": bullish_setup,
        "bearish_setup": bearish_setup,
        "rationale": rationale,
        "permission": {
            "aggression": aggression,
            "size_cap": size_cap,
            "note": f"Size: {size_cap}, Entry style: {aggression}"
        }
    }


def _match_playbook(day_type, trend_strength, bias, confidence, dpoc_regime, aggression, ib_data, volume_profile):
    """
    Match market conditions to playbook and generate setups.

    Returns:
        tuple: (matched_playbook, bullish_setup, bearish_setup, rationale)
    """
    bullish_setup = None
    bearish_setup = None
    rationale = []

    # Extract key levels
    ib_high = ib_data.get('ib_high')
    ib_low = ib_data.get('ib_low')
    poc = volume_profile.get('current_session', {}).get('poc')
    vah = volume_profile.get('current_session', {}).get('vah')
    val = volume_profile.get('current_session', {}).get('val')

    # === PLAYBOOK 1 & 2: Super Trend Days ===
    if day_type == "Trend Up" and trend_strength in ["Strong", "Super"] and bias in ["Very Bullish", "Bullish"]:
        matched_playbook = "Super Trend Day Bull"
        bullish_setup = _setup_ibh_retest_long(ib_high, poc, vah, val)
        bearish_setup = _setup_value_rejection_short(val, ib_low, poc)
        rationale = [
            f"Trend Up {trend_strength} trend confirmed",
            f"Bias {bias} with {confidence}% confidence",
            "Setup: IBH retest long favored, only short on value rejection below VAL"
        ]

    elif day_type == "Trend Down" and trend_strength in ["Strong", "Super"] and bias in ["Very Bearish", "Bearish"]:
        matched_playbook = "Super Trend Day Bear"
        bearish_setup = _setup_ibl_retest_short(ib_low, poc, val, vah)
        bullish_setup = _setup_value_acceptance_long(vah, ib_high, poc)
        rationale = [
            f"Trend Down {trend_strength} trend confirmed",
            f"Bias {bias} with {confidence}% confidence",
            "Setup: IBL retest short favored, only long on value acceptance above VAH"
        ]

    # === PLAYBOOK 3 & 4: Fading Trends ===
    elif "trending_fading_momentum" in dpoc_regime and trend_strength == "Moderate":
        if bias in ["Very Bullish", "Bullish"]:
            matched_playbook = "Fading Trend Long"
            bullish_setup = _setup_poc_hold_long(poc, ib_high, ib_low, vah)
            bearish_setup = _setup_extreme_rejection_short(vah, poc, val)
            rationale = [
                "Trend fading but still bullish bias",
                f"Confidence {confidence}% supports countertrend entry",
                "Setup: Hold POC for long continuation, short on VAH rejection only"
            ]
        else:
            matched_playbook = "Fading Trend Short"
            bearish_setup = _setup_poc_hold_short(poc, ib_low, ib_high, val)
            bullish_setup = _setup_extreme_acceptance_long(val, poc, vah)
            rationale = [
                "Trend fading but still bearish bias",
                f"Confidence {confidence}% supports countertrend entry",
                "Setup: Hold POC for short continuation, long on VAL acceptance only"
            ]

    # === PLAYBOOK 5 & 6: Balance Days ===
    elif day_type in ["Balance", "Neutral Range"] and trend_strength in ["Weak", "Moderate"]:
        if bias in ["Very Bullish", "Bullish", "Neutral-Upper"]:
            matched_playbook = "Balance Day Long"
            bullish_setup = _setup_val_reclaim_long(val, vah, poc)
            bearish_setup = _setup_vah_rejection_short(vah, poc, val)
            rationale = [
                "Balance day: fade extremes",
                f"Bias {bias} supports VAL reclaim longs",
                "Setup: Buy VAL rejection and hold for POC/VAH, short above VAH only"
            ]
        else:
            matched_playbook = "Balance Day Short"
            bearish_setup = _setup_vah_rejection_short(vah, poc, val)
            bullish_setup = _setup_val_reclaim_long(val, vah, poc)
            rationale = [
                "Balance day: fade extremes",
                f"Bias {bias} supports VAH rejection shorts",
                "Setup: Sell VAH and target POC/VAL, long below VAL only"
            ]

    # === PLAYBOOK 7 & 8: Open Drive ===
    elif day_type == "Open Drive" and trend_strength in ["Moderate", "Strong"]:
        if bias in ["Very Bullish", "Bullish"]:
            matched_playbook = "Open Drive Bull"
            bullish_setup = _setup_open_drive_long(ib_high, ib_low, vah)
            bearish_setup = _setup_break_hold_short(ib_low, poc)
            rationale = [
                "Strong open displacement",
                f"{trend_strength} trend confirms breakout",
                "Setup: Ride initial displacement, only short on break of IB low"
            ]
        else:
            matched_playbook = "Open Drive Bear"
            bearish_setup = _setup_open_drive_short(ib_low, ib_high, val)
            bullish_setup = _setup_break_hold_long(ib_high, poc)
            rationale = [
                "Strong open displacement",
                f"{trend_strength} trend confirms breakdown",
                "Setup: Ride initial displacement, only long on break of IB high"
            ]

    # === PLAYBOOK 9: Reversal Pattern ===
    elif day_type in ["Double Distribution", "Open Auction"] and "potential_bpr_reversal" in dpoc_regime:
        matched_playbook = "Reversional Pattern"
        # Reversal typically goes opposite to current bias
        if bias in ["Very Bullish", "Bullish"]:
            bearish_setup = _setup_reversal_short(poc, vah, ib_high)
            bullish_setup = _setup_value_acceptance_long(val, ib_low, poc)
            rationale = [
                "Reversal setup detected: double distribution + BPR potential",
                f"Current bias {bias} but reversal likely post-10:30",
                "Setup: Short VAH breakdown with VAL as target, watch for reversal signal"
            ]
        else:
            bullish_setup = _setup_reversal_long(poc, val, ib_low)
            bearish_setup = _setup_value_rejection_short(vah, ib_high, poc)
            rationale = [
                "Reversal setup detected: double distribution + BPR potential",
                f"Current bias {bias} but reversal likely post-10:30",
                "Setup: Long VAL breakout with VAH as target, watch for reversal signal"
            ]

    # === PLAYBOOK 10: Standby ===
    else:
        matched_playbook = "Standby"
        bullish_setup = None
        bearish_setup = None
        rationale = [
            f"No clear playbook match: {day_type} {trend_strength} {bias}",
            "Action: Observe market structure, wait for confirmation"
        ]

    return matched_playbook, bullish_setup, bearish_setup, rationale


# ============================================================================
# Setup Builders (Return standardized setup dicts)
# ============================================================================

def _setup_ibh_retest_long(ib_high, poc, vah, val):
    """IBH retest long setup."""
    if not all([ib_high, poc, vah]):
        return None
    return {
        "setup_name": "IBH Retest Long",
        "entry": ib_high + 2,
        "stop": poc - 10,
        "target1": vah + 25,
        "target2": vah + 50,
        "target3": ib_high + 100,
        "rationale": "Strong trend, retest initial balance high for continuation",
        "risk_reward": "1:3",
        "size": "Full"
    }


def _setup_ibl_retest_short(ib_low, poc, val, vah):
    """IBL retest short setup."""
    if not all([ib_low, poc, val]):
        return None
    return {
        "setup_name": "IBL Retest Short",
        "entry": ib_low - 2,
        "stop": poc + 10,
        "target1": val - 25,
        "target2": val - 50,
        "target3": ib_low - 100,
        "rationale": "Strong downtrend, retest initial balance low for continuation",
        "risk_reward": "1:3",
        "size": "Full"
    }


def _setup_poc_hold_long(poc, ib_high, ib_low, vah):
    """POC hold long setup (fading trend)."""
    if not all([poc, vah]):
        return None
    return {
        "setup_name": "POC Hold Long",
        "entry": poc + 2,
        "stop": (ib_low or poc - 50) - 5,
        "target1": vah + 10,
        "target2": vah + 30,
        "rationale": "Fading uptrend, hold POC for possible acceleration",
        "risk_reward": "1:2.5",
        "size": "Half"
    }


def _setup_poc_hold_short(poc, ib_low, ib_high, val):
    """POC hold short setup (fading trend)."""
    if not all([poc, val]):
        return None
    return {
        "setup_name": "POC Hold Short",
        "entry": poc - 2,
        "stop": (ib_high or poc + 50) + 5,
        "target1": val - 10,
        "target2": val - 30,
        "rationale": "Fading downtrend, hold POC for possible acceleration",
        "risk_reward": "1:2.5",
        "size": "Half"
    }


def _setup_val_reclaim_long(val, vah, poc):
    """VAL reclaim long setup (balance day)."""
    if not all([val, poc]):
        return None
    return {
        "setup_name": "VAL Reclaim Long",
        "entry": val - 2,
        "stop": val - 15,
        "target1": poc + 5,
        "target2": vah - 10,
        "rationale": "Balance day, support at VAL, fade extremes",
        "risk_reward": "1:1.5",
        "size": "Half"
    }


def _setup_vah_rejection_short(vah, poc, val):
    """VAH rejection short setup (balance day)."""
    if not all([vah, poc]):
        return None
    return {
        "setup_name": "VAH Rejection Short",
        "entry": vah + 2,
        "stop": vah + 15,
        "target1": poc - 5,
        "target2": val + 10,
        "rationale": "Balance day, resistance at VAH, fade extremes",
        "risk_reward": "1:1.5",
        "size": "Half"
    }


def _setup_open_drive_long(ib_high, ib_low, vah):
    """Open drive long setup."""
    if not all([ib_high, vah]):
        return None
    return {
        "setup_name": "Open Drive Long",
        "entry": ib_high + 5,
        "stop": ib_low - 10,
        "target1": vah + 30,
        "target2": ib_high + 150,
        "rationale": "Strong open displacement, ride initial momentum",
        "risk_reward": "1:2.5",
        "size": "Full"
    }


def _setup_open_drive_short(ib_low, ib_high, val):
    """Open drive short setup."""
    if not all([ib_low, val]):
        return None
    return {
        "setup_name": "Open Drive Short",
        "entry": ib_low - 5,
        "stop": ib_high + 10,
        "target1": val - 30,
        "target2": ib_low - 150,
        "rationale": "Strong open displacement, ride initial momentum",
        "risk_reward": "1:2.5",
        "size": "Full"
    }


def _setup_reversal_long(poc, val, ib_low):
    """Reversal long setup."""
    if not all([poc, val]):
        return None
    return {
        "setup_name": "Reversal Long",
        "entry": val - 5,
        "stop": val - 20,
        "target1": poc + 15,
        "target2": ib_low + 100,
        "rationale": "Reversal pattern, BPR potential, VAL support",
        "risk_reward": "1:2",
        "size": "Micro"
    }


def _setup_reversal_short(poc, vah, ib_high):
    """Reversal short setup."""
    if not all([poc, vah]):
        return None
    return {
        "setup_name": "Reversal Short",
        "entry": vah + 5,
        "stop": vah + 20,
        "target1": poc - 15,
        "target2": ib_high - 100,
        "rationale": "Reversal pattern, BPR potential, VAH resistance",
        "risk_reward": "1:2",
        "size": "Micro"
    }


def _setup_value_acceptance_long(vah, ib_high, poc):
    """Value acceptance long (bearish day but upside available)."""
    if not all([vah, poc]):
        return None
    return {
        "setup_name": "Value Acceptance Long",
        "entry": vah + 3,
        "stop": poc - 10,
        "target1": vah + 30,
        "target2": ib_high + 50,
        "rationale": "Downtrend exhausted, value acceptance above VAH",
        "risk_reward": "1:2",
        "size": "Micro"
    }


def _setup_value_rejection_short(val, ib_low, poc):
    """Value rejection short (bullish day but downside available)."""
    if not all([val, poc]):
        return None
    return {
        "setup_name": "Value Rejection Short",
        "entry": val - 3,
        "stop": poc + 10,
        "target1": val - 30,
        "target2": ib_low - 50,
        "rationale": "Uptrend exhausted, value rejection below VAL",
        "risk_reward": "1:2",
        "size": "Micro"
    }


def _setup_break_hold_long(ib_high, poc):
    """Break and hold long setup (open drive exhaustion)."""
    if not all([ib_high, poc]):
        return None
    return {
        "setup_name": "Break Hold Long",
        "entry": ib_high + 2,
        "stop": poc - 15,
        "target1": ib_high + 50,
        "target2": ib_high + 100,
        "rationale": "Uptrend exhaustion, break of IB high confirms continuation",
        "risk_reward": "1:2",
        "size": "Half"
    }


def _setup_break_hold_short(ib_low, poc):
    """Break and hold short setup (open drive exhaustion)."""
    if not all([ib_low, poc]):
        return None
    return {
        "setup_name": "Break Hold Short",
        "entry": ib_low - 2,
        "stop": poc + 15,
        "target1": ib_low - 50,
        "target2": ib_low - 100,
        "rationale": "Downtrend exhaustion, break of IB low confirms continuation",
        "risk_reward": "1:2",
        "size": "Half"
    }


def _setup_extreme_acceptance_long(val, poc, vah):
    """Extreme value acceptance long."""
    if not all([val, poc]):
        return None
    return {
        "setup_name": "Extreme Acceptance Long",
        "entry": val + 5,
        "stop": val - 10,
        "target1": poc,
        "target2": vah - 5,
        "rationale": "Strong move below VAL, reversal acceptance likely",
        "risk_reward": "1:1.5",
        "size": "Micro"
    }


def _setup_extreme_rejection_short(vah, poc, val):
    """Extreme value rejection short."""
    if not all([vah, poc]):
        return None
    return {
        "setup_name": "Extreme Rejection Short",
        "entry": vah - 5,
        "stop": vah + 10,
        "target1": poc,
        "target2": val + 5,
        "rationale": "Strong move above VAH, reversal rejection likely",
        "risk_reward": "1:1.5",
        "size": "Micro"
    }


def _generate_standby_setup(snapshot, reason):
    """Generate standby (observe only) setup."""
    return {
        "matched_playbook": "Standby",
        "bullish_setup": None,
        "bearish_setup": None,
        "rationale": [f"No clear playbook match: {reason}", "Action: Observe market structure, wait for confirmation"],
        "permission": {
            "aggression": "Observe only",
            "size_cap": "Flat",
            "note": "Stand down - no valid setup"
        }
    }
