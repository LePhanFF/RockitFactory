"""NWOG Study Part 2: Strategy simulation and advanced analysis."""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# ── Load Data ──
df = pd.read_csv(
    "data/sessions/NQ_Volumetric_1.csv",
    usecols=["timestamp", "open", "high", "low", "close", "volume", "session_date"],
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["session_date"] = pd.to_datetime(df["session_date"])

nwog = pd.read_csv("data/nwog_study_raw.csv")
nwog["monday_date"] = pd.to_datetime(nwog["monday_date"])
nwog["friday_date"] = pd.to_datetime(nwog["friday_date"])


# ═════════════════════════════════════════════════════════════════════════════
# A) STRATEGY SIMULATION: Trade toward gap fill on Monday RTH
# ═════════════════════════════════════════════════════════════════════════════

print("=" * 70)
print("NWOG STRATEGY SIMULATION")
print("=" * 70)

# Strategy parameters to test:
# Entry: At OR close (9:45), or on first pullback after OR
# Direction: Toward gap fill (short if UP gap, long if DOWN gap)
# Stop: Beyond gap edge + buffer (gap_edge + 0.5*ATR or fixed 40pts for NQ)
# Target: Gap fill (Friday RTH close)
# Timeout: EOD (16:15) - exit at market if not filled

NQ_TICK = 0.25
NQ_DOLLAR_PER_POINT = 20  # $20 per point per MNQ contract

trade_results = []

for _, row in nwog.iterrows():
    gap_abs = row["nwog_gap_abs"]
    if gap_abs < 20:
        continue  # Skip trivial gaps

    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")
    direction = row["direction"]
    fri_rth_close = row["fri_rth_close"]
    sun_open = row["sun_open"]

    mon_bars = df[df["session_date"] == mon_date]
    if len(mon_bars) == 0:
        continue

    # Entry at OR close (9:45)
    or_bars = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:30:00"))
        & (mon_bars["timestamp"] < pd.Timestamp(f"{mon_date_str} 09:45:00"))
    ]
    if len(or_bars) == 0:
        continue

    entry_price = or_bars.iloc[-1]["close"]  # OR close
    entry_time = or_bars.iloc[-1]["timestamp"]

    # Post-entry bars (9:45 to 16:15)
    post_bars = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:45:00"))
        & (mon_bars["timestamp"] <= pd.Timestamp(f"{mon_date_str} 16:15:00"))
    ]
    if len(post_bars) == 0:
        continue

    # Target = Friday RTH close (gap fill)
    target = fri_rth_close

    # Multiple stop sizes to test
    for stop_pts in [30, 40, 50, 75]:
        if direction == "UP":
            # Gap up -> SHORT toward fill
            trade_dir = "SHORT"
            stop_price = entry_price + stop_pts
            # Check: did we enter above target? (must be above to short toward fill)
            if entry_price <= target:
                # Already at/below target at entry - skip
                continue

            actual_reward = entry_price - target
            actual_rr = actual_reward / stop_pts if stop_pts > 0 else 0

            # Walk through bars
            exit_price = None
            exit_reason = None
            exit_time_val = None
            mae = 0  # worst adverse move (pts above entry for short)
            mfe = 0  # best favorable move (pts below entry for short)

            for _, bar in post_bars.iterrows():
                # Check stop hit (high >= stop)
                adverse = bar["high"] - entry_price
                favorable = entry_price - bar["low"]
                mae = max(mae, adverse)
                mfe = max(mfe, favorable)

                if bar["high"] >= stop_price:
                    exit_price = stop_price
                    exit_reason = "STOP"
                    exit_time_val = bar["timestamp"]
                    break
                if bar["low"] <= target:
                    exit_price = target
                    exit_reason = "TARGET"
                    exit_time_val = bar["timestamp"]
                    break

            if exit_price is None:
                # EOD exit
                exit_price = post_bars.iloc[-1]["close"]
                exit_reason = "EOD"
                exit_time_val = post_bars.iloc[-1]["timestamp"]

            pnl_pts = entry_price - exit_price  # short: entry - exit
            pnl_r = pnl_pts / stop_pts if stop_pts > 0 else 0

        else:
            # Gap down -> LONG toward fill
            trade_dir = "LONG"
            stop_price = entry_price - stop_pts
            if entry_price >= target:
                continue

            actual_reward = target - entry_price
            actual_rr = actual_reward / stop_pts if stop_pts > 0 else 0

            exit_price = None
            exit_reason = None
            exit_time_val = None
            mae = 0
            mfe = 0

            for _, bar in post_bars.iterrows():
                adverse = entry_price - bar["low"]
                favorable = bar["high"] - entry_price
                mae = max(mae, adverse)
                mfe = max(mfe, favorable)

                if bar["low"] <= stop_price:
                    exit_price = stop_price
                    exit_reason = "STOP"
                    exit_time_val = bar["timestamp"]
                    break
                if bar["high"] >= target:
                    exit_price = target
                    exit_reason = "TARGET"
                    exit_time_val = bar["timestamp"]
                    break

            if exit_price is None:
                exit_price = post_bars.iloc[-1]["close"]
                exit_reason = "EOD"
                exit_time_val = post_bars.iloc[-1]["timestamp"]

            pnl_pts = exit_price - entry_price
            pnl_r = pnl_pts / stop_pts if stop_pts > 0 else 0

        pnl_dollar = pnl_pts * NQ_DOLLAR_PER_POINT

        # Time to resolution
        if exit_time_val:
            rth_open = pd.Timestamp(f"{mon_date_str} 09:30:00")
            time_to_exit = (exit_time_val - rth_open).total_seconds() / 60
        else:
            time_to_exit = None

        trade_results.append(
            {
                "monday_date": mon_date,
                "gap": row["nwog_gap"],
                "gap_abs": gap_abs,
                "direction": direction,
                "trade_dir": trade_dir,
                "stop_pts": stop_pts,
                "entry_price": entry_price,
                "target": target,
                "stop_price": stop_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "actual_reward_pts": actual_reward,
                "actual_rr": actual_rr,
                "pnl_pts": pnl_pts,
                "pnl_r": pnl_r,
                "pnl_dollar": pnl_dollar,
                "mae_pts": mae,
                "mfe_pts": mfe,
                "time_to_exit_min": time_to_exit,
            }
        )

