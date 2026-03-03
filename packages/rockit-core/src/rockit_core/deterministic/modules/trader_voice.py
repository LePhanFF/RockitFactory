#!/usr/bin/env python3
"""
Trader Voice Injection

Adds conviction-based trading commentary to training data.
Not dry technical analysis - real trader perspective with clear bias and action.

Key principle: The LLM should learn to think like a trader, not like a bot.
Examples:
- "Sellers CRUSHED. Reclaimed VAL with strong fattening. LONG here. Size it."
- "Stop fading. DPOC +85pts, bars IBH. This TREND is real. Full conviction."
- "Ambiguous. DPOC flat, balance forming. HANDS OFF. Not worth it."
"""


def inject_trader_voice(snapshot, market_events, playbook, confidence, dpoc_mig, features):
    """
    Convert technical output into trader voice with conviction and bias.

    Returns: String with trader's direct perspective
    """

    intraday = snapshot.get("intraday", {})
    ib = intraday.get("ib", {})
    vp = intraday.get("volume_profile", {}).get("current_session", {})
    dpoc = intraday.get("dpoc_migration", {})
    tpo = intraday.get("tpo_profile", {})

    current_close = ib.get("current_close", 0)
    ib_high = ib.get("ib_high", 0)
    ib_low = ib.get("ib_low", 0)
    vah = vp.get("vah", 0)
    val = vp.get("val", 0)
    regime = dpoc.get("dpoc_regime", "")
    net_mig = dpoc.get("net_migration_pts", 0)

    single_above = tpo.get("single_prints_above_vah", 0)
    single_below = tpo.get("single_prints_below_val", 0)
    poor_high = tpo.get("poor_high", False)
    poor_low = tpo.get("poor_low", False)
    fattening = tpo.get("fattening_zone", "")

    narrative = ""

    # ─────────────────────────────────────────────────────────────
    # CONVICTION LONG SETUPS
    # ─────────────────────────────────────────────────────────────

    if net_mig > 50 and "trending_on_the_move" in regime and current_close > ib_high and confidence > 70:
        narrative = (
            f"🔥 CONVICTION LONG. DPOC migrated +{net_mig:.0f}pts. Bars holding ABOVE IBH ({ib_high:.0f}). "
            f"This trend is REAL. Sellers got crushed. Size this position FULL. "
            f"Target: overnight high. Keep hands on desk."
        )

    elif net_mig > 30 and fattening == "at_vah" and single_above < 10 and confidence > 65:
        narrative = (
            f"🟢 STRONG LONG SETUP. VAH acceptance forming with fattening. DPOC +{net_mig:.0f}pts. "
            f"Buyers in control here. Enter 2/3 size, scale to full. This is YOUR edge."
        )

    elif current_close > val and fattening == "at_val" and single_below < 8 and poor_low and confidence > 60:
        narrative = (
            f"✅ VAL RECLAIMED. Swept {val:.0f} then reclaimed with fattening. "
            f"Sellers got shaken out. Buyers are in control. LONG from here. Stop at poor low."
        )

    # ─────────────────────────────────────────────────────────────
    # CONVICTION SHORT SETUPS
    # ─────────────────────────────────────────────────────────────

    elif net_mig < -50 and "trending_on_the_move" in regime and current_close < ib_low and confidence > 70:
        narrative = (
            f"🔥 CONVICTION SHORT. DPOC migrated {net_mig:.0f}pts. Bars holding BELOW IBL ({ib_low:.0f}). "
            f"This trend is REAL. Buyers got crushed. Size this position FULL. "
            f"Target: overnight low. Keep hands on desk."
        )

    elif net_mig < -30 and fattening == "at_val" and single_below < 10 and confidence > 65:
        narrative = (
            f"🔴 STRONG SHORT SETUP. VAL acceptance forming with fattening. DPOC {net_mig:.0f}pts. "
            f"Sellers in control here. Enter 2/3 size, scale to full. This is YOUR edge."
        )

    elif current_close < vah and fattening == "at_vah" and single_above < 8 and poor_high and confidence > 60:
        narrative = (
            f"✅ VAH REJECTED. Swept {vah:.0f} then failed to reclaim with poor TPO. "
            f"Buyers got shaken out. Sellers are in control. SHORT from here. Stop at poor high."
        )

    # ─────────────────────────────────────────────────────────────
    # REJECTION & FADE SETUPS (Mean Reversion)
    # ─────────────────────────────────────────────────────────────

    elif single_above > 20 and poor_high and current_close < vah and confidence > 55:
        narrative = (
            f"⚠️ BREAKOUT REJECTION. {single_above} single prints above VAH. "
            f"Longs just got trapped. This is the TOP. SHORT here or wait for pullback. "
            f"Fade the break, trade the range."
        )

    elif single_below > 20 and poor_low and current_close > val and confidence > 55:
        narrative = (
            f"⚠️ BREAKDOWN REJECTION. {single_below} single prints below VAL. "
            f"Shorts just got trapped. This is the BOTTOM. LONG here or wait for bounce. "
            f"Fade the break, trade the range."
        )

    elif bullish_wicks > 8 and current_close < (ib_high - (ib_high - ib_low) * 0.3) and confidence > 50:
        narrative = (
            f"🪤 BULL TRAP. {bullish_wicks} bullish wicks at IBH but price collapsing lower. "
            f"Longs are trapped. This reversal is coming. SHORT the trap."
        )

    elif bearish_wicks > 8 and current_close > (ib_low + (ib_high - ib_low) * 0.3) and confidence > 50:
        narrative = (
            f"🪤 BEAR TRAP. {bearish_wicks} bearish wicks at IBL but price rallying higher. "
            f"Shorts are trapped. This reversal is coming. LONG the trap."
        )

    # ─────────────────────────────────────────────────────────────
    # CAUTIOUS/AMBIGUOUS SETUPS
    # ─────────────────────────────────────────────────────────────

    elif "balancing_choppy" in regime and abs(net_mig) < 10 and confidence < 45:
        narrative = (
            f"🔄 BALANCE DAY. DPOC flat, no direction. Price rotating in range. "
            f"Ambiguous. Don't force it. Fade VAH, fade VAL. Small size only. Respect structure."
        )

    elif "transitional_unclear" in regime and confidence < 50:
        narrative = (
            f"❓ UNCLEAR STRUCTURE. Regime transitioning. Could go either way. "
            f"Don't take conviction trades here. Watch and wait. Clarity is coming."
        )

    elif confidence < 40:
        narrative = (
            f"🛑 HANDS OFF. Low conviction setup. Multiple conflicting signals. "
            f"Not worth the risk/reward. Sit back. Better trades are coming."
        )

    # ─────────────────────────────────────────────────────────────
    # MOMENTUM CONFIRMATION (Trend Days)
    # ─────────────────────────────────────────────────────────────

    elif net_mig > 20 and "trending_on_the_move" in regime and confidence > 65:
        narrative = (
            f"📈 TREND CONFIRMED HIGHER. DPOC +{net_mig:.0f}pts advancing. "
            f"Bars holding. This is real momentum. LONG conviction here. "
            f"Don't fight it. Trend is your friend."
        )

    elif net_mig < -20 and "trending_on_the_move" in regime and confidence > 65:
        narrative = (
            f"📉 TREND CONFIRMED LOWER. DPOC {net_mig:.0f}pts retreating. "
            f"Bars breaking. This is real momentum. SHORT conviction here. "
            f"Don't fight it. Trend is your friend."
        )

    # ─────────────────────────────────────────────────────────────
    # FALLBACK (Generic but direct)
    # ─────────────────────────────────────────────────────────────

    if not narrative:
        if confidence > 65:
            narrative = (
                f"Playbook: {playbook}. Confidence {confidence}%. "
                f"DPOC {net_mig:+.0f}pts. Market has conviction. Trade it."
            )
        elif confidence > 50:
            narrative = (
                f"Playbook: {playbook}. Confidence {confidence}%. "
                f"Setup is valid but not obvious. Probe 1/3 size, scale if it works."
            )
        else:
            narrative = (
                f"Playbook: {playbook}. Confidence {confidence}%. "
                f"Low odds here. HANDS OFF. Wait for better setup."
            )

    return narrative


