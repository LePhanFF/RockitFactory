# modules/inference_engine.py
"""
Phase 1 Inference Engine: 8 HIGH-Priority Deterministic Rules

Implements rules for converting core_confluences and intraday data into preliminary trading decisions.
Each rule is deterministic, operates on precomputed booleans from core_confluences, and contributes
to bias/confidence/day_type decisions.

Signal Priority Hierarchy:
1. IB acceptance + 30/60-min TPO hold
2. DPOC regime (post-10:30)
3. DPOC migration net direction/pts
4. DPOC extreme position/compression
5. Upper/lower third hug + fattening
6. Wick parade count & direction
7. Single print imbalance

Rules implemented (in order):
- Rule 2: Trend Strength Quantification
- Rule 3: Weak Trend Strength Bias Cap
- Rule 4: DPOC Regime Rules (lookup table)
- Rule 5: IB Acceptance Rules
- Rule 6: DPOC Extreme Position
- Rule 7: DPOC Compression
- Rule 11: Neutral-Upper/Lower Rules
- Rule 13: Morph Status String
- Rule 14: Balance Morph Bias Adjustment
"""

from datetime import time, datetime
from typing import Dict, Any, List, Tuple


# ============================================================================
# LOOKUP TABLES & CONSTANTS
# ============================================================================

DPOC_REGIME_RULES = {
    "trending_on_the_move": {
        "bias_delta": "+3",
        "confidence_delta": 25,
        "bias_preference": "Very Bullish" if None else "Very Bearish",  # Will be set per direction
        "interpretation": "Strongest continuation bias, minimal pullback expected"
    },
    "trending_fading_momentum": {
        "bias_delta": "+1",
        "confidence_delta": -10,
        "bias_preference": "Bullish" if None else "Bearish",
        "interpretation": "Momentum weakening; expect small counter-move then possible resumption/failure"
    },
    "stabilizing_hold forming_floor": {
        "bias_delta": "-1",
        "confidence_delta": -5,
        "bias_preference": "Neutral-Lower",
        "interpretation": "Potential strong support forming at cluster; watch for acceptance"
    },
    "stabilizing_hold forming_ceiling": {
        "bias_delta": "-1",
        "confidence_delta": -5,
        "bias_preference": "Neutral-Upper",
        "interpretation": "Potential strong resistance forming at cluster; watch for acceptance"
    },
    "potential_bpr_reversal": {
        "bias_delta": "-2",
        "confidence_delta": 0,
        "bias_preference": "Neutral",
        "interpretation": "Highest probability reversal setup; favor opposite bias if reclaiming"
    },
    "balancing_choppy": {
        "bias_delta": "0",
        "confidence_delta": -15,
        "bias_preference": "Flat",
        "interpretation": "Neutral, no directional conviction from DPOC"
    },
    "transitional_unclear": {
        "bias_delta": "0",
        "confidence_delta": -10,
        "bias_preference": "Flat",
        "interpretation": "Transitional period; await clearer setup"
    }
}

# Bias strength levels (ordered)
BIAS_LEVELS = [
    "Very Bearish",
    "Bearish",
    "Neutral-Lower",
    "Flat",
    "Neutral-Upper",
    "Bullish",
    "Very Bullish"
]

BIAS_LEVEL_INDEX = {bias: idx for idx, bias in enumerate(BIAS_LEVELS)}


# ============================================================================
# RULE 2: TREND STRENGTH QUANTIFICATION (15 lines)
# ============================================================================

