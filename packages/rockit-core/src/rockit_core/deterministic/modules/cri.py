# modules/cri.py
"""
Contextual Readiness Index (CRI) module.
Computes trading readiness based on volatility, reclaim, breath, trap, and terrain analysis.

CRI computes:
- Volatility State: Low/Medium/High based on ATR multiplier
- Reclaim Status: Analysis of key levels (IBH, IBL, VAH, VAL, VWAP, PDH, PDL, London levels)
- Breath Analysis: Market expansion/shallow/erratic based on DPOC migration
- Trap Detection: Wick parade analysis for trap detection
- Terrain Classification: A1/A3 (Clean/Expanding), A2 (Hesitant), A4 (Failed)
- Posture Proxy: Torque analysis via volume spikes
- Identity Mapping: Warrior/Squire/Knight/Observer based on terrain + trend
- Permission Logic: Size caps and aggression levels
- Overall Status: STAND_DOWN, PROBE_ONLY, READY
"""

from rockit_core.deterministic.modules.dalton import get_trend_analysis


# === Configuration Thresholds ===
VOLATILITY_LOW_THRESHOLD = 0.8
VOLATILITY_HIGH_THRESHOLD = 1.5
RECLAIM_MIN_CLOSES = 2
RECLAIM_MIN_TPO = 1
RECLAIM_BUFFER_PTS = 10
TRAP_WICK_THRESHOLD = 6


def get_cri_readiness(df_nq, intraday_data, premarket_data, current_time_str="11:45"):
    """
    Main entry point for CRI computation.

    Args:
        df_nq: DataFrame with 5-min price data
        intraday_data: Dict from orchestrator containing all intraday module outputs
        premarket_data: Dict from premarket module
        current_time_str: Current snapshot time

    Returns:
        dict: CRI readiness dictionary with overall_status, terrain, identity, permission, etc.
    """
    # Extract required data from intraday_data
    ib_data = intraday_data.get('ib', {})
    wick_data = intraday_data.get('wick_parade', {})
    dpoc_data = intraday_data.get('dpoc_migration', {})
    volume_profile = intraday_data.get('volume_profile', {})
    tpo_profile = intraday_data.get('tpo_profile', {})
    core_confluences = intraday_data.get('core_confluences', {})
    trend_analysis = intraday_data.get('trend_analysis', {})

    # Get current price and ATR
    current_close = ib_data.get('current_close')
    atr14 = ib_data.get('atr14', 25)  # Default ATR if not available
    current_volume = ib_data.get('current_volume', 0)

    if current_close is None:
        return _empty_cri_result("no_price_data")

    # === 1. Compute Volatility State ===
    volatility = _compute_volatility(ib_data, atr14)

    # === 2. Compute Reclaim Status ===
    reclaim = _compute_reclaim(intraday_data, premarket_data, current_close)

    # === 3. Compute Breath Analysis ===
    breath = _compute_breath(dpoc_data)

    # === 4. Compute Trap Detection ===
    trap = _compute_trap(wick_data)

    # === 5. Aggregate Terrain ===
    terrain = _aggregate_terrain(volatility, reclaim, breath, trap)

    # === 6. Compute Posture Proxy ===
    posture = _compute_posture_proxy(intraday_data, current_volume)

    # === 7. Map Identity ===
    identity = _map_identity(terrain, trend_analysis, core_confluences)

    # === 8. Apply Permission ===
    permission = _apply_permission(terrain, identity, trend_analysis, trap)

    # === 9. Derive Overall Status ===
    overall_status = _derive_overall_status(terrain, posture, identity, permission)

    # === 10. Compile Danger Flags ===
    danger_flags = _compile_danger_flags(terrain, trap, volatility, dpoc_data)

    # === 11. Build Readiness Summary ===
    readiness_summary = _build_readiness_summary(overall_status, terrain, posture, reclaim)

    return {
        "overall_status": overall_status,
        "posture": posture,
        "terrain": terrain,
        "identity": identity,
        "permission": permission,
        "reclaim": reclaim,
        "volatility": volatility,
        "breath": breath,
        "trap": trap,
        "danger_flags": danger_flags,
        "readiness_summary": readiness_summary
    }


