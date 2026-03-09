"""NWOG Study Part 4: VWAP-filtered strategy sim + final best strategy."""

import pandas as pd
import numpy as np

df = pd.read_csv(
    "data/sessions/NQ_Volumetric_1.csv",
    usecols=["timestamp", "open", "high", "low", "close", "volume", "session_date"],
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["session_date"] = pd.to_datetime(df["session_date"])

full_df = pd.read_csv(
    "data/sessions/NQ_Volumetric_1.csv",
    usecols=["timestamp", "close", "vwap", "vol_delta", "session_date"],
)
full_df["timestamp"] = pd.to_datetime(full_df["timestamp"])
full_df["session_date"] = pd.to_datetime(full_df["session_date"])

nwog = pd.read_csv("data/nwog_study_raw.csv")
nwog["monday_date"] = pd.to_datetime(nwog["monday_date"])

NQ_DOLLAR_PER_POINT = 20

# Recompute acceptance + VWAP for each NWOG
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
    if len(first_30) > 0:
        if direction == "UP":
            accepting = (first_30["close"] < gap_mid).sum()
        else:
            accepting = (first_30["close"] > gap_mid).sum()
        nwog.loc[nwog["monday_date"] == mon_date, "acceptance_pct"] = accepting / len(first_30) * 100

    # VWAP check at 10:00
    mon_full = full_df[full_df["session_date"] == mon_date]
    bar_10 = mon_full[
        (mon_full["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:55:00"))
        & (mon_full["timestamp"] <= pd.Timestamp(f"{mon_date_str} 10:00:00"))
    ]
    if len(bar_10) > 0:
        last = bar_10.iloc[-1]
        above_vwap = last["close"] > last["vwap"]
        if direction == "UP":
            vwap_supports = not above_vwap
        else:
            vwap_supports = above_vwap
        nwog.loc[nwog["monday_date"] == mon_date, "vwap_supports_fill"] = vwap_supports
        nwog.loc[nwog["monday_date"] == mon_date, "vwap_at_10"] = last["vwap"]
        nwog.loc[nwog["monday_date"] == mon_date, "close_at_10"] = last["close"]


# ════════════════════════════════════════════════════════════════
# BEST STRATEGY: VWAP-FILTERED, entry at 10:00
# ════════════════════════════════════════════════════════════════
print("=" * 70)
print("VWAP-FILTERED NWOG STRATEGY (price on fill side of session VWAP)")
print("=" * 70)

vwap_filtered = nwog[(nwog["nwog_gap_abs"] >= 20) & (nwog["vwap_supports_fill"] == True)].copy()
print(f"\nNWOGs with VWAP supporting fill: {len(vwap_filtered)} / {(nwog['nwog_gap_abs'] >= 20).sum()}")

trade_results = []

for _, row in vwap_filtered.iterrows():
    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")
    direction = row["direction"]
    gap_abs = row["nwog_gap_abs"]
    fri_rth_close = row["fri_rth_close"]
    sun_open = row["sun_open"]

    mon_bars = df[df["session_date"] == mon_date]
    if len(mon_bars) == 0:
        continue

    # Entry at 10:00
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

    for stop_pts in [30, 40, 50, 60, 75]:
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
        })

trades_df = pd.DataFrame(trade_results)

print("\n--- VWAP-FILTERED: Entry at 10:00, Target = Full Gap Fill ---")
for stop in [30, 40, 50, 60, 75]:
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
    if len(wins) > 0:
        print(f"    Winners MAE: mean={wins['mae_pts'].mean():.1f}, max={wins['mae_pts'].max():.1f}")

    # Trade-by-trade
    print(f"    Trade details:")
    for _, t in subset.iterrows():
        print(f"      {t['monday_date'].strftime('%Y-%m-%d')} | gap={t['gap']:>+.0f} | {t['trade_dir']} | entry={t['entry_price']:.0f} | tgt={t['target']:.0f} | exit={t['exit_price']:.0f} | {t['exit_reason']:>6s} | pnl=${t['pnl_dollar']:>+,.0f} | MAE={t['mae_pts']:.0f} | MFE={t['mfe_pts']:.0f}")


# ════════════════════════════════════════════════════════════════
# COMBINED BEST: VWAP + ACCEPTANCE
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("COMBINED: VWAP + ACCEPTANCE >= 30%")
print("=" * 70)

combined = nwog[
    (nwog["nwog_gap_abs"] >= 20)
    & (nwog["vwap_supports_fill"] == True)
    & (nwog["acceptance_pct"] >= 30)
].copy()
print(f"\nQualifying NWOGs: {len(combined)} / {(nwog['nwog_gap_abs'] >= 20).sum()}")
print(f"Mon RTH fill: {combined['rth_filled'].mean()*100:.1f}%")
print(f"Week fill: {combined['week_filled'].mean()*100:.1f}%")
print(f"Dates: {', '.join(combined['monday_date'].dt.strftime('%Y-%m-%d').tolist())}")