def rule_2_trend_strength(snapshot: Dict[str, Any]) -> str:
    """
    Rule 2: Classify trend strength into Weak/Moderate/Strong/Super based on:
    - IB range extension multiple
    - Full 30-min bracket holds
    - Migration characteristics

    Returns one of: "Weak" | "Moderate" | "Strong" | "Super" | "NA"

    Logic:
    - Weak: <0.5x IB range extension, minimal/no full bracket hold, hovering/poke
    - Moderate: 0.5-1.0x extension, >=1 full 30-min hold outside IB, emerging fattening
    - Strong: 1.0-2.0x extension, >=60 min stacked brackets, sustained fattening
    - Super: >2.0x extension OR extreme DPOC migration + compression + >=60 min hold
    """
    intraday = snapshot.get("intraday", {})
    core_confluences = snapshot.get("core_confluences", {})

    # Extract IB data
    ib = intraday.get("ib", {})
    ib_range = ib.get("ib_range")
    current_close = ib.get("current_close")

    if ib_range is None or ib_range == 0:
        return "NA"

    # Calculate extension from IB
    ib_high = ib.get("ib_high")
    ib_low = ib.get("ib_low")

    if ib_high is None or ib_low is None or current_close is None:
        return "NA"

    # Extension above/below IB
    ext_above_ibh = max(0, current_close - ib_high)
    ext_below_ibl = max(0, ib_low - current_close)
    extension = max(ext_above_ibh, ext_below_ibl)
    extension_multiple = round(extension / ib_range, 2)

    # Evaluate other signals
    dpoc_migration = intraday.get("dpoc_migration", {})
    abs_velocity = dpoc_migration.get("abs_velocity", 0)
    cluster_range = dpoc_migration.get("cluster_range_last_4", 0)
    relative_retain = dpoc_migration.get("relative_retain_percent", 0)
    dpoc_regime = dpoc_migration.get("dpoc_regime", "")

    # Check for extreme compression (proxy for Strong/Super)
    dpoc_vs_ib = core_confluences.get("dpoc_vs_ib", {})
    dpoc_compression = core_confluences.get("dpoc_compression", {})
    extreme_position = dpoc_vs_ib.get("dpoc_above_ibh", False) or dpoc_vs_ib.get("dpoc_below_ibl", False)
    extreme_compression = (dpoc_compression.get("compressing_against_vah", False) or
                          dpoc_compression.get("compressing_against_val", False))

    # Check migration signals (Strong/Super requires good follow-through)
    migration = core_confluences.get("migration", {})
    significant_migration = migration.get("significant_up", False) or migration.get("significant_down", False)

    # Classification logic
    # Super: >2.0x extension with extreme signals, OR trending_on_the_move with high retention
    if extension_multiple > 2.0 and (extreme_compression or abs_velocity > 25):
        return "Super"
    elif dpoc_regime == "trending_on_the_move" and relative_retain >= 70 and abs_velocity >= 20:
        return "Super"

    # Strong: 1.0-2.0x extension OR trending_on_the_move with good signals
    elif extension_multiple > 2.0:
        return "Strong"
    elif extension_multiple >= 1.0 and (extreme_position or extreme_compression or significant_migration):
        return "Strong"
    elif dpoc_regime == "trending_on_the_move":
        return "Strong"

    # Moderate: 0.5-1.0x extension with some fattening/acceptance
    elif extension_multiple >= 0.5 and significant_migration:
        return "Moderate"
    elif extension_multiple >= 0.5:
        return "Moderate"

    # Weak: <0.5x extension
    else:
        return "Weak"


# ============================================================================
# RULE 3: WEAK TREND STRENGTH BIAS CAP (20 lines)
# ============================================================================

def rule_3_weak_trend_cap(bias: str, confidence: int, trend_strength: str) -> Tuple[str, int]:
    """
    Rule 3: If trend_strength = "Weak", downgrade bias and cap confidence at 75%.

    FORBIDDEN: Assign "Very Bullish" or "Very Bearish" when trend_strength = "Weak"

    Logic:
    - If trend_strength != "Weak" or "NA": return bias/confidence unchanged
    - If trend_strength == "Weak":
      - Remove "Very" prefix from bias (Very Bullish → Bullish, Very Bearish → Bearish)
      - Cap confidence at 75%
      - If bias is Neutral-Upper/Lower/Flat: no change
    """
    if trend_strength != "Weak":
        return bias, confidence

    # Downgrade bias
    if bias == "Very Bullish":
        bias = "Bullish"
    elif bias == "Very Bearish":
        bias = "Bearish"

    # Cap confidence
    confidence = min(confidence, 75)

    return bias, confidence


# ============================================================================
# RULE 4: DPOC REGIME RULES (50 lines)
# ============================================================================

