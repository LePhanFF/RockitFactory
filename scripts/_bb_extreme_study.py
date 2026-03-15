#!/usr/bin/env python3
"""
Bollinger Band Extreme Reversal — Quantitative Study
=====================================================
Replacement candidate for the disabled Mean Reversion VWAP strategy (-$6,925).

Tests all combinations of:
  - Entry: bb_touch, bb_break, bb_vwap
  - ADX gate: none, <20, <25, <30
  - RSI confirmation: none, 30/70, 25/75, 20/80
  - Volume filter: none, declining (<1.2), spike (>1.5)
  - Stop model: bb_opposite, fixed_20pt, fixed_30pt, fixed_40pt, atr_1x
  - Target model: bb_middle, vwap, 1R, 2R
  - Time window: morning (10:30-13:00), midday (11:00-14:30), full (9:30-15:00)
  - Direction: LONG, SHORT, BOTH
  - Time exit: 15 bars, 30 bars, none

Usage:
    uv run python scripts/_bb_extreme_study.py
"""

import sys
import time
import warnings
from datetime import time as dtime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Setup path ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "rockit-core" / "src"))

from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features
from rockit_core.indicators.technical import add_all_indicators

# ── Constants ───────────────────────────────────────────────────
NQ_TICK_VALUE = 5.0  # $5 per point for NQ (1 tick = 0.25pt = $5, 1pt = $20)
NQ_POINT_VALUE = 20.0
SLIPPAGE_PER_SIDE = 1  # 1 tick = 0.25 points
SLIPPAGE_TOTAL = SLIPPAGE_PER_SIDE * 2 * 0.25  # 0.5 points round trip

# ── Dimension definitions ──────────────────────────────────────
ENTRY_MODES = ["bb_touch", "bb_break", "bb_vwap"]

ADX_GATES = {
    "no_adx": lambda adx: True,
    "adx_lt_20": lambda adx: adx < 20,
    "adx_lt_25": lambda adx: adx < 25,
    "adx_lt_30": lambda adx: adx < 30,
}

RSI_FILTERS = {
    "no_rsi": {"long_max": 100, "short_min": 0},
    "rsi_30_70": {"long_max": 30, "short_min": 70},
    "rsi_25_75": {"long_max": 25, "short_min": 75},
    "rsi_20_80": {"long_max": 20, "short_min": 80},
}

VOL_FILTERS = {
    "no_vol": lambda vs: True,
    "vol_declining": lambda vs: vs < 1.2,
    "vol_spike": lambda vs: vs > 1.5,
}

STOP_MODELS = ["bb_opposite", "fixed_20pt", "fixed_30pt", "fixed_40pt", "atr_1x"]
TARGET_MODELS = ["bb_middle", "vwap", "1R", "2R"]

TIME_WINDOWS = {
    "morning": (dtime(10, 30), dtime(13, 0)),
    "midday": (dtime(11, 0), dtime(14, 30)),
    "full": (dtime(9, 30), dtime(15, 0)),
}

DIRECTIONS = ["LONG", "SHORT", "BOTH"]

TIME_EXITS = {"15_bars": 15, "30_bars": 30, "no_time_exit": 9999}


