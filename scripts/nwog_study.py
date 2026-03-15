"""NWOG (New Week Opening Gap) quantitative study for NQ futures."""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

# ─── Load Data ───────────────────────────────────────────────────────────────
df = pd.read_csv(
    "data/sessions/NQ_Volumetric_1.csv",
    usecols=["timestamp", "open", "high", "low", "close", "volume", "session_date"],
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["session_date"] = pd.to_datetime(df["session_date"])

sessions_meta = df.groupby("session_date").first().reset_index()
sessions_meta["dow"] = sessions_meta["session_date"].dt.dayofweek

fridays = sessions_meta[sessions_meta["dow"] == 4]["session_date"].sort_values().tolist()
mondays = sessions_meta[sessions_meta["dow"] == 0]["session_date"].sort_values().tolist()
tuesdays = sessions_meta[sessions_meta["dow"] == 1]["session_date"].sort_values().tolist()
wednesdays = sessions_meta[sessions_meta["dow"] == 2]["session_date"].sort_values().tolist()
thursdays = sessions_meta[sessions_meta["dow"] == 3]["session_date"].sort_values().tolist()
all_sessions = sessions_meta["session_date"].sort_values().tolist()


def check_fill(bars, target, gap_dir):
    """Check if bars reach the fill target. Returns (filled, fill_time, extreme)."""
    if len(bars) == 0:
        return False, None, None
    if gap_dir == "UP":
        min_low = bars["low"].min()
        if min_low <= target:
            fill_bar = bars[bars["low"] <= target].iloc[0]
            return True, fill_bar["timestamp"], fill_bar["low"]
        return False, None, min_low
    else:
        max_high = bars["high"].max()
        if max_high >= target:
            fill_bar = bars[bars["high"] >= target].iloc[0]
            return True, fill_bar["timestamp"], fill_bar["high"]
        return False, None, max_high


def get_rth_bars(bars, date_str):
    """Get RTH bars (9:30 - 16:15) for a given session."""
    return bars[
        (bars["timestamp"] >= pd.Timestamp(f"{date_str} 09:30:00"))
        & (bars["timestamp"] <= pd.Timestamp(f"{date_str} 16:15:00"))
    ]


def get_or_bars(bars, date_str):
    """Get Opening Range bars (9:30 - 9:45)."""
    return bars[
        (bars["timestamp"] >= pd.Timestamp(f"{date_str} 09:30:00"))
        & (bars["timestamp"] < pd.Timestamp(f"{date_str} 09:45:00"))
    ]


# ─── Build NWOG Dataset ─────────────────────────────────────────────────────
results = []

for mon_date in mondays:
    prev_fridays = [f for f in fridays if f < mon_date]
    if not prev_fridays:
        continue
    fri_date = prev_fridays[-1]
    diff = (mon_date - fri_date).days
    if diff > 4:
        continue

    fri_bars = df[df["session_date"] == fri_date]
    fri_date_str = fri_date.strftime("%Y-%m-%d")
    fri_rth_close_bars = fri_bars[
        fri_bars["timestamp"] <= pd.Timestamp(f"{fri_date_str} 16:15:00")
    ]
    if len(fri_rth_close_bars) == 0:
        continue
    fri_rth_close = fri_rth_close_bars.iloc[-1]["close"]
    fri_settlement = fri_bars.iloc[-1]["close"]

    # Friday RTH range
    fri_rth = get_rth_bars(fri_bars, fri_date_str)
    fri_rth_high = fri_rth["high"].max() if len(fri_rth) > 0 else None
    fri_rth_low = fri_rth["low"].min() if len(fri_rth) > 0 else None
    fri_rth_range = fri_rth_high - fri_rth_low if fri_rth_high and fri_rth_low else None

    mon_bars = df[df["session_date"] == mon_date]
    sun_open = mon_bars.iloc[0]["open"]
    mon_date_str = mon_date.strftime("%Y-%m-%d")

    gap = sun_open - fri_rth_close
    gap_abs = abs(gap)
    direction = "UP" if gap > 0 else "DOWN"

    # ── Monday analysis ──
    mon_globex = mon_bars[
        mon_bars["timestamp"] < pd.Timestamp(f"{mon_date_str} 09:30:00")
    ]
    mon_rth = get_rth_bars(mon_bars, mon_date_str)
    mon_first_hour = mon_bars[
        (mon_bars["timestamp"] >= pd.Timestamp(f"{mon_date_str} 09:30:00"))
        & (mon_bars["timestamp"] < pd.Timestamp(f"{mon_date_str} 10:30:00"))
    ]
    mon_or = get_or_bars(mon_bars, mon_date_str)

    # Monday RTH open
    mon_rth_open = mon_rth.iloc[0]["open"] if len(mon_rth) > 0 else None

    # Monday OR high/low
    mon_or_high = mon_or["high"].max() if len(mon_or) > 0 else None
    mon_or_low = mon_or["low"].min() if len(mon_or) > 0 else None

    # Monday RTH high/low
    mon_rth_high = mon_rth["high"].max() if len(mon_rth) > 0 else None
    mon_rth_low = mon_rth["low"].min() if len(mon_rth) > 0 else None

    # Globex range
    globex_high = mon_globex["high"].max() if len(mon_globex) > 0 else None
    globex_low = mon_globex["low"].min() if len(mon_globex) > 0 else None

    # Fill checks
    globex_filled, globex_fill_time, _ = check_fill(
        mon_globex, fri_rth_close, direction
    )
    first_hour_filled, fh_fill_time, _ = check_fill(
        mon_first_hour, fri_rth_close, direction
    )
    rth_filled, rth_fill_time, _ = check_fill(mon_rth, fri_rth_close, direction)
    mon_filled, mon_fill_time, mon_closest = check_fill(
        mon_bars, fri_rth_close, direction
    )

    # Tuesday fill
    tue_filled = False
    tue_fill_time = None
    next_tues = [t for t in tuesdays if t > mon_date]
    if next_tues and not mon_filled:
        tue_date = next_tues[0]
        if (tue_date - mon_date).days <= 2:
            tue_bars = df[df["session_date"] == tue_date]
            tue_filled, tue_fill_time, _ = check_fill(
                tue_bars, fri_rth_close, direction
            )

    # Full week fill
    week_filled = mon_filled or tue_filled
    if not week_filled:
        for day_list in [wednesdays, thursdays, fridays]:
            next_days = [
                d for d in day_list if d > mon_date and (d - mon_date).days <= 5
            ]
            if next_days:
                day_bars = df[df["session_date"] == next_days[0]]
                filled, _, _ = check_fill(day_bars, fri_rth_close, direction)
                if filled:
                    week_filled = True
                    break

    # Partial fill %
    if not mon_filled and gap_abs > 0:
        if direction == "UP":
            mon_low = mon_bars["low"].min()
            distance_covered = sun_open - mon_low
            partial_fill_pct = min(distance_covered / gap_abs * 100, 100)
        else:
            mon_high = mon_bars["high"].max()
            distance_covered = mon_high - sun_open
            partial_fill_pct = min(distance_covered / gap_abs * 100, 100)
    else:
        partial_fill_pct = 100.0

    # Fill time relative to RTH open (minutes)
    fill_time_minutes = None
    if rth_filled and rth_fill_time:
        rth_open = pd.Timestamp(f"{mon_date_str} 09:30:00")
        fill_time_minutes = (rth_fill_time - rth_open).total_seconds() / 60

    # RTH open relative to gap: does RTH open inside the gap?
    rth_open_in_gap = None
    if mon_rth_open is not None:
        if direction == "UP":
            rth_open_in_gap = fri_rth_close <= mon_rth_open <= sun_open
        else:
            rth_open_in_gap = sun_open <= mon_rth_open <= fri_rth_close

    # Monday OR direction vs gap direction
    or_against_gap = None
    if mon_or_high and mon_or_low and mon_rth_open:
        or_move = mon_or["close"].iloc[-1] - mon_rth_open if len(mon_or) > 0 else 0
        if direction == "UP":
            or_against_gap = or_move < 0  # OR moves down toward fill
        else:
            or_against_gap = or_move > 0  # OR moves up toward fill

    # Did Monday RTH open above/below Friday's RTH close?
    gap_rth = None
    if mon_rth_open is not None:
        gap_rth = mon_rth_open - fri_rth_close

    results.append(
        {
            "monday_date": mon_date,
            "friday_date": fri_date,
            "fri_rth_close": fri_rth_close,
            "fri_settlement": fri_settlement,
            "fri_rth_high": fri_rth_high,
            "fri_rth_low": fri_rth_low,
            "fri_rth_range": fri_rth_range,
            "sun_open": sun_open,
            "mon_rth_open": mon_rth_open,
            "mon_or_high": mon_or_high,
            "mon_or_low": mon_or_low,
            "mon_rth_high": mon_rth_high,
            "mon_rth_low": mon_rth_low,
            "globex_high": globex_high,
            "globex_low": globex_low,
            "nwog_gap": gap,
            "nwog_gap_abs": gap_abs,
            "nwog_pct": gap / fri_rth_close * 100,
            "direction": direction,
            "gap_rth": gap_rth,
            "rth_open_in_gap": rth_open_in_gap,
            "or_against_gap": or_against_gap,
            "globex_filled": globex_filled,
            "first_hour_filled": first_hour_filled,
            "rth_filled": rth_filled,
            "mon_session_filled": mon_filled,
            "tue_filled": tue_filled,
            "week_filled": week_filled,
            "partial_fill_pct": partial_fill_pct,
            "fill_time_minutes": fill_time_minutes,
        }
    )

rdf = pd.DataFrame(results)

# ═════════════════════════════════════════════════════════════════════════════
# REPORTING
# ═════════════════════════════════════════════════════════════════════════════

print("=" * 70)
print("NWOG GAP FILL STUDY - NQ Futures")
print(
    f"Period: {rdf['friday_date'].min().date()} to {rdf['monday_date'].max().date()}"
)
print(f"Total NWOG observations: {len(rdf)}")
print("=" * 70)

# ── 1. GAP DISTRIBUTION ──
print("\n--- 1. GAP SIZE DISTRIBUTION ---")
print(f"Mean gap:   {rdf['nwog_gap'].mean():>8.1f} pts ({rdf['nwog_pct'].mean():.3f}%)")
print(
    f"Median gap: {rdf['nwog_gap'].median():>8.1f} pts ({rdf['nwog_pct'].median():.3f}%)"
)
print(f"Std dev:    {rdf['nwog_gap'].std():>8.1f} pts")
print(f"Min gap:    {rdf['nwog_gap'].min():>8.1f} pts")
print(f"Max gap:    {rdf['nwog_gap'].max():>8.1f} pts")
print(f"Mean abs:   {rdf['nwog_gap_abs'].mean():>8.1f} pts")
print(f"Median abs: {rdf['nwog_gap_abs'].median():>8.1f} pts")
print(f"\nDirection: UP={len(rdf[rdf['direction']=='UP'])}, DOWN={len(rdf[rdf['direction']=='DOWN'])}")

thresholds = [10, 20, 30, 50, 75, 100, 150, 200, 300]
print("\nGap size thresholds:")
for t in thresholds:
    count = (rdf["nwog_gap_abs"] >= t).sum()
    print(f"  >= {t:>3d} pts: {count:>2d} / {len(rdf)} ({count/len(rdf)*100:.1f}%)")

# ── 2. OVERALL FILL RATES ──
print("\n--- 2. OVERALL FILL RATES (all gaps) ---")
print(
    f"Globex fill (before RTH):    {rdf['globex_filled'].sum():>3d} / {len(rdf)} = {rdf['globex_filled'].mean()*100:.1f}%"
)
print(
    f"First hour fill (9:30-10:30):{rdf['first_hour_filled'].sum():>3d} / {len(rdf)} = {rdf['first_hour_filled'].mean()*100:.1f}%"
)
print(
    f"Monday RTH fill:             {rdf['rth_filled'].sum():>3d} / {len(rdf)} = {rdf['rth_filled'].mean()*100:.1f}%"
)
print(
    f"Monday full session fill:    {rdf['mon_session_filled'].sum():>3d} / {len(rdf)} = {rdf['mon_session_filled'].mean()*100:.1f}%"
)
mon_or_tue = rdf["mon_session_filled"] | rdf["tue_filled"]
print(
    f"Mon or Tue fill:             {mon_or_tue.sum():>3d} / {len(rdf)} = {mon_or_tue.mean()*100:.1f}%"
)
print(
    f"Within-week fill:            {rdf['week_filled'].sum():>3d} / {len(rdf)} = {rdf['week_filled'].mean()*100:.1f}%"
)

# ── 3. FILL RATES BY GAP SIZE ──
print("\n--- 3. FILL RATES BY GAP SIZE ---")
bins = [0, 20, 50, 100, 200, 600]
labels = ["0-20", "20-50", "50-100", "100-200", "200+"]
rdf["gap_bucket"] = pd.cut(rdf["nwog_gap_abs"], bins=bins, labels=labels)
print(
    f"{'Bucket':>10s} | {'N':>3s} | {'Globex':>7s} | {'1st Hr':>7s} | {'Mon RTH':>7s} | {'Mon Sess':>8s} | {'Week':>7s} | {'Partial':>7s}"
)
print("-" * 80)
for bucket in labels:
    subset = rdf[rdf["gap_bucket"] == bucket]
    if len(subset) == 0:
        continue
    print(
        f"{bucket:>10s} | {len(subset):>3d} | {subset['globex_filled'].mean()*100:>6.0f}% | {subset['first_hour_filled'].mean()*100:>6.0f}% | {subset['rth_filled'].mean()*100:>6.0f}% | {subset['mon_session_filled'].mean()*100:>7.0f}% | {subset['week_filled'].mean()*100:>6.0f}% | {subset['partial_fill_pct'].mean():>6.0f}%"
    )

# ── 4. FILL RATES BY DIRECTION ──
print("\n--- 4. FILL RATES BY DIRECTION ---")
for d in ["UP", "DOWN"]:
    subset = rdf[rdf["direction"] == d]
    print(
        f"  {d:>5s} gap (n={len(subset)}): Globex={subset['globex_filled'].mean()*100:.1f}%  1stHr={subset['first_hour_filled'].mean()*100:.1f}%  MonRTH={subset['rth_filled'].mean()*100:.1f}%  MonSess={subset['mon_session_filled'].mean()*100:.1f}%  Week={subset['week_filled'].mean()*100:.1f}%"
    )

# Direction x size cross
print("\n  Direction x Size (Monday RTH fill %):")
for d in ["UP", "DOWN"]:
    for bucket in labels:
        subset = rdf[(rdf["direction"] == d) & (rdf["gap_bucket"] == bucket)]
        if len(subset) == 0:
            continue
        print(
            f"    {d} {bucket}: n={len(subset)}, fill={subset['rth_filled'].mean()*100:.0f}%"
        )

# ── 5. FILL TIMING ──
filled_with_time = rdf[rdf["fill_time_minutes"].notna()].copy()
print(f"\n--- 5. FILL TIMING (Monday RTH fills, n={len(filled_with_time)}) ---")
if len(filled_with_time) > 0:
    print(
        f"Mean fill time:   {filled_with_time['fill_time_minutes'].mean():.0f} min after RTH open"
    )
    print(f"Median fill time: {filled_with_time['fill_time_minutes'].median():.0f} min")
    print(f"Std dev:          {filled_with_time['fill_time_minutes'].std():.0f} min")
    time_buckets = [15, 30, 60, 90, 120, 180, 240, 405]
    time_labels = [
        "0:15",
        "0:30",
        "1:00",
        "1:30",
        "2:00",
        "3:00",
        "4:00",
        "EOD",
    ]
    print("\nCumulative fill by time:")
    for tb, tl in zip(time_buckets, time_labels):
        count = (filled_with_time["fill_time_minutes"] <= tb).sum()
        print(
            f"  By {tl}: {count:>2d} / {len(filled_with_time)} = {count/len(filled_with_time)*100:.0f}%"
        )

# ── 6. PARTIAL FILL ANALYSIS ──
unfilled_mon = rdf[~rdf["mon_session_filled"]].copy()
print(f"\n--- 6. PARTIAL FILL (Monday non-fills, n={len(unfilled_mon)}) ---")
if len(unfilled_mon) > 0:
    print(f"Mean partial fill:   {unfilled_mon['partial_fill_pct'].mean():.1f}%")
    print(f"Median partial fill: {unfilled_mon['partial_fill_pct'].median():.1f}%")
    print(
        f">50% filled:  {(unfilled_mon['partial_fill_pct'] > 50).sum()} / {len(unfilled_mon)}"
    )
    print(
        f">75% filled:  {(unfilled_mon['partial_fill_pct'] > 75).sum()} / {len(unfilled_mon)}"
    )
    print(
        f">90% filled:  {(unfilled_mon['partial_fill_pct'] > 90).sum()} / {len(unfilled_mon)}"
    )

# ── 7. GLOBEX BEHAVIOR ──
print("\n--- 7. GLOBEX BEHAVIOR ---")
# How much of the gap does Globex cover?
rdf["globex_range"] = rdf["globex_high"] - rdf["globex_low"]
for _, row in rdf.iterrows():
    if row["direction"] == "UP":
        # Globex moved toward fill if it went below sunday open
        toward = row["sun_open"] - row["globex_low"]
    else:
        toward = row["globex_high"] - row["sun_open"]
rdf["globex_toward_fill"] = rdf.apply(
    lambda r: (r["sun_open"] - r["globex_low"])
    if r["direction"] == "UP"
    else (r["globex_high"] - r["sun_open"]),
    axis=1,
)
rdf["globex_fill_pct"] = np.where(
    rdf["nwog_gap_abs"] > 0,
    rdf["globex_toward_fill"] / rdf["nwog_gap_abs"] * 100,
    0,
)
print(f"Mean Globex coverage toward fill: {rdf['globex_fill_pct'].mean():.1f}%")
print(f"Median Globex coverage:           {rdf['globex_fill_pct'].median():.1f}%")

# ── 8. RTH OPEN POSITION RELATIVE TO GAP ──
print("\n--- 8. RTH OPEN vs GAP ---")
in_gap = rdf[rdf["rth_open_in_gap"] == True]
out_gap = rdf[rdf["rth_open_in_gap"] == False]
print(f"RTH opens inside gap:  {len(in_gap)} / {len(rdf)} ({len(in_gap)/len(rdf)*100:.1f}%)")
print(f"RTH opens outside gap: {len(out_gap)} / {len(rdf)} ({len(out_gap)/len(rdf)*100:.1f}%)")
if len(in_gap) > 0:
    print(
        f"  Inside gap -> Mon RTH fill: {in_gap['rth_filled'].mean()*100:.1f}%, Week fill: {in_gap['week_filled'].mean()*100:.1f}%"
    )
if len(out_gap) > 0:
    print(
        f"  Outside gap -> Mon RTH fill: {out_gap['rth_filled'].mean()*100:.1f}%, Week fill: {out_gap['week_filled'].mean()*100:.1f}%"
    )

# ── 9. OR DIRECTION vs GAP ──
print("\n--- 9. OPENING RANGE DIRECTION vs GAP ---")
or_for = rdf[rdf["or_against_gap"] == True]  # OR moves toward fill
or_against = rdf[rdf["or_against_gap"] == False]  # OR moves away from fill
print(f"OR moves toward gap fill:  {len(or_for)} / {len(rdf)}")
print(f"OR moves away from fill:   {len(or_against)} / {len(rdf)}")
if len(or_for) > 0:
    print(
        f"  Toward fill → Mon RTH fill: {or_for['rth_filled'].mean()*100:.1f}%, Week: {or_for['week_filled'].mean()*100:.1f}%"
    )
if len(or_against) > 0:
    print(
        f"  Away from fill → Mon RTH fill: {or_against['rth_filled'].mean()*100:.1f}%, Week: {or_against['week_filled'].mean()*100:.1f}%"
    )

# ── 10. GAP vs FRIDAY RANGE ──
print("\n--- 10. GAP RELATIVE TO FRIDAY RANGE ---")
rdf["gap_vs_fri_range"] = np.where(
    rdf["fri_rth_range"] > 0,
    rdf["nwog_gap_abs"] / rdf["fri_rth_range"] * 100,
    0,
)
print(f"Mean gap/Fri range:   {rdf['gap_vs_fri_range'].mean():.1f}%")
print(f"Median gap/Fri range: {rdf['gap_vs_fri_range'].median():.1f}%")

# Quartile analysis
q_labels = ["Q1 (small relative)", "Q2", "Q3", "Q4 (large relative)"]
rdf["gap_rel_q"] = pd.qcut(
    rdf["gap_vs_fri_range"], q=4, labels=q_labels, duplicates="drop"
)
for q in q_labels:
    subset = rdf[rdf["gap_rel_q"] == q]
    if len(subset) > 0:
        print(
            f"  {q}: n={len(subset)}, Mon RTH fill={subset['rth_filled'].mean()*100:.0f}%, Week={subset['week_filled'].mean()*100:.0f}%"
        )

# ── 11. DETAILED GAP TABLE ──
print("\n--- 11. DETAILED NWOG TABLE (gaps >= 20 pts) ---")
big = rdf[rdf["nwog_gap_abs"] >= 20].copy()
big = big.sort_values("monday_date")
print(
    f"{'Monday':>12s} | {'Gap':>8s} | {'Dir':>4s} | {'Glbx':>5s} | {'1stHr':>5s} | {'MonRTH':>6s} | {'MonSes':>6s} | {'Week':>5s} | {'FillMin':>7s} | {'Partial':>7s}"
)
print("-" * 100)
for _, row in big.iterrows():
    fill_min_str = f"{row['fill_time_minutes']:.0f}" if pd.notna(row["fill_time_minutes"]) else "-"
    print(
        f"{row['monday_date'].strftime('%Y-%m-%d'):>12s} | {row['nwog_gap']:>+8.1f} | {row['direction']:>4s} | {'Y' if row['globex_filled'] else 'N':>5s} | {'Y' if row['first_hour_filled'] else 'N':>5s} | {'Y' if row['rth_filled'] else 'N':>6s} | {'Y' if row['mon_session_filled'] else 'N':>6s} | {'Y' if row['week_filled'] else 'N':>5s} | {fill_min_str:>7s} | {row['partial_fill_pct']:>6.0f}%"
    )

# ── 12. STRATEGY OVERLAP (check DuckDB for existing strategy signals on Mondays) ──
print("\n--- 12. STRATEGY OVERLAP (DuckDB) ---")
try:
    sys.path.insert(0, "packages/rockit-core/src")
    from rockit_core.research.db import connect, query_df

    conn = connect()

    # Get Monday trades
    monday_dates = [m.strftime("%Y-%m-%d") for m in mondays]
    monday_trades = query_df(
        conn,
        """
        SELECT session_date, strategy_name, direction, entry_time, net_pnl, outcome
        FROM trades
        WHERE session_date IN (SELECT UNNEST(?::VARCHAR[]))
        ORDER BY session_date, entry_time
        """,
        [monday_dates],
    )

    if len(monday_trades) > 0:
        print(f"Monday trades in DuckDB: {len(monday_trades)}")
        print("\nTrades per strategy on Mondays:")
        strat_counts = monday_trades.groupby("strategy_name").agg(
            trades=("net_pnl", "count"),
            wins=("outcome", lambda x: (x == "WIN").sum()),
            net_pnl=("net_pnl", "sum"),
        )
        strat_counts["wr"] = strat_counts["wins"] / strat_counts["trades"] * 100
        print(strat_counts.to_string())

        # Check overlap: Monday trades that occur on NWOG fill days
        nwog_fill_mondays = set(
            rdf[rdf["mon_session_filled"]]["monday_date"]
            .dt.strftime("%Y-%m-%d")
            .tolist()
        )
        monday_trades["on_fill_day"] = monday_trades["session_date"].isin(
            nwog_fill_mondays
        )
        print(f"\nTrades on NWOG fill days vs non-fill days:")
        for fill_flag in [True, False]:
            subset = monday_trades[monday_trades["on_fill_day"] == fill_flag]
            if len(subset) > 0:
                wr = (subset["outcome"] == "WIN").mean() * 100
                print(
                    f"  {'Fill day' if fill_flag else 'Non-fill':>10s}: {len(subset)} trades, WR={wr:.1f}%, PnL=${subset['net_pnl'].sum():,.0f}"
                )
    else:
        print("No Monday trades found in DuckDB")

    # Also check session context for day types
    session_ctx = query_df(
        conn,
        """
        SELECT session_date, day_type, bias, composite_regime, vix_regime, ib_range, atr14_daily
        FROM session_context
        WHERE session_date IN (SELECT UNNEST(?::VARCHAR[]))
        """,
        [monday_dates],
    )

    if len(session_ctx) > 0:
        print(f"\nMonday session context available: {len(session_ctx)} sessions")
        # Merge with NWOG data
        rdf_str = rdf.copy()
        rdf_str["monday_str"] = rdf_str["monday_date"].dt.strftime("%Y-%m-%d")
        merged = rdf_str.merge(
            session_ctx, left_on="monday_str", right_on="session_date", how="left"
        )

        # Day type vs fill rate
        print("\nMonday day type vs NWOG fill:")
        for dt in merged["day_type"].dropna().unique():
            subset = merged[merged["day_type"] == dt]
            if len(subset) > 0:
                print(
                    f"  {dt:>20s}: n={len(subset)}, Mon RTH fill={subset['rth_filled'].mean()*100:.0f}%, Week={subset['week_filled'].mean()*100:.0f}%"
                )

        # Regime vs fill rate
        print("\nComposite regime vs NWOG fill:")
        for reg in merged["composite_regime"].dropna().unique():
            subset = merged[merged["composite_regime"] == reg]
            if len(subset) > 0:
                print(
                    f"  {reg:>25s}: n={len(subset)}, Mon RTH fill={subset['rth_filled'].mean()*100:.0f}%, Week={subset['week_filled'].mean()*100:.0f}%"
                )

    conn.close()
except Exception as e:
    print(f"DuckDB analysis failed: {e}")
    import traceback
    traceback.print_exc()

# ── 13. SAVE RAW DATA ──
output = rdf.copy()
output["monday_date"] = output["monday_date"].dt.strftime("%Y-%m-%d")
output["friday_date"] = output["friday_date"].dt.strftime("%Y-%m-%d")
output.to_csv("data/nwog_study_raw.csv", index=False)
print(f"\nRaw data saved to data/nwog_study_raw.csv")

# ── 14. PROPOSED STRATEGY STATS ──
print("\n" + "=" * 70)
print("PROPOSED NWOG STRATEGY BACKTEST ESTIMATES")
print("=" * 70)

# Focus on gaps >= 30 pts (significant enough to trade)
tradeable = rdf[rdf["nwog_gap_abs"] >= 30].copy()
print(f"\nTradeable NWOGs (>= 30 pts): {len(tradeable)} / {len(rdf)}")
print(f"  Mon RTH fill rate: {tradeable['rth_filled'].mean()*100:.1f}%")
print(f"  Mon session fill:  {tradeable['mon_session_filled'].mean()*100:.1f}%")
print(f"  Week fill:         {tradeable['week_filled'].mean()*100:.1f}%")

# Estimate P&L if we trade toward the gap fill
# Entry: Monday RTH open, Stop: 1 ATR beyond gap edge, Target: gap fill
# For NQ, 1 point = $20/contract
# Use conservative 1R stop
for entry_desc, entry_col in [("OR close (9:45)", None)]:
    print(f"\n  If entering at {entry_desc}:")
    wins = tradeable[tradeable["rth_filled"]].copy()
    losses = tradeable[~tradeable["rth_filled"]].copy()

    # Average gap size
    avg_gap = tradeable["nwog_gap_abs"].mean()
    print(f"    Avg gap size: {avg_gap:.0f} pts")
    print(f"    Win rate (Mon RTH): {len(wins)}/{len(tradeable)} = {len(wins)/len(tradeable)*100:.1f}%")

    # Average reward on wins (gap pts)
    if len(wins) > 0:
        avg_reward = wins["nwog_gap_abs"].mean()
        print(f"    Avg reward (pts): {avg_reward:.0f}")

    # Estimated per-trade PnL (assume 50% of gap as avg reward, 1:1 R:R stop)
    print(f"    Frequency: ~{len(tradeable)/54*52:.0f} trades/year (52 weeks)")

print("\n--- STUDY COMPLETE ---")
