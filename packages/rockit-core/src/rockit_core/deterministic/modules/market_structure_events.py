#!/usr/bin/env python3
"""
Market Structure Event Detection

Detects when market structure CHANGES (rejection, acceptance, reversals, regime shifts)
between consecutive snapshots. This teaches the LLM to recognize turning points.

Examples:
- "Price rejected at VAH: single prints above + poor high TPO"
- "Reclaimed VAL with fattening: acceptance + floor established"
- "DPOC regime flipped from trending to balancing: momentum lost"
- "5-min inversion below previous high: weakness detected"
- "Bars holding above IBH + DPOC advancing: breakout confirmed"
"""

import pandas as pd
from datetime import datetime


def detect_market_structure_events(current_snapshot, previous_snapshot=None):
    """
    Detect market structure events that occurred at current_time.

    Args:
        current_snapshot: Current 5-min snapshot with full technical data
        previous_snapshot: Previous 5-min snapshot (for comparison)

    Returns:
        dict: {
            "structure_events": [],
            "acceptance_signals": [],
            "rejection_signals": [],
            "reversal_signals": [],
            "regime_shifts": [],
            "narrative": str  # Plain English description of what just happened
        }
    """

    events = {
        "structure_events": [],
        "acceptance_signals": [],
        "rejection_signals": [],
        "reversal_signals": [],
        "regime_shifts": [],
        "narratives": []
    }

    if not current_snapshot:
        return events

    intraday = current_snapshot.get("intraday", {})
    ib = intraday.get("ib", {})
    vp = intraday.get("volume_profile", {}).get("current_session", {})
    tpo = intraday.get("tpo_profile", {})
    dpoc = intraday.get("dpoc_migration", {})
    wick = intraday.get("wick_parade", {})

    # Current values
    current_close = ib.get("current_close", 0)
    current_high = ib.get("current_high", 0)
    current_low = ib.get("current_low", 0)
    ib_high = ib.get("ib_high", 0)
    ib_low = ib.get("ib_low", 0)
    vah = vp.get("vah", 0)
    val = vp.get("val", 0)
    poc = vp.get("poc", 0)

    single_above = tpo.get("single_prints_above_vah", 0)
    single_below = tpo.get("single_prints_below_val", 0)
    poor_high = tpo.get("poor_high", False)
    poor_low = tpo.get("poor_low", False)
    fattening = tpo.get("fattening_zone", "")

    dpoc_level = dpoc.get("dpoc_level", 0)
    dpoc_regime = dpoc.get("dpoc_regime", "")
    net_mig = dpoc.get("net_migration_pts", 0)

    bullish_wicks = wick.get("bullish_wick_parade_count", 0)
    bearish_wicks = wick.get("bearish_wick_parade_count", 0)

    # ─────────────────────────────────────────────────────────────
    # 1. REJECTION SIGNALS (price pushed away, no acceptance)
    # ─────────────────────────────────────────────────────────────

    # Rejection at VAH (broke above, couldn't hold, poor high TPO)
    if current_close < vah and current_high > vah and single_above > 15:
        events["rejection_signals"].append({
            "type": "rejection_at_vah",
            "description": f"Price rejected at VAH ({vah:.1f}): {single_above} single prints above, poor high TPO. Breakout failed.",
            "severity": "high" if single_above > 25 else "medium",
            "action": "FADE breakout. Short rejection or mean revert."
        })
        events["narratives"].append(
            f"🔴 REJECTION AT VAH: Broke above {vah:.0f} but poor TPO. Sellers active. No acceptance."
        )

    # Rejection at VAL (broke below, couldn't hold, poor low TPO)
    if current_close > val and current_low < val and single_below > 15:
        events["rejection_signals"].append({
            "type": "rejection_at_val",
            "description": f"Price rejected at VAL ({val:.1f}): {single_below} single prints below, poor low TPO. Breakdown failed.",
            "severity": "high" if single_below > 25 else "medium",
            "action": "FADE breakdown. Long reversal or mean revert."
        })
        events["narratives"].append(
            f"🔴 REJECTION AT VAL: Broke below {val:.0f} but poor TPO. Buyers active. No acceptance."
        )

    # Rejection at IBH (multiple wicks, no follow-through)
    if bullish_wicks > 6 and current_close < (ib_high - (ib_high - ib_low) * 0.3):
        events["rejection_signals"].append({
            "type": "rejection_at_ibh",
            "description": f"Bullish wick parade at IBH: {bullish_wicks} wicks, price closing in lower half. Longs trapped.",
            "severity": "high" if bullish_wicks > 8 else "medium",
            "action": "FADE. Short trapped longs or mean revert."
        })
        events["narratives"].append(
            f"🔴 BULL TRAP AT IBH: {bullish_wicks} bullish wicks but price retreating. Weak buyers."
        )

    # Rejection at IBL (multiple wicks, no follow-through)
    if bearish_wicks > 6 and current_close > (ib_low + (ib_high - ib_low) * 0.3):
        events["rejection_signals"].append({
            "type": "rejection_at_ibl",
            "description": f"Bearish wick parade at IBL: {bearish_wicks} wicks, price closing in upper half. Shorts trapped.",
            "severity": "high" if bearish_wicks > 8 else "medium",
            "action": "FADE. Long trapped shorts or mean revert."
        })
        events["narratives"].append(
            f"🔴 BEAR TRAP AT IBL: {bearish_wicks} bearish wicks but price rallying. Weak sellers."
        )

    # ─────────────────────────────────────────────────────────────
    # 2. ACCEPTANCE SIGNALS (price accepted, held, fattening)
    # ─────────────────────────────────────────────────────────────

    # Accepted above IBH (close > IBH, fattening forming, strong DPOC)
    if current_close > ib_high:
        if fattening == "at_vah" or (single_above < 10):  # Fattening or limited single prints
            events["acceptance_signals"].append({
                "type": "acceptance_above_ibh",
                "description": f"Price accepted above IBH ({ib_high:.1f}). Close: {current_close:.1f}. Fattening forming. Buyers in control.",
                "severity": "high" if net_mig > 20 else "medium",
                "action": "LONG conviction. Bars holding above IBH = strength."
            })
            events["narratives"].append(
                f"🟢 ACCEPTANCE ABOVE IBH: Price holding {current_close:.0f}, fattening at VAH. Buyers confirmed."
            )

    # Accepted below IBL (close < IBL, fattening forming, strong DPOC)
    if current_close < ib_low:
        if fattening == "at_val" or (single_below < 10):  # Fattening or limited single prints
            events["acceptance_signals"].append({
                "type": "acceptance_below_ibl",
                "description": f"Price accepted below IBL ({ib_low:.1f}). Close: {current_close:.1f}. Fattening forming. Sellers in control.",
                "severity": "high" if net_mig < -20 else "medium",
                "action": "SHORT conviction. Bars holding below IBL = weakness."
            })
            events["narratives"].append(
                f"🟢 ACCEPTANCE BELOW IBL: Price holding {current_close:.0f}, fattening at VAL. Sellers confirmed."
            )

    # ─────────────────────────────────────────────────────────────
    # RECLAIM ANALYSIS: Did price reclaim after sweep? Success or failure?
    # ─────────────────────────────────────────────────────────────

    if previous_snapshot:
        prev_close = previous_snapshot.get("intraday", {}).get("ib", {}).get("current_close", 0)
        prev_low = previous_snapshot.get("intraday", {}).get("ib", {}).get("current_low", 0)
        prev_high = previous_snapshot.get("intraday", {}).get("ib", {}).get("current_high", 0)
        prev_val = previous_snapshot.get("intraday", {}).get("volume_profile", {}).get("current_session", {}).get("val", 0)
        prev_vah = previous_snapshot.get("intraday", {}).get("volume_profile", {}).get("current_session", {}).get("vah", 0)
        prev_tpo = previous_snapshot.get("intraday", {}).get("tpo_profile", {})

        # VAL RECLAIM SUCCESS: Price swept below VAL, now reclaimed with acceptance
        if prev_low < val and current_close > val:
            if fattening == "at_val" and single_below < 10:
                events["acceptance_signals"].append({
                    "type": "val_reclaim_success",
                    "description": f"VAL SWEEP + RECLAIM SUCCESS: Swept {val:.0f}, now reclaimed with fattening. Floor established. Buyers won.",
                    "severity": "high",
                    "action": "LONG from VAL. Strong support confirmed."
                })
                events["narratives"].append(
                    f"🟢 VAL RECLAIM SUCCESS: Swept and reclaimed {val:.0f} with fattening. Buyers in control."
                )
        # VAL RECLAIM FAILURE: Price swept below VAL, failed to reclaim (poor TPO, weak)
        elif prev_low < val and current_close < val and poor_low:
            events["rejection_signals"].append({
                "type": "val_reclaim_failure",
                "description": f"VAL RECLAIM FAILURE: Swept {val:.0f}, failed to reclaim. Poor low TPO. Sellers still strong.",
                "severity": "high",
                "action": "SHORT continuation. Sellers dominant."
            })
            events["narratives"].append(
                f"🔴 VAL RECLAIM FAILURE: Swept but can't reclaim {val:.0f}. Weak buyers, strong sellers."
            )

        # VAH RECLAIM SUCCESS: Price swept above VAH, now reclaimed with acceptance
        if prev_high > vah and current_close < vah:
            if fattening == "at_vah" and single_above < 10:
                events["acceptance_signals"].append({
                    "type": "vah_reclaim_success",
                    "description": f"VAH SWEEP + RECLAIM SUCCESS: Swept {vah:.0f}, now reclaimed below with fattening. Ceiling holding. Sellers won.",
                    "severity": "high",
                    "action": "SHORT from VAH. Strong resistance confirmed."
                })
                events["narratives"].append(
                    f"🟢 VAH RECLAIM SUCCESS: Swept and reclaimed {vah:.0f} with fattening. Sellers in control."
                )
        # VAH RECLAIM FAILURE: Price swept above VAH, failed to reclaim (poor TPO, weak)
        elif prev_high > vah and current_close > vah and poor_high:
            events["rejection_signals"].append({
                "type": "vah_reclaim_failure",
                "description": f"VAH RECLAIM FAILURE: Swept {vah:.0f}, failed to reclaim. Poor high TPO. Buyers still strong.",
                "severity": "high",
                "action": "LONG continuation. Buyers dominant."
            })
            events["narratives"].append(
                f"🔴 VAH RECLAIM FAILURE: Swept but can't break {vah:.0f}. Weak sellers, strong buyers."
            )

    # Reclaimed VAL (broke below, now above + fattening = floor)
    if current_close > val and val > 0 and not previous_snapshot:
        if fattening == "at_val" and single_below < 10:
            events["acceptance_signals"].append({
                "type": "reclaim_val",
                "description": f"Reclaimed VAL floor ({val:.1f}). Close: {current_close:.1f}. Fattening at VAL. Buyers accepting this level.",
                "severity": "high",
                "action": "LONG from VAL. Floor established."
            })
            events["narratives"].append(
                f"🟢 VAL RECLAIM: Price above {val:.0f} with fattening. Floor confirmed."
            )

    # Reclaimed VAH (broke above, now above + fattening = ceiling break)
    if current_close > vah and vah > 0 and not previous_snapshot:
        if fattening == "at_vah" and single_above < 10:
            events["acceptance_signals"].append({
                "type": "break_vah",
                "description": f"Broke and holding above VAH ({vah:.1f}). Close: {current_close:.1f}. Fattening forming. Buyers taking control.",
                "severity": "high",
                "action": "LONG breakout. Trend higher likely."
            })
            events["narratives"].append(
                f"🟢 VAH BREAK: Price above {vah:.0f} with fattening. Ceiling broken."
            )

    # ─────────────────────────────────────────────────────────────
    # 3. REVERSAL SIGNALS (trend change, momentum loss, regime flip)
    # ─────────────────────────────────────────────────────────────

    # DPOC regime shift (trend → balance = momentum loss)
    if previous_snapshot:
        prev_regime = previous_snapshot.get("intraday", {}).get("dpoc_migration", {}).get("dpoc_regime", "")
        if "trending_on_the_move" in prev_regime and "balancing_choppy" in dpoc_regime:
            events["regime_shifts"].append({
                "type": "trend_to_balance",
                "description": "DPOC regime flipped from TRENDING to BALANCING. Momentum lost. Reversal likely.",
                "severity": "high",
                "action": "Take profits on trending positions. Prepare for range."
            })
            events["narratives"].append(
                f"🔄 MOMENTUM LOSS: Trend → Balance regime shift detected. Reversion likely."
            )

        # Trend reversal (trending down → trending up or vice versa)
        prev_trend = "up" if "trending_on_the_move" in prev_regime and \
            previous_snapshot.get("intraday", {}).get("dpoc_migration", {}).get("net_migration_pts", 0) > 0 else (
            "down" if "trending_on_the_move" in prev_regime else "none"
        )
        curr_trend = "up" if "trending_on_the_move" in dpoc_regime and net_mig > 0 else (
            "down" if "trending_on_the_move" in dpoc_regime and net_mig < 0 else "none"
        )

        if prev_trend != "none" and curr_trend != "none" and prev_trend != curr_trend:
            events["reversals"].append({
                "type": "trend_reversal",
                "description": f"Trend reversed: {prev_trend.upper()} → {curr_trend.upper()}. Major regime flip.",
                "severity": "critical",
                "action": "EXIT opposite trend. Reverse positions."
            })
            events["narratives"].append(
                f"⚠️ TREND REVERSAL: {prev_trend.upper()} → {curr_trend.upper()}. Major shift!"
            )

    # ─────────────────────────────────────────────────────────────
    # 4. STRUCTURAL EVENTS (5-min inversion, range formation, etc.)
    # ─────────────────────────────────────────────────────────────

    if previous_snapshot:
        prev_high = previous_snapshot.get("intraday", {}).get("ib", {}).get("current_high", 0)
        prev_low = previous_snapshot.get("intraday", {}).get("ib", {}).get("current_low", 0)

        # 5-min inversion candle (lower high or higher low = weakness)
        if current_high < prev_high and current_low < prev_low:
            events["structure_events"].append({
                "type": "inversion_candle_down",
                "description": f"5-min inversion below: High {current_high:.0f} < {prev_high:.0f}, Low {current_low:.0f} < {prev_low:.0f}. Weakness.",
                "severity": "medium",
                "action": "Caution on longs. Short bias preferred."
            })
            events["narratives"].append(
                f"📉 INVERSION DOWN: 5-min bar inverted below previous. Weakness signal."
            )

        elif current_high > prev_high and current_low > prev_low:
            events["structure_events"].append({
                "type": "inversion_candle_up",
                "description": f"5-min inversion above: High {current_high:.0f} > {prev_high:.0f}, Low {current_low:.0f} > {prev_low:.0f}. Strength.",
                "severity": "medium",
                "action": "Strength signal. Long bias preferred."
            })
            events["narratives"].append(
                f"📈 INVERSION UP: 5-min bar inverted above previous. Strength signal."
            )

    # TPO profile widening (VAH - VAL increasing = volatility/acceptance)
    if vah > 0 and val > 0:
        vah_val_width = vah - val
        if vah_val_width > 100:  # Significant width
            events["structure_events"].append({
                "type": "tpo_widening",
                "description": f"TPO profile widening: VAH-VAL = {vah_val_width:.0f}pts. Market exploring range.",
                "severity": "medium",
                "action": "Expect continued movement. Mean revert extremes."
            })
            events["narratives"].append(
                f"📊 TPO WIDENING: Profile expanding {vah_val_width:.0f}pts (VAL-VAH). Range extension."
            )

    # ─────────────────────────────────────────────────────────────
    # 5. CONFIDENCE BOOST/CAP BASED ON EVENTS
    # ─────────────────────────────────────────────────────────────

    confidence_adjustment = 0

    # Strong acceptance signals = boost confidence
    if events["acceptance_signals"]:
        confidence_adjustment += 20

    # Rejection signals = cap confidence (be cautious)
    if events["rejection_signals"]:
        confidence_adjustment -= 15

    # Regime shift from trend to balance = be cautious
    if any("trend_to_balance" in e.get("type", "") for e in events.get("regime_shifts", [])):
        confidence_adjustment -= 20

    # Inversion candle = slight caution
    if any("inversion_candle" in e.get("type", "") for e in events.get("structure_events", [])):
        confidence_adjustment -= 10

    events["confidence_adjustment"] = confidence_adjustment

    # Combine all narratives into single summary
    if events["narratives"]:
        events["narrative_summary"] = " | ".join(events["narratives"])
    else:
        events["narrative_summary"] = "Structure unchanged. No major events."

    return events


def main():
    """Test the detector with a sample snapshot."""
    # This is just for testing - normally called from synthesize_llm_output()
    pass


if __name__ == "__main__":
    main()
