---
name: meta-review
description: Review accumulated agent observations, strategy trends, and performance — generate meta-observations for the self-learning loop
allowed-tools: ["Bash", "Read", "Glob", "Grep", "Write", "Edit", "Agent"]
---

Review accumulated observations, agent accuracy, and strategy performance to generate meta-level insights. This is the periodic reflection step in the self-learning loop.

## Usage
- `/meta-review` — Review all observations since last meta-review
- `/meta-review --since 2026-03-01` — Review observations since a specific date
- `/meta-review --strategy OR_Reversal` — Focus on a specific strategy

## Steps

### Step 1: Gather Data from DuckDB

Run this to pull all the data needed for the review:

```bash
uv run python -c "
import sys, json; sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.research.db import connect, query

conn = connect()

# 1. Observations since last meta-review (or --since date)
last_meta = query(conn, \"\"\"
    SELECT MAX(created_at) FROM observations WHERE source = 'meta_review'
\"\"\")
since = last_meta[0][0] if last_meta and last_meta[0][0] else '2020-01-01'
# Override with --since if provided: since = '{SINCE_DATE}'

obs = query(conn, '''
    SELECT obs_id, scope, strategy, session_date, observation, evidence, source, confidence, created_at
    FROM observations
    WHERE created_at > ?
    ORDER BY created_at DESC
''', [str(since)])
print(f'=== OBSERVATIONS SINCE {since} ({len(obs)} total) ===')
for o in obs:
    print(f'  [{o[6]:20s}] {o[2] or \"portfolio\":20s} | {o[4][:80]}')

# 2. Agent accuracy stats
agent_acc = query(conn, '''
    SELECT strategy_name, decision, total, correct, accuracy_pct, avg_confidence
    FROM v_agent_accuracy
    ORDER BY strategy_name, decision
''')
print(f'\\n=== AGENT ACCURACY ({len(agent_acc)} rows) ===')
for a in agent_acc:
    print(f'  {a[0]:20s} | {a[1]:12s} | {a[2]:3d} decisions | {a[4]:.1f}% accurate | conf={a[5]:.3f}')

# 3. Agent TAKE vs SKIP comparison
agent_vs = query(conn, '''
    SELECT strategy_name, agent_decisions, takes, skips,
           avg_take_pnl, avg_skip_pnl, skip_would_have_lost_pct
    FROM v_agent_vs_mechanical
    ORDER BY strategy_name
''')
print(f'\\n=== AGENT TAKE vs SKIP ===')
for a in agent_vs:
    print(f'  {a[0]:20s} | {a[2]} takes (avg \${a[4]:+.0f}) | {a[3]} skips (avg \${a[5]:+.0f}) | skip_correct={a[6]:.0f}%')

# 4. Strategy performance trends (recent vs all-time)
strat_perf = query(conn, '''
    SELECT strategy_name,
           COUNT(*) AS n,
           ROUND(100.0 * SUM(CASE WHEN outcome=\"WIN\" THEN 1 ELSE 0 END) / COUNT(*), 1) AS wr,
           ROUND(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END) /
                 NULLIF(ABS(SUM(CASE WHEN net_pnl <= 0 THEN net_pnl ELSE 0 END)), 0), 2) AS pf,
           ROUND(SUM(net_pnl), 0) AS total_pnl
    FROM trades
    GROUP BY strategy_name
    ORDER BY total_pnl DESC
''')
print(f'\\n=== STRATEGY PERFORMANCE ===')
for s in strat_perf:
    print(f'  {s[0]:20s} | {s[1]:3d} trades | {s[2]:.1f}% WR | PF {s[3]:.2f} | \${s[4]:+,.0f}')

# 5. Session reviews
reviews = query(conn, '''
    SELECT session_date, reviewer, signals_fired, trades_taken, net_pnl, day_type, bias
    FROM session_reviews
    ORDER BY session_date DESC
    LIMIT 20
''')
print(f'\\n=== RECENT SESSION REVIEWS ({len(reviews)}) ===')
for r in reviews:
    print(f'  {r[0]} | {r[1]:8s} | {r[2]} signals | {r[3]} trades | \${r[4]:+,.0f} | {r[5]} | {r[6]}')

# 6. LLM trade review summary
llm_reviews = query(conn, '''
    SELECT COUNT(*) AS n,
           AVG(CAST(outcome_quality AS DOUBLE)) AS avg_quality,
           COUNT(CASE WHEN why_worked IS NOT NULL THEN 1 END) AS worked,
           COUNT(CASE WHEN why_failed IS NOT NULL THEN 1 END) AS failed
    FROM trade_assessments
    WHERE outcome_quality IS NOT NULL AND outcome_quality != ''
''')
if llm_reviews:
    r = llm_reviews[0]
    print(f'\\n=== LLM TRADE REVIEWS: {r[0]} total, avg quality={r[1]:.1f}, {r[2]} worked, {r[3]} failed ===')

conn.close()
"
```

