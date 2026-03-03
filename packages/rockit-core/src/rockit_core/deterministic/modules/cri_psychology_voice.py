#!/usr/bin/env python3
"""
CRI Psychology Voice Injection

Maps market terrain (A1-A4) + posture to trader psychology and permission.

Critical insight: CRI tells you WHAT THE MARKET IS SAYING about what's allowed.

A1 (Expanding, Clean): 🔥 WARRIOR - "Go for the KILL. Full aggression justified."
A2 (Hesitant): ⚠️ SQUIRE - "Market is uncertain. Probe 1/3 size. Respect risk."
A3 (Trending): 🎯 KNIGHT - "Methodical. Wait for confirmation. Patience wins."
A4 (Failed): 🛑 OBSERVER - "Market is broken. Stand down. Not your trade."

This is NOT about setup quality - it's about MARKET PERMISSION.
Same setup in A1 = FULL SIZE. Same setup in A2 = 1/3 PROBE.
"""


def inject_cri_psychology(snapshot, playbook_confidence, dpoc_mig, market_events):
    """
    Extract CRI psychology and translate to trader conviction.

    Returns: (terrain_type, market_posture, permission_level, psychology_narrative)
    """

    cri = snapshot.get("cri_readiness", {})
    overall_status = cri.get("overall_status", "STAND_DOWN")
    terrain = cri.get("terrain", {})
    terrain_class = terrain.get("classification", "A4")
    terrain_expansion = terrain.get("expansion_level", "minimal")

    posture = cri.get("market_posture", {})
    posture_type = posture.get("posture_type", "passive")
    posture_strength = posture.get("posture_strength", "weak")

    permission = cri.get("permission_logic", {})
    max_size = permission.get("max_size_allowed", "PROBE_ONLY")
    aggression_level = permission.get("aggression_level", "caution")

    psychology_narrative = ""
    market_signal = ""

    # ─────────────────────────────────────────────────────────────
    # A1: CLEAN EXPANDING - WARRIOR PSYCHOLOGY
    # ─────────────────────────────────────────────────────────────

    if terrain_class == "A1" and "expanding" in terrain_expansion:
        market_signal = "🔥 A1 WARRIOR TERRAIN"

        if "clean" in terrain_expansion or posture_type == "aggressive":
            if max_size == "FULL_SIZE" and overall_status == "READY":
                psychology_narrative = (
                    "🔥🔥🔥 A1 TERRAIN ACTIVE. CLEAN & EXPANDING. "
                    "Market is saying 'GO FOR THE KILL.' This is YOUR moment. "
                    "Conviction is JUSTIFIED. Full 3/3 size execution. "
                    "Sellers/buyers are CRUSHED. No hesitation. Attack."
                )
            elif max_size == "FULL_SIZE" and overall_status == "PROBE_ONLY":
                psychology_narrative = (
                    "🔥 A1 TERRAIN with PROBE STATUS. Market expanding but caution flag. "
                    "Start 2/3 size, probe the reaction. If buyers/sellers step in, scale to FULL. "
                    "Conviction is building."
                )
        else:
            psychology_narrative = (
                "🔥 A1 TERRAIN FORMING. Market is expanding but not yet CLEAN. "
                "Get ready. This is the setup phase. When it cleans up, attack with FULL conviction."
            )

    # ─────────────────────────────────────────────────────────────
    # A2: HESITANT - SQUIRE PSYCHOLOGY
    # ─────────────────────────────────────────────────────────────

    elif terrain_class == "A2":
        market_signal = "⚠️ A2 SQUIRE TERRAIN"

        if posture_strength == "weak" or "hesitant" in posture_type:
            psychology_narrative = (
                "⚠️ A2 TERRAIN. Market is UNCERTAIN and HESITANT. "
                "Buyers AND sellers are questioning the move. "
                "This is NOT a conviction trade. Probe 1/3 size ONLY. Tight stops. "
                "Ready to exit. Market is playing defense, not attack."
            )
        else:
            psychology_narrative = (
                "⚠️ A2 TERRAIN (SQUIRE). Market is developing but uncertain. "
                "Permission: 2/3 size maximum. Ready to scale down if conviction fails. "
                "This could flip either way. Respect the uncertainty."
            )

    # ─────────────────────────────────────────────────────────────
    # A3: TRENDING - KNIGHT PSYCHOLOGY
    # ─────────────────────────────────────────────────────────────

    elif terrain_class == "A3":
        market_signal = "🎯 A3 KNIGHT TERRAIN"

        if "trending" in posture_type and posture_strength == "strong":
            psychology_narrative = (
                "🎯 A3 TERRAIN (KNIGHT MODE). Market is TRENDING with CONVICTION. "
                "But Knight philosophy: 'Wait for confirmation.' "
                "Don't jump in early. Wait for pullback/support hold. "
                "When it confirms, 2/3 size scale. Methodical wins. No FOMO."
            )
        elif "trending" in posture_type:
            psychology_narrative = (
                "🎯 A3 TERRAIN. Trend is forming but not yet PROVEN. "
                "Methodical approach: Probe 1/3, wait for 2nd bar confirmation, then scale. "
                "Knight principle: Patience beats speed."
            )
        else:
            psychology_narrative = (
                "🎯 A3 TERRAIN DEVELOPING. Market has potential but needs setup confirmation. "
                "Don't rush. Wait. Good entry will present itself. Timing > Size."
            )

    # ─────────────────────────────────────────────────────────────
    # A4: FAILED - OBSERVER PSYCHOLOGY
    # ─────────────────────────────────────────────────────────────

    elif terrain_class == "A4" or posture_type == "passive":
        market_signal = "🛑 A4 OBSERVER TERRAIN"

        psychology_narrative = (
            "🛑 A4 TERRAIN (OBSERVER MODE). Market FAILED. "
            "Breakouts rejected. Buyers exhausted. Sellers overwhelmed. "
            "Market is BROKEN. Don't trade this. HANDS COMPLETELY OFF. "
            "Wait for A1-A3 to set up. Not your trade."
        )

    # ─────────────────────────────────────────────────────────────
    # DEFAULT / TRANSITION
    # ─────────────────────────────────────────────────────────────

    else:
        market_signal = f"? {terrain_class} TERRAIN (Transitional)"
        psychology_narrative = (
            f"Terrain: {terrain_class}. Market is in transition. "
            f"Unclear what's forming. Watch and wait. Clarity is coming."
        )

    # ─────────────────────────────────────────────────────────────
    # POSTURE-SPECIFIC WAKE UP CALLS
    # ─────────────────────────────────────────────────────────────

    if overall_status == "READY" and terrain_class in ["A1", "A3"]:
        wake_up_call = " 🔔 WAKE UP - MARKET IS READY. SOMETHING IS HAPPENING HERE."
        psychology_narrative += wake_up_call

    if overall_status == "PROBE_ONLY":
        probe_call = " ⚡ PROBE SIGNAL - Test the waters. Market says 'be careful.'"
        psychology_narrative += probe_call

    if overall_status == "STAND_DOWN" and terrain_class == "A4":
        standdown_call = " ❌ MARKET SAYS NO. Hands off desk completely."
        psychology_narrative += standdown_call

    return {
        "terrain_type": terrain_class,
        "terrain_description": terrain_expansion,
        "market_posture": posture_type,
        "posture_strength": posture_strength,
        "permission_level": max_size,
        "aggression_level": aggression_level,
        "market_signal": market_signal,
        "psychology_narrative": psychology_narrative,
        "overall_status": overall_status
    }