def _compute_volatility(ib_data, atr14):
    """Compute volatility state based on ATR and IB range."""
    ib_range = ib_data.get('ib_range', 0)

    if ib_range is None or ib_range == 0 or atr14 is None:
        return {
            "state": "Medium",
            "atr14": atr14 or 25,
            "ib_range": ib_range or 0,
            "atr_to_ib_ratio": 1.0,
            "note": "insufficient_data_for_volatility"
        }

    # ATR as multiple of IB range
    atr_to_ib_ratio = atr14 / ib_range

    if atr_to_ib_ratio < VOLATILITY_LOW_THRESHOLD:
        state = "Low"
    elif atr_to_ib_ratio > VOLATILITY_HIGH_THRESHOLD:
        state = "High"
    else:
        state = "Medium"

    return {
        "state": state,
        "atr14": round(atr14, 2),
        "ib_range": round(ib_range, 2),
        "atr_to_ib_ratio": round(atr_to_ib_ratio, 2),
        "note": f"Volatility {state}: ATR/IB ratio {atr_to_ib_ratio:.2f}"
    }


def _compute_reclaim(intraday_data, premarket_data, current_close):
    """Compute reclaim status for key levels."""
    reclaim_data = []
    clean_count = 0
    hesitant_count = 0
    failed_count = 0

    # Define levels to check (simplified for now)
    levels = [
        {"name": "IBH", "value": intraday_data.get('ib', {}).get('ib_high')},
        {"name": "IBL", "value": intraday_data.get('ib', {}).get('ib_low')},
        {"name": "VAH", "value": intraday_data.get('volume_profile', {}).get('current_session', {}).get('vah')},
        {"name": "VAL", "value": intraday_data.get('volume_profile', {}).get('current_session', {}).get('val')},
    ]

    for level_info in levels:
        level_name = level_info['name']
        level_value = level_info['value']

        if level_value is None or level_value == 'not_available':
            continue

        distance = current_close - level_value
        is_above = distance > 0
        distance_pts = abs(distance)

        if distance_pts <= RECLAIM_BUFFER_PTS:
            status = "testing"
            score = 2.0
        elif is_above:
            if distance_pts > RECLAIM_BUFFER_PTS * 2:
                status = "clean_reclaim"
                score = 4.0
                clean_count += 1
            else:
                status = "hesitant_reclaim"
                score = 3.0
                hesitant_count += 1
        else:
            if distance_pts > RECLAIM_BUFFER_PTS * 2:
                status = "failed_reclaim"
                score = 1.0
                failed_count += 1
            else:
                status = "hesitant_reclaim"
                score = 2.0
                hesitant_count += 1

        reclaim_data.append({"level": level_name, "status": status, "score": score})

    # Aggregate scores
    if clean_count > 0:
        state = "Clean"
        avg_score = 4.0 if clean_count >= 2 else 3.5
    elif hesitant_count >= failed_count:
        state = "Hesitant"
        avg_score = 2.5
    else:
        state = "Failed"
        avg_score = 1.5

    return {
        "state": state,
        "score": avg_score,
        "clean_count": clean_count,
        "hesitant_count": hesitant_count,
        "failed_count": failed_count,
        "key_summary": f"{state} reclaim ({clean_count} clean, {hesitant_count} hesitant, {failed_count} failed)",
        "reclaim_data": reclaim_data
    }


def _compute_breath(dpoc_data):
    """Compute breath analysis (market expansion/shallow/erratic)."""
    if not dpoc_data:
        return {
            "state": "Shallow",
            "direction": "flat",
            "velocity": 0,
            "score": 2.0,
            "note": "no_dpoc_data"
        }

    direction = dpoc_data.get('direction', 'flat')
    velocity = abs(dpoc_data.get('avg_velocity_per_30min', 0))
    dpoc_regime = dpoc_data.get('dpoc_regime', '')
    is_stabilizing = dpoc_data.get('is_stabilizing', False)
    oscillating = 'balancing' in dpoc_regime.lower() if dpoc_regime else False

    if oscillating:
        state = "Erratic"
        score = 1.0
    elif is_stabilizing:
        state = "Shallow"
        score = 2.0
    elif velocity >= 25:
        state = "Expansion"
        score = 4.0
    elif velocity >= 10:
        state = "Shallow"
        score = 3.0
    else:
        state = "Shallow"
        score = 2.0

    return {
        "state": state,
        "direction": direction,
        "velocity": round(velocity, 2),
        "dpoc_regime": dpoc_regime,
        "score": score,
        "note": f"Breath {state}: DPOC {direction} at {velocity:.1f} pts/30min"
    }


