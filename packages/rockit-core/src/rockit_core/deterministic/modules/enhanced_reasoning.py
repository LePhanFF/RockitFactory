#!/usr/bin/env python3
"""
Enhanced Reasoning with Explicit Field References

Generates structured reasoning that teaches LLM to examine deterministic input fields.
Each step explicitly shows:
1. JSON path to the field
2. Actual value from input
3. Interpretation/what it means
4. Impact on playbook decision

This is the foundation for LLM to learn "where to look" and "why each field matters."
"""

from typing import Dict, List, Any


def generate_enhanced_reasoning(snapshot: Dict, features: Dict) -> List[Dict]:
    """
    Generate 8-step field-referenced reasoning.

    Args:
        snapshot: Complete input JSON snapshot with all 77 TIER 1+2 fields
        features: Pre-computed features dict

    Returns:
        List of reasoning steps, each with:
        {
            "step": 0-8,
            "phase": "Opening Range Analysis" | "Day Type" | "CRI" etc.,
            "fields_examined": [list of JSON paths],
            "findings": [key observations with field values],
            "decision": "what this means for playbook",
            "confidence_factor": +/- points on confidence
        }
    """

    intraday = snapshot.get("intraday", {})
    ib = intraday.get("ib", {})
    vp = intraday.get("volume_profile", {})
    dpoc = intraday.get("dpoc_migration", {})
    tpo = intraday.get("tpo_profile", {})
    fvg = intraday.get("fvg_detection", {})
    cri = snapshot.get("cri_readiness", {})
    inference = snapshot.get("inference", {})
    premarket = snapshot.get("premarket", {})
    current_time = snapshot.get("current_et_time", "")

    reasoning_steps = []

    # =========================================================================
    # STEP 0: OPENING RANGE ANALYSIS (09:30-10:45 critical filter)
    # =========================================================================

    step0 = {
        "step": 0,
        "phase": "Opening Range Analysis (Critical Filter)",
        "fields_examined": [
            "input.intraday.ib.ib_range",
            "input.intraday.ib.ib_high",
            "input.intraday.ib.ib_low",
            "input.current_et_time",
            "input.intraday.fvg_detection.recent_fvgs"
        ],
        "findings": [
            f"IB Range: {ib.get('ib_range', 'N/A')} pts (from {ib.get('ib_high', 'N/A')} to {ib.get('ib_low', 'N/A')})",
            f"OR Maturity: {_classify_or_maturity(current_time)}",
            f"Breakout Direction: {_detect_or_breakout_direction(ib, intraday)}",
            f"FVG Support: {_summarize_fvg_support(fvg)}"
        ],
        "decision": "If tight OR (<100pts) + breakout above 10:00 = Opening Range Reversal candidate",
        "confidence_factor": _compute_or_confidence(ib, current_time)
    }
    reasoning_steps.append(step0)

    # =========================================================================
    # STEP 1: DAY TYPE CONFIRMATION (Foundation)
    # =========================================================================

    step1 = {
        "step": 1,
        "phase": "Day Type Confirmation (Foundation)",
        "fields_examined": [
            "input.inference.day_type",
            "input.intraday.dpoc_migration.dpoc_regime",
            "input.intraday.ib.ib_acceptance"
        ],
        "findings": [
            f"Day Type: {inference.get('day_type', 'Unknown')}",
            f"DPOC Regime: {dpoc.get('dpoc_regime', 'N/A')}",
            f"IB Acceptance: {_get_ib_acceptance_status(ib, intraday)}"
        ],
        "decision": f"Day type '{inference.get('day_type')}' drives playbook selection priority",
        "confidence_factor": _get_day_type_confidence(inference, dpoc)
    }
    reasoning_steps.append(step1)

    # =========================================================================
    # STEP 2: CRI TERRAIN ANALYSIS
    # =========================================================================

    terrain = cri.get("terrain", {}).get("classification", "A4")
    step2 = {
        "step": 2,
        "phase": "CRI Terrain (Market Identity)",
        "fields_examined": [
            "input.cri_readiness.terrain.classification",
            "input.cri_readiness.overall_status",
            "input.cri_readiness.permission_logic.max_size_allowed"
        ],
        "findings": [
            f"CRI Terrain: {terrain}",
            f"  A1/A3 = Aggressive (Warrior/Knight) - accept directional trades",
            f"  A2 = Cautious (Squire) - probe and fade",
            f"  A4 = Broken (Observer) - stand down",
            f"Overall Status: {cri.get('overall_status', 'UNKNOWN')}",
            f"Permission Logic: {cri.get('permission_logic', {}).get('max_size_allowed', 'N/A')}"
        ],
        "decision": f"CRI Terrain '{terrain}' limits position sizing and playbook selection",
        "confidence_factor": _get_cri_terrain_confidence(terrain, cri)
    }
    reasoning_steps.append(step2)

    # =========================================================================
    # STEP 3: TREND STRENGTH VALIDATION
    # =========================================================================

    trend_strength = inference.get("trend_strength", "Weak")
    step3 = {
        "step": 3,
        "phase": "Trend Strength Validation",
        "fields_examined": [
            "input.trend_analysis.trend_confirmed",
            "input.trend_analysis.trend_strength",
            "input.inference.confidence",
            "input.intraday.dpoc_migration.net_migration_pts"
        ],
        "findings": [
            f"Trend Confirmed: {snapshot.get('trend_analysis', {}).get('trend_confirmed', False)}",
            f"Trend Strength: {trend_strength}",
            f"  Weak (<0.5× IB): Cap bias at Bullish/Bearish (no Very prefix)",
            f"  Moderate (0.5-1.0×): Allow Bullish/Bearish, cautious 2/3 sizing",
            f"  Strong (1-2×): Full Bullish/Very Bullish bias, 2-3/3 sizing",
            f"  Super (>2.0×): Very Bullish/Very Bearish, 3/3 sizing",
            f"DPOC Migration: {dpoc.get('net_migration_pts', 0)} pts {dpoc.get('net_direction', '')}"
        ],
        "decision": f"Trend strength '{trend_strength}' caps confidence and sizing caps",
        "confidence_factor": _get_trend_confidence(trend_strength, dpoc)
    }
    reasoning_steps.append(step3)

    # =========================================================================
    # STEP 4: DPOC REGIME ANALYSIS (Post-10:30 critical)
    # =========================================================================

    regime = dpoc.get("dpoc_regime", "unknown")
    step4 = {
        "step": 4,
        "phase": "DPOC Regime Analysis (Post-10:30 Critical)",
        "fields_examined": [
            "input.intraday.dpoc_migration.dpoc_regime",
            "input.intraday.dpoc_migration.net_migration_pts",
            "input.intraday.dpoc_migration.net_direction",
            "input.current_et_time"
        ],
        "findings": [
            f"DPOC Regime: {regime}",
            f"  trending_on_the_move = Strong 1-directional bias, favor trend playbook",
            f"  trending_fading_momentum = Initial trend slowing, reversals possible",
            f"  potential_bpr_reversal = Mean reversion setup (edge fades work well)",
            f"  stabilizing_hold = Forming support/resistance, balanced structure",
            f"  balancing_choppy = 2-sided rotation, fades preferred, trend risky",
            f"  transitional_unclear = Ambiguous regime, wait for clarity",
            f"Net Migration: {dpoc.get('net_migration_pts', 0)} pts {dpoc.get('net_direction', '')}"
        ],
        "decision": f"Regime '{regime}' is the PRIMARY post-10:30 signal - overrides early signals",
        "confidence_factor": _get_regime_confidence(regime, dpoc)
    }
    reasoning_steps.append(step4)

    # =========================================================================
    # STEP 5: PRICE STRUCTURE (Support/Resistance from Profiles)
    # =========================================================================

    step5 = {
        "step": 5,
        "phase": "Price Structure (Support/Resistance)",
        "fields_examined": [
            "input.intraday.ib.ib_high",
            "input.intraday.ib.ib_low",
            "input.intraday.volume_profile.vah",
            "input.intraday.volume_profile.val",
            "input.intraday.volume_profile.poc",
            "input.premarket.previous_day_high",
            "input.premarket.previous_day_low",
            "input.intraday.fvg_detection.gap_direction"
        ],
        "findings": [
            f"IB: {ib.get('ib_low', 'N/A')} (low) ← {ib.get('ib_high', 'N/A')} (high)",
            f"VAH (70% upper): {vp.get('vah', 'N/A')} - Resistance to shorts",
            f"VAL (70% lower): {vp.get('val', 'N/A')} - Support to longs",
            f"POC (Highest Vol): {vp.get('poc', 'N/A')} - Fair value magnet",
            f"Previous Day High: {premarket.get('previous_day_high', 'N/A')} - Overhead resistance",
            f"Previous Day Low: {premarket.get('previous_day_low', 'N/A')} - Support floor",
            f"Recent FVGs: {_summarize_fvg_impact(fvg)}"
        ],
        "decision": "Price structure defines where buyers/sellers gather - use for target selection",
        "confidence_factor": 0  # Neutral - structure just defines zones
    }
    reasoning_steps.append(step5)

    # =========================================================================
    # STEP 6: TPO STRUCTURE (Acceptance vs Rejection at Key Levels)
    # =========================================================================

    step6 = {
        "step": 6,
        "phase": "TPO Structure (Acceptance/Rejection Analysis)",
        "fields_examined": [
            "input.intraday.tpo_profile.fattening_zone",
            "input.intraday.tpo_profile.single_prints_above_vah",
            "input.intraday.tpo_profile.single_prints_below_val",
            "input.intraday.tpo_profile.current_poc",
            "input.intraday.tpo_profile.current_vah",
            "input.intraday.tpo_profile.current_val"
        ],
        "findings": [
            f"Fattening Zone: {tpo.get('fattening_zone', 'N/A')} - Price ACCEPTED here",
            f"  Fattening = Many TPO letters = Buyers/Sellers committed = Support/Resistance",
            f"Single Prints ABOVE VAH: {tpo.get('single_prints_above_vah', 0)} count",
            f"  High count = Rejection of higher prices = Shorts have edge on rallies",
            f"Single Prints BELOW VAL: {tpo.get('single_prints_below_val', 0)} count",
            f"  High count = Rejection of lower prices = Longs have edge on dips",
            f"Current TPO Levels: POC={tpo.get('current_poc', 'N/A')}, "
            f"VAH={tpo.get('current_vah', 'N/A')}, VAL={tpo.get('current_val', 'N/A')}"
        ],
        "decision": "TPO Acceptance > Rejection - fattening overrides single prints (buyers/sellers in control)",
        "confidence_factor": _get_tpo_confidence(tpo, vp)
    }
    reasoning_steps.append(step6)

    # =========================================================================
    # STEP 7: PLAYBOOK SELECTION
    # =========================================================================

    playbook = snapshot.get("playbook_setup", {}).get("matched_playbook", "Standby")
    step7 = {
        "step": 7,
        "phase": "Playbook Selection (Time-Windowed Priority)",
        "fields_examined": [
            "input.current_et_time",
            "input.playbook_setup.matched_playbook",
            "input.inference.day_type",
            "input.intraday.dpoc_migration.dpoc_regime"
        ],
        "findings": [
            f"Current Time: {current_time}",
            f"Selected Playbook: {playbook}",
            f"Priority by Time Window:",
            f"  09:30-10:45: Opening Range Reversal (highest priority, 61.5% WR)",
            f"  10:00-13:30: Edge Fade mean reversion (56.2% WR, runs parallel to OR overlap)",
            f"  13:30-16:00: Daily structure (Trend Following, Balance Fade, Range Fade)",
            f"Day Type Influence: {inference.get('day_type', 'Unknown')} → selects between Trend/Balance/Range playbooks"
        ],
        "decision": f"Playbook '{playbook}' determines entry/stop/target pricing and sizing",
        "confidence_factor": _get_playbook_confidence(playbook, inference, current_time)
    }
    reasoning_steps.append(step7)

    # =========================================================================
    # STEP 8: STRUCTURE CONFIRMATION GATE (All checks must pass)
    # =========================================================================

    gate_results = _check_structure_confirmation_gate(snapshot)
    step8 = {
        "step": 8,
        "phase": "Structure Confirmation Gate (Final Filter)",
        "fields_examined": [
            "input.cri_readiness.overall_status",
            "input.trend_analysis.trend_strength",
            "input.intraday.tpo_profile.fattening_zone",
            "input.intraday.dpoc_migration.dpoc_regime"
        ],
        "findings": [
            f"Gate Check 1 - CRI Status: {gate_results['cri_status']} {'✓' if gate_results['cri_ok'] else '✗'}",
            f"Gate Check 2 - Trend Strength: {gate_results['trend_strength']} {'✓' if gate_results['trend_ok'] else '✗'}",
            f"Gate Check 3 - Price Acceptance: {gate_results['acceptance']} {'✓' if gate_results['acceptance_ok'] else '✗'}",
            f"Gate Check 4 - Regime Clarity: {gate_results['regime']} {'✓' if gate_results['regime_ok'] else '✗'}",
        ],
        "decision": f"Gate Result: {'PASS - Ready to trade' if gate_results['all_pass'] else 'FAIL - Stand down or reduce sizing'}",
        "confidence_factor": _get_gate_confidence(gate_results)
    }
    reasoning_steps.append(step8)

    return reasoning_steps