def rule_4_dpoc_regime(snapshot: Dict[str, Any], current_bias: str = "Flat") -> Tuple[str, int, List[str]]:
    """
    Rule 4: Map DPOC regime string to bias/confidence deltas using lookup table.

    Applies ONLY post-10:30. Before 10:30, returns current_bias unchanged.

    Returns:
    - Updated bias (may shift bullish/bearish based on regime + direction)
    - Confidence delta to apply
    - Reasoning bullets (list of strings)
    """
    intraday = snapshot.get("intraday", {})
    current_et_time = snapshot.get("current_et_time", "09:30")

    # Time check: only apply post-10:30
    try:
        ct = time(*map(int, current_et_time.split(':')))
        if ct < time(10, 30):
            return current_bias, 0, []
    except:
        return current_bias, 0, []

    dpoc_migration = intraday.get("dpoc_migration", {})
    dpoc_regime = dpoc_migration.get("dpoc_regime", "transitional_unclear")
    direction = dpoc_migration.get("direction", "flat")

    if dpoc_regime not in DPOC_REGIME_RULES:
        return current_bias, 0, ["DPOC regime unknown or transitional"]

    rule = DPOC_REGIME_RULES[dpoc_regime]
    conf_delta = rule.get("confidence_delta", 0)
    interpretation = rule.get("interpretation", "")

    reasoning = [f"DPOC regime: \"{dpoc_regime}\" — {interpretation}"]

    # Adjust bias based on regime + direction
    bias_adjusted = current_bias

    if dpoc_regime == "trending_on_the_move":
        bias_adjusted = "Very Bullish" if direction == "up" else "Very Bearish" if direction == "down" else current_bias
    elif dpoc_regime == "trending_fading_momentum":
        bias_adjusted = "Bullish" if direction == "up" else "Bearish" if direction == "down" else current_bias
    elif dpoc_regime == "stabilizing_hold forming_ceiling":
        bias_adjusted = "Neutral-Upper"
    elif dpoc_regime == "stabilizing_hold forming_floor":
        bias_adjusted = "Neutral-Lower"
    elif dpoc_regime == "potential_bpr_reversal":
        # Opposite direction if reclaiming
        reclaiming = dpoc_migration.get("reclaiming_opposite", False)
        if reclaiming:
            bias_adjusted = "Bullish" if direction == "down" else "Bearish" if direction == "up" else current_bias
    elif dpoc_regime in ["balancing_choppy", "transitional_unclear"]:
        bias_adjusted = "Flat"

    return bias_adjusted, conf_delta, reasoning


# ============================================================================
# RULE 5: IB ACCEPTANCE RULES (30 lines)
# ============================================================================

def rule_5_ib_acceptance(snapshot: Dict[str, Any], current_bias: str = "Flat") -> Tuple[str, int, List[str]]:
    """
    Rule 5: Close above IBH or below IBL triggers immediate override.

    Signal Priority: Highest (immediately after TPO hold check)

    Logic:
    - If close_above_ibh (from core_confluences.ib_acceptance) → bullish override
    - If close_below_ibl → bearish override
    - Apply confidence boost (+10-15%)

    Returns:
    - Updated bias (may be overridden to Bullish/Bearish)
    - Confidence delta
    - Reasoning bullets
    """
    core_confluences = snapshot.get("core_confluences", {})
    ib_acceptance = core_confluences.get("ib_acceptance", {})

    close_above_ibh = ib_acceptance.get("close_above_ibh", False)
    close_below_ibl = ib_acceptance.get("close_below_ibl", False)

    reasoning = []
    conf_delta = 0
    bias_adjusted = current_bias

    if close_above_ibh:
        bias_adjusted = "Bullish"
        conf_delta = 15
        ib_high = snapshot.get("intraday", {}).get("ib", {}).get("ib_high", "N/A")
        current_close = snapshot.get("intraday", {}).get("ib", {}).get("current_close", "N/A")
        reasoning.append(f"IB acceptance CONFIRMED: Close {current_close} above IBH {ib_high} — immediate bullish override")
    elif close_below_ibl:
        bias_adjusted = "Bearish"
        conf_delta = 15
        ib_low = snapshot.get("intraday", {}).get("ib", {}).get("ib_low", "N/A")
        current_close = snapshot.get("intraday", {}).get("ib", {}).get("current_close", "N/A")
        reasoning.append(f"IB acceptance CONFIRMED: Close {current_close} below IBL {ib_low} — immediate bearish override")

    return bias_adjusted, conf_delta, reasoning


# ============================================================================
# RULE 6: DPOC EXTREME POSITION (20 lines)
# ============================================================================