def _compute_trap(wick_data):
    """Compute trap detection based on wick parade."""
    if not wick_data:
        return {
            "detected": False,
            "type": "None",
            "bullish_wick_count": 0,
            "bearish_wick_count": 0,
            "score": 4.0,
            "note": "no_wick_data"
        }

    bullish_count = wick_data.get('bullish_wick_parade_count', 0)
    bearish_count = wick_data.get('bearish_wick_parade_count', 0)

    if bullish_count >= TRAP_WICK_THRESHOLD:
        detected = True
        trap_type = "Bear Trap"
        score = 1.0
    elif bearish_count >= TRAP_WICK_THRESHOLD:
        detected = True
        trap_type = "Bull Trap"
        score = 1.0
    else:
        detected = False
        trap_type = "None"
        score = 4.0

    return {
        "detected": detected,
        "type": trap_type,
        "bullish_wick_count": bullish_count,
        "bearish_wick_count": bearish_count,
        "score": score,
        "note": f"Trap: {trap_type} (bullish wicks: {bullish_count}, bearish wicks: {bearish_count})"
    }


def _aggregate_terrain(volatility, reclaim, breath, trap):
    """Aggregate terrain classification from component scores."""
    signals = []

    # Collect scores
    vol_score = 4.0 if volatility.get('state') == 'Low' else 3.0 if volatility.get('state') == 'Medium' else 2.0
    rec_score = reclaim.get('score', 2.0)
    breath_score = breath.get('score', 2.0)
    trap_score = trap.get('score', 4.0)

    # Weighted average
    total_score = (vol_score * 0.2 + rec_score * 0.3 + breath_score * 0.25 + trap_score * 0.25)

    # Build signals
    signals.append(f"Volatility: {volatility.get('state', 'Unknown')}")
    signals.append(f"Reclaim: {reclaim.get('state', 'Unknown')}")
    signals.append(f"Breath: {breath.get('state', 'Unknown')}")
    if trap.get('detected', False):
        signals.append(f"TRAP DETECTED: {trap.get('type', 'Unknown')}")

    # Classify terrain
    if total_score >= 3.0:
        classification = "A1/A3"
    elif total_score >= 2.0:
        classification = "A2"
    else:
        classification = "A4"

    # BUG FIX #3: Include trap in returned terrain dict
    return {
        "classification": classification,
        "score": round(total_score, 2),
        "key_signals": signals,
        "trap": trap,  # <-- ADD TRAP HERE (Bug fix)
        "component_scores": {
            "volatility": vol_score,
            "reclaim": rec_score,
            "breath": breath_score,
            "trap": trap_score
        }
    }


def _compute_posture_proxy(intraday_data, current_volume):
    """Compute posture proxy based on volume torque analysis."""
    dpoc_data = intraday_data.get('dpoc_migration', {})

    is_stabilizing = dpoc_data.get('is_stabilizing', False)
    prior_exhausted = dpoc_data.get('prior_exhausted', False)
    dpoc_regime = dpoc_data.get('dpoc_regime', '')

    volume_spike = current_volume > 10000 if current_volume else False

    if 'trending_on_the_move' in dpoc_regime:
        state = "High Torque"
        score = 2.0
        signal = "Posture: High torque - trending with momentum"
    elif is_stabilizing and not prior_exhausted:
        state = "Stabilized"
        score = 4.0
        signal = "Posture: Stabilized - floor/ceiling forming"
    elif prior_exhausted:
        state = "Mild Torque"
        score = 2.5
        signal = "Posture: Exhausted trend - potential reversal"
    elif volume_spike:
        state = "High Torque"
        score = 2.0
        signal = "Posture: Volume spike detected - high torque"
    else:
        state = "Stabilized"
        score = 3.5
        signal = "Posture: Normal conditions"

    return {
        "state": state,
        "score": score,
        "signal": signal
    }


def _map_identity(terrain, trend_analysis, core_confluences):
    """Map trader identity based on terrain and trend."""
    terrain_class = terrain.get('classification', 'A4')
    trend_strength = trend_analysis.get('trend_strength', 'Weak')
    trend_confirmed = trend_analysis.get('trend_confirmed', False)

    # Map identity
    if terrain_class == "A1/A3" and trend_strength in ["Super", "Strong"]:
        identity = "Warrior"
        match = "Aligned"
    elif terrain_class in ["A1/A3", "A2"] and trend_confirmed:
        identity = "Knight"
        match = "Aligned"
    elif terrain_class == "A2" and trend_strength in ["Moderate", "Weak"]:
        identity = "Squire"
        match = "Partial"
    elif terrain_class == "A4":
        identity = "Observer"
        match = "Partial"
    else:
        identity = "Squire"
        match = "Partial"

    return {
        "permitted": identity,
        "match": match,
        "trend_strength": trend_strength,
        "terrain_class": terrain_class,
        "note": f"Identity: {identity} ({match}) - Terrain {terrain_class}, Trend {trend_strength}"
    }