### Step 2: Analyze Patterns

Read the output from Step 1 and analyze:

1. **Observation clusters** — Group observations by strategy/theme. What patterns repeat?
2. **Agent accuracy trends** — Are agents making better decisions over time? Which strategies have low accuracy?
3. **Strategy health** — Are any strategies degrading? Any showing improvement?
4. **Human vs system alignment** — Do human reviews agree with system reviews?
5. **Actionable gaps** — What's the system missing that human reviewers catch consistently?

### Step 3: Generate Meta-Observations

Based on your analysis, generate 3-8 meta-level observations. These should be:
- **Higher-level** than individual session observations
- **Pattern-spanning** — observed across multiple sessions/trades
- **Actionable** — leads to a specific improvement

Examples:
- "80P LONG trades entering above POC consistently lose. Agent should flag entry_price > POC as a high-risk indicator."
- "OR Reversal accuracy drops significantly after 10:00. Consider time-gating OR Rev signals to fire only before 9:50."
- "Agent SKIP decisions are 73% correct for B-Day strategy — the deterministic filters already catch most bad B-Day setups."

### Step 4: Persist Meta-Observations

```bash
uv run python -c "
import sys, uuid; sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.research.db import connect, persist_observation

conn = connect()

# For each meta-observation from Step 3:
observations = [
    # Fill these in from your analysis
    # {'strategy': 'strategy_name or None', 'observation': 'text', 'confidence': 0.7},
]

for obs in observations:
    persist_observation(conn, {
        'obs_id': f'meta_{uuid.uuid4().hex[:8]}',
        'scope': obs.get('scope', 'portfolio'),
        'strategy': obs.get('strategy'),
        'observation': obs['observation'],
        'evidence': 'Meta-review of accumulated observations and agent performance',
        'source': 'meta_review',
        'confidence': obs.get('confidence', 0.7),
    })

conn.close()
print(f'Persisted {len(observations)} meta-observations to DuckDB')
"
```

### Step 5: Write Report

Write the meta-review report to `data/meta_reviews/meta_review_{DATE}.md`:

```markdown
# Meta-Review: {DATE}

## Period: {SINCE_DATE} to {DATE}

## Summary
- Observations reviewed: {N}
- Strategies analyzed: {N}
- Agent decisions evaluated: {N}

## Key Findings

### Strategy Health
[Strategy-level performance analysis]

### Agent Performance
[Agent accuracy trends, TAKE vs SKIP analysis]

### Pattern Insights
[Cross-session patterns discovered]

### Recommendations
1. [Specific actionable recommendation]
2. [...]

## Meta-Observations Persisted
1. [obs text]
2. [...]
```

### Step 6: Report to User

Present the analysis conversationally:
- Top 3 most important findings
- Any strategies that need attention (degrading performance)
- Recommendations for parameter/prompt changes
- Count of new meta-observations persisted

## Notes
- This skill runs locally in Claude Code — no API calls
- Meta-observations automatically feed into future Advocate/Skeptic debates via `_query_historical()`
- Run every 3-5 days or after 50+ new observations accumulate
- The `meta_review` source tag distinguishes these from session-level observations
- All data comes from DuckDB — no external dependencies
