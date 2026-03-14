"""Generate comprehensive backtest report from DuckDB data."""
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else None
DB_PATH = "data/research.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

# ── Step 1: Identify run ──
if not RUN_ID:
    rows = conn.execute("""
        SELECT run_id, instrument, total_trades, win_rate, profit_factor, net_pnl, notes, timestamp
        FROM backtest_runs ORDER BY timestamp DESC LIMIT 5
    """).fetchall()
    print("Recent runs:")
    for r in rows:
        print(f"  {r[0]} | {r[2]} trades | {r[3]}% WR | PF {r[4]} | ${r[5]:,.2f} | {r[6]}")
    RUN_ID = rows[0][0]
    print(f"\nUsing latest: {RUN_ID}")

# ── Step 2: Run summary ──
run = conn.execute("""
    SELECT run_id, instrument, sessions, total_trades, win_rate, profit_factor, net_pnl,
           max_drawdown, avg_win, avg_loss, expectancy, by_strategy, config, notes,
           git_branch, git_commit, timestamp
    FROM backtest_runs WHERE run_id = ?
""", [RUN_ID]).fetchone()

if not run:
    print(f"ERROR: Run {RUN_ID} not found")
    sys.exit(1)

cols = ["run_id", "instrument", "sessions", "total_trades", "win_rate", "profit_factor",
        "net_pnl", "max_drawdown", "avg_win", "avg_loss", "expectancy", "by_strategy",
        "config", "notes", "git_branch", "git_commit", "timestamp"]
run_dict = dict(zip(cols, run))
by_strategy = json.loads(run_dict["by_strategy"]) if run_dict["by_strategy"] else {}

print(f"Run: {RUN_ID}")
print(f"  {run_dict['total_trades']} trades, {run_dict['win_rate']}% WR, PF {run_dict['profit_factor']}, ${run_dict['net_pnl']:,.2f}")

# ── Step 3: All trades ──
trades = conn.execute("""
    SELECT t.strategy_name, t.direction, t.session_date, t.entry_time, t.exit_time,
           t.entry_price, t.exit_price, t.net_pnl, t.outcome, t.exit_reason,
           t.mae_price, t.mfe_price, t.bars_held,
           sc.day_type, sc.bias
    FROM trades t
    LEFT JOIN session_context sc ON t.session_date = sc.session_date
    WHERE t.run_id = ?
    ORDER BY t.net_pnl DESC
""", [RUN_ID]).fetchall()
trade_cols = ["strategy_name", "direction", "session_date", "entry_time", "exit_time",
              "entry_price", "exit_price", "net_pnl", "outcome", "exit_reason",
              "mae_price", "mfe_price", "bars_held", "day_type", "bias"]
trade_dicts = [dict(zip(trade_cols, t)) for t in trades]

avg_win_val = run_dict["avg_win"] or 500
avg_loss_val = run_dict["avg_loss"] or -500

# ── Step 4: Classify trades ──
classifications = {"strong_win": [], "lucky_win": [], "barely_profitable": [],
                   "clean_loss": [], "avoidable_loss": []}

for t in trade_dicts:
    pnl = t["net_pnl"] or 0
    exit_r = t["exit_reason"] or ""
    if pnl > 0:
        if exit_r == "TARGET" and pnl >= avg_win_val * 0.8:
            classifications["strong_win"].append(t)
        elif exit_r in ("EOD", "DAILY_LOSS", "VWAP_BREACH"):
            classifications["lucky_win"].append(t)
        elif pnl < avg_win_val * 0.5:
            classifications["barely_profitable"].append(t)
        else:
            classifications["strong_win"].append(t)
    else:
        if exit_r == "STOP":
            classifications["clean_loss"].append(t)
        else:
            classifications["avoidable_loss"].append(t)