trades_df = pd.DataFrame(trade_results)

# ── Report by stop size ──
print("\n--- STRATEGY SIM: Entry at OR Close (9:45), Target = Gap Fill ---")
for stop in [30, 40, 50, 75]:
    subset = trades_df[trades_df["stop_pts"] == stop]
    if len(subset) == 0:
        continue
    wins = subset[subset["pnl_pts"] > 0]
    losses = subset[subset["pnl_pts"] <= 0]
    targets = subset[subset["exit_reason"] == "TARGET"]
    stops = subset[subset["exit_reason"] == "STOP"]
    eods = subset[subset["exit_reason"] == "EOD"]
    net_pnl = subset["pnl_dollar"].sum()
    avg_win = wins["pnl_dollar"].mean() if len(wins) > 0 else 0
    avg_loss = losses["pnl_dollar"].mean() if len(losses) > 0 else 0
    pf = abs(wins["pnl_dollar"].sum() / losses["pnl_dollar"].sum()) if losses["pnl_dollar"].sum() != 0 else 999

    print(f"\n  Stop = {stop} pts:")
    print(f"    Trades: {len(subset)}")
    print(f"    Wins: {len(wins)} ({len(wins)/len(subset)*100:.1f}%)")
    print(f"    Targets hit: {len(targets)}, Stops hit: {len(stops)}, EOD: {len(eods)}")
    print(f"    Net PnL: ${net_pnl:,.0f} (${net_pnl/len(subset):,.0f}/trade)")
    print(f"    Avg win: ${avg_win:,.0f}, Avg loss: ${avg_loss:,.0f}")
    print(f"    Profit Factor: {pf:.2f}")
    print(f"    Avg MAE: {subset['mae_pts'].mean():.1f} pts, Avg MFE: {subset['mfe_pts'].mean():.1f} pts")
    print(f"    Avg time to exit: {subset['time_to_exit_min'].mean():.0f} min")

    # By gap size
    print(f"    By gap size:")
    for lo, hi, label in [(20, 50, "20-50"), (50, 100, "50-100"), (100, 200, "100-200"), (200, 600, "200+")]:
        sub2 = subset[(subset["gap_abs"] >= lo) & (subset["gap_abs"] < hi)]
        if len(sub2) == 0:
            continue
        wr = (sub2["pnl_pts"] > 0).mean() * 100
        print(
            f"      {label}: n={len(sub2)}, WR={wr:.0f}%, PnL=${sub2['pnl_dollar'].sum():,.0f}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# B) LONDON / ASIA SESSION ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("LONDON / ASIA SESSION CONTEXT ON MONDAYS")
print("=" * 70)

# Asia session: ~20:00-02:00 ET (Sunday night for Monday)
# London session: ~03:00-09:30 ET
# We approximate: Asia = 20:00-02:00, London = 03:00-09:30

for _, row in nwog.iterrows():
    gap_abs = row["nwog_gap_abs"]
    if gap_abs < 20:
        continue

    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")
    sun_date_str = (mon_date - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    mon_bars = df[df["session_date"] == mon_date]
    if len(mon_bars) == 0:
        continue

    # Asia: Sun 20:00 to Mon 02:00
    asia = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{sun_date_str} 20:00:00"))
        & (mon_bars["timestamp"] < pd.Timestamp(f"{mon_date_str} 02:00:00"))
    ]
    # London: Mon 03:00 to 09:30
    london = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 03:00:00"))
        & (mon_bars["timestamp"] < pd.Timestamp(f"{mon_date_str} 09:30:00"))
    ]

    if len(asia) > 0:
        asia_high = asia["high"].max()
        asia_low = asia["low"].min()
        nwog.loc[nwog["monday_date"] == mon_date, "asia_high"] = asia_high
        nwog.loc[nwog["monday_date"] == mon_date, "asia_low"] = asia_low
        nwog.loc[nwog["monday_date"] == mon_date, "asia_range"] = asia_high - asia_low

    if len(london) > 0:
        london_high = london["high"].max()
        london_low = london["low"].min()
        nwog.loc[nwog["monday_date"] == mon_date, "london_high"] = london_high
        nwog.loc[nwog["monday_date"] == mon_date, "london_low"] = london_low
        nwog.loc[nwog["monday_date"] == mon_date, "london_range"] = london_high - london_low

        # London relative to Asia
        if len(asia) > 0:
            lon_above_asia = london_high > asia_high
            lon_below_asia = london_low < asia_low
            nwog.loc[nwog["monday_date"] == mon_date, "london_above_asia"] = lon_above_asia
            nwog.loc[nwog["monday_date"] == mon_date, "london_below_asia"] = lon_below_asia