def get_cri_based_sizing(terrain_class, cri_status, setup_quality_confidence):
    """
    Get position sizing recommendation based on TERRAIN, not just setup quality.

    CRITICAL: Same setup = different sizes in different terrain.

    Example:
    - Setup confidence: 75% (good breakout)
    - A1 terrain: 3/3 full size (permission granted)
    - A2 terrain: 1/3 probe size (market uncertain)
    - A4 terrain: 0 (stand down)
    """

    if cri_status == "STAND_DOWN" or terrain_class == "A4":
        return {
            "size": "HANDS OFF",
            "notation": "0/3",
            "reasoning": "Market is broken. No permission."
        }

    if terrain_class == "A1":
        if setup_quality_confidence > 70:
            return {
                "size": "FULL AGGRESSION",
                "notation": "3/3",
                "reasoning": f"A1 terrain + {setup_quality_confidence}% setup = Full size justified. Market is saying ATTACK."
            }
        else:
            return {
                "size": "2/3 SCALE",
                "notation": "2/3",
                "reasoning": f"A1 terrain but setup only {setup_quality_confidence}%. Start 2/3, add if confirms."
            }

    if terrain_class == "A3":
        if setup_quality_confidence > 70 and cri_status == "READY":
            return {
                "size": "METHODICAL ENTRY",
                "notation": "2/3",
                "reasoning": f"A3 trend + {setup_quality_confidence}% setup. Knight approach: 2/3 on confirmation, hold for pullback."
            }
        else:
            return {
                "size": "PROBE 1/3",
                "notation": "1/3",
                "reasoning": f"A3 terrain developing. Probe 1/3, wait for 2nd confirmation bar, then scale."
            }

    if terrain_class == "A2":
        return {
            "size": "PROBE ONLY",
            "notation": "1/3",
            "reasoning": f"A2 hesitant terrain. Setup {setup_quality_confidence}% but market uncertain. Probe 1/3, tight stops, ready to exit."
        }

    return {
        "size": "UNCLEAR",
        "notation": "?",
        "reasoning": f"Terrain {terrain_class} unclear. Watch first."
    }


