# modules/decision_engine.py
"""
Phase 2: Deterministic Decision Engine

Moves 10 trading rules from LLM inference → Python code.
Replaces 165-line inference prompt with 48-line LLM "context + insight only" mode.

Rules implemented (deterministic, testable, debuggable):
1. Day Type Classification (Trend Up/Down, Balance, Open Drive, etc.)
2. Trend Strength (Weak/Moderate/Strong/Super)
3. Morph Status (Potential/Morphing/Super-trending/Locked)
4. Bias Cap Enforcement (downgrades Very→ when Weak trend)
5. Confidence Time Caps (55%/<10:00, 70%/<10:30, no cap after)
6. DPOC Regime → Bias Modifier (+25% trending, -15% fading, -10% balancing, flip on reversal)
7. TPO Acceptance Conflict (fattening wins over single prints)
8. Value Acceptance String (POC location + acceptance narrative)
9. TPO Read Strings (profile_signals, dpoc_migration, extreme_or_compression)
10. One-Liner Template (bias + trend_strength + confidence + regime)
"""

from typing import Dict, Any, List, Tuple


# ============================================================================
# RULE 1: DAY TYPE CLASSIFICATION
# ============================================================================

def classify_day_type(snapshot: Dict[str, Any]) -> str:
    """
    Classify day type into one of 7 exact values.

    Logic:
    - Trend Up: IB acceptance higher + ≥1 full 30-min TPO hold above IBH + upper fattening
    - Trend Down: Symmetric, IB acceptance lower
    - Open Drive: Immediate early displacement pre-10:30
    - Open Auction: Pre-10:30 two-sided rotation inside prior range
    - Double Distribution: Separated value areas (AM + PM distinct)
    - Neutral Range: Contained with minor skew, minor net migration
    - Balance: Pure rotational chop within IB, flat VWAP/POC
    """
    intraday = snapshot.get("intraday", {})
    core_confluences = snapshot.get("core_confluences", {})
    current_time_str = snapshot.get("current_et_time", "11:45")

    # Extract signals
    ib = intraday.get("ib", {})
    ib_acceptance = core_confluences.get("ib_acceptance", {})
    dpoc_migration = intraday.get("dpoc_migration", {})
    tpo_profile = intraday.get("tpo_profile", {})
    core_conf_dpoc = core_confluences.get("dpoc_vs_ib", {})

    close_above_ibh = ib_acceptance.get("close_above_ibh", False)
    close_below_ibl = ib_acceptance.get("close_below_ibl", False)
    dpoc_regime = dpoc_migration.get("dpoc_regime", "")
    fattening_zone = tpo_profile.get("fattening_zone", "inside_va").lower()
    direction = dpoc_migration.get("direction", "flat")

    # Time check: pre/post 10:30
    try:
        time_parts = list(map(int, current_time_str.split(":")))
        is_post_1030 = (time_parts[0] > 10) or (time_parts[0] == 10 and time_parts[1] >= 30)
    except:
        is_post_1030 = True

    # Decision tree
    if not is_post_1030:
        # Pre-10:30 classification
        if close_above_ibh or close_below_ibl:
            return "Open Drive"
        else:
            return "Open Auction"

    # Post-10:30 classification
    if dpoc_regime == "trending_on_the_move" and (close_above_ibh or close_below_ibl):
        if direction == "up" and close_above_ibh and "at_vah" in fattening_zone:
            return "Trend Up"
        elif direction == "down" and close_below_ibl and "at_val" in fattening_zone:
            return "Trend Down"
        elif direction == "up":
            return "Trend Up"
        elif direction == "down":
            return "Trend Down"

    if dpoc_regime in ["balancing_choppy", "transitional_unclear"]:
        return "Balance"

    if "stabilizing" in dpoc_regime.lower():
        return "Neutral Range"

    # Default: check for double distribution or balanced setup
    migration_pts = dpoc_migration.get("net_migration_pts", 0)
    if abs(migration_pts) < 10:
        return "Balance"
    elif abs(migration_pts) < 20:
        return "Neutral Range"
    else:
        return "Trend Up" if migration_pts > 0 else "Trend Down"


# ============================================================================
# RULE 2: TREND STRENGTH
# ============================================================================