def get_trader_bias_assignment(narrative, confidence, net_mig):
    """
    Assign trader bias based on narrative (Not technical bias - CONVICTION BIAS).

    Returns: (bias_type, sizing_recommendation, conviction_level)
    """

    # Extract conviction from narrative
    has_conviction_long = any(kw in narrative for kw in ["CONVICTION LONG", "STRONG LONG", "VAL RECLAIMED", "LONG conviction"])
    has_conviction_short = any(kw in narrative for kw in ["CONVICTION SHORT", "STRONG SHORT", "VAH REJECTED", "SHORT conviction"])
    has_fade = any(kw in narrative for kw in ["FADE", "REJECTION", "TRAP"])
    has_ambiguous = any(kw in narrative for kw in ["AMBIGUOUS", "UNCLEAR", "don't force", "HANDS OFF"])

    if has_conviction_long and confidence > 70:
        return ("Bullish Conviction", "Full 3/3 size", "High")
    elif has_conviction_long and confidence > 55:
        return ("Bullish Strong", "2/3 size with scale", "Medium-High")
    elif has_conviction_short and confidence > 70:
        return ("Bearish Conviction", "Full 3/3 size", "High")
    elif has_conviction_short and confidence > 55:
        return ("Bearish Strong", "2/3 size with scale", "Medium-High")
    elif has_fade and confidence > 55:
        return ("Neutral-Edge Fade", "1/3 size, tight stops", "Medium")
    elif has_ambiguous or confidence < 50:
        return ("Stand Down", "No position", "Low")
    else:
        return ("Neutral", "Probe 1/3", "Medium")