# ===========================================================================================
# HELPER FUNCTIONS (Field-Specific Analysis)
# ===========================================================================================

def _classify_or_maturity(current_time: str) -> str:
    """Classify OR maturity based on time"""
    if not current_time:
        return "unknown"

    try:
        hour, minute = map(int, current_time.split(':'))
        total_mins = hour * 60 + minute
        open_mins = total_mins - (9 * 60 + 30)  # Minutes since 09:30

        if open_mins < 30:
            return "early (< 30 min)"
        elif open_mins < 60:
            return "mid-formation (30-60 min)"
        elif open_mins < 75:
            return "near-complete (60-75 min)"
        else:
            return "complete (> 75 min, after 10:45)"
    except:
        return "unknown"


def _detect_or_breakout_direction(ib: Dict, intraday: Dict) -> str:
    """Detect opening range breakout direction"""
    ib_high = ib.get("ib_high", 0)
    ib_low = ib.get("ib_low", 0)
    current_close = ib.get("current_close", 0)

    if current_close > ib_high:
        return "UP (above IBH)"
    elif current_close < ib_low:
        return "DOWN (below IBL)"
    else:
        return "INSIDE (within IB)"


def _summarize_fvg_support(fvg: Dict) -> str:
    """Summarize FVG support available"""
    recent = fvg.get("recent_fvgs", [])
    if not recent:
        return "No recent FVGs"

    count = len(recent)
    direction = fvg.get("gap_direction", "mixed")
    return f"{count} FVGs, direction: {direction}"