# ── Step 5: Agent decisions ──
decisions = conn.execute("""
    SELECT decision, confidence, strategy_name, signal_direction, session_date,
           reasoning, bull_score, bear_score, conviction,
           advocate_thesis, advocate_direction, advocate_confidence,
           skeptic_thesis, skeptic_direction, skeptic_confidence,
           actual_outcome, actual_pnl
    FROM agent_decisions
    WHERE run_id = ?
    ORDER BY session_date
""", [RUN_ID]).fetchall()
dec_cols = ["decision", "confidence", "strategy_name", "signal_direction", "session_date",
            "reasoning", "bull_score", "bear_score", "conviction",
            "advocate_thesis", "advocate_direction", "advocate_confidence",
            "skeptic_thesis", "skeptic_direction", "skeptic_confidence",
            "actual_outcome", "actual_pnl"]
dec_dicts = [dict(zip(dec_cols, d)) for d in decisions]

take_decisions = [d for d in dec_dicts if d["decision"] == "TAKE"]
skip_decisions = [d for d in dec_dicts if d["decision"] == "SKIP"]
reduce_decisions = [d for d in dec_dicts if d["decision"] == "REDUCE_SIZE"]

# ── Step 6: Filtered signal analysis ──
# Find baseline run
baseline_row = conn.execute("""
    SELECT run_id FROM backtest_runs
    WHERE notes LIKE '%No filters%' OR notes LIKE '%baseline%'
    ORDER BY timestamp DESC LIMIT 1
""").fetchone()

filtered_analysis = None
if baseline_row:
    baseline_id = baseline_row[0]
    filtered_trades = conn.execute("""
        SELECT t.strategy_name, t.direction, t.session_date, t.net_pnl, t.outcome
        FROM trades t
        WHERE t.run_id = ?
        AND NOT EXISTS (
            SELECT 1 FROM trades t2
            WHERE t2.run_id = ?
            AND t2.session_date = t.session_date
            AND t2.strategy_name = t.strategy_name
        )
    """, [baseline_id, RUN_ID]).fetchall()

    filtered_wins = [f for f in filtered_trades if f[4] == "WIN"]
    filtered_losses = [f for f in filtered_trades if f[4] != "WIN"]
    filtered_pnl = sum(f[3] for f in filtered_trades if f[3])
    filtered_win_pnl = sum(f[3] for f in filtered_wins if f[3])
    filtered_loss_pnl = sum(f[3] for f in filtered_losses if f[3])

    # By strategy
    filtered_by_strat = {}
    for f in filtered_trades:
        s = f[0]
        if s not in filtered_by_strat:
            filtered_by_strat[s] = {"total": 0, "wins": 0, "losses": 0, "pnl": 0}
        filtered_by_strat[s]["total"] += 1
        if f[4] == "WIN":
            filtered_by_strat[s]["wins"] += 1
        else:
            filtered_by_strat[s]["losses"] += 1
        filtered_by_strat[s]["pnl"] += f[3] or 0

    filtered_analysis = {
        "baseline_id": baseline_id,
        "total": len(filtered_trades),
        "wins": len(filtered_wins),
        "losses": len(filtered_losses),
        "net_pnl": filtered_pnl,
        "win_pnl": filtered_win_pnl,
        "loss_pnl": filtered_loss_pnl,
        "by_strategy": filtered_by_strat,
    }

# ── Step 7: Deterministic context for top winners/losers ──
def get_det_context(session_date, entry_time):
    """Get deterministic tape context near entry time."""
    try:
        row = conn.execute("""
            SELECT cri_status, tpo_shape, day_type, dpoc_migration, trend_strength,
                   extension_multiple, bias
            FROM deterministic_tape
            WHERE session_date = ?
            ORDER BY ABS(EXTRACT(EPOCH FROM (snapshot_time::TIMESTAMP - ?::TIMESTAMP)))
            LIMIT 1
        """, [session_date, entry_time]).fetchone()
        if row:
            return {"cri": row[0], "tpo": row[1], "day_type": row[2], "dpoc": row[3],
                    "trend": row[4], "extension": row[5], "bias": row[6]}
    except Exception:
        pass
    return {}