def get_trend_strength(snapshot: Dict[str, Any]) -> str:
    """
    Classify trend strength: Weak/Moderate/Strong/Super.

    Logic:
    - Weak: <0.5x IB range extension
    - Moderate: 0.5-1.0x extension + ≥1 30-min bracket
    - Strong: 1.0-2.0x extension + ≥60 min stacked brackets
    - Super: >2.0x extension OR extreme DPOC compression + ≥60 min hold
    """
    intraday = snapshot.get("intraday", {})
    ib = intraday.get("ib", {})
    dpoc_migration = intraday.get("dpoc_migration", {})
    trend_analysis = intraday.get("trend_analysis", {})

    # Get from trend_analysis if available (uses dalton.py logic)
    if trend_analysis and "trend_strength" in trend_analysis:
        return trend_analysis.get("trend_strength", "Moderate")

    # Fallback: compute from IB extension
    ib_range = ib.get("ib_range", 0)
    ib_high = ib.get("ib_high", 0)
    ib_low = ib.get("ib_low", 0)
    current_close = ib.get("current_close", 0)

    if ib_range == 0:
        return "Moderate"

    # Calculate extension
    if current_close > ib_high:
        extension = current_close - ib_high
        extension_multiple = extension / ib_range
    elif current_close < ib_low:
        extension = ib_low - current_close
        extension_multiple = extension / ib_range
    else:
        return "Weak"

    # Classify
    if extension_multiple > 2.0:
        return "Super"
    elif extension_multiple >= 1.0:
        return "Strong"
    elif extension_multiple >= 0.5:
        return "Moderate"
    else:
        return "Weak"


# ============================================================================
# RULE 3: MORPH STATUS
# ============================================================================

def get_morph_status(snapshot: Dict[str, Any]) -> str:
    """
    Generate morph status: Potential/Morphing/Super-trending/Locked.

    Logic:
    - 15-min shaping above IBH/below IBL but <30-min → Potential
    - ≥30-min hold/close → Morphing
    - ≥60-min hold → Super-trending
    - No morph signals → Locked no morph
    """
    intraday = snapshot.get("intraday", {})
    dpoc_migration = intraday.get("dpoc_migration", {})
    trend_analysis = intraday.get("trend_analysis", {})

    morph_status = trend_analysis.get("morph_status", "none")
    if morph_status and morph_status != "none":
        return morph_status

    # Compute from DPOC signals
    dpoc_regime = dpoc_migration.get("dpoc_regime", "")
    relative_retain = dpoc_migration.get("relative_retain_percent", 0)

    if dpoc_regime == "trending_on_the_move" and relative_retain >= 70:
        return "Super-trending locked"
    elif "trending" in dpoc_regime.lower():
        return "Morphing confirmed"
    elif dpoc_regime in ["stabilizing_hold forming_ceiling", "stabilizing_hold forming_floor"]:
        return "Potential morph"
    else:
        return "Locked no morph"


# ============================================================================
# RULE 4: BIAS CAP ENFORCEMENT
# ============================================================================

def apply_bias_cap(bias: str, trend_strength: str) -> str:
    """
    Enforce weak trend bias cap: downgrade Very→ if trend_strength == Weak.

    Logic:
    - If trend_strength != Weak: return bias unchanged
    - If trend_strength == Weak:
      - Very Bullish → Bullish
      - Very Bearish → Bearish
      - Others: unchanged
    """
    if trend_strength != "Weak":
        return bias

    if bias == "Very Bullish":
        return "Bullish"
    elif bias == "Very Bearish":
        return "Bearish"

    return bias


# ============================================================================
# RULE 5: CONFIDENCE TIME CAPS
# ============================================================================

def apply_confidence_time_cap(confidence: int, current_time_str: str) -> int:
    """
    Cap confidence by time of day.

    Logic:
    - Before 10:00: max 55%
    - 10:00-10:30: max 70%
    - After 10:30: no cap
    """
    try:
        hour_minute = current_time_str.replace(":", "")  # "0930" format
        if hour_minute < "1000":
            return min(confidence, 55)
        elif hour_minute < "1030":
            return min(confidence, 70)
    except:
        pass

    return confidence


# ============================================================================
# RULE 6: DPOC REGIME BIAS MODIFIER
# ============================================================================

def apply_dpoc_bias_modifier(bias: str, dpoc_regime: str, direction: str, confidence: int) -> Tuple[str, int]:
    """
    Modify bias and confidence based on DPOC regime.

    Logic:
    - trending_on_the_move: +25% confidence, reinforce direction
    - trending_fading_momentum: -10% confidence
    - potential_bpr_reversal: flip bias if reclaiming
    - balancing_choppy: flatten to Flat, -15% confidence
    - others: no change
    """
    if dpoc_regime == "trending_on_the_move":
        confidence = min(100, confidence + 25)
        if direction == "up":
            bias = "Very Bullish" if bias in ["Bullish", "Neutral-Upper"] else bias
        elif direction == "down":
            bias = "Very Bearish" if bias in ["Bearish", "Neutral-Lower"] else bias
        return bias, confidence

    elif dpoc_regime == "trending_fading_momentum":
        confidence = max(0, confidence - 10)
        return bias, confidence

    elif dpoc_regime == "balancing_choppy":
        bias = "Flat"
        confidence = max(0, confidence - 15)
        return bias, confidence

    return bias, confidence