def _compute_or_confidence(ib: Dict, current_time: str) -> int:
    """Compute confidence boost/penalty for OR analysis"""
    or_range = ib.get("ib_range", 0)

    if or_range < 100:
        return +20  # Tight OR is ideal
    elif or_range < 150:
        return +10  # Normal OR
    else:
        return -10  # Wide OR, less clarity


def _get_ib_acceptance_status(ib: Dict, intraday: Dict) -> str:
    """Get IB acceptance status"""
    ib_high = ib.get("ib_high", 0)
    ib_low = ib.get("ib_low", 0)
    current_close = ib.get("current_close", 0)

    if current_close > ib_high * 1.001:  # >0.1% above
        return "Bullish (above IBH)"
    elif current_close < ib_low * 0.999:  # >0.1% below
        return "Bearish (below IBL)"
    else:
        return "Neutral (inside IB)"


def _get_day_type_confidence(inference: Dict, dpoc: Dict) -> int:
    """Confidence adjustment based on day type clarity"""
    day_type = inference.get("day_type", "Unknown")

    if day_type in ["Trend Up", "Trend Down"]:
        return +15
    elif day_type in ["Balance", "Neutral Range"]:
        return +10
    else:
        return -5


def _get_cri_terrain_confidence(terrain: str, cri: Dict) -> int:
    """Confidence adjustment based on CRI clarity"""
    if terrain in ["A1/A3"]:
        return +20  # Aggressive clear signal
    elif terrain == "A2":
        return +5  # Cautious probe
    elif terrain == "A4":
        return -100  # Broken, reduce confidence drastically
    else:
        return 0


