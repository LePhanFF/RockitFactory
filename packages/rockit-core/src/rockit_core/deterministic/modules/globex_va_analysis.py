#!/usr/bin/env python3
"""
Globex VA Analysis - Previous Session Value Area + 80P Rule Detection

Implements Dalton 80% Rule: RTH open outside previous ETH Value Area,
fails to hold outside, re-enters VA = mean reversion with 100% gap fill.

Key research findings (Feb 2026, 259 sessions backtest):
- Best entry: Limit 50% VA depth + 4R target → $1,922/mo, PF 2.57, 44.7% WR
- Best WR:    100% Retest (double top/bottom) + 2R → 65.7% WR, PF 3.45
- Stop:       VA edge + 10pt ONLY (candle-based stops catastrophic: 5-14% WR)
- ETH VA outperforms RTH VA in all configurations (width 158 vs 126 pts median)
- Entry cutoff hard at 13:00 ET

Setup Classification:
  - Model A: Acceptance close (1 x 30-min bar closes inside VA after opening outside)
  - Model B: Limit at 50% VA depth (best $/mo)
  - Model C: 100% Retest / Double Top-Bottom (best WR)
"""

import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta


def get_prior_va_analysis(
    df_extended: pd.DataFrame,
    df_current: pd.DataFrame,
    current_time_str: str = "11:45",
    session_date: str = None,
    tpo_profile: dict = None,
    **kwargs
) -> Dict:
    """
    Analyze previous session ETH Value Area, gap status, and acceptance models.

    Market structure module: Detects prior session VA levels, gap classification,
    and acceptance/rejection patterns. Pure observation — no trade signals.

    Args:
        df_extended: Full historical data including prior sessions + overnight
        df_current: Current session only (filtered to current_time externally)
        current_time_str: Current time like "10:30"
        session_date: Current session date string

    Returns:
        Prior VA levels, gap status, acceptance model triggers, confidence
    """

    if not session_date:
        if not df_extended.empty and "session_date" in df_extended.columns:
            session_date = str(df_extended.iloc[-1]["session_date"])
        else:
            return {"status": "no_session_date"}

    # =========================================================================
    # STEP 1: Previous session ETH Value Area (CBOT standard 70% POC expansion)
    # =========================================================================

    previous_vah, previous_val, previous_poc = _compute_previous_session_va(
        df_extended, session_date
    )

    if previous_vah is None or previous_val is None:
        return {
            "status": "no_previous_session_data",
            "previous_session_vah": None,
            "previous_session_val": None,
        }

    previous_va_width = previous_vah - previous_val

    # Min VA width filter: research says skip if < 25 pts (too narrow = noise)
    if previous_va_width < 25:
        return {
            "status": "va_too_narrow",
            "previous_session_vah": round(previous_vah, 2),
            "previous_session_val": round(previous_val, 2),
            "previous_session_va_width": round(previous_va_width, 2),
            "previous_session_poc": round(previous_poc, 2) if previous_poc else None,
            "note": "VA width < 25pts — 80P setup skipped (research filter)"
        }

    # =========================================================================
    # STEP 2: Today's price action vs previous VA
    # =========================================================================

    current_time = pd.to_datetime(current_time_str).time()
    available_df = df_current[df_current.index.time <= current_time].copy()

    if available_df.empty:
        return {
            "status": "no_current_data",
            "previous_session_vah": round(previous_vah, 2),
            "previous_session_val": round(previous_val, 2),
            "previous_session_va_width": round(previous_va_width, 2),
        }

    current_open = available_df.iloc[0]["open"]
    current_high = available_df["high"].max()
    current_low = available_df["low"].min()
    current_close = available_df.iloc[-1]["close"]

    gap_status = _classify_gap_status(current_open, previous_vah, previous_val)
    opened_outside_va = gap_status in ["above_vah", "below_val"]

    # =========================================================================
    # STEP 3: Acceptance detection — model-specific triggers
    # =========================================================================

    # Model A: Any 30-min window close inside VA (from 09:30-10:00 period)
    model_a_triggered, model_a_entry_price, model_a_entry_time = _detect_model_a(
        available_df, previous_vah, previous_val, gap_status, opened_outside_va
    )

    # Model B: After first 1-min bar inside VA, limit at 50% VA depth
    model_b_triggered, model_b_limit_price = _detect_model_b(
        available_df, previous_vah, previous_val, gap_status, opened_outside_va,
        previous_va_width, current_time_str
    )

    # Model C: 100% retest (double top/bottom) after acceptance
    model_c_triggered, model_c_limit_price = _detect_model_c(
        available_df, previous_vah, previous_val, gap_status, opened_outside_va,
        model_a_triggered, model_a_entry_price
    )

    # Overall 80P setup = gap outside + any model detected
    any_model_triggered = model_a_triggered or model_b_triggered or model_c_triggered
    eighty_p_setup = opened_outside_va and any_model_triggered

    # 80P confidence score
    confidence = _compute_80p_confidence(
        gap_status, any_model_triggered, model_a_triggered,
        model_b_triggered, model_c_triggered, previous_va_width
    )

    # Setup type label
    if eighty_p_setup:
        setup_type = "bearish_rejection" if gap_status == "above_vah" else "bullish_rejection"
    elif opened_outside_va:
        setup_type = "watching_above_vah" if gap_status == "above_vah" else "watching_below_val"
    else:
        setup_type = "none"

    # OR context (mutually exclusive with 80P)
    or_context = _evaluate_or_context(gap_status, opened_outside_va, eighty_p_setup)

    # TPO cross-reference: check if TPO VA aligns with volume VA
    tpo_va_alignment = "no_data"
    if tpo_profile and isinstance(tpo_profile, dict):
        tpo_vah = tpo_profile.get("current_vah")
        tpo_val = tpo_profile.get("current_val")
        if isinstance(tpo_vah, (int, float)) and isinstance(tpo_val, (int, float)):
            tpo_inside_prior_va = tpo_val >= previous_val and tpo_vah <= previous_vah
            tpo_va_alignment = "inside_prior_va" if tpo_inside_prior_va else "extending_beyond"

    # =========================================================================
    # STEP 5: Active setup summary
    # =========================================================================

    active_model = None
    if eighty_p_setup:
        if model_c_triggered:
            active_model = "C_retest_double_top_bottom"
        elif model_b_triggered:
            active_model = "B_limit_50pct_va"
        elif model_a_triggered:
            active_model = "A_acceptance_close"

    return {
        # Previous session VA (ETH = overnight + RTH)
        "previous_session_vah": round(previous_vah, 2),
        "previous_session_val": round(previous_val, 2),
        "previous_session_poc": round(previous_poc, 2) if previous_poc else None,
        "va_width": round(previous_va_width, 2),

        # Today's price vs prior VA
        "current_open": round(current_open, 2),
        "current_high": round(current_high, 2),
        "current_low": round(current_low, 2),
        "current_close": round(current_close, 2),
        "gap_status": gap_status,                    # above_vah | below_val | inside_va
        "gap_direction": "up" if gap_status == "above_vah" else ("down" if gap_status == "below_val" else "none"),
        "gap_size_pts": round(abs(current_open - previous_vah), 2) if gap_status == "above_vah"
                        else (round(abs(previous_val - current_open), 2) if gap_status == "below_val" else 0.0),

        # Model triggers (acceptance detection)
        "model_a_triggered": model_a_triggered,      # Acceptance close
        "model_b_triggered": model_b_triggered,      # 50% VA depth reached
        "model_c_triggered": model_c_triggered,      # 100% retest (double top/bottom)
        "active_model": active_model,                # Highest priority model triggered

        # 80P setup state
        "80p_setup_ready": eighty_p_setup,
        "80p_setup_type": setup_type,
        "80p_confidence": confidence,

        # OR context (mutually exclusive with 80P)
        "or_context": or_context,

        # TPO cross-reference
        "tpo_va_alignment": tpo_va_alignment,

        "status": "complete",
        "note": f"Prior VA analysis: gap={gap_status}, 80p_ready={eighty_p_setup}, model={active_model or 'none'}"
    }