big_nwog = nwog[nwog["nwog_gap_abs"] >= 20].copy()

if "london_range" in big_nwog.columns:
    print(f"\nLondon/Asia data available for {big_nwog['london_range'].notna().sum()} / {len(big_nwog)} NWOGs")

    # London range above Asia -> bullish signal
    lon_above = big_nwog[big_nwog.get("london_above_asia", pd.Series(dtype=bool)) == True]
    lon_not_above = big_nwog[big_nwog.get("london_above_asia", pd.Series(dtype=bool)) == False]

    print(f"\nLondon breaks above Asia high:")
    if len(lon_above) > 0:
        print(f"  n={len(lon_above)}, Mon RTH fill={lon_above['rth_filled'].mean()*100:.1f}%")
    print(f"London stays within/below Asia:")
    if len(lon_not_above) > 0:
        print(f"  n={len(lon_not_above)}, Mon RTH fill={lon_not_above['rth_filled'].mean()*100:.1f}%")

    # Does London sweep predict fill?
    # London sweep of Asia high (for UP gap) or Asia low (for DOWN gap)
    print("\nLondon sweep analysis (gap direction aware):")
    sweep_count = 0
    sweep_fill = 0
    no_sweep_count = 0
    no_sweep_fill = 0

    for _, row in big_nwog.iterrows():
        if pd.isna(row.get("london_high")) or pd.isna(row.get("asia_high")):
            continue
        if row["direction"] == "UP":
            # UP gap: bearish fill expected. Does London sweep Asia HIGH (liquidity grab) then reverse?
            swept = row.get("london_high", 0) > row.get("asia_high", 0)
        else:
            # DOWN gap: bullish fill expected. Does London sweep Asia LOW?
            swept = row.get("london_low", 999999) < row.get("asia_low", 999999)

        if swept:
            sweep_count += 1
            if row["rth_filled"]:
                sweep_fill += 1
        else:
            no_sweep_count += 1
            if row["rth_filled"]:
                no_sweep_fill += 1

    if sweep_count > 0:
        print(f"  London sweeps liquidity: n={sweep_count}, fill rate={sweep_fill/sweep_count*100:.1f}%")
    if no_sweep_count > 0:
        print(f"  No London sweep:         n={no_sweep_count}, fill rate={no_sweep_fill/no_sweep_count*100:.1f}%")


