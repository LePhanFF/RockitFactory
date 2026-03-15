"""NWOG Study Part 3: Acceptance-filtered strategy sim + final stats."""

import pandas as pd
import numpy as np

# ── Load Data ──
df = pd.read_csv(
    "data/sessions/NQ_Volumetric_1.csv",
    usecols=["timestamp", "open", "high", "low", "close", "volume", "session_date"],
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["session_date"] = pd.to_datetime(df["session_date"])

nwog = pd.read_csv("data/nwog_study_raw.csv")
nwog["monday_date"] = pd.to_datetime(nwog["monday_date"])

NQ_DOLLAR_PER_POINT = 20

# Recompute acceptance for each NWOG
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
        accepting = (first_30["close"] < gap_mid).sum()
    else:
        accepting = (first_30["close"] > gap_mid).sum()

    accept_pct = accepting / len(first_30) * 100
    nwog.loc[nwog["monday_date"] == mon_date, "acceptance_pct"] = accept_pct


# ════════════════════════════════════════════════════════════════
# ACCEPTANCE-FILTERED STRATEGY SIMULATION
# Entry: 10:00 (after acceptance confirmation)
# Filter: acceptance_pct >= 50%
# Stop: 40 pts, 50 pts
# Target: gap fill
# ════════════════════════════════════════════════════════════════

print("=" * 70)
print("ACCEPTANCE-FILTERED NWOG STRATEGY")
print("=" * 70)

trade_results = []

accepted = nwog[(nwog["nwog_gap_abs"] >= 20) & (nwog["acceptance_pct"] >= 50)].copy()
print(f"\nNWOGs with >= 50% acceptance: {len(accepted)} / {(nwog['nwog_gap_abs'] >= 20).sum()}")

for _, row in accepted.iterrows():
    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")
    direction = row["direction"]
    gap_abs = row["nwog_gap_abs"]
    fri_rth_close = row["fri_rth_close"]
    sun_open = row["sun_open"]

    mon_bars = df[df["session_date"] == mon_date]
    if len(mon_bars) == 0:
        continue

    # Entry at 10:00 (after acceptance confirmed)
    entry_bar = mon_bars[mon_bars["timestamp"] == pd.Timestamp(f"{mon_date_str} 10:00:00")]
    if len(entry_bar) == 0:
        entry_bar = mon_bars[
            (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:59:00"))
            & (mon_bars["timestamp"] <= pd.Timestamp(f"{mon_date_str} 10:01:00"))
        ]
    if len(entry_bar) == 0:
        continue

    entry_price = entry_bar.iloc[0]["close"]
    target = fri_rth_close

    post_bars = mon_bars[
        (mon_bars["timestamp"] > pd.Timestamp(f"{mon_date_str} 10:00:00"))
        & (mon_bars["timestamp"] <= pd.Timestamp(f"{mon_date_str} 16:15:00"))
    ]
    if len(post_bars) == 0:
        continue

    for stop_pts in [30, 40, 50, 60]:
        if direction == "UP":
            trade_dir = "SHORT"
            stop_price = entry_price + stop_pts
            if entry_price <= target:
                continue
            actual_reward = entry_price - target

            exit_price = None
            exit_reason = None
            exit_time_val = None
            mae = 0
            mfe = 0

            for _, bar in post_bars.iterrows():
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
                exit_price = post_bars.iloc[-1]["close"]
                exit_reason = "EOD"
                exit_time_val = post_bars.iloc[-1]["timestamp"]
            pnl_pts = entry_price - exit_price

        else:
            trade_dir = "LONG"
            stop_price = entry_price - stop_pts
            if entry_price >= target:
                continue
            actual_reward = target - entry_price

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

        pnl_dollar = pnl_pts * NQ_DOLLAR_PER_POINT
        rth_open = pd.Timestamp(f"{mon_date_str} 09:30:00")
        time_to_exit = (exit_time_val - rth_open).total_seconds() / 60 if exit_time_val else None

        trade_results.append({
            "monday_date": mon_date,
            "gap": row["nwog_gap"],
            "gap_abs": gap_abs,
            "direction": direction,
            "trade_dir": trade_dir,
            "stop_pts": stop_pts,
            "entry_price": entry_price,
            "target": target,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "actual_reward_pts": actual_reward,
            "pnl_pts": pnl_pts,
            "pnl_dollar": pnl_dollar,
            "mae_pts": mae,
            "mfe_pts": mfe,
            "time_to_exit_min": time_to_exit,
            "acceptance_pct": row["acceptance_pct"],
        })

trades_df = pd.DataFrame(trade_results)

print("\n--- ACCEPTANCE-FILTERED: Entry at 10:00, Target = Gap Fill ---")
for stop in [30, 40, 50, 60]:
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
    loss_sum = losses["pnl_dollar"].sum()
    pf = abs(wins["pnl_dollar"].sum() / loss_sum) if loss_sum != 0 else 999

    print(f"\n  Stop = {stop} pts:")
    print(f"    Trades: {len(subset)}")
    print(f"    Wins: {len(wins)} ({len(wins)/len(subset)*100:.1f}%)")
    print(f"    Targets: {len(targets)}, Stops: {len(stops)}, EOD: {len(eods)}")
    print(f"    Net PnL: ${net_pnl:,.0f} (${net_pnl/len(subset):,.0f}/trade)")
    print(f"    Avg win: ${avg_win:,.0f}, Avg loss: ${avg_loss:,.0f}")
    print(f"    PF: {pf:.2f}")
    print(f"    MAE: mean={subset['mae_pts'].mean():.1f}, MFE: mean={subset['mfe_pts'].mean():.1f}")
    if len(wins) > 0:
        print(f"    Winners MAE: mean={wins['mae_pts'].mean():.1f}")

    # Trade-by-trade
    print(f"    Trade details:")
    for _, t in subset.iterrows():
        print(f"      {t['monday_date'].strftime('%Y-%m-%d')} | gap={t['gap']:>+.0f} | {t['trade_dir']} | entry={t['entry_price']:.0f} | tgt={t['target']:.0f} | exit={t['exit_price']:.0f} | {t['exit_reason']:>6s} | pnl=${t['pnl_dollar']:>+,.0f} | MAE={t['mae_pts']:.0f}")


# ════════════════════════════════════════════════════════════════
# HIGHER ACCEPTANCE THRESHOLD
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("ACCEPTANCE THRESHOLD SENSITIVITY")
print("=" * 70)

for thresh in [30, 40, 50, 60, 70, 80]:
    subset = nwog[(nwog["nwog_gap_abs"] >= 20) & (nwog["acceptance_pct"] >= thresh)]
    if len(subset) == 0:
        print(f"  Threshold {thresh}%: n=0")
        continue
    fill_rate = subset["rth_filled"].mean() * 100
    week_fill = subset["week_filled"].mean() * 100
    print(f"  Threshold {thresh}%: n={len(subset)}, Mon RTH fill={fill_rate:.1f}%, Week fill={week_fill:.1f}%")


# ════════════════════════════════════════════════════════════════
# 50% TARGET (half gap fill) SIMULATION
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("50% GAP FILL TARGET (conservative approach)")
print("=" * 70)

half_results = []
for _, row in nwog.iterrows():
    gap_abs = row["nwog_gap_abs"]
    if gap_abs < 30:
        continue

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

    entry_price = or_bars.iloc[-1]["close"]

    # 50% gap fill target
    half_target = (fri_rth_close + sun_open) / 2

    post_bars = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:45:00"))
        & (mon_bars["timestamp"] <= pd.Timestamp(f"{mon_date_str} 16:15:00"))
    ]
    if len(post_bars) == 0:
        continue

    for stop_pts in [40]:
        if direction == "UP":
            trade_dir = "SHORT"
            stop_price = entry_price + stop_pts
            if entry_price <= half_target:
                continue

            exit_price = None
            exit_reason = None
            for _, bar in post_bars.iterrows():
                if bar["high"] >= stop_price:
                    exit_price = stop_price
                    exit_reason = "STOP"
                    break
                if bar["low"] <= half_target:
                    exit_price = half_target
                    exit_reason = "TARGET"
                    break
            if exit_price is None:
                exit_price = post_bars.iloc[-1]["close"]
                exit_reason = "EOD"
            pnl_pts = entry_price - exit_price
        else:
            trade_dir = "LONG"
            stop_price = entry_price - stop_pts
            if entry_price >= half_target:
                continue

            exit_price = None
            exit_reason = None
            for _, bar in post_bars.iterrows():
                if bar["low"] <= stop_price:
                    exit_price = stop_price
                    exit_reason = "STOP"
                    break
                if bar["high"] >= half_target:
                    exit_price = half_target
                    exit_reason = "TARGET"
                    break
            if exit_price is None:
                exit_price = post_bars.iloc[-1]["close"]
                exit_reason = "EOD"
            pnl_pts = exit_price - entry_price

        pnl_dollar = pnl_pts * NQ_DOLLAR_PER_POINT
        half_results.append({
            "monday_date": mon_date,
            "gap_abs": gap_abs,
            "direction": direction,
            "pnl_pts": pnl_pts,
            "pnl_dollar": pnl_dollar,
            "exit_reason": exit_reason,
        })

hdf = pd.DataFrame(half_results)
if len(hdf) > 0:
    wins = hdf[hdf["pnl_pts"] > 0]
    losses = hdf[hdf["pnl_pts"] <= 0]
    loss_sum = losses["pnl_dollar"].sum()
    pf = abs(wins["pnl_dollar"].sum() / loss_sum) if loss_sum != 0 else 999
    print(f"\n50% gap fill target, 40pt stop, gaps >= 30pts:")
    print(f"  Trades: {len(hdf)}")
    print(f"  WR: {len(wins)/len(hdf)*100:.1f}%")
    print(f"  Net PnL: ${hdf['pnl_dollar'].sum():,.0f}")
    print(f"  PF: {pf:.2f}")
    print(f"  Targets: {(hdf['exit_reason']=='TARGET').sum()}, Stops: {(hdf['exit_reason']=='STOP').sum()}, EOD: {(hdf['exit_reason']=='EOD').sum()}")


# ════════════════════════════════════════════════════════════════
# CORRELATION WITH VWAP / DELTA
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("VWAP SESSION CONTEXT ON MONDAYS")
print("=" * 70)

for _, row in nwog.iterrows():
    gap_abs = row["nwog_gap_abs"]
    if gap_abs < 20:
        continue

    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")

    mon_bars = df[df["session_date"] == mon_date]
    if len(mon_bars) == 0:
        continue

    # Get VWAP data from the full CSV
    full_df = pd.read_csv(
        "data/sessions/NQ_Volumetric_1.csv",
        usecols=["timestamp", "close", "vwap", "vol_delta", "session_date"],
    )
    full_df["timestamp"] = pd.to_datetime(full_df["timestamp"])
    full_df["session_date"] = pd.to_datetime(full_df["session_date"])

    mon_full = full_df[full_df["session_date"] == mon_date]
    rth_bars = mon_full[
        (mon_full["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:30:00"))
        & (mon_full["timestamp"] <= pd.Timestamp(f"{mon_date_str} 10:30:00"))
    ]
    if len(rth_bars) > 0:
        # Price vs VWAP at 10:00
        bar_10 = rth_bars[rth_bars["timestamp"] <= pd.Timestamp(f"{mon_date_str} 10:00:00")]
        if len(bar_10) > 0:
            last_bar = bar_10.iloc[-1]
            above_vwap = last_bar["close"] > last_bar["vwap"]
            delta_sum = rth_bars["vol_delta"].sum()

            nwog.loc[nwog["monday_date"] == mon_date, "above_vwap_10am"] = above_vwap
            nwog.loc[nwog["monday_date"] == mon_date, "delta_first_hour"] = delta_sum
    break  # Only do this once since we load full CSV each time - just check one

# Simpler approach: just check price vs VWAP from the existing loaded data
print("\nLoading VWAP data for all Mondays...")
full_df = pd.read_csv(
    "data/sessions/NQ_Volumetric_1.csv",
    usecols=["timestamp", "close", "vwap", "vol_delta", "session_date"],
)
full_df["timestamp"] = pd.to_datetime(full_df["timestamp"])
full_df["session_date"] = pd.to_datetime(full_df["session_date"])

for _, row in nwog.iterrows():
    gap_abs = row["nwog_gap_abs"]
    if gap_abs < 20:
        continue

    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")
    direction = row["direction"]

    mon_full = full_df[full_df["session_date"] == mon_date]
    bar_10 = mon_full[
        (mon_full["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:55:00"))
        & (mon_full["timestamp"] <= pd.Timestamp(f"{mon_date_str} 10:00:00"))
    ]
    first_hour = mon_full[
        (mon_full["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:30:00"))
        & (mon_full["timestamp"] < pd.Timestamp(f"{mon_date_str} 10:30:00"))
    ]

    if len(bar_10) > 0 and len(first_hour) > 0:
        last = bar_10.iloc[-1]
        above_vwap = last["close"] > last["vwap"]
        delta_sum = first_hour["vol_delta"].sum()

        nwog.loc[nwog["monday_date"] == mon_date, "above_vwap_10am"] = above_vwap
        nwog.loc[nwog["monday_date"] == mon_date, "delta_first_hour"] = delta_sum

        # Does VWAP position support fill direction?
        if direction == "UP":
            vwap_supports_fill = not above_vwap  # Below VWAP supports short (fill down)
            delta_supports_fill = delta_sum < 0  # Negative delta supports selling
        else:
            vwap_supports_fill = above_vwap  # Above VWAP supports long (fill up)
            delta_supports_fill = delta_sum > 0  # Positive delta supports buying

        nwog.loc[nwog["monday_date"] == mon_date, "vwap_supports_fill"] = vwap_supports_fill
        nwog.loc[nwog["monday_date"] == mon_date, "delta_supports_fill"] = delta_supports_fill

big = nwog[nwog["nwog_gap_abs"] >= 20].copy()
if "vwap_supports_fill" in big.columns:
    vwap_yes = big[big["vwap_supports_fill"] == True]
    vwap_no = big[big["vwap_supports_fill"] == False]
    print(f"\nVWAP supports fill direction (at 10:00):")
    if len(vwap_yes) > 0:
        print(f"  Yes (n={len(vwap_yes)}): Mon RTH fill={vwap_yes['rth_filled'].mean()*100:.1f}%, Week={vwap_yes['week_filled'].mean()*100:.1f}%")
    if len(vwap_no) > 0:
        print(f"  No  (n={len(vwap_no)}):  Mon RTH fill={vwap_no['rth_filled'].mean()*100:.1f}%, Week={vwap_no['week_filled'].mean()*100:.1f}%")

if "delta_supports_fill" in big.columns:
    delta_yes = big[big["delta_supports_fill"] == True]
    delta_no = big[big["delta_supports_fill"] == False]
    print(f"\nFirst-hour delta supports fill:")
    if len(delta_yes) > 0:
        print(f"  Yes (n={len(delta_yes)}): Mon RTH fill={delta_yes['rth_filled'].mean()*100:.1f}%")
    if len(delta_no) > 0:
        print(f"  No  (n={len(delta_no)}):  Mon RTH fill={delta_no['rth_filled'].mean()*100:.1f}%")

# Combined filter: acceptance + VWAP
if "acceptance_pct" in big.columns and "vwap_supports_fill" in big.columns:
    combined = big[(big["acceptance_pct"] >= 50) & (big["vwap_supports_fill"] == True)]
    print(f"\nCombined: Acceptance >= 50% AND VWAP supports fill:")
    if len(combined) > 0:
        print(f"  n={len(combined)}, Mon RTH fill={combined['rth_filled'].mean()*100:.1f}%, Week={combined['week_filled'].mean()*100:.1f}%")
    else:
        print("  n=0")

print("\n--- PART 3 COMPLETE ---")