# Keep old name as alias for backward compatibility during transition
get_globex_va_analysis = get_prior_va_analysis


# ============================================================================
# VA COMPUTATION (CBOT Standard: POC expansion to 70%)
# ============================================================================


def _compute_previous_session_va(df_extended, session_date):
    """
    Compute previous session ETH Value Area using CBOT standard POC expansion.

    CBOT Standard:
    1. Find POC (price bin with max volume)
    2. Expand outward: compare one bin above VAH vs one bin below VAL
    3. Add side with more volume
    4. Repeat until 70% of total volume captured
    """
    if df_extended.empty:
        return None, None, None

    try:
        previous_day_df = df_extended[
            df_extended["session_date"] < pd.Timestamp(session_date).strftime("%Y-%m-%d")
        ]
        if previous_day_df.empty:
            return None, None, None

        last_prev_date = previous_day_df["session_date"].max()
        prev_session_df = previous_day_df[previous_day_df["session_date"] == last_prev_date]

        if prev_session_df.empty or len(prev_session_df) < 5:
            return None, None, None

        # Build volume profile at tick resolution (0.25 for NQ)
        tick_size = 0.25
        price_bins = {}
        for _, row in prev_session_df.iterrows():
            low = row["low"]
            high = row["high"]
            vol = row["volume"]
            num_ticks = max(1, round((high - low) / tick_size))
            vol_per_tick = vol / num_ticks
            tick = low
            while tick <= high + tick_size * 0.5:
                key = round(round(tick / tick_size) * tick_size, 2)
                price_bins[key] = price_bins.get(key, 0) + vol_per_tick
                tick += tick_size

        if not price_bins:
            return None, None, None

        total_volume = sum(price_bins.values())
        if total_volume == 0:
            return None, None, None

        # Find POC (max volume price)
        poc = max(price_bins, key=lambda p: price_bins[p])

        # Expand outward from POC (CBOT standard)
        sorted_prices = sorted(price_bins.keys())
        poc_idx = sorted_prices.index(poc) if poc in sorted_prices else len(sorted_prices) // 2
        vah_idx = poc_idx
        val_idx = poc_idx
        cumulative = price_bins.get(poc, 0)
        target_volume = 0.70 * total_volume

        while cumulative < target_volume:
            # Check above and below
            can_go_up = vah_idx + 1 < len(sorted_prices)
            can_go_down = val_idx - 1 >= 0

            if not can_go_up and not can_go_down:
                break

            vol_above = price_bins.get(sorted_prices[vah_idx + 1], 0) if can_go_up else 0
            vol_below = price_bins.get(sorted_prices[val_idx - 1], 0) if can_go_down else 0

            if vol_above >= vol_below and can_go_up:
                vah_idx += 1
                cumulative += price_bins.get(sorted_prices[vah_idx], 0)
            elif can_go_down:
                val_idx -= 1
                cumulative += price_bins.get(sorted_prices[val_idx], 0)
            else:
                break

        vah = sorted_prices[vah_idx]
        val = sorted_prices[val_idx]
        return vah, val, poc

    except Exception as e:
        return None, None, None