# ═════════════════════════════════════════════════════════════════════════════
# C) FILTERED STRATEGY: Only trade when conditions favor fill
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("FILTERED STRATEGY VARIANTS")
print("=" * 70)

# Variant 1: Only DOWN gaps (higher base fill rate)
down_trades = trades_df[(trades_df["direction"] == "DOWN") & (trades_df["stop_pts"] == 40)]
if len(down_trades) > 0:
    wins = (down_trades["pnl_pts"] > 0).sum()
    print(f"\nVariant 1: DOWN gaps only, 40pt stop")
    print(f"  Trades: {len(down_trades)}, WR: {wins/len(down_trades)*100:.1f}%, Net PnL: ${down_trades['pnl_dollar'].sum():,.0f}")
    print(f"  Avg PnL/trade: ${down_trades['pnl_dollar'].mean():,.0f}")
    pf = abs(down_trades[down_trades['pnl_pts'] > 0]['pnl_dollar'].sum() / down_trades[down_trades['pnl_pts'] <= 0]['pnl_dollar'].sum()) if down_trades[down_trades['pnl_pts'] <= 0]['pnl_dollar'].sum() != 0 else 999
    print(f"  PF: {pf:.2f}")

# Variant 2: Gaps 30-150 pts only (sweet spot?)
mid_trades = trades_df[(trades_df["gap_abs"] >= 30) & (trades_df["gap_abs"] <= 150) & (trades_df["stop_pts"] == 40)]
if len(mid_trades) > 0:
    wins = (mid_trades["pnl_pts"] > 0).sum()
    print(f"\nVariant 2: Gaps 30-150 pts, 40pt stop")
    print(f"  Trades: {len(mid_trades)}, WR: {wins/len(mid_trades)*100:.1f}%, Net PnL: ${mid_trades['pnl_dollar'].sum():,.0f}")
    pf = abs(mid_trades[mid_trades['pnl_pts'] > 0]['pnl_dollar'].sum() / mid_trades[mid_trades['pnl_pts'] <= 0]['pnl_dollar'].sum()) if mid_trades[mid_trades['pnl_pts'] <= 0]['pnl_dollar'].sum() != 0 else 999
    print(f"  PF: {pf:.2f}")

# Variant 3: DOWN gaps 30-150 pts (best of both)
best_trades = trades_df[(trades_df["direction"] == "DOWN") & (trades_df["gap_abs"] >= 30) & (trades_df["gap_abs"] <= 150) & (trades_df["stop_pts"] == 40)]
if len(best_trades) > 0:
    wins = (best_trades["pnl_pts"] > 0).sum()
    print(f"\nVariant 3: DOWN gaps 30-150 pts, 40pt stop")
    print(f"  Trades: {len(best_trades)}, WR: {wins/len(best_trades)*100:.1f}%, Net PnL: ${best_trades['pnl_dollar'].sum():,.0f}")
    pf = abs(best_trades[best_trades['pnl_pts'] > 0]['pnl_dollar'].sum() / best_trades[best_trades['pnl_pts'] <= 0]['pnl_dollar'].sum()) if best_trades[best_trades['pnl_pts'] <= 0]['pnl_dollar'].sum() != 0 else 999
    print(f"  PF: {pf:.2f}")