def _get_trend_confidence(trend_strength: str, dpoc: Dict) -> int:
    """Confidence adjustment based on trend strength"""
    if trend_strength == "Super":
        return +30
    elif trend_strength == "Strong":
        return +20
    elif trend_strength == "Moderate":
        return +10
    elif trend_strength == "Weak":
        return -10
    else:
        return 0


def _get_regime_confidence(regime: str, dpoc: Dict) -> int:
    """Confidence adjustment based on DPOC regime clarity"""
    if regime in ["trending_on_the_move", "potential_bpr_reversal"]:
        return +25
    elif regime in ["stabilizing_hold", "balancing_choppy"]:
        return +10
    else:
        return -5


def _summarize_fvg_impact(fvg: Dict) -> str:
    """Summarize FVG impact on current price"""
    recent = fvg.get("recent_fvgs", [])
    if not recent:
        return "No FVGs"

    latest_fvg = recent[0] if recent else {}
    direction = latest_fvg.get("direction", "unknown")
    size = latest_fvg.get("size", 0)
    return f"Latest FVG: {direction} ({size}pts)"


def _get_tpo_confidence(tpo: Dict, vp: Dict) -> int:
    """Confidence from TPO structure"""
    fattening = tpo.get("fattening_zone", "")
    vah = vp.get("vah", 0)
    val = vp.get("val", 0)

    if fattening:
        return +10  # Fattening shows acceptance
    else:
        return 0