# ============================================================================
# GAP CLASSIFICATION
# ============================================================================


def _classify_gap_status(current_open, previous_vah, previous_val):
    if current_open > previous_vah:
        return "above_vah"
    elif current_open < previous_val:
        return "below_val"
    else:
        return "inside_va"


# ============================================================================
# MODEL DETECTION
# ============================================================================


def _detect_model_a(available_df, previous_vah, previous_val, gap_status, opened_outside_va):
    """
    Model A: Acceptance Close
    Wait for 1 x 30-min bar to close INSIDE VA after opening outside.
    30-min bar = any bar where 30 minutes have elapsed since open.
    In 5-min bar data: look for 5-min close inside VA after 6+ bars.
    """
    if not opened_outside_va:
        return False, None, None

    # Need at least 6 bars (30 min) before checking acceptance
    rth_bars = available_df[available_df.index.time >= pd.to_datetime("09:30").time()]
    if len(rth_bars) < 6:
        return False, None, None

    # Check each bar from 6th onward for close inside VA
    for i in range(5, len(rth_bars)):
        bar = rth_bars.iloc[i]
        close = bar["close"]
        if gap_status == "above_vah" and close <= previous_vah:
            return True, round(close, 2), str(rth_bars.index[i].time())
        elif gap_status == "below_val" and close >= previous_val:
            return True, round(close, 2), str(rth_bars.index[i].time())

    return False, None, None


def _detect_model_b(available_df, previous_vah, previous_val, gap_status, opened_outside_va,
                    va_width, current_time_str):
    """
    Model B: Limit at 50% VA Depth (Best $/Mo — $1,922/mo, PF 2.57)
    After first 1-min bar touches VA boundary, place limit near POC.
    SHORT: limit = VAH - 0.50 * VA_width
    LONG:  limit = VAL + 0.50 * VA_width
    Cancel if not filled by 13:00 ET.
    """
    if not opened_outside_va:
        return False, None

    # Check entry cutoff (hard at 13:00 ET per research)
    current_hour = int(current_time_str.split(":")[0])
    current_min = int(current_time_str.split(":")[1])
    if current_hour >= 13:
        return False, None

    # Check if price has touched VA boundary (first bar inside VA)
    touched_va = False
    for _, row in available_df.iterrows():
        if gap_status == "above_vah" and row["low"] <= previous_vah:
            touched_va = True
            break
        elif gap_status == "below_val" and row["high"] >= previous_val:
            touched_va = True
            break

    if not touched_va:
        return False, None

    # Compute limit price (50% VA depth from entry side)
    if gap_status == "above_vah":
        limit_price = round(previous_vah - 0.50 * va_width, 2)  # Near POC
    else:
        limit_price = round(previous_val + 0.50 * va_width, 2)  # Near POC

    # Check if ANY bar after VA touch traded through the limit price
    # (limit order fills when price reaches level, not just at current close)
    is_filled = False
    va_touched = False
    for _, row in available_df.iterrows():
        # First, detect the VA touch
        if not va_touched:
            if gap_status == "above_vah" and row["low"] <= previous_vah:
                va_touched = True
            elif gap_status == "below_val" and row["high"] >= previous_val:
                va_touched = True
            continue
        # After VA touch, check if any bar's extreme crossed the limit
        if gap_status == "above_vah" and row["low"] <= limit_price:
            is_filled = True
            break
        elif gap_status == "below_val" and row["high"] >= limit_price:
            is_filled = True
            break

    return is_filled, limit_price


