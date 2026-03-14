"""Quick check: is Run E data in DuckDB?"""
import duckdb

conn = duckdb.connect("data/research.duckdb", read_only=True)

# Backtest runs
rows = conn.execute("""
    SELECT run_id, instrument, notes, summary, created_at
    FROM backtest_runs
    WHERE run_id LIKE '%20260311%' OR notes LIKE '%Debate%'
    ORDER BY created_at DESC
""").fetchall()
print(f"Run E backtest runs found: {len(rows)}")
for r in rows:
    print(f"  {r[0]} | {r[1]} | {r[2]} | created={r[4]}")

# Trades
rows2 = conn.execute("""
    SELECT COUNT(*) as n,
           ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr,
           ROUND(SUM(net_pnl), 2) as pnl
    FROM trades
    WHERE run_id LIKE '%20260311%'
""").fetchall()
print(f"\nRun E trades: {rows2[0][0]}, WR: {rows2[0][1]}%, PnL: ${rows2[0][2]}")

# Agent decisions
rows3 = conn.execute("""
    SELECT COUNT(*) FROM agent_decisions WHERE run_id LIKE '%20260311%'
""").fetchall()
print(f"Agent decisions: {rows3[0][0]}")

# Strategy breakdown
rows4 = conn.execute("""
    SELECT strategy_name, COUNT(*) as n,
           ROUND(100.0 * SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) / COUNT(*), 1) as wr,
           ROUND(SUM(net_pnl), 2) as pnl
    FROM trades
    WHERE run_id LIKE '%20260311%'
    GROUP BY strategy_name
    ORDER BY pnl DESC
""").fetchall()
print(f"\nStrategy breakdown:")
for r in rows4:
    print(f"  {r[0]:25s} {r[1]:3d} trades, {r[2]}% WR, ${r[3]:,.2f}")

# Total runs in DB
total = conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0]
total_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
total_decisions = conn.execute("SELECT COUNT(*) FROM agent_decisions").fetchone()[0]
print(f"\nDB totals: {total} runs, {total_trades} trades, {total_decisions} agent decisions")

conn.close()