def load_data() -> pd.DataFrame:
    """Load NQ data with all features and indicators."""
    print("Loading NQ data...")
    # Use main repo data dir (worktrees don't have data/)
    main_data = Path(__file__).resolve().parent.parent.parent.parent / "RockitFactory" / "data" / "sessions"
    if not main_data.exists():
        main_data = Path("C:/Users/lehph/Documents/GitHub/RockitFactory/data/sessions")
    mgr = SessionDataManager(data_dir=str(main_data))
    df = mgr.load("NQ")
    print(f"  Raw rows: {len(df):,}, sessions: {df['session_date'].nunique()}")

    df = compute_all_features(df)
    df = add_all_indicators(df)

    # Parse bar time for filtering
    df["bar_time"] = pd.to_datetime(df["timestamp"]).dt.time

    # Ensure numeric columns
    for col in ["bb_upper", "bb_lower", "bb_middle", "adx14", "rsi14",
                "vwap", "atr14", "volume_spike", "ib_range", "close",
                "open", "high", "low"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    print(f"  Final rows: {len(df):,}, sessions: {df['session_date'].nunique()}")
    print(f"  Date range: {df['session_date'].min()} to {df['session_date'].max()}")
    return df


def check_entry(row, entry_mode: str, direction: str) -> bool:
    """Check if a bar meets entry conditions for the given mode and direction."""
    if direction == "LONG":
        if entry_mode == "bb_touch":
            return row["close"] <= row["bb_lower"]
        elif entry_mode == "bb_break":
            return row["low"] < row["bb_lower"]
        elif entry_mode == "bb_vwap":
            ib_range = row["ib_range"]
            if pd.isna(ib_range) or ib_range <= 0:
                return False
            vwap_dev = abs(row["close"] - row["vwap"])
            return row["close"] <= row["bb_lower"] and vwap_dev > 0.5 * ib_range
    elif direction == "SHORT":
        if entry_mode == "bb_touch":
            return row["close"] >= row["bb_upper"]
        elif entry_mode == "bb_break":
            return row["high"] > row["bb_upper"]
        elif entry_mode == "bb_vwap":
            ib_range = row["ib_range"]
            if pd.isna(ib_range) or ib_range <= 0:
                return False
            vwap_dev = abs(row["close"] - row["vwap"])
            return row["close"] >= row["bb_upper"] and vwap_dev > 0.5 * ib_range
    return False


def compute_stop(row, stop_model: str, direction: str) -> float:
    """Compute stop price."""
    entry = row["close"]
    if direction == "LONG":
        if stop_model == "bb_opposite":
            return row["bb_upper"]  # Wait, opposite for LONG = lower... no, opposite band
            # Actually for LONG entry near lower band, opposite = upper band makes no sense as stop
            # Opposite BB for LONG = the entry band side minus buffer? Let's use bb_lower as reference
            # "bb_opposite" = stop at the opposite band from entry. For LONG (entered near lower),
            # the opposite is upper — but that's the target side, not stop side.
            # Re-interpreting: stop at opposite side of the range = below the lower band
            # Let's use: stop = bb_lower - (bb_upper - bb_lower) * 0.1 (10% below lower band)
        elif stop_model == "fixed_20pt":
            return entry - 20
        elif stop_model == "fixed_30pt":
            return entry - 30
        elif stop_model == "fixed_40pt":
            return entry - 40
        elif stop_model == "atr_1x":
            return entry - row["atr14"]
    else:  # SHORT
        if stop_model == "bb_opposite":
            return entry  # placeholder
        elif stop_model == "fixed_20pt":
            return entry + 20
        elif stop_model == "fixed_30pt":
            return entry + 30
        elif stop_model == "fixed_40pt":
            return entry + 40
        elif stop_model == "atr_1x":
            return entry + row["atr14"]
    return entry  # fallback


def get_stop_distance(row, stop_model: str, direction: str) -> float:
    """Get stop distance in points (always positive)."""
    if stop_model == "bb_opposite":
        # For BB opposite: use the BB width as stop reference
        # LONG: stop below lower band by some margin
        # SHORT: stop above upper band by some margin
        bb_width = row["bb_upper"] - row["bb_lower"]
        return bb_width * 0.15 + 5  # 15% of BB width + 5pt buffer, min ~8-10pt
    elif stop_model == "fixed_20pt":
        return 20
    elif stop_model == "fixed_30pt":
        return 30
    elif stop_model == "fixed_40pt":
        return 40
    elif stop_model == "atr_1x":
        atr = row["atr14"]
        return max(atr, 5) if not pd.isna(atr) else 20  # floor at 5pt
    return 20  # fallback


def get_target_distance(row, target_model: str, stop_dist: float, direction: str) -> float:
    """Get target distance in points (always positive)."""
    entry = row["close"]
    if target_model == "bb_middle":
        if direction == "LONG":
            return max(row["bb_middle"] - entry, 2)
        else:
            return max(entry - row["bb_middle"], 2)
    elif target_model == "vwap":
        if direction == "LONG":
            return max(row["vwap"] - entry, 2)
        else:
            return max(entry - row["vwap"], 2)
    elif target_model == "1R":
        return stop_dist
    elif target_model == "2R":
        return stop_dist * 2
    return stop_dist  # fallback


def simulate_trades(df: pd.DataFrame, config: dict) -> list[dict]:
    """
    Simulate trades for a single configuration.
    Returns list of trade dicts.
    """
    entry_mode = config["entry"]
    adx_key = config["adx"]
    rsi_key = config["rsi"]
    vol_key = config["vol"]
    stop_model = config["stop"]
    target_model = config["target"]
    time_key = config["time_window"]
    direction = config["direction"]
    time_exit_bars = TIME_EXITS[config["time_exit"]]

    adx_fn = ADX_GATES[adx_key]
    rsi_cfg = RSI_FILTERS[rsi_key]
    vol_fn = VOL_FILTERS[vol_key]
    tw_start, tw_end = TIME_WINDOWS[time_key]

    directions = ["LONG", "SHORT"] if direction == "BOTH" else [direction]
    trades = []

    for session_date, session_df in df.groupby("session_date"):
        for d in directions:
            in_trade = False
            entry_price = 0.0
            stop_price = 0.0
            target_price = 0.0
            entry_bar_idx = 0
            entry_time = None
            cooldown_until = 0  # bar index cooldown (1 trade per direction per session)

            for i, (idx, row) in enumerate(session_df.iterrows()):
                bt = row["bar_time"]

                # Skip bars outside time window
                if bt < tw_start or bt > tw_end:
                    if in_trade and bt > tw_end:
                        # Force close at window end
                        pnl_pts = (row["close"] - entry_price) if d == "LONG" else (entry_price - row["close"])
                        pnl_pts -= SLIPPAGE_TOTAL
                        trades.append({
                            "session_date": session_date,
                            "direction": d,
                            "entry_price": entry_price,
                            "exit_price": row["close"],
                            "pnl_pts": pnl_pts,
                            "pnl_usd": pnl_pts * NQ_POINT_VALUE,
                            "exit_reason": "time_window_close",
                            "bars_held": i - entry_bar_idx,
                            "entry_time": entry_time,
                        })
                        in_trade = False
                    continue

                if in_trade:
                    # Check stop
                    if d == "LONG":
                        if row["low"] <= stop_price:
                            pnl_pts = stop_price - entry_price - SLIPPAGE_TOTAL
                            trades.append({
                                "session_date": session_date,
                                "direction": d,
                                "entry_price": entry_price,
                                "exit_price": stop_price,
                                "pnl_pts": pnl_pts,
                                "pnl_usd": pnl_pts * NQ_POINT_VALUE,
                                "exit_reason": "stop",
                                "bars_held": i - entry_bar_idx,
                                "entry_time": entry_time,
                            })
                            in_trade = False
                            continue
                        # Check target
                        if row["high"] >= target_price:
                            pnl_pts = target_price - entry_price - SLIPPAGE_TOTAL
                            trades.append({
                                "session_date": session_date,
                                "direction": d,
                                "entry_price": entry_price,
                                "exit_price": target_price,
                                "pnl_pts": pnl_pts,
                                "pnl_usd": pnl_pts * NQ_POINT_VALUE,
                                "exit_reason": "target",
                                "bars_held": i - entry_bar_idx,
                                "entry_time": entry_time,
                            })
                            in_trade = False
                            continue
                    else:  # SHORT
                        if row["high"] >= stop_price:
                            pnl_pts = entry_price - stop_price - SLIPPAGE_TOTAL
                            trades.append({
                                "session_date": session_date,
                                "direction": d,
                                "entry_price": entry_price,
                                "exit_price": stop_price,
                                "pnl_pts": pnl_pts,
                                "pnl_usd": pnl_pts * NQ_POINT_VALUE,
                                "exit_reason": "stop",
                                "bars_held": i - entry_bar_idx,
                                "entry_time": entry_time,
                            })
                            in_trade = False
                            continue
                        if row["low"] <= target_price:
                            pnl_pts = entry_price - target_price - SLIPPAGE_TOTAL
                            trades.append({
                                "session_date": session_date,
                                "direction": d,
                                "entry_price": entry_price,
                                "exit_price": target_price,
                                "pnl_pts": pnl_pts,
                                "pnl_usd": pnl_pts * NQ_POINT_VALUE,
                                "exit_reason": "target",
                                "bars_held": i - entry_bar_idx,
                                "entry_time": entry_time,
                            })
                            in_trade = False
                            continue

                    # Time exit
                    bars_held = i - entry_bar_idx
                    if bars_held >= time_exit_bars:
                        pnl_pts = (row["close"] - entry_price) if d == "LONG" else (entry_price - row["close"])
                        pnl_pts -= SLIPPAGE_TOTAL
                        trades.append({
                            "session_date": session_date,
                            "direction": d,
                            "entry_price": entry_price,
                            "exit_price": row["close"],
                            "pnl_pts": pnl_pts,
                            "pnl_usd": pnl_pts * NQ_POINT_VALUE,
                            "exit_reason": "time_exit",
                            "bars_held": bars_held,
                            "entry_time": entry_time,
                        })
                        in_trade = False
                        continue

                else:
                    # Only 1 trade per direction per session
                    if i <= cooldown_until:
                        continue

                    # Skip if key indicators are NaN
                    if pd.isna(row["bb_upper"]) or pd.isna(row["bb_lower"]) or pd.isna(row["bb_middle"]):
                        continue
                    if pd.isna(row["adx14"]) or pd.isna(row["rsi14"]):
                        continue

                    # Entry check
                    if not check_entry(row, entry_mode, d):
                        continue

                    # ADX gate
                    if not adx_fn(row["adx14"]):
                        continue

                    # RSI filter
                    if d == "LONG" and row["rsi14"] > rsi_cfg["long_max"]:
                        continue
                    if d == "SHORT" and row["rsi14"] < rsi_cfg["short_min"]:
                        continue

                    # Volume filter
                    vs = row["volume_spike"]
                    if pd.isna(vs):
                        continue
                    if not vol_fn(vs):
                        continue

                    # All conditions met — enter trade
                    in_trade = True
                    entry_price = row["close"]
                    entry_bar_idx = i
                    entry_time = row["bar_time"]

                    stop_dist = get_stop_distance(row, stop_model, d)
                    target_dist = get_target_distance(row, target_model, stop_dist, d)

                    if d == "LONG":
                        stop_price = entry_price - stop_dist
                        target_price = entry_price + target_dist
                    else:
                        stop_price = entry_price + stop_dist
                        target_price = entry_price - target_dist

                    # Cooldown: only 1 trade per direction per session
                    cooldown_until = len(session_df)

            # Force close if still in trade at session end
            if in_trade:
                last_row = session_df.iloc[-1]
                pnl_pts = (last_row["close"] - entry_price) if d == "LONG" else (entry_price - last_row["close"])
                pnl_pts -= SLIPPAGE_TOTAL
                trades.append({
                    "session_date": session_date,
                    "direction": d,
                    "entry_price": entry_price,
                    "exit_price": last_row["close"],
                    "pnl_pts": pnl_pts,
                    "pnl_usd": pnl_pts * NQ_POINT_VALUE,
                    "exit_reason": "session_close",
                    "bars_held": len(session_df) - entry_bar_idx,
                    "entry_time": entry_time,
                })

    return trades


def compute_metrics(trades: list[dict]) -> dict:
    """Compute performance metrics from a list of trades."""
    if not trades:
        return {"trades": 0, "wr": 0, "pf": 0, "total_pnl": 0, "avg_pnl": 0,
                "max_dd": 0, "avg_win": 0, "avg_loss": 0, "win_trades": 0, "loss_trades": 0}

    pnls = [t["pnl_usd"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0.01

    # Max drawdown
    cumsum = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumsum)
    drawdowns = running_max - cumsum
    max_dd = drawdowns.max() if len(drawdowns) > 0 else 0

    return {
        "trades": len(trades),
        "wr": len(wins) / len(trades) * 100 if trades else 0,
        "pf": gross_profit / gross_loss if gross_loss > 0 else 999,
        "total_pnl": sum(pnls),
        "avg_pnl": np.mean(pnls),
        "max_dd": max_dd,
        "avg_win": np.mean(wins) if wins else 0,
        "avg_loss": np.mean(losses) if losses else 0,
        "win_trades": len(wins),
        "loss_trades": len(losses),
    }


def run_study(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full combinatorial study."""
    # Reduce combos: test all entries × ADX × RSI × vol × stop × target × time × direction × time_exit
    # Full grid: 3 × 4 × 4 × 3 × 5 × 4 × 3 × 3 × 3 = 38,880 combos — too many
    # Smart approach: test in stages

    # Stage 1: Find best entry + ADX + RSI + direction (fix stop=fixed_30pt, target=bb_middle, time=morning, time_exit=30_bars)
    print("\n" + "=" * 70)
    print("STAGE 1: Entry × ADX × RSI × Direction scan")
    print("  Fixed: stop=fixed_30pt, target=bb_middle, time=morning, time_exit=30_bars")
    print("=" * 70)

    stage1_results = []
    combos = list(product(ENTRY_MODES, ADX_GATES.keys(), RSI_FILTERS.keys(), DIRECTIONS))
    total = len(combos)

    for i, (entry, adx, rsi, direction) in enumerate(combos):
        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{total}]")
        config = {
            "entry": entry, "adx": adx, "rsi": rsi, "vol": "no_vol",
            "stop": "fixed_30pt", "target": "bb_middle", "time_window": "morning",
            "direction": direction, "time_exit": "30_bars",
        }
        trades = simulate_trades(df, config)
        metrics = compute_metrics(trades)
        stage1_results.append({**config, **metrics})

    s1_df = pd.DataFrame(stage1_results)
    viable = s1_df[s1_df["trades"] >= 15].sort_values("pf", ascending=False)
    print(f"\n  Stage 1 viable configs (>=15 trades): {len(viable)}/{len(s1_df)}")

    if len(viable) > 0:
        print("\n  Top 10 by PF:")
        for _, r in viable.head(10).iterrows():
            print(f"    {r['entry']:10s} {r['adx']:10s} {r['rsi']:10s} {r['direction']:5s} "
                  f"| {r['trades']:3.0f} trades, {r['wr']:5.1f}% WR, PF {r['pf']:5.2f}, ${r['total_pnl']:>8,.0f}")

    # Stage 2: Take top entry/adx/rsi combos, vary stop + target + vol + time_window + time_exit
    print("\n" + "=" * 70)
    print("STAGE 2: Full grid on top Stage 1 combos")
    print("=" * 70)

    # Get unique top combos (top by PF per entry+direction)
    top_combos = []
    if len(viable) > 0:
        for _, r in viable.head(20).iterrows():
            top_combos.append((r["entry"], r["adx"], r["rsi"], r["direction"]))
    else:
        # Fallback: use reasonable defaults
        top_combos = [
            ("bb_touch", "adx_lt_25", "no_rsi", "BOTH"),
            ("bb_break", "adx_lt_25", "no_rsi", "BOTH"),
            ("bb_touch", "no_adx", "rsi_30_70", "BOTH"),
        ]

    stage2_combos = list(product(
        top_combos,
        VOL_FILTERS.keys(),
        STOP_MODELS,
        TARGET_MODELS,
        TIME_WINDOWS.keys(),
        TIME_EXITS.keys(),
    ))
    total2 = len(stage2_combos)
    print(f"  Combos: {total2}")

    stage2_results = []
    for i, ((entry, adx, rsi, direction), vol, stop, target, tw, te) in enumerate(stage2_combos):
        if (i + 1) % 200 == 0:
            print(f"  [{i+1}/{total2}]")
        config = {
            "entry": entry, "adx": adx, "rsi": rsi, "vol": vol,
            "stop": stop, "target": target, "time_window": tw,
            "direction": direction, "time_exit": te,
        }
        trades = simulate_trades(df, config)
        metrics = compute_metrics(trades)
        stage2_results.append({**config, **metrics})

    s2_df = pd.DataFrame(stage2_results)

    # Combine all results
    all_results = pd.concat([s1_df, s2_df], ignore_index=True)
    # Deduplicate
    config_cols = ["entry", "adx", "rsi", "vol", "stop", "target", "time_window", "direction", "time_exit"]
    all_results = all_results.drop_duplicates(subset=config_cols, keep="last")

    print(f"\n  Total unique configs tested: {len(all_results)}")
    print(f"  Configs with >= 15 trades: {len(all_results[all_results['trades'] >= 15])}")

    return all_results


def generate_report(results_df: pd.DataFrame, report_path: Path):
    """Generate the markdown report."""
    viable = results_df[results_df["trades"] >= 15].copy()
    viable_pf = viable.sort_values("pf", ascending=False)

    lines = []
    lines.append("# Bollinger Band Extreme Reversal — Quant Study Report")
    lines.append(f"\n**Date**: 2026-03-12")
    lines.append(f"**Instrument**: NQ futures")
    lines.append(f"**Total configs tested**: {len(results_df):,}")
    lines.append(f"**Viable configs (>=15 trades)**: {len(viable):,}")
    lines.append(f"**Sessions**: ~270")
    lines.append("")

    # ── Top 30 by PF ────────────────────────────────────────────
    lines.append("## Top 30 Configs by Profit Factor (min 15 trades)")
    lines.append("")
    lines.append("| # | Entry | ADX | RSI | Vol | Stop | Target | Time | Dir | TimeExit | Trades | WR% | PF | Total PnL | Avg PnL | MaxDD |")
    lines.append("|---|-------|-----|-----|-----|------|--------|------|-----|----------|--------|-----|-----|-----------|---------|-------|")

    for rank, (_, r) in enumerate(viable_pf.head(30).iterrows(), 1):
        lines.append(
            f"| {rank} | {r['entry']} | {r['adx']} | {r['rsi']} | {r['vol']} | "
            f"{r['stop']} | {r['target']} | {r['time_window']} | {r['direction']} | {r['time_exit']} | "
            f"{r['trades']:.0f} | {r['wr']:.1f} | {r['pf']:.2f} | ${r['total_pnl']:,.0f} | "
            f"${r['avg_pnl']:,.0f} | ${r['max_dd']:,.0f} |"
        )

    # ── ADX Gate Analysis ───────────────────────────────────────
    lines.append("\n## ADX Gate Analysis")
    lines.append("")
    lines.append("| ADX Gate | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL |")
    lines.append("|----------|---------|-----------|---------|--------|---------|")

    for adx_key in ADX_GATES:
        subset = viable[viable["adx"] == adx_key]
        if len(subset) > 0:
            lines.append(
                f"| {adx_key} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | ${subset['avg_pnl'].mean():,.0f} |"
            )

    # ── RSI Threshold Comparison ────────────────────────────────
    lines.append("\n## RSI Threshold Comparison")
    lines.append("")
    lines.append("| RSI Filter | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL |")
    lines.append("|------------|---------|-----------|---------|--------|---------|")

    for rsi_key in RSI_FILTERS:
        subset = viable[viable["rsi"] == rsi_key]
        if len(subset) > 0:
            lines.append(
                f"| {rsi_key} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | ${subset['avg_pnl'].mean():,.0f} |"
            )

    # ── Volume Filter Impact ────────────────────────────────────
    lines.append("\n## Volume Filter Impact")
    lines.append("")
    lines.append("| Vol Filter | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL |")
    lines.append("|------------|---------|-----------|---------|--------|---------|")

    for vol_key in VOL_FILTERS:
        subset = viable[viable["vol"] == vol_key]
        if len(subset) > 0:
            lines.append(
                f"| {vol_key} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | ${subset['avg_pnl'].mean():,.0f} |"
            )

    # ── Stop / Target Optimization ──────────────────────────────
    lines.append("\n## Stop Model Comparison")
    lines.append("")
    lines.append("| Stop | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL |")
    lines.append("|------|---------|-----------|---------|--------|---------|")

    for stop_key in STOP_MODELS:
        subset = viable[viable["stop"] == stop_key]
        if len(subset) > 0:
            lines.append(
                f"| {stop_key} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | ${subset['avg_pnl'].mean():,.0f} |"
            )

    lines.append("\n## Target Model Comparison")
    lines.append("")
    lines.append("| Target | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL |")
    lines.append("|--------|---------|-----------|---------|--------|---------|")

    for target_key in TARGET_MODELS:
        subset = viable[viable["target"] == target_key]
        if len(subset) > 0:
            lines.append(
                f"| {target_key} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | ${subset['avg_pnl'].mean():,.0f} |"
            )

    # ── Time Window Analysis ────────────────────────────────────
    lines.append("\n## Time Window Analysis")
    lines.append("")
    lines.append("| Time Window | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL |")
    lines.append("|-------------|---------|-----------|---------|--------|---------|")

    for tw_key in TIME_WINDOWS:
        subset = viable[viable["time_window"] == tw_key]
        if len(subset) > 0:
            lines.append(
                f"| {tw_key} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | ${subset['avg_pnl'].mean():,.0f} |"
            )

    # ── LONG vs SHORT Analysis ──────────────────────────────────
    lines.append("\n## LONG vs SHORT Analysis")
    lines.append("")
    lines.append("| Direction | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Total PnL |")
    lines.append("|-----------|---------|-----------|---------|--------|---------|-----------|")

    for d in DIRECTIONS:
        subset = viable[viable["direction"] == d]
        if len(subset) > 0:
            lines.append(
                f"| {d} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | "
                f"${subset['avg_pnl'].mean():,.0f} | ${subset['total_pnl'].sum():,.0f} |"
            )

    # ── Time Exit Analysis ──────────────────────────────────────
    lines.append("\n## Time Exit Analysis")
    lines.append("")
    lines.append("| Time Exit | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL |")
    lines.append("|-----------|---------|-----------|---------|--------|---------|")

    for te_key in TIME_EXITS:
        subset = viable[viable["time_exit"] == te_key]
        if len(subset) > 0:
            lines.append(
                f"| {te_key} | {len(subset)} | {subset['trades'].mean():.0f} | "
                f"{subset['wr'].mean():.1f} | {subset['pf'].mean():.2f} | ${subset['avg_pnl'].mean():,.0f} |"
            )

    # ── VERDICT ─────────────────────────────────────────────────
    lines.append("\n## VERDICT: Recommended Production Config")
    lines.append("")

    if len(viable_pf) > 0:
        best = viable_pf.iloc[0]
        # Also find best by total PnL (min 15 trades, PF > 1.5)
        profitable = viable[(viable["pf"] > 1.5) & (viable["total_pnl"] > 0)]
        if len(profitable) > 0:
            best_pnl = profitable.sort_values("total_pnl", ascending=False).iloc[0]
        else:
            best_pnl = best

        # Find best balanced (PF * sqrt(trades) score)
        viable_copy = viable.copy()
        viable_copy["score"] = viable_copy["pf"] * np.sqrt(viable_copy["trades"])
        best_balanced = viable_copy.sort_values("score", ascending=False).iloc[0]

        lines.append("### Best by Profit Factor")
        lines.append(f"- **Entry**: {best['entry']}")
        lines.append(f"- **ADX**: {best['adx']}")
        lines.append(f"- **RSI**: {best['rsi']}")
        lines.append(f"- **Volume**: {best['vol']}")
        lines.append(f"- **Stop**: {best['stop']}")
        lines.append(f"- **Target**: {best['target']}")
        lines.append(f"- **Time Window**: {best['time_window']}")
        lines.append(f"- **Direction**: {best['direction']}")
        lines.append(f"- **Time Exit**: {best['time_exit']}")
        lines.append(f"- **Results**: {best['trades']:.0f} trades, {best['wr']:.1f}% WR, "
                     f"PF {best['pf']:.2f}, ${best['total_pnl']:,.0f}")
        lines.append("")

        lines.append("### Best by Total PnL (PF > 1.5)")
        lines.append(f"- **Entry**: {best_pnl['entry']}")
        lines.append(f"- **ADX**: {best_pnl['adx']}")
        lines.append(f"- **RSI**: {best_pnl['rsi']}")
        lines.append(f"- **Volume**: {best_pnl['vol']}")
        lines.append(f"- **Stop**: {best_pnl['stop']}")
        lines.append(f"- **Target**: {best_pnl['target']}")
        lines.append(f"- **Time Window**: {best_pnl['time_window']}")
        lines.append(f"- **Direction**: {best_pnl['direction']}")
        lines.append(f"- **Time Exit**: {best_pnl['time_exit']}")
        lines.append(f"- **Results**: {best_pnl['trades']:.0f} trades, {best_pnl['wr']:.1f}% WR, "
                     f"PF {best_pnl['pf']:.2f}, ${best_pnl['total_pnl']:,.0f}")
        lines.append("")

        lines.append("### Best Balanced (PF × sqrt(trades))")
        lines.append(f"- **Entry**: {best_balanced['entry']}")
        lines.append(f"- **ADX**: {best_balanced['adx']}")
        lines.append(f"- **RSI**: {best_balanced['rsi']}")
        lines.append(f"- **Volume**: {best_balanced['vol']}")
        lines.append(f"- **Stop**: {best_balanced['stop']}")
        lines.append(f"- **Target**: {best_balanced['target']}")
        lines.append(f"- **Time Window**: {best_balanced['time_window']}")
        lines.append(f"- **Direction**: {best_balanced['direction']}")
        lines.append(f"- **Time Exit**: {best_balanced['time_exit']}")
        lines.append(f"- **Score**: {best_balanced['score']:.1f}")
        lines.append(f"- **Results**: {best_balanced['trades']:.0f} trades, {best_balanced['wr']:.1f}% WR, "
                     f"PF {best_balanced['pf']:.2f}, ${best_balanced['total_pnl']:,.0f}")
    else:
        lines.append("**No viable configs found with >= 15 trades.**")

    # ── Comparison to old Mean Reversion VWAP ───────────────────
    lines.append("\n## Comparison to Old Mean Reversion VWAP")
    lines.append("")
    lines.append("| Metric | Old MR VWAP | BB Extreme (Best PF) | BB Extreme (Best PnL) | BB Extreme (Balanced) |")
    lines.append("|--------|-------------|---------------------|----------------------|----------------------|")

    old_mr = {"trades": "?", "wr": "?", "pf": "< 1.0", "total_pnl": "-$6,925"}

    if len(viable_pf) > 0:
        best = viable_pf.iloc[0]
        profitable = viable[(viable["pf"] > 1.5) & (viable["total_pnl"] > 0)]
        best_pnl = profitable.sort_values("total_pnl", ascending=False).iloc[0] if len(profitable) > 0 else best
        viable_copy = viable.copy()
        viable_copy["score"] = viable_copy["pf"] * np.sqrt(viable_copy["trades"])
        best_balanced = viable_copy.sort_values("score", ascending=False).iloc[0]

        lines.append(f"| Trades | {old_mr['trades']} | {best['trades']:.0f} | {best_pnl['trades']:.0f} | {best_balanced['trades']:.0f} |")
        lines.append(f"| WR% | {old_mr['wr']} | {best['wr']:.1f}% | {best_pnl['wr']:.1f}% | {best_balanced['wr']:.1f}% |")
        lines.append(f"| PF | {old_mr['pf']} | {best['pf']:.2f} | {best_pnl['pf']:.2f} | {best_balanced['pf']:.2f} |")
        lines.append(f"| Total PnL | {old_mr['total_pnl']} | ${best['total_pnl']:,.0f} | ${best_pnl['total_pnl']:,.0f} | ${best_balanced['total_pnl']:,.0f} |")
    else:
        lines.append("| Trades | ? | N/A | N/A | N/A |")
        lines.append("| WR% | ? | N/A | N/A | N/A |")
        lines.append("| PF | < 1.0 | N/A | N/A | N/A |")
        lines.append("| Total PnL | -$6,925 | N/A | N/A | N/A |")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by `scripts/_bb_extreme_study.py`*")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {report_path}")


def main():
    t0 = time.time()

    df = load_data()
    results_df = run_study(df)

    report_path = Path(__file__).resolve().parent.parent / "reports" / "quant-study-bb-extreme-reversal.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    generate_report(results_df, report_path)

    # Also save raw results CSV
    csv_path = report_path.with_suffix(".csv")
    results_df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Raw results CSV: {csv_path}")

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.0f}s ({elapsed/60:.1f}m)")


if __name__ == "__main__":
    main()