def rule_6_dpoc_extreme_position(snapshot: Dict[str, Any], current_bias: str = "Flat") -> Tuple[str, int, List[str]]:
    """
    Rule 6: DPOC above IBH or below IBL → extreme shift.

    Logic:
    - If dpoc_above_ibh → "extreme bullish shift" → bias toward Very Bullish, +25% confidence
    - If dpoc_below_ibl → "extreme bearish shift" → bias toward Very Bearish, +25% confidence
    - Does not override IB acceptance (lower priority)

    Returns:
    - Updated bias
    - Confidence delta
    - Reasoning bullets
    """
    core_confluences = snapshot.get("core_confluences", {})
    dpoc_vs_ib = core_confluences.get("dpoc_vs_ib", {})

    dpoc_above_ibh = dpoc_vs_ib.get("dpoc_above_ibh", False)
    dpoc_below_ibl = dpoc_vs_ib.get("dpoc_below_ibl", False)

    reasoning = []
    conf_delta = 0
    bias_adjusted = current_bias

    if dpoc_above_ibh:
        bias_adjusted = "Very Bullish"
        conf_delta = 25
        intraday = snapshot.get("intraday", {})
        tpo_profile = intraday.get("tpo_profile", {})
        volume_profile = intraday.get("volume_profile", {})
        poc = tpo_profile.get("current_poc") or volume_profile.get("current_session", {}).get("poc", "N/A")
        ib_high = intraday.get("ib", {}).get("ib_high", "N/A")
        reasoning.append(f"DPOC extreme bullish shift: POC {poc} above IBH {ib_high} — explosive day potential, minimal pullback expected")
    elif dpoc_below_ibl:
        bias_adjusted = "Very Bearish"
        conf_delta = 25
        intraday = snapshot.get("intraday", {})
        tpo_profile = intraday.get("tpo_profile", {})
        volume_profile = intraday.get("volume_profile", {})
        poc = tpo_profile.get("current_poc") or volume_profile.get("current_session", {}).get("poc", "N/A")
        ib_low = intraday.get("ib", {}).get("ib_low", "N/A")
        reasoning.append(f"DPOC extreme bearish shift: POC {poc} below IBL {ib_low} — explosive short potential, minimal pullback expected")

    return bias_adjusted, conf_delta, reasoning


# ============================================================================
# RULE 7: DPOC COMPRESSION (20 lines)
# ============================================================================

def rule_7_dpoc_compression(snapshot: Dict[str, Any], current_bias: str = "Flat") -> Tuple[str, int, List[str]]:
    """
    Rule 7: DPOC compressing against VAH (bullish) or VAL (bearish).

    Strict interpretation: Do NOT interpret compression as bearish if upper fattening/
    acceptance present. Compression = aggressive buyer/seller control.

    Logic:
    - If compressing_against_vah → extreme bullish buyer control, short trap → Very Bullish, +15% conf
    - If compressing_against_val → extreme bearish seller control, long trap → Very Bearish, +15% conf

    Returns:
    - Updated bias
    - Confidence delta
    - Reasoning bullets
    """
    core_confluences = snapshot.get("core_confluences", {})
    dpoc_compression = core_confluences.get("dpoc_compression", {})

    compressing_vah = dpoc_compression.get("compressing_against_vah", False)
    compressing_val = dpoc_compression.get("compressing_against_val", False)

    reasoning = []
    conf_delta = 0
    bias_adjusted = current_bias

    if compressing_vah:
        bias_adjusted = "Very Bullish"
        conf_delta = 15
        reasoning.append("DPOC compressing against VAH: Aggressive buyer control — short trap setup, extreme bullish trend")
    elif compressing_val:
        bias_adjusted = "Very Bearish"
        conf_delta = 15
        reasoning.append("DPOC compressing against VAL: Aggressive seller control — long trap setup, extreme bearish trend")

    return bias_adjusted, conf_delta, reasoning


# ============================================================================
# RULE 11: NEUTRAL-UPPER / NEUTRAL-LOWER (25 lines)
# ============================================================================

def rule_11_neutral_upper_lower(snapshot: Dict[str, Any]) -> str:
    """
    Rule 11: Price in upper/lower third with no momentum continuation.

    Logic:
    - If price_vs_ib = "upper_third_hug" AND no bullish acceptance/fattening above → Neutral-Upper
    - If price_vs_ib = "lower_third_hug" AND no bearish acceptance/fattening below → Neutral-Lower
    - Avoids FOMO longs into overhead resistance or shorts into underfoot support

    Returns: "Neutral-Upper" | "Neutral-Lower" | "NA"
    """
    intraday = snapshot.get("intraday", {})
    core_confluences = snapshot.get("core_confluences", {})

    ib = intraday.get("ib", {})
    price_vs_ib = ib.get("price_vs_ib", "unknown")

    tpo_profile = intraday.get("tpo_profile", {})
    fattening_zone = tpo_profile.get("fattening_zone", "inside_va").lower()

    # Check fattening signals
    tpo_signals = core_confluences.get("tpo_signals", {})
    fattening_upper = tpo_signals.get("fattening_upper", False)
    fattening_lower = tpo_signals.get("fattening_lower", False)

    # Check acceptance signals
    ib_acceptance = core_confluences.get("ib_acceptance", {})
    acceptance_higher = ib_acceptance.get("close_above_ibh", False)
    acceptance_lower = ib_acceptance.get("close_below_ibl", False)

    migration = core_confluences.get("migration", {})
    significant_up = migration.get("significant_up", False)
    significant_down = migration.get("significant_down", False)

    if price_vs_ib == "upper_third_hug":
        # Check for bullish continuation
        if fattening_upper or acceptance_higher or significant_up:
            return "NA"  # Strong bullish acceptance, not Neutral-Upper
        return "Neutral-Upper"
    elif price_vs_ib == "lower_third_hug":
        # Check for bearish continuation
        if fattening_lower or acceptance_lower or significant_down:
            return "NA"  # Strong bearish acceptance, not Neutral-Lower
        return "Neutral-Lower"

    return "NA"