top_winners = sorted(trade_dicts, key=lambda t: t["net_pnl"] or 0, reverse=True)[:5]
top_losers = sorted(trade_dicts, key=lambda t: t["net_pnl"] or 0)[:5]

for t in top_winners + top_losers:
    t["det_context"] = get_det_context(t["session_date"], t["entry_time"])

# ── Step 8: Strategy scorecards ──
strat_details = {}
for s_name in set(t["strategy_name"] for t in trade_dicts):
    s_trades = [t for t in trade_dicts if t["strategy_name"] == s_name]
    s_wins = [t for t in s_trades if (t["net_pnl"] or 0) > 0]
    s_losses = [t for t in s_trades if (t["net_pnl"] or 0) <= 0]
    s_pnl = sum(t["net_pnl"] or 0 for t in s_trades)
    s_wr = len(s_wins) / len(s_trades) * 100 if s_trades else 0
    s_gp = sum(t["net_pnl"] for t in s_wins if t["net_pnl"])
    s_gl = abs(sum(t["net_pnl"] for t in s_losses if t["net_pnl"]))
    s_pf = s_gp / s_gl if s_gl > 0 else float("inf")
    s_avg_win = s_gp / len(s_wins) if s_wins else 0
    s_avg_loss = -s_gl / len(s_losses) if s_losses else 0
    s_expectancy = (s_wr / 100 * s_avg_win) - ((1 - s_wr / 100) * abs(s_avg_loss))

    # By direction
    dir_stats = {}
    for d in ["LONG", "SHORT"]:
        d_trades = [t for t in s_trades if t["direction"] == d]
        d_wins = [t for t in d_trades if (t["net_pnl"] or 0) > 0]
        if d_trades:
            dir_stats[d] = {"trades": len(d_trades), "wr": round(len(d_wins)/len(d_trades)*100, 1),
                           "pnl": round(sum(t["net_pnl"] or 0 for t in d_trades), 2)}

    # By day type
    dt_stats = {}
    for t in s_trades:
        dt = t["day_type"] or "unknown"
        if dt not in dt_stats:
            dt_stats[dt] = {"trades": 0, "wins": 0, "pnl": 0}
        dt_stats[dt]["trades"] += 1
        if (t["net_pnl"] or 0) > 0:
            dt_stats[dt]["wins"] += 1
        dt_stats[dt]["pnl"] += t["net_pnl"] or 0

    # Agent decisions for this strategy
    s_decisions = [d for d in dec_dicts if d["strategy_name"] == s_name]
    s_takes = [d for d in s_decisions if d["decision"] == "TAKE"]
    s_skips = [d for d in s_decisions if d["decision"] == "SKIP"]

    strat_details[s_name] = {
        "trades": len(s_trades), "wr": round(s_wr, 1), "pf": round(s_pf, 2),
        "pnl": round(s_pnl, 2), "avg_win": round(s_avg_win, 2), "avg_loss": round(s_avg_loss, 2),
        "expectancy": round(s_expectancy, 2), "dir_stats": dir_stats, "dt_stats": dt_stats,
        "best": max(s_trades, key=lambda t: t["net_pnl"] or 0),
        "worst": min(s_trades, key=lambda t: t["net_pnl"] or 0),
        "agent_takes": len(s_takes), "agent_skips": len(s_skips),
    }

# ── Step 9: Pattern discovery ──
# Time of day
time_stats = conn.execute("""
    SELECT EXTRACT(HOUR FROM entry_time::TIMESTAMP) as hour, COUNT(*) as n,
           ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr,
           ROUND(SUM(net_pnl), 2) as pnl
    FROM trades WHERE run_id = ? GROUP BY 1 ORDER BY 1
""", [RUN_ID]).fetchall()