def _detect_model_c(available_df, previous_vah, previous_val, gap_status, opened_outside_va,
                    model_a_triggered, model_a_entry):
    """
    Model C: 100% Retest / Double Top-Bottom (Best WR — 65.7%, PF 3.45)
    After acceptance bar closes inside VA:
      SHORT: place LIMIT SELL at acceptance candle high (double top)
      LONG:  place LIMIT BUY at acceptance candle low (double bottom)
    """
    if not opened_outside_va or not model_a_triggered or model_a_entry is None:
        return False, None

    rth_bars = available_df[available_df.index.time >= pd.to_datetime("09:30").time()]
    if len(rth_bars) < 7:
        return False, None

    # Find the acceptance bar
    acceptance_bar = None
    for i in range(5, len(rth_bars)):
        bar = rth_bars.iloc[i]
        close = bar["close"]
        if gap_status == "above_vah" and close <= previous_vah:
            acceptance_bar = bar
            acceptance_idx = i
            break
        elif gap_status == "below_val" and close >= previous_val:
            acceptance_bar = bar
            acceptance_idx = i
            break

    if acceptance_bar is None:
        return False, None

    # Limit at acceptance candle extreme (retest level)
    if gap_status == "above_vah":
        limit_price = round(acceptance_bar["high"], 2)  # Short at double top
    else:
        limit_price = round(acceptance_bar["low"], 2)   # Long at double bottom

    # Check if price has retested to this limit
    subsequent_bars = rth_bars.iloc[acceptance_idx + 1:]
    if subsequent_bars.empty:
        return False, limit_price  # Setup staged but not filled yet

    for _, bar in subsequent_bars.iterrows():
        if gap_status == "above_vah" and bar["high"] >= limit_price:
            return True, limit_price   # Retest filled
        elif gap_status == "below_val" and bar["low"] <= limit_price:
            return True, limit_price

    return False, limit_price  # Retest level set, not yet filled


# ============================================================================
# CONFIDENCE SCORING
# ============================================================================


def _compute_80p_confidence(gap_status, any_triggered, model_a, model_b, model_c, va_width):
    """
    Confidence 0-100 based on research performance.
    Model C highest WR (65.7%), Model B best $/mo (44.7%), Model A baseline (38.3%)
    """
    if not gap_status in ["above_vah", "below_val"]:
        return 0

    if not any_triggered:
        # Gap outside but no acceptance yet — watching
        base = 40 if va_width >= 50 else 30
        return base

    # Triggered: confidence based on which model
    if model_c:
        return 90  # Best WR (65.7%), selective entries
    elif model_b:
        return 82  # Best $/mo (44.7% WR, PF 2.57)
    elif model_a:
        return 70  # Baseline acceptance (38.3% WR)
    else:
        return 50


# ============================================================================
# OR CONTEXT (MUTUALLY EXCLUSIVE WITH 80P)
# ============================================================================


def _evaluate_or_context(gap_status, opened_outside_va, eighty_p_setup):
    if not opened_outside_va:
        return {
            "or_playbook_viable": True,
            "reason": "Opened inside previous VA — normal IB, OR candidate",
        }
    if eighty_p_setup:
        return {
            "or_playbook_viable": False,
            "reason": "80P triggered — gap failed, mean reversion active. OR does NOT apply.",
        }
    return {
        "or_playbook_viable": True,
        "reason": "Gap outside VA but acceptance not yet confirmed — OR still possible",
        "note": "By 10:30: if acceptance happens = 80P; if gap holds = OR",
    }


if __name__ == "__main__":
    import sys
    from rockit_core.deterministic.modules.loader import load_nq_csv

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw_csv/NQ_Minute_5_CME US Index Futures ETH_VWAP_Tick.csv"
    session_date = sys.argv[2] if len(sys.argv) > 2 else "2026-01-02"

    df_ext, df_curr = load_nq_csv(csv_path, session_date)
    result = get_globex_va_analysis(df_ext, df_curr, "10:30", session_date)

    import json
    print(json.dumps(result, indent=2))