# ============================================================================
# RULE 7: TPO ACCEPTANCE CONFLICT
# ============================================================================

def resolve_tpo_conflict(tpo_profile: Dict[str, Any], core_confluences: Dict[str, Any]) -> str:
    """
    Resolve TPO acceptance vs rejection conflict.

    Logic:
    - fattening_zone at VAH/VAL with single_prints above/below: acceptance WINS
    - Fattening inside VA: acceptance
    - Single prints alone: rejection
    """
    fattening_zone = tpo_profile.get("fattening_zone", "inside_va").lower()
    tpo_signals = core_confluences.get("tpo_signals", {})
    single_above = tpo_signals.get("single_prints_above", False)
    single_below = tpo_signals.get("single_prints_below", False)

    if "at_vah" in fattening_zone and single_above:
        return "Acceptance above VAH (bullish)"
    elif "at_val" in fattening_zone and single_below:
        return "Acceptance below VAL (bearish)"
    elif "at_vah" in fattening_zone:
        return "Upper acceptance"
    elif "at_val" in fattening_zone:
        return "Lower acceptance"
    elif "inside_va" in fattening_zone:
        return "Balanced acceptance"
    else:
        return "Neutral"


# ============================================================================
# RULE 8: VALUE ACCEPTANCE STRING
# ============================================================================

def build_value_acceptance_string(snapshot: Dict[str, Any]) -> str:
    """
    Build value acceptance narrative.

    Format: "POC [high|mid|low] | [Acceptance above VAH|below VAL|inside VA]"
    """
    intraday = snapshot.get("intraday", {})
    tpo_profile = intraday.get("tpo_profile", {})

    poc = tpo_profile.get("current_poc")
    vah = tpo_profile.get("current_vah")
    val = tpo_profile.get("current_val")

    if not poc:
        return "Value undefined"

    # POC location
    if vah and poc > vah:
        poc_loc = "high"
        acceptance = "Acceptance above VAH (bullish)"
    elif val and poc < val:
        poc_loc = "low"
        acceptance = "Acceptance below VAL (bearish)"
    else:
        poc_loc = "mid"
        acceptance = "Acceptance inside VA"

    return f"POC {poc_loc} | {acceptance}"


# ============================================================================
# RULE 9: TPO READ STRINGS
# ============================================================================

def build_tpo_read_strings(snapshot: Dict[str, Any]) -> Dict[str, str]:
    """
    Build TPO read narrative with 3 parts: profile, migration, extreme.
    """
    intraday = snapshot.get("intraday", {})
    core_confluences = snapshot.get("core_confluences", {})

    tpo_signals = core_confluences.get("tpo_signals", {})
    dpoc_migration = intraday.get("dpoc_migration", {})
    dpoc_vs_ib = core_confluences.get("dpoc_vs_ib", {})
    dpoc_compression = core_confluences.get("dpoc_compression", {})

    # Profile signals
    profile_parts = []
    if tpo_signals.get("fattening_upper"):
        profile_parts.append("Upper fattening")
    if tpo_signals.get("fattening_lower"):
        profile_parts.append("Lower fattening")
    if tpo_signals.get("single_prints_above"):
        profile_parts.append("Single prints high")
    if tpo_signals.get("single_prints_below"):
        profile_parts.append("Single prints low")
    profile_signals = " | ".join(profile_parts) if profile_parts else "Symmetric build"

    # Migration
    direction = dpoc_migration.get("direction", "flat")
    pts = dpoc_migration.get("net_migration_pts", 0)
    dpoc_mig_str = f"DPOC {direction} {abs(pts):.1f}pts" if direction != "flat" else "DPOC flat"

    # Extreme or compression
    extreme_or_comp = "none"
    if dpoc_vs_ib.get("dpoc_above_ibh"):
        extreme_or_comp = "Extreme bullish shift"
    elif dpoc_vs_ib.get("dpoc_below_ibl"):
        extreme_or_comp = "Extreme bearish shift"
    elif dpoc_compression.get("compressing_against_vah"):
        extreme_or_comp = "Compressing against VAH"
    elif dpoc_compression.get("compressing_against_val"):
        extreme_or_comp = "Compressing against VAL"

    return {
        "profile_signals": profile_signals,
        "dpoc_migration": dpoc_mig_str,
        "extreme_or_compression": extreme_or_comp
    }