def _apply_permission(terrain, identity, trend_analysis, trap):
    """Apply permission logic based on identity and terrain."""
    identity_type = identity.get('permitted', 'Observer')
    terrain_class = terrain.get('classification', 'A4')
    trap_detected = trap.get('detected', False)  # BUG FIX: Get trap from parameter, not terrain

    # Permission matrix
    if identity_type == "Warrior" and terrain_class == "A1/A3":
        size_cap = "Full"
        aggression = "Pyramid OK"
    elif identity_type == "Knight" and terrain_class in ["A1/A3", "A2"]:
        size_cap = "Half"
        aggression = "Single entry only"
    elif identity_type == "Squire":
        size_cap = "Micro"
        aggression = "Single entry only"
    else:
        size_cap = "Flat"
        aggression = "No entry"

    # Override for trap detection
    if trap_detected:
        aggression = "No entry"
        size_cap = "Flat"

    return {
        "size_cap": size_cap,
        "aggression": aggression,
        "note": f"Permission: {size_cap} size, {aggression}"
    }


def _derive_overall_status(terrain, posture, identity, permission):
    """Derive overall CRI status."""
    terrain_class = terrain.get('classification', 'A4')
    terrain_score = terrain.get('score', 0)
    posture_state = posture.get('state', 'High Torque')
    identity_type = identity.get('permitted', 'Observer')
    permission_aggression = permission.get('aggression', 'No entry')

    # Decision logic
    if permission_aggression == "No entry":
        return "STAND_DOWN"
    elif terrain_class == "A4":
        return "STAND_DOWN"
    elif identity_type == "Observer":
        return "STAND_DOWN"
    elif terrain_class == "A2" or identity_type == "Squire":
        return "PROBE_ONLY"
    elif terrain_score >= 3.0 and posture_state == "Stabilized":
        return "READY"
    elif terrain_score >= 2.5 and identity_type in ["Warrior", "Knight"]:
        return "READY"
    else:
        return "PROBE_ONLY"


def _compile_danger_flags(terrain, trap, volatility, dpoc_data):
    """Compile list of danger flags for the current state."""
    flags = []

    # Trap detection
    if trap.get('detected', False):
        flags.append(f"TRAP: {trap.get('type', 'Unknown')}")

    # High volatility
    if volatility.get('state') == 'High':
        flags.append("HIGH_VOLATILITY: ATR/IB ratio elevated")

    # Failed terrain
    if terrain.get('classification') == 'A4':
        flags.append("TERRAIN_FAILED: Multiple reclaim failures")

    # DPOC exhaustion
    if dpoc_data.get('prior_exhausted', False):
        flags.append("DPOC_EXHAUSTED: Extended migration with retention <50%")

    # DPOC reversal potential
    if 'potential_bpr_reversal' in dpoc_data.get('dpoc_regime', ''):
        flags.append("POTENTIAL_REVERSAL: DPOC exhausted + reclaiming opposite")

    return flags


def _build_readiness_summary(overall_status, terrain, posture, reclaim):
    """Build human-readable readiness summary."""
    terrain_class = terrain.get('classification', 'Unknown')
    posture_state = posture.get('state', 'Unknown')
    reclaim_state = reclaim.get('state', 'Unknown')

    summary = f"{overall_status} - {terrain_class} terrain, {posture_state} posture, reclaim {reclaim_state}"

    return summary


def _empty_cri_result(note):
    """Return empty CRI result dict with note."""
    return {
        "overall_status": "STAND_DOWN",
        "posture": {
            "state": "Unknown",
            "score": 0,
            "signal": "No data"
        },
        "terrain": {
            "classification": "A4",
            "score": 0,
            "key_signals": [],
            "trap": {"detected": False, "type": "None"}
        },
        "identity": {
            "permitted": "Observer",
            "match": "Partial"
        },
        "permission": {
            "size_cap": "Flat",
            "aggression": "No entry"
        },
        "reclaim": {
            "state": "Unknown",
            "score": 0,
            "key_summary": "No data"
        },
        "volatility": {
            "state": "Unknown"
        },
        "breath": {
            "state": "Unknown"
        },
        "trap": {
            "detected": False,
            "type": "None"
        },
        "danger_flags": ["NO_DATA"],
        "readiness_summary": f"STAND_DOWN - {note}",
        "note": note
    }