# ============================================================================
# RULE 13: MORPH STATUS STRING (10 lines)
# ============================================================================

def rule_13_morph_status(snapshot: Dict[str, Any]) -> str:
    """
    Rule 13: Generate morph status based on IB extension and DPOC migration.

    Uses IB extension directly (not just DPOC regime) so morph detection works
    as soon as price breaks IB, even before DPOC has enough completed slices.

    Logic:
    - Price holding beyond IB for 15+ mins → "Potential morph"
    - 30+ mins hold → "Morphing confirmed"
    - >1.5x IB extension → "Trend day confirmed"
    - DPOC trending_on_the_move + high retention → "Super-trending locked"

    Returns: String describing morph status
    """
    intraday = snapshot.get("intraday", {})
    ib = intraday.get("ib", {})
    dpoc_migration = intraday.get("dpoc_migration", {})

    ib_high = ib.get("ib_high")
    ib_low = ib.get("ib_low")
    ib_range = ib.get("ib_range", 0)
    current_close = ib.get("current_close")

    # Pre-IB: can't assess morph
    current_et_time = snapshot.get("current_et_time", "09:30")
    try:
        ct = time(*map(int, current_et_time.split(':')))
        if ct < time(10, 30):
            return "NA"
    except (ValueError, AttributeError):
        return "NA"

    if not ib_high or not ib_low or not ib_range or ib_range == 0 or not current_close:
        return "NA"

    # Calculate IB extension
    ext_above = max(0, current_close - ib_high)
    ext_below = max(0, ib_low - current_close)
    extension = max(ext_above, ext_below)
    ext_mult = extension / ib_range if ib_range > 0 else 0
    ext_dir = "up" if ext_above > ext_below else "down" if ext_below > ext_above else "flat"

    # DPOC regime (may be None if insufficient slices — that's OK)
    dpoc_regime = dpoc_migration.get("dpoc_regime", "")
    direction = dpoc_migration.get("direction", "flat")
    relative_retain = dpoc_migration.get("relative_retain_percent", 0)

    # Super-trending: DPOC confirms + large extension
    if dpoc_regime == "trending_on_the_move" and relative_retain >= 70 and ext_mult >= 1.0:
        dir_label = "Up" if ext_dir == "up" or direction == "up" else "Down"
        return f"Trend {dir_label} confirmed — super-trending ({ext_mult:.1f}x IB extension, DPOC on the move)"

    # Strong trend: >1.0x IB extension (even without DPOC confirmation)
    if ext_mult >= 1.0:
        dir_label = "Up" if ext_dir == "up" else "Down"
        return f"Morphing to Trend {dir_label} confirmed — {ext_mult:.1f}x IB extension"

    # Moderate extension: 0.5-1.0x → potential morph
    if ext_mult >= 0.5:
        dir_label = "Up" if ext_dir == "up" else "Down"
        return f"Potential morph to Trend {dir_label} — {ext_mult:.1f}x IB extension, watching for continuation"

    # Small extension with DPOC trending → potential morph
    if dpoc_regime in ["trending_fading_momentum", "trending_on_the_move"]:
        dir_label = "Up" if direction == "up" else "Down"
        return f"Potential morph to Trend {dir_label} — DPOC {dpoc_regime.replace('_', ' ')}"

    # No morph signals
    if ext_mult < 0.2:
        return "No morph — price inside IB range"

    return "Developing — watching for IB extension"


# ============================================================================
# RULE 14: BALANCE MORPH BIAS ADJUSTMENT (25 lines)
# ============================================================================