# Run strategy sim for combined filter
combined_trades = []
for _, row in combined.iterrows():
    mon_date = row["monday_date"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")
    direction = row["direction"]
    gap_abs = row["nwog_gap_abs"]
    fri_rth_close = row["fri_rth_close"]

    mon_bars = df[df["session_date"] == mon_date]
    if len(mon_bars) == 0:
        continue

    entry_bar = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:59:00"))
        & (mon_bars["timestamp"] <= pd.Timestamp(f"{mon_date_str} 10:01:00"))
    ]
    if len(entry_bar) == 0:
        continue

    entry_price = entry_bar.iloc[0]["close"]
    target = fri_rth_close
    stop_pts = 50  # use 50pt stop

    post_bars = mon_bars[
        (mon_bars["timestamp"] > pd.Timestamp(f"{mon_date_str} 10:00:00"))
        & (mon_bars["timestamp"] <= pd.Timestamp(f"{mon_date_str} 16:15:00"))
    ]
    if len(post_bars) == 0:
        continue

    if direction == "UP":
        stop_price = entry_price + stop_pts
        if entry_price <= target:
            continue
        exit_price = None
        exit_reason = None
        mae = 0
        mfe = 0
        for _, bar in post_bars.iterrows():
            mae = max(mae, bar["high"] - entry_price)
            mfe = max(mfe, entry_price - bar["low"])
            if bar["high"] >= stop_price:
                exit_price = stop_price
                exit_reason = "STOP"
                break
            if bar["low"] <= target:
                exit_price = target
                exit_reason = "TARGET"
                break
        if exit_price is None:
            exit_price = post_bars.iloc[-1]["close"]
            exit_reason = "EOD"
        pnl_pts = entry_price - exit_price
    else:
        stop_price = entry_price - stop_pts
        if entry_price >= target:
            continue
        exit_price = None
        exit_reason = None
        mae = 0
        mfe = 0
        for _, bar in post_bars.iterrows():
            mae = max(mae, entry_price - bar["low"])
            mfe = max(mfe, bar["high"] - entry_price)
            if bar["low"] <= stop_price:
                exit_price = stop_price
                exit_reason = "STOP"
                break
            if bar["high"] >= target:
                exit_price = target
                exit_reason = "TARGET"
                break
        if exit_price is None:
            exit_price = post_bars.iloc[-1]["close"]
            exit_reason = "EOD"
        pnl_pts = exit_price - entry_price

    pnl_dollar = pnl_pts * NQ_DOLLAR_PER_POINT
    combined_trades.append({
        "monday_date": mon_date,
        "gap": row["nwog_gap"],
        "gap_abs": gap_abs,
        "direction": direction,
        "entry_price": entry_price,
        "target": target,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "pnl_pts": pnl_pts,
        "pnl_dollar": pnl_dollar,
        "mae_pts": mae,
        "mfe_pts": mfe,
    })

cdf = pd.DataFrame(combined_trades)
if len(cdf) > 0:
    wins = cdf[cdf["pnl_pts"] > 0]
    losses = cdf[cdf["pnl_pts"] <= 0]
    loss_sum = losses["pnl_dollar"].sum()
    pf = abs(wins["pnl_dollar"].sum() / loss_sum) if loss_sum != 0 else 999
    print(f"\nCombined filter, 50pt stop:")
    print(f"  Trades: {len(cdf)}, WR: {len(wins)/len(cdf)*100:.1f}%")
    print(f"  Net PnL: ${cdf['pnl_dollar'].sum():,.0f}")
    print(f"  PF: {pf:.2f}")
    print(f"  Trade details:")
    for _, t in cdf.iterrows():
        print(f"    {t['monday_date'].strftime('%Y-%m-%d')} | gap={t['gap']:>+.0f} | entry={t['entry_price']:.0f} | tgt={t['target']:.0f} | exit={t['exit_price']:.0f} | {t['exit_reason']:>6s} | pnl=${t['pnl_dollar']:>+,.0f}")


# ════════════════════════════════════════════════════════════════
# YEARLY FREQUENCY ESTIMATE
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("FREQUENCY ESTIMATES (annualized from 54 weeks of data)")
print("=" * 70)
total_weeks = 54
big_gaps = (nwog["nwog_gap_abs"] >= 20).sum()
big_vwap = len(vwap_filtered)
big_accept = (nwog[(nwog["nwog_gap_abs"] >= 20) & (nwog.get("acceptance_pct", 0) >= 30)]).shape[0] if "acceptance_pct" in nwog.columns else 0
combined_n = len(combined)

print(f"  All NWOGs >= 20 pts: {big_gaps} ({big_gaps/total_weeks*52:.0f}/year)")
print(f"  VWAP supports fill:  {big_vwap} ({big_vwap/total_weeks*52:.0f}/year)")
print(f"  Acceptance >= 30%:   {big_accept} ({big_accept/total_weeks*52:.0f}/year)")
print(f"  Combined (VWAP+Acc): {combined_n} ({combined_n/total_weeks*52:.0f}/year)")


print("\n--- PART 4 COMPLETE ---")