# Day type performance
daytype_stats = conn.execute("""
    SELECT sc.day_type, COUNT(*) as n,
           ROUND(100.0 * SUM(CASE WHEN t.outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr,
           ROUND(SUM(t.net_pnl), 2) as pnl
    FROM trades t
    JOIN session_context sc ON t.session_date = sc.session_date
    WHERE t.run_id = ? GROUP BY 1 ORDER BY 4 DESC
""", [RUN_ID]).fetchall()

# Exit reason breakdown
exit_stats = conn.execute("""
    SELECT exit_reason, COUNT(*) as n,
           ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr,
           ROUND(SUM(net_pnl), 2) as pnl
    FROM trades WHERE run_id = ? GROUP BY 1 ORDER BY 2 DESC
""", [RUN_ID]).fetchall()

# Win/loss streaks
outcomes = conn.execute("""
    SELECT outcome FROM trades WHERE run_id = ? ORDER BY session_date, entry_time
""", [RUN_ID]).fetchall()
outcomes_list = [o[0] for o in outcomes]
max_win_streak = max_loss_streak = current_streak = 0
current_type = None
for o in outcomes_list:
    if o == current_type:
        current_streak += 1
    else:
        current_type = o
        current_streak = 1
    if o == "WIN":
        max_win_streak = max(max_win_streak, current_streak)
    else:
        max_loss_streak = max(max_loss_streak, current_streak)

# MAE/MFE for winners vs losers
mae_mfe = conn.execute("""
    SELECT outcome,
           ROUND(AVG(ABS(entry_price - mae_price)), 1) as avg_mae,
           ROUND(AVG(ABS(mfe_price - entry_price)), 1) as avg_mfe,
           ROUND(AVG(bars_held), 0) as avg_bars
    FROM trades WHERE run_id = ? AND mae_price IS NOT NULL
    GROUP BY 1
""", [RUN_ID]).fetchall()

conn.close()

# ── Step 10: Generate report ──
study_targets = {"Opening Range Rev": 64.4, "OR Acceptance": 59.9,
                 "20P IB Extension": 45.5, "B-Day": 82.0, "80P Rule": 42.3}

report = []
report.append(f"# Backtest Report: {RUN_ID}")
report.append(f"> Date: {run_dict['timestamp']} | Instrument: {run_dict['instrument']} | "
              f"Sessions: {run_dict['sessions']} | Branch: {run_dict.get('git_branch', 'N/A')}")
report.append(f"> Notes: {run_dict['notes']}")
report.append("")

# Executive Summary
total_wins = len([t for t in trade_dicts if (t["net_pnl"] or 0) > 0])
total_losses = len(trade_dicts) - total_wins
report.append("## Executive Summary")
report.append(f"- **{run_dict['total_trades']} trades** across {run_dict['sessions']} sessions: "
              f"**{run_dict['win_rate']}% WR**, PF **{run_dict['profit_factor']}**, "
              f"net **${run_dict['net_pnl']:,.2f}**")
best_strat = max(strat_details.items(), key=lambda x: x[1]["pnl"])
report.append(f"- Top performer: **{best_strat[0]}** — {best_strat[1]['trades']} trades, "
              f"{best_strat[1]['wr']}% WR, ${best_strat[1]['pnl']:,.2f}")
if filtered_analysis:
    report.append(f"- Filters removed {filtered_analysis['total']} trades "
                  f"({filtered_analysis['wins']}W / {filtered_analysis['losses']}L, "
                  f"net ${filtered_analysis['net_pnl']:,.2f}) — "
                  f"{'filters helped' if filtered_analysis['net_pnl'] > 0 else 'filters may be too aggressive'}")
report.append("")