# ============================================================================
# RULE 10: ONE-LINER TEMPLATE
# ============================================================================

def build_one_liner(bias: str, trend_strength: str, confidence: int, dpoc_regime: str = "") -> str:
    """
    Build single high-conviction line: bias + trend_strength + confidence + regime.

    Template: "{bias} ({trend_strength} trend, {confidence}% confidence) — {regime_clause}"
    """
    strength_desc = {
        "Weak": "weak",
        "Moderate": "moderate",
        "Strong": "strong",
        "Super": "super-trending"
    }

    strength_text = strength_desc.get(trend_strength, "uncertain")

    regime_text = ""
    if dpoc_regime:
        if "trending_on_the_move" in dpoc_regime:
            regime_text = "on the move"
        elif "trending_fading" in dpoc_regime:
            regime_text = "fading momentum"
        elif "potential_bpr" in dpoc_regime:
            regime_text = "reversal setup"
        elif "stabilizing" in dpoc_regime:
            regime_text = "stabilizing"
        elif "balancing" in dpoc_regime:
            regime_text = "choppy rotation"

    regime_clause = f" — {regime_text}" if regime_text else ""

    return f"{bias} ({strength_text} trend, {confidence}% confidence){regime_clause}"


# ============================================================================
# MAIN ORCHESTRATOR: Apply All 10 Rules
# ============================================================================

def apply_all_rules(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply all 10 rules in order.

    Returns dict suitable for LLM "context + insight only" mode.
    """
    intraday = snapshot.get("intraday", {})
    core_confluences = snapshot.get("core_confluences", {})
    current_time_str = snapshot.get("current_et_time", "11:45")

    # Rule 1: Day Type
    day_type = classify_day_type(snapshot)

    # Rule 2: Trend Strength
    trend_strength = get_trend_strength(snapshot)

    # Rule 3: Morph Status
    morph_status = get_morph_status(snapshot)

    # Compute initial bias (from ib acceptance + dpoc + confluences)
    ib_acceptance = core_confluences.get("ib_acceptance", {})
    dpoc_vs_ib = core_confluences.get("dpoc_vs_ib", {})
    dpoc_migration = intraday.get("dpoc_migration", {})

    if ib_acceptance.get("close_above_ibh"):
        bias = "Bullish"
        confidence = 60
    elif ib_acceptance.get("close_below_ibl"):
        bias = "Bearish"
        confidence = 60
    elif dpoc_vs_ib.get("dpoc_above_ibh"):
        bias = "Very Bullish"
        confidence = 70
    elif dpoc_vs_ib.get("dpoc_below_ibl"):
        bias = "Very Bearish"
        confidence = 70
    else:
        bias = "Flat"
        confidence = 50

    # Rule 4: Bias Cap
    bias = apply_bias_cap(bias, trend_strength)

    # Rule 5: Confidence Time Cap
    confidence = apply_confidence_time_cap(confidence, current_time_str)

    # Rule 6: DPOC Bias Modifier
    dpoc_regime = dpoc_migration.get("dpoc_regime", "")
    direction = dpoc_migration.get("direction", "flat")
    bias, confidence = apply_dpoc_bias_modifier(bias, dpoc_regime, direction, confidence)

    # Rule 7: TPO Conflict
    tpo_profile = intraday.get("tpo_profile", {})
    tpo_conflict_resolution = resolve_tpo_conflict(tpo_profile, core_confluences)

    # Rule 8: Value Acceptance
    value_acceptance = build_value_acceptance_string(snapshot)

    # Rule 9: TPO Read Strings
    tpo_read = build_tpo_read_strings(snapshot)

    # Rule 10: One-Liner
    one_liner = build_one_liner(bias, trend_strength, confidence, dpoc_regime)

    return {
        "day_type": day_type,
        "trend_strength": trend_strength,
        "morph_status": morph_status,
        "bias": bias,
        "confidence": confidence,
        "value_acceptance": value_acceptance,
        "tpo_read": tpo_read,
        "tpo_conflict_resolution": tpo_conflict_resolution,
        "one_liner": one_liner,
        "rules_applied": [
            "day_type_classification",
            "trend_strength",
            "morph_status",
            "bias_cap_enforcement",
            "confidence_time_caps",
            "dpoc_bias_modifier",
            "tpo_acceptance_conflict",
            "value_acceptance_string",
            "tpo_read_strings",
            "one_liner_template"
        ]
    }