def rule_14_balance_morph_bias(snapshot: Dict[str, Any], current_bias: str = "Flat",
                                current_confidence: int = 50) -> Tuple[str, int, List[str]]:
    """
    Rule 14: Adjust bias/confidence when balance day morph is detected.

    Reads market_structure.balance_type.morph and applies:
    - morph confirmed neutral_to_bullish → bias += "Bullish", confidence += 10
    - morph confirmed neutral_to_bearish → bias += "Bearish", confidence += 10
    - morph confirmed to_trend_up → bias += "Very Bullish", confidence += 15
    - morph confirmed to_trend_down → bias += "Very Bearish", confidence += 15
    - morph developing → confidence += 5 (directional hint only)
    - morph none → no change

    Returns:
    - Updated bias
    - Confidence delta
    - Reasoning bullets
    """
    market_structure = snapshot.get("market_structure", {})
    balance_type_data = market_structure.get("balance_type", {})
    morph = balance_type_data.get("morph", {})

    morph_status = morph.get("status", "none")
    morph_type = morph.get("morph_type", "none")
    morph_confidence = morph.get("morph_confidence", 0.0)

    reasoning = []
    conf_delta = 0
    bias_adjusted = current_bias

    if morph_status == "none" or morph_type == "none":
        return bias_adjusted, conf_delta, reasoning

    morph_signals = morph.get("morph_signals", [])
    signal_summary = ", ".join(morph_signals[:3]) if morph_signals else "no signals"

    if morph_status == "confirmed":
        if morph_type == "neutral_to_bullish":
            bias_adjusted = "Bullish"
            conf_delta = 10
            reasoning.append(f"Balance morph CONFIRMED: neutral → bullish ({signal_summary})")
        elif morph_type == "neutral_to_bearish":
            bias_adjusted = "Bearish"
            conf_delta = 10
            reasoning.append(f"Balance morph CONFIRMED: neutral → bearish ({signal_summary})")
        elif morph_type == "to_trend_up":
            bias_adjusted = "Very Bullish"
            conf_delta = 15
            reasoning.append(f"Balance morph CONFIRMED: → trend up ({signal_summary})")
        elif morph_type == "to_trend_down":
            bias_adjusted = "Very Bearish"
            conf_delta = 15
            reasoning.append(f"Balance morph CONFIRMED: → trend down ({signal_summary})")
    elif morph_status == "developing":
        conf_delta = 5
        direction = "bullish" if "bullish" in morph_type or "up" in morph_type else "bearish"
        reasoning.append(f"Balance morph developing ({direction}, {morph_confidence:.0%} confidence): {signal_summary}")

    return bias_adjusted, conf_delta, reasoning


# ============================================================================
# MAIN ENGINE: ORCHESTRATE ALL RULES
# ============================================================================