# Portfolio Metrics
report.append("## Portfolio Metrics")
report.append("")
report.append("| Metric | Value |")
report.append("|--------|-------|")
report.append(f"| Total Trades | {run_dict['total_trades']} ({total_wins}W / {total_losses}L) |")
report.append(f"| Win Rate | {run_dict['win_rate']}% |")
report.append(f"| Profit Factor | {run_dict['profit_factor']} |")
report.append(f"| Net PnL | ${run_dict['net_pnl']:,.2f} |")
report.append(f"| Expectancy | ${run_dict['expectancy']:,.2f} / trade |")
report.append(f"| Avg Win | ${run_dict['avg_win']:,.2f} |")
report.append(f"| Avg Loss | ${run_dict['avg_loss']:,.2f} |")
report.append(f"| Max Drawdown | ${run_dict['max_drawdown']:,.2f} |")
report.append(f"| Max Win Streak | {max_win_streak} |")
report.append(f"| Max Loss Streak | {max_loss_streak} |")
report.append("")

# Strategy Scorecards
report.append("## Strategy Scorecards")
report.append("")
for s_name in sorted(strat_details.keys(), key=lambda k: strat_details[k]["pnl"], reverse=True):
    s = strat_details[s_name]
    target = study_targets.get(s_name, "N/A")
    status = ""
    if isinstance(target, (int, float)):
        status = " ✓ EXCEEDS" if s["wr"] >= target else " ✗ BELOW"

    report.append(f"### {s_name}")
    report.append(f"| Metric | Value | Study Target |")
    report.append(f"|--------|-------|-------------|")
    report.append(f"| Trades | {s['trades']} | — |")
    report.append(f"| Win Rate | {s['wr']}% | {target}%{status} |")
    report.append(f"| Profit Factor | {s['pf']} | — |")
    report.append(f"| Net PnL | ${s['pnl']:,.2f} | — |")
    report.append(f"| Avg Win | ${s['avg_win']:,.2f} | — |")
    report.append(f"| Avg Loss | ${s['avg_loss']:,.2f} | — |")
    report.append(f"| Expectancy | ${s['expectancy']:,.2f} | — |")
    if s.get("agent_takes") or s.get("agent_skips"):
        report.append(f"| Agent TAKE | {s['agent_takes']} | — |")
        report.append(f"| Agent SKIP | {s['agent_skips']} | — |")
    report.append("")

    # Direction breakdown
    if s["dir_stats"]:
        report.append(f"**By Direction:**")
        report.append(f"| Direction | Trades | WR | PnL |")
        report.append(f"|-----------|--------|-----|-----|")
        for d, ds in s["dir_stats"].items():
            report.append(f"| {d} | {ds['trades']} | {ds['wr']}% | ${ds['pnl']:,.2f} |")
        report.append("")

    # Day type breakdown
    if s["dt_stats"]:
        report.append(f"**By Day Type:**")
        report.append(f"| Day Type | Trades | WR | PnL |")
        report.append(f"|----------|--------|-----|-----|")
        for dt, ds in sorted(s["dt_stats"].items(), key=lambda x: x[1]["pnl"], reverse=True):
            wr = round(ds["wins"] / ds["trades"] * 100, 1) if ds["trades"] else 0
            report.append(f"| {dt} | {ds['trades']} | {wr}% | ${ds['pnl']:,.2f} |")
        report.append("")

# Trade Classification
report.append("## Trade Classification")
report.append("")
report.append("| Category | Count | Net PnL | Avg PnL |")
report.append("|----------|-------|---------|---------|")
for cat, label in [("strong_win", "Strong Wins"), ("lucky_win", "Lucky Wins"),
                   ("barely_profitable", "Barely Profitable"),
                   ("clean_loss", "Clean Losses"), ("avoidable_loss", "Avoidable Losses")]:
    trades_in_cat = classifications[cat]
    cat_pnl = sum(t["net_pnl"] or 0 for t in trades_in_cat)
    cat_avg = cat_pnl / len(trades_in_cat) if trades_in_cat else 0
    report.append(f"| {label} | {len(trades_in_cat)} | ${cat_pnl:,.2f} | ${cat_avg:,.2f} |")
report.append("")