# Variant 4: OR moves toward fill + 40pt stop (filter for confirming OR)
# Need to merge OR direction info
nwog_or = nwog[["monday_date", "or_against_gap"]].copy()
trades_merged = trades_df.merge(nwog_or, on="monday_date", how="left")
or_confirm = trades_merged[(trades_merged["or_against_gap"] == True) & (trades_merged["stop_pts"] == 40)]
if len(or_confirm) > 0:
    wins = (or_confirm["pnl_pts"] > 0).sum()
    print(f"\nVariant 4: OR confirms fill direction, 40pt stop")
    print(f"  Trades: {len(or_confirm)}, WR: {wins/len(or_confirm)*100:.1f}%, Net PnL: ${or_confirm['pnl_dollar'].sum():,.0f}")
    pf = abs(or_confirm[or_confirm['pnl_pts'] > 0]['pnl_dollar'].sum() / or_confirm[or_confirm['pnl_pts'] <= 0]['pnl_dollar'].sum()) if or_confirm[or_confirm['pnl_pts'] <= 0]['pnl_dollar'].sum() != 0 else 999
    print(f"  PF: {pf:.2f}")


# ═════════════════════════════════════════════════════════════════════════════
# D) 80P-LIKE SETUP ANALYSIS: Does price need to accept in the gap zone?
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("80P-STYLE ACCEPTANCE ANALYSIS")
print("=" * 70)

# For 80P, we look for price spending time (accepting) near the gap zone
# Check: In the first 30 minutes of RTH, does price spend >50% of bars
# on the fill side of the gap midpoint?

for _, row in nwog.iterrows():
    gap_abs = row["nwog_gap_abs"]
    if gap_abs < 20:
        continue

    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")
    direction = row["direction"]
    fri_rth_close = row["fri_rth_close"]
    sun_open = row["sun_open"]
    gap_mid = (fri_rth_close + sun_open) / 2

    mon_bars = df[df["session_date"] == mon_date]
    first_30 = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:30:00"))
        & (mon_bars["timestamp"] < pd.Timestamp(f"{mon_date_str} 10:00:00"))
    ]
    if len(first_30) == 0:
        continue

    if direction == "UP":
        # Fill means going down. Acceptance = bars closing below gap midpoint
        accepting = (first_30["close"] < gap_mid).sum()
    else:
        # Fill means going up. Acceptance = bars closing above gap midpoint
        accepting = (first_30["close"] > gap_mid).sum()

    accept_pct = accepting / len(first_30) * 100
    nwog.loc[nwog["monday_date"] == mon_date, "acceptance_pct"] = accept_pct

big_nwog = nwog[nwog["nwog_gap_abs"] >= 20].copy()
if "acceptance_pct" in big_nwog.columns:
    high_accept = big_nwog[big_nwog["acceptance_pct"] >= 50]
    low_accept = big_nwog[big_nwog["acceptance_pct"] < 50]

    print(f"\nFirst 30min acceptance (>= 50% bars on fill side of gap midpoint):")
    print(f"  High acceptance (n={len(high_accept)}): Mon RTH fill={high_accept['rth_filled'].mean()*100:.1f}%, Week={high_accept['week_filled'].mean()*100:.1f}%")
    print(f"  Low acceptance  (n={len(low_accept)}):  Mon RTH fill={low_accept['rth_filled'].mean()*100:.1f}%, Week={low_accept['week_filled'].mean()*100:.1f}%")


# ═════════════════════════════════════════════════════════════════════════════
# E) OPTIMAL STOP SIZE ANALYSIS (MAE distribution)
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("MAE DISTRIBUTION (for optimal stop sizing)")
print("=" * 70)

stop40 = trades_df[trades_df["stop_pts"] == 40].copy()
winning = stop40[stop40["exit_reason"] == "TARGET"]
losing = stop40[stop40["exit_reason"] == "STOP"]
eod = stop40[stop40["exit_reason"] == "EOD"]