def _get_playbook_confidence(playbook: str, inference: Dict, current_time: str) -> int:
    """Confidence from playbook selection clarity"""
    if playbook in ["Opening Range Reversal", "Edge Fade"]:
        return +15
    elif playbook in ["Trend Following", "Balance Fade"]:
        return +10
    elif playbook == "Stand By":
        return -20
    else:
        return 0


def _check_structure_confirmation_gate(snapshot: Dict) -> Dict:
    """Check all structure confirmation gates"""
    cri = snapshot.get("cri_readiness", {})
    trend_data = snapshot.get("trend_analysis", {})
    tpo = snapshot.get("intraday", {}).get("tpo_profile", {})
    dpoc = snapshot.get("intraday", {}).get("dpoc_migration", {})

    cri_ok = cri.get("overall_status") != "STAND_DOWN"
    trend_ok = trend_data.get("trend_strength") != "Weak"
    acceptance_ok = bool(tpo.get("fattening_zone"))
    regime_ok = dpoc.get("dpoc_regime") not in ["transitional_unclear"]

    return {
        "cri_status": cri.get("overall_status", "UNKNOWN"),
        "cri_ok": cri_ok,
        "trend_strength": trend_data.get("trend_strength", "Unknown"),
        "trend_ok": trend_ok,
        "acceptance": "Fattening detected" if acceptance_ok else "No fattening",
        "acceptance_ok": acceptance_ok,
        "regime": dpoc.get("dpoc_regime", "unknown"),
        "regime_ok": regime_ok,
        "all_pass": cri_ok and trend_ok and acceptance_ok and regime_ok
    }


def _get_gate_confidence(gate_results: Dict) -> int:
    """Compute confidence from gate checks"""
    if gate_results["all_pass"]:
        return +30
    elif sum([gate_results["cri_ok"], gate_results["trend_ok"],
              gate_results["acceptance_ok"], gate_results["regime_ok"]]) >= 3:
        return +10
    else:
        return -30