# Agent Decision Analysis
if dec_dicts:
    report.append("## Agent Decision Analysis")
    report.append("")
    report.append(f"- **Total decisions**: {len(dec_dicts)}")
    report.append(f"- **TAKE**: {len(take_decisions)} "
                  f"({sum(1 for d in take_decisions if d.get('actual_outcome')=='WIN')} won)")
    report.append(f"- **SKIP**: {len(skip_decisions)}")
    report.append(f"- **REDUCE_SIZE**: {len(reduce_decisions)}")
    report.append("")

    # SKIP analysis
    if skip_decisions:
        report.append("### Skipped Signals")
        report.append(f"| Strategy | Direction | Date | Reasoning (excerpt) |")
        report.append(f"|----------|-----------|------|---------------------|")
        for d in skip_decisions[:15]:
            reasoning = (d.get("reasoning") or "")[:80]
            report.append(f"| {d['strategy_name']} | {d['signal_direction']} | "
                         f"{d['session_date']} | {reasoning} |")
        if len(skip_decisions) > 15:
            report.append(f"| ... | ... | ... | ({len(skip_decisions)-15} more) |")
        report.append("")

    # Debate context (if available — new columns)
    debates_with_thesis = [d for d in dec_dicts if d.get("advocate_thesis")]
    if debates_with_thesis:
        report.append("### Debate Reasoning Samples")
        report.append("")
        for d in debates_with_thesis[:5]:
            report.append(f"**{d['session_date']} | {d['strategy_name']} {d['signal_direction']} → {d['decision']}**")
            if d.get("advocate_thesis"):
                report.append(f"- Advocate ({d['advocate_direction']}, {d['advocate_confidence']:.0%}): {d['advocate_thesis'][:120]}")
            if d.get("skeptic_thesis"):
                report.append(f"- Skeptic ({d['skeptic_direction']}, {d['skeptic_confidence']:.0%}): {d['skeptic_thesis'][:120]}")
            report.append("")

# Filtered Signal Analysis
if filtered_analysis:
    report.append("## Filtered Signal Analysis")
    report.append(f"> Compared to baseline run: `{filtered_analysis['baseline_id']}`")
    report.append("")
    report.append(f"- **Trades filtered out**: {filtered_analysis['total']}")
    report.append(f"- **Winners removed**: {filtered_analysis['wins']} (${filtered_analysis['win_pnl']:,.2f})")
    report.append(f"- **Losers removed**: {filtered_analysis['losses']} (${filtered_analysis['loss_pnl']:,.2f})")
    report.append(f"- **Net PnL of filtered trades**: ${filtered_analysis['net_pnl']:,.2f}")
    verdict = "Filters are net positive" if filtered_analysis['net_pnl'] > 0 else "Filters are removing more winners than losers"
    report.append(f"- **Verdict**: {verdict}")
    report.append("")

    report.append("**By Strategy:**")
    report.append("| Strategy | Filtered | Wins | Losses | Net PnL |")
    report.append("|----------|----------|------|--------|---------|")
    for s, fs in sorted(filtered_analysis["by_strategy"].items(), key=lambda x: x[1]["pnl"]):
        report.append(f"| {s} | {fs['total']} | {fs['wins']} | {fs['losses']} | ${fs['pnl']:,.2f} |")
    report.append("")

# Top 5 Winners
report.append("## Top 5 Winners")
report.append("")
for i, t in enumerate(top_winners):
    ctx = t.get("det_context", {})
    report.append(f"### #{i+1}: {t['strategy_name']} {t['direction']} — ${t['net_pnl']:,.2f}")
    report.append(f"- **Date**: {t['session_date']} | Entry: {t['entry_time']} | Exit: {t['exit_time']}")
    report.append(f"- **Prices**: Entry ${t['entry_price']:.2f} → Exit ${t['exit_price']:.2f}")
    report.append(f"- **Exit reason**: {t['exit_reason']} | R-multiple: {t.get('r_multiple', 'N/A')}")
    report.append(f"- **Day type**: {t.get('day_type', 'N/A')} | Bias: {t.get('bias', 'N/A')}")
    if ctx:
        report.append(f"- **Deterministic**: CRI={ctx.get('cri','?')}, TPO={ctx.get('tpo','?')}, "
                      f"DPOC={ctx.get('dpoc','?')}, Trend={ctx.get('trend','?')}")
    report.append("")