def detect_terrain_setup_conflict(snapshot, playbook_match, bias_signal):
    """
    Detect conflicts between setup and terrain.

    Examples:
    - Setup: SHORT (good technical rejection at VAH)
      Terrain: A1 (bullish, expanding)
      Conflict: ❌ "Don't short in A1 WARRIOR terrain. Buyers are attacking."

    - Setup: LONG (trend following)
      Terrain: A4 (failed, choppy)
      Conflict: ❌ "Don't trend trade in A4. Too choppy. Fade instead."
    """

    cri = snapshot.get("cri_readiness", {})
    terrain = cri.get("terrain", {}).get("classification", "A4")

    conflicts = []

    # A1 BULLISH: Don't go short
    if terrain == "A1":
        if bias_signal.lower() in ["bearish", "short", "bearish_conviction"]:
            conflicts.append(
                "❌ NO SHORT HERE. A1 BULLISH WARRIOR TERRAIN. Buyers are ATTACKING. "
                "Shorts will get CRUSHED. This is a LONG market. Respect the terrain."
            )

    # A4 CHOPPY: Don't trend follow
    if terrain == "A4":
        if playbook_match == "Trend Following":
            conflicts.append(
                "❌ DON'T TREND FOLLOW IN A4. Market is BROKEN and CHOPPY. "
                "Trends fail here. Fade the extremes instead. Mean reversion only."
            )

    # A3 TRENDING: Don't mean revert
    if terrain == "A3":
        if playbook_match == "Mean Reversion":
            conflicts.append(
                "⚠️ A3 TREND TERRAIN. Mean reversion setup but market is TRENDING. "
                "Trend is your friend. Don't fade. Follow the trend instead."
            )

    return conflicts


def create_cri_psychology_block(snapshot, confidence, playbook_match="", bias_signal=""):
    """
    Create the full CRI psychology block for training data.
    Includes conflict detection: "This setup doesn't belong in this terrain."
    """

    cri_block = inject_cri_psychology(
        snapshot,
        confidence,
        snapshot.get("intraday", {}).get("dpoc_migration", {}).get("net_migration_pts", 0),
        {}
    )

    sizing = get_cri_based_sizing(
        cri_block["terrain_type"],
        cri_block["overall_status"],
        confidence
    )

    # CONFLICT DETECTION: Setup vs Terrain
    conflicts = detect_terrain_setup_conflict(snapshot, playbook_match, bias_signal)

    conflict_warning = ""
    if conflicts:
        conflict_warning = " ".join(conflicts)

    return {
        "cri_psychology": cri_block,
        "sizing_recommendation": sizing,
        "market_permission": f"{cri_block['permission_level']} ({sizing['notation']})",
        "terrain_conflict": conflict_warning if conflict_warning else None,
        "trader_wake_up_call": "🔔 WAKE UP - MARKET READY" if cri_block["overall_status"] == "READY" and cri_block["terrain_type"] in ["A1", "A3"] else ""
    }


# ─────────────────────────────────────────────────────────────
# EXAMPLE: What the LLM should learn to SAY
# ─────────────────────────────────────────────────────────────

EXAMPLE_A1_WARRIOR = """
🔥 A1 WARRIOR TERRAIN ACTIVE.
Market is CLEAN and EXPANDING. Buyers are CRUSHING sellers.
Permission: FULL 3/3 SIZE AGGRESSION.
This is YOUR moment. No hesitation. Attack with conviction.
DPOC is advancing, bars holding, this trend is REAL.
Go for the kill. Full size execution justified.
"""

EXAMPLE_A2_SQUIRE = """
⚠️ A2 SQUIRE TERRAIN.
Market is HESITANT and UNCERTAIN. Buyers and sellers questioning the move.
Permission: PROBE 1/3 SIZE ONLY. Tight stops. Ready to exit.
Don't fall for the fake. Respect the uncertainty.
If market proves conviction, scale to 2/3. But start small.
"""

EXAMPLE_A3_KNIGHT = """
🎯 A3 KNIGHT TERRAIN.
Market is TRENDING but needs CONFIRMATION.
Permission: METHODICAL 2/3 SIZE APPROACH.
Don't jump in early. Probe 1/3 on setup, wait for 2nd bar hold, then scale to 2/3.
Knight philosophy: Patience wins. Timing beats speed.
Wait for the pullback or support hold. Good entry will come.
"""

EXAMPLE_A4_OBSERVER = """
🛑 A4 OBSERVER TERRAIN.
Market FAILED. Breakouts rejected. Momentum exhausted.
Permission: HANDS COMPLETELY OFF. ZERO POSITION.
Don't trade this. Not your fight. Market is broken.
Wait for A1-A3 setup to form. Better opportunities coming.
"""