print(f"\nAll trades (40pt stop, n={len(stop40)}):")
print(f"  MAE: mean={stop40['mae_pts'].mean():.1f}, median={stop40['mae_pts'].median():.1f}, max={stop40['mae_pts'].max():.1f}")
print(f"  MFE: mean={stop40['mfe_pts'].mean():.1f}, median={stop40['mfe_pts'].median():.1f}, max={stop40['mfe_pts'].max():.1f}")

if len(winning) > 0:
    print(f"\nWinning trades (n={len(winning)}):")
    print(f"  MAE: mean={winning['mae_pts'].mean():.1f}, median={winning['mae_pts'].median():.1f}, max={winning['mae_pts'].max():.1f}")
    print(f"  MFE: mean={winning['mfe_pts'].mean():.1f}, median={winning['mfe_pts'].median():.1f}")

if len(losing) > 0:
    print(f"\nLosing trades - stopped out (n={len(losing)}):")
    print(f"  MFE before stop: mean={losing['mfe_pts'].mean():.1f}, median={losing['mfe_pts'].median():.1f}")

if len(eod) > 0:
    print(f"\nEOD exits (n={len(eod)}):")
    print(f"  MAE: mean={eod['mae_pts'].mean():.1f}, MFE: mean={eod['mfe_pts'].mean():.1f}")
    print(f"  PnL: mean=${eod['pnl_dollar'].mean():,.0f}, sum=${eod['pnl_dollar'].sum():,.0f}")

# Edge ratio
stop40["edge_ratio"] = stop40["mfe_pts"] / stop40["mae_pts"].replace(0, 0.25)
print(f"\nEdge Ratio (MFE/MAE): mean={stop40['edge_ratio'].mean():.2f}, median={stop40['edge_ratio'].median():.2f}")


# ═════════════════════════════════════════════════════════════════════════════
# F) CONSECUTIVE WEEK ANALYSIS
# ═════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("WEEK-OVER-WEEK PATTERNS")
print("=" * 70)

nwog_big = nwog[nwog["nwog_gap_abs"] >= 20].sort_values("monday_date").reset_index(drop=True)
if len(nwog_big) > 1:
    # Did prior week's gap fill predict this week?
    for i in range(1, len(nwog_big)):
        prev = nwog_big.iloc[i - 1]
        curr = nwog_big.iloc[i]
        # Check if consecutive weeks
        if (curr["monday_date"] - prev["monday_date"]).days <= 8:
            nwog_big.loc[nwog_big.index[i], "prev_week_filled"] = prev["mon_session_filled"]
            nwog_big.loc[nwog_big.index[i], "prev_gap_direction"] = prev["direction"]

    if "prev_week_filled" in nwog_big.columns:
        prev_filled = nwog_big[nwog_big["prev_week_filled"] == True]
        prev_not = nwog_big[nwog_big["prev_week_filled"] == False]
        print(f"\nPrior week gap filled -> this week fill rate:")
        if len(prev_filled) > 0:
            print(f"  Prior filled (n={len(prev_filled)}): Mon RTH={prev_filled['rth_filled'].mean()*100:.1f}%")
        if len(prev_not) > 0:
            print(f"  Prior NOT filled (n={len(prev_not)}): Mon RTH={prev_not['rth_filled'].mean()*100:.1f}%")

        # Same direction vs opposite
        same_dir = nwog_big[nwog_big.apply(lambda r: r.get("prev_gap_direction") == r["direction"], axis=1)]
        diff_dir = nwog_big[nwog_big.apply(lambda r: r.get("prev_gap_direction") != r["direction"] and pd.notna(r.get("prev_gap_direction")), axis=1)]
        print(f"\nSame direction as prior week:")
        if len(same_dir) > 0:
            print(f"  n={len(same_dir)}, Mon RTH fill={same_dir['rth_filled'].mean()*100:.1f}%")
        if len(diff_dir) > 0:
            print(f"  Opposite direction: n={len(diff_dir)}, Mon RTH fill={diff_dir['rth_filled'].mean()*100:.1f}%")


print("\n--- PART 2 COMPLETE ---")