# Top 5 Losers
report.append("## Top 5 Losers")
report.append("")
for i, t in enumerate(top_losers):
    ctx = t.get("det_context", {})
    report.append(f"### #{i+1}: {t['strategy_name']} {t['direction']} — ${t['net_pnl']:,.2f}")
    report.append(f"- **Date**: {t['session_date']} | Entry: {t['entry_time']} | Exit: {t['exit_time']}")
    report.append(f"- **Prices**: Entry ${t['entry_price']:.2f} → Exit ${t['exit_price']:.2f}")
    report.append(f"- **Exit reason**: {t['exit_reason']} | R-multiple: {t.get('r_multiple', 'N/A')}")
    report.append(f"- **Day type**: {t.get('day_type', 'N/A')} | Bias: {t.get('bias', 'N/A')}")
    if ctx:
        report.append(f"- **Deterministic**: CRI={ctx.get('cri','?')}, TPO={ctx.get('tpo','?')}, "
                      f"DPOC={ctx.get('dpoc','?')}, Trend={ctx.get('trend','?')}")
    report.append("")

# Pattern Discoveries
report.append("## Pattern Discoveries")
report.append("")

# Time of day
report.append("### Time of Day")
report.append("| Hour | Trades | WR | PnL |")
report.append("|------|--------|-----|-----|")
for h in time_stats:
    report.append(f"| {int(h[0]):02d}:00 | {h[1]} | {h[2]}% | ${h[3]:,.2f} |")
report.append("")

# Day type
report.append("### Day Type Performance")
report.append("| Day Type | Trades | WR | PnL |")
report.append("|----------|--------|-----|-----|")
for d in daytype_stats:
    report.append(f"| {d[0]} | {d[1]} | {d[2]}% | ${d[3]:,.2f} |")
report.append("")

# Exit reasons
report.append("### Exit Reason Distribution")
report.append("| Exit Reason | Count | WR | PnL |")
report.append("|-------------|-------|-----|-----|")
for e in exit_stats:
    report.append(f"| {e[0]} | {e[1]} | {e[2]}% | ${e[3]:,.2f} |")
report.append("")

# MAE/MFE
report.append("### MAE/MFE by Outcome")
report.append("| Outcome | Avg MAE (pts) | Avg MFE (pts) | Avg Bars |")
report.append("|---------|--------------|--------------|----------|")
for m in mae_mfe:
    report.append(f"| {m[0]} | {m[1]} | {m[2]} | {int(m[3])} |")
report.append("")

report.append(f"### Streaks")
report.append(f"- Max win streak: **{max_win_streak}**")
report.append(f"- Max loss streak: **{max_loss_streak}**")
report.append("")

# Recommendations
report.append("## Recommendations")
report.append("")
for s_name, s in strat_details.items():
    target = study_targets.get(s_name)
    if target and s["wr"] < target:
        report.append(f"- **{s_name}**: WR {s['wr']}% below study target {target}% — investigate or adjust filters")
    if s["trades"] <= 2:
        report.append(f"- **{s_name}**: Only {s['trades']} trades — filters may be too aggressive, review agent reasoning")
report.append("")

if filtered_analysis and filtered_analysis["net_pnl"] > 20000:
    report.append(f"- **Filter aggressiveness**: Filters removed ${filtered_analysis['net_pnl']:,.2f} net profitable trades — consider loosening")
report.append("")

report.append("---")
report.append(f"*Generated by `/backtest-report` on {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
              f"Run persisted to DuckDB as `{RUN_ID}`.*")

# Write report
out_path = Path(f"reports/backtest_{RUN_ID}.md")
out_path.write_text("\n".join(report), encoding="utf-8")
print(f"\nReport saved: {out_path}")
print(f"  {len(report)} lines, {len(trade_dicts)} trades analyzed")