def apply_inference_rules(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 1 Inference Engine: Apply all 8 HIGH-priority rules in order.

    Input: orchestrator snapshot containing:
    - session_date, current_et_time
    - intraday (ib, dpoc_migration, tpo_profile, volume_profile)
    - core_confluences (ib_acceptance, dpoc_vs_ib, dpoc_compression, price_location, etc.)

    Output: Preliminary decision dictionary with:
    - day_type (type, timestamp)
    - day_type_morph
    - trend_strength
    - bias
    - value_acceptance
    - tpo_read (profile_signals, dpoc_migration, extreme_or_compression)
    - confidence (0-100)
    - day_type_reasoning (list of bullets)
    - one_liner

    Rules applied in order:
    1. Rule 2: Trend Strength Quantification
    2. Rule 3: Weak Trend Strength Bias Cap
    3. Rule 4: DPOC Regime Rules
    4. Rule 5: IB Acceptance Rules
    5. Rule 6: DPOC Extreme Position
    6. Rule 7: DPOC Compression
    7. Rule 11: Neutral-Upper/Lower
    8. Rule 13: Morph Status String
    9. Rule 14: Balance Morph Bias Adjustment
    """
    # Initialize
    bias = "Flat"
    confidence = 50
    reasoning_bullets = []

    # Rule 2: Trend Strength
    trend_strength = rule_2_trend_strength(snapshot)
    if trend_strength != "NA":
        reasoning_bullets.append(f"Trend strength: {trend_strength}")

    # Rule 3: Weak Trend Cap (applied later, after bias determination)
    # Rule 4: DPOC Regime
    bias, conf_delta_regime, regime_reasoning = rule_4_dpoc_regime(snapshot, bias)
    confidence += conf_delta_regime
    reasoning_bullets.extend(regime_reasoning)

    # Rule 5: IB Acceptance (highest priority bias override)
    bias, conf_delta_ib, ib_reasoning = rule_5_ib_acceptance(snapshot, bias)
    confidence += conf_delta_ib
    reasoning_bullets.extend(ib_reasoning)

    # Rule 6: DPOC Extreme Position (unless already overridden by IB acceptance)
    conf_delta_extreme = 0
    if conf_delta_ib == 0:  # No IB acceptance override
        bias, conf_delta_extreme, extreme_reasoning = rule_6_dpoc_extreme_position(snapshot, bias)
        confidence += conf_delta_extreme
        reasoning_bullets.extend(extreme_reasoning)

    # Rule 7: DPOC Compression (unless already overridden)
    conf_delta_comp = 0
    if conf_delta_ib == 0:
        bias, conf_delta_comp, comp_reasoning = rule_7_dpoc_compression(snapshot, bias)
        confidence += conf_delta_comp
        reasoning_bullets.extend(comp_reasoning)

    # Rule 11: Neutral-Upper/Lower (skip if higher-priority rules already set directional bias)
    # Rules 5/6/7 are higher priority — IB acceptance, DPOC extreme, DPOC compression
    high_priority_fired = (conf_delta_ib != 0 or conf_delta_extreme != 0 or conf_delta_comp != 0)
    if not high_priority_fired:
        neutral_override = rule_11_neutral_upper_lower(snapshot)
        if neutral_override != "NA":
            bias = neutral_override
            reasoning_bullets.append(f"Price in {neutral_override.lower().replace('-', ' ')}: No momentum continuation — avoiding FOMO")

    # Rule 3: Apply weak trend cap AFTER bias is set
    bias, confidence = rule_3_weak_trend_cap(bias, confidence, trend_strength)
    if trend_strength == "Weak":
        reasoning_bullets.append(f"Weak trend strength cap applied: Bias downgraded, confidence capped at 75%")

    # Rule 13: Morph Status
    morph_status = rule_13_morph_status(snapshot)

    # Rule 14: Balance Morph Bias Adjustment
    bias, conf_delta_morph, morph_reasoning = rule_14_balance_morph_bias(snapshot, bias, confidence)
    confidence += conf_delta_morph
    reasoning_bullets.extend(morph_reasoning)

    # Build TPO read
    intraday = snapshot.get("intraday", {})
    core_confluences = snapshot.get("core_confluences", {})
    tpo_profile = intraday.get("tpo_profile", {})
    dpoc_migration = intraday.get("dpoc_migration", {})
    dpoc_vs_ib = core_confluences.get("dpoc_vs_ib", {})
    dpoc_compression = core_confluences.get("dpoc_compression", {})
    tpo_signals = core_confluences.get("tpo_signals", {})

    profile_signals = []
    if tpo_signals.get("fattening_upper"):
        profile_signals.append("Upper fattening")
    if tpo_signals.get("fattening_lower"):
        profile_signals.append("Lower fattening")
    if tpo_signals.get("single_prints_above"):
        profile_signals.append("Single prints high")
    if tpo_signals.get("single_prints_below"):
        profile_signals.append("Single prints low")
    if not profile_signals:
        profile_signals.append("Symmetric build")

    dpoc_mig_str = "NA"
    if dpoc_migration.get("dpoc_regime") not in ["no_data_yet", "pre_1030"]:
        pts = dpoc_migration.get("net_migration_pts", 0)
        direction = dpoc_migration.get("direction", "flat")
        dpoc_mig_str = f"DPOC migration {direction} {abs(pts):.1f} pts"

    extreme_or_comp = "none"
    if dpoc_vs_ib.get("dpoc_above_ibh"):
        extreme_or_comp = "extreme bullish shift"
    elif dpoc_vs_ib.get("dpoc_below_ibl"):
        extreme_or_comp = "extreme bearish shift"
    elif dpoc_compression.get("compressing_against_vah"):
        extreme_or_comp = "compressing against VAH (bullish)"
    elif dpoc_compression.get("compressing_against_val"):
        extreme_or_comp = "compressing against VAL (bearish)"

    # Build value acceptance string
    value_acceptance = "NA"
    poc_location = tpo_profile.get("current_poc")
    if poc_location:
        if poc_location > tpo_profile.get("current_vah", 0):
            value_acceptance = f"POC {poc_location} above VAH (bullish acceptance)"
        elif poc_location < tpo_profile.get("current_val", 0):
            value_acceptance = f"POC {poc_location} below VAL (bearish acceptance)"
        else:
            value_acceptance = f"POC {poc_location} inside VA"

    # Apply time-of-day confidence caps (per inference-json.md, lines 111-114)
    try:
        current_et_time = snapshot.get("current_et_time", "11:45")
        hour_minute = current_et_time.replace(":", "")  # "0930" format
        if hour_minute < "1000":
            confidence = min(confidence, 55)  # Before 10:00: max 55%
        elif hour_minute < "1030":
            confidence = min(confidence, 70)  # 10:00-10:30: max 70%
        # After 10:30: no cap
    except (ValueError, AttributeError):
        pass  # If time parsing fails, proceed without capping

    # Clamp confidence to 0-100
    confidence = max(0, min(100, confidence))

    # Determine day_type (placeholder - can be enhanced in Phase 2)
    day_type = _infer_day_type(snapshot, bias, trend_strength)

    # One-liner
    one_liner = _build_one_liner(bias, trend_strength, confidence, dpoc_migration.get("dpoc_regime"))

    # Build output dictionary
    output = {
        "day_type": {
            "type": day_type,
            "timestamp": f"{snapshot.get('session_date', 'YYYY-MM-DD')} / {snapshot.get('current_et_time', 'HH:MM')}"
        },
        "day_type_morph": morph_status,
        "trend_strength": trend_strength,
        "bias": bias,
        "value_acceptance": value_acceptance,
        "tpo_read": {
            "profile_signals": " | ".join(profile_signals) if profile_signals else "NA",
            "dpoc_migration": dpoc_mig_str,
            "extreme_or_compression": extreme_or_comp
        },
        "confidence": confidence,
        "day_type_reasoning": reasoning_bullets if reasoning_bullets else ["NA"],
        "one_liner": one_liner
    }

    return output


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _infer_day_type(snapshot: Dict[str, Any], bias: str, trend_strength: str) -> str:
    """
    Infer day_type from IB extension, bias, trend strength, and DPOC regime.

    Uses IB extension data directly (not just DPOC regime) so classification
    works even before DPOC has enough completed slices.
    """
    intraday = snapshot.get("intraday", {})
    ib = intraday.get("ib", {})
    dpoc_migration = intraday.get("dpoc_migration", {})
    dpoc_regime = dpoc_migration.get("dpoc_regime", "")
    direction = dpoc_migration.get("direction", "flat")

    ib_high = ib.get("ib_high")
    ib_low = ib.get("ib_low")
    ib_range = ib.get("ib_range", 0)
    current_close = ib.get("current_close")

    # Calculate IB extension directly
    ext_direction = "flat"
    extension_mult = 0.0
    if ib_high and ib_low and ib_range and ib_range > 0 and current_close:
        ext_above = max(0, current_close - ib_high)
        ext_below = max(0, ib_low - current_close)
        if ext_above > ext_below:
            extension_mult = ext_above / ib_range
            ext_direction = "up"
        elif ext_below > ext_above:
            extension_mult = ext_below / ib_range
            ext_direction = "down"

    # Strong/Super trend strength or large IB extension → Trend day
    if trend_strength in ["Strong", "Super"]:
        return "Trend Up" if ext_direction == "up" or direction == "up" else \
               "Trend Down" if ext_direction == "down" or direction == "down" else "Trend Up"

    # >1.0x IB extension → Trend day even without DPOC confirmation
    if extension_mult >= 1.0:
        return "Trend Up" if ext_direction == "up" else "Trend Down"

    # DPOC regime trending → Trend day
    if dpoc_regime == "trending_on_the_move":
        return "Trend Up" if direction == "up" else "Trend Down"

    # 0.5-1.0x IB extension → P-Day (directional but not full trend)
    if extension_mult >= 0.5:
        return "P-Day Up" if ext_direction == "up" else "P-Day Down"

    # Bias-based classification
    if bias in ["Very Bullish", "Very Bearish"]:
        return "Trend Up" if "Bullish" in bias else "Trend Down"

    # Confirmed choppy DPOC + price inside IB → Balance
    if dpoc_regime == "balancing_choppy" and extension_mult < 0.3:
        return "Balance"

    # 0.2-0.5x extension with fading momentum → P-Day (marginal breakout)
    if extension_mult >= 0.2 and dpoc_regime == "trending_fading_momentum":
        return "P-Day Up" if ext_direction == "up" else "P-Day Down"

    # Inside IB with no meaningful extension → Neutral Range or Balance
    if extension_mult < 0.2:
        if dpoc_regime in ["balancing_choppy", "transitional_unclear"]:
            return "Balance"
        return "Neutral Range"

    # Small extension (0.2-0.5x) with unclear DPOC → Neutral Range
    return "Neutral Range"


def _build_one_liner(bias: str, trend_strength: str, confidence: int, dpoc_regime: str = "") -> str:
    """
    Build a single high-conviction line summarizing the bias, strength, and setup.
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

    regime_clause = f" — {regime_text}" if regime_text else ""

    one_liner = f"{bias} ({strength_text} trend, {confidence}% confidence){regime_clause}"

    return one_liner
