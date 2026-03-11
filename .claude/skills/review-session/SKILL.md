---
name: review-session
description: Interactive session review — backtest signals, deterministic context, agent evaluation, comparison to user notes
allowed-tools: ["Bash", "Read", "Glob", "Grep", "Write", "Edit", "Agent"]
---

Review a trading session collaboratively: run strategies, analyze market structure, evaluate with agents, and compare system output to the user's written observations.

## Usage
- `/review-session 2026-03-10` — Deterministic analysis (fast, no LLM)
- `/review-session 2026-03-10 --llm` — Include LLM Advocate/Skeptic debate
- `/review-session today` — Today's session
- `/review-session 2026-03-10 --no-merge` — Skip CSV merge from Google Drive

## Steps

### Step 1: Parse Arguments & Load Data

Parse the date from args. Accept `YYYY-MM-DD`, `YYYY.MM.DD`, or `today` (resolve to current date).
Detect flags: `--llm` (enable debate), `--no-merge` (skip merge).
Default instrument is **NQ**.

**Merge & load** (unless `--no-merge`):
```bash
uv run python -c "
import sys; sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.data.manager import SessionDataManager
mgr = SessionDataManager()
for inst in ['NQ', 'ES', 'YM']:
    try:
        mgr.merge_delta(inst)
    except Exception as e:
        print(f'{inst}: {e}')
"
```

Then load and filter to the single session date:
```bash
uv run python -c "
import sys, json; sys.path.insert(0, 'packages/rockit-core/src')
import pandas as pd
from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features

mgr = SessionDataManager()
df = mgr.load('NQ')
df = compute_all_features(df)
session_df = df[df['session_date'].astype(str).str.startswith('{DATE}')]
print(f'Rows for {DATE}: {len(session_df)}')
if len(session_df) == 0:
    print('ERROR: No data for this date. Check if CSV has been merged.')
else:
    print(f'Time range: {session_df[\"timestamp\"].min()} to {session_df[\"timestamp\"].max()}')
"
```

If no data found, stop and tell the user to merge data first.

### Step 2: Read User Review Notes

Look for the user's review file at `brainstorm/review-sessions/{YYYY.MM.DD}.md` (dot-separated date).

If found, read and present the user's observations.
If not found, note "No review notes found" and continue — the system analysis is still valuable.

### Step 3: Run Backtest — Two Passes (Single Session)

Run the backtest engine on the single session, twice:

**Pass A — No filters** (all signals that fired):
```bash
uv run python -c "
import sys, json; sys.path.insert(0, 'packages/rockit-core/src')
import pandas as pd
from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features
from rockit_core.config.instruments import get_instrument
from rockit_core.strategies.loader import load_strategies_from_config
from rockit_core.engine.backtest import BacktestEngine

mgr = SessionDataManager()
df = compute_all_features(mgr.load('NQ'))
df = df[df['session_date'].astype(str).str.startswith('{DATE}')]

inst = get_instrument('NQ')
strategies = load_strategies_from_config('configs/strategies.yaml')
engine = BacktestEngine(instrument=inst, strategies=strategies)
result = engine.run(df, verbose=False)

for t in result.trades:
    outcome = 'WIN' if t.net_pnl > 0 else 'LOSS'
    print(f'{t.strategy_name} | {t.direction} | Entry {t.entry_price} | PnL \${t.net_pnl:+,.0f} | {outcome} | {t.exit_reason} | {t.day_type}')
print(f'---')
print(f'Total signals: {result.signals_generated}, Executed: {len(result.trades)}')
"
```

**Pass B — With mechanical filters** (production config):
```bash
uv run python -c "
import sys, json; sys.path.insert(0, 'packages/rockit-core/src')
import pandas as pd
from rockit_core.data.manager import SessionDataManager
from rockit_core.data.features import compute_all_features
from rockit_core.config.instruments import get_instrument
from rockit_core.strategies.loader import load_strategies_from_config
from rockit_core.filters.pipeline import build_filter_pipeline
from rockit_core.engine.backtest import BacktestEngine

# Load session bias from DuckDB
session_bias = {}
try:
    from rockit_core.research.db import connect, query
    conn = connect()
    rows = query(conn, 'SELECT session_date, bias FROM session_context WHERE bias IS NOT NULL')
    session_bias = {str(r[0]).split(' ')[0]: r[1] for r in rows}
    conn.close()
except: pass

mgr = SessionDataManager()
df = compute_all_features(mgr.load('NQ'))
df = df[df['session_date'].astype(str).str.startswith('{DATE}')]

inst = get_instrument('NQ')
strategies = load_strategies_from_config('configs/strategies.yaml')
filters = build_filter_pipeline('configs/filters.yaml')
engine = BacktestEngine(instrument=inst, strategies=strategies, filters=filters, session_bias_lookup=session_bias)
result = engine.run(df, verbose=False)

for t in result.trades:
    outcome = 'WIN' if t.net_pnl > 0 else 'LOSS'
    print(f'{t.strategy_name} | {t.direction} | Entry {t.entry_price} | PnL \${t.net_pnl:+,.0f} | {outcome} | {t.exit_reason} | {t.day_type}')
print(f'---')
print(f'Total signals: {result.signals_generated}, Filtered: {result.signals_filtered}, Executed: {len(result.trades)}')
"
```

Report both passes in a comparison table:
```
| Strategy | Dir | Entry | PnL | Outcome | Pass A | Pass B (filtered) |
```

### Step 4: Market Structure Context

Check if deterministic snapshots exist for the date:
```bash
ls data/json_snapshots/deterministic_{DATE}.jsonl 2>/dev/null
```

If not found, generate them:
```bash
uv run python scripts/generate_deterministic_tape.py --date {DATE}
```

Read the JSONL and extract snapshots at key times: **9:30, 9:45, 10:00, 10:30, 11:00, 13:00, 15:00**

For each key time, report:
- Day type classification + trend strength
- Session bias / regime bias
- CRI status (READY / CAUTION / STAND_DOWN)
- IB range, IB high, IB low, IB classification
- DPOC location and migration direction
- TPO shape (b, p, D, B, etc.)
- Prior day VA (POC, VAH, VAL)
- Key levels (VWAP, London high/low, overnight high/low)
- FVG presence + direction

Present as a timeline:
```
09:30  Opening — Day type: TBD, Bias: neutral, CRI: STAND_DOWN
09:45  OR Close — OR range X pts, OR high/low
10:00  EOR — Day type: emerging_trend_up, Bias: BULL
10:30  IB Close — IB range X pts, IB class: normal
...
```

### Step 5: Agent Evaluation (Deterministic)

For each signal from Pass A, run the deterministic agent pipeline:
```bash
uv run python -c "
import sys, json; sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.observers import ProfileObserver, MomentumObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator

pipeline = AgentPipeline(
    gate=CRIGateAgent(),
    observers=[ProfileObserver(), MomentumObserver()],
    orchestrator=DeterministicOrchestrator(),
)

# For each signal, call:
# decision = pipeline.evaluate_signal(signal_dict, bar, session_context)
# Report: decision.action (TAKE/SKIP/REDUCE_SIZE), evidence_cards, confluence_score
"
```

For each signal, report:
- Gate pass/fail (CRI check)
- Evidence cards generated (with category, direction, strength)
- Confluence score
- Final decision: TAKE / SKIP / REDUCE_SIZE
- Key reasoning

### Step 6 (Optional): LLM Debate — only if `--llm` flag

Check LLM availability:
```bash
uv run python -c "
import sys; sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.agents.llm_client import OllamaClient
client = OllamaClient()
print('LLM available' if client.is_available() else 'LLM unreachable')
"
```

If available, run the full pipeline with debate enabled:
```bash
uv run python -c "
import sys; sys.path.insert(0, 'packages/rockit-core/src')
from rockit_core.agents.pipeline import AgentPipeline
from rockit_core.agents.llm_client import OllamaClient

client = OllamaClient()
pipeline = AgentPipeline(llm_client=client, enable_debate=True)
# Run evaluate_signal for each gate-passing signal
"
```

For each debated signal, report:
- **Advocate thesis**: key bull/bear arguments, admitted/rejected cards
- **Skeptic counter-thesis**: warnings, risks, rejected cards
- **Instinct cards**: LLM-generated evidence (at 0.6x weight)
- **Disputed cards**: resolution (admitted at 0.7x or rejected)
- **Final decision** with adjusted confluence score

If LLM unreachable: print warning and continue with deterministic-only results from Step 5.

### Step 7: System vs User Comparison

Map user's written observations (from Step 2) to system signals and deterministic data.

**Keyword mapping** (fuzzy match user language to system concepts):
- "IB extension" / "IBH" / "IB range" → 20P IB Extension strategy, IB metrics
- "OR reversal" / "OR" / "opening range" → OR Reversal strategy
- "OR acceptance" / "acceptance" → OR Acceptance strategy
- "London sweep" / "London low" / "London high" → London levels in deterministic data
- "SMT" / "divergence" → Cross-instrument divergence (flag as system gap — we don't track SMT yet)
- "balance day" / "B-day" → day_type classification, B-Day strategy
- "FVG" / "fair value gap" → FVG features in deterministic data
- "VWAP" → VWAP level in deterministic data
- "80P" / "value area" / "20P" → 80P Rule, 20P IB Extension
- "trend" / "bullish" / "bearish" → bias, day_type
- "pulled back" / "pullback" / "retracement" → entry quality assessment

Categorize into four buckets:
1. **Aligned** — Both user and system identified the same setup/condition
2. **System gap** — User observed something the system doesn't track (e.g., SMT, cross-instrument divergence, specific price action)
3. **User gap** — System caught a signal the user didn't mention
4. **Disagreement** — User and system have conflicting directional reads

### Step 8: Report

Present the full analysis in this format:

```
=== SESSION REVIEW: {DATE} (NQ) ===

--- Market Structure Timeline ---
[From Step 4: key times with day type, bias, IB, levels]

--- Your Notes ---
[User's observations from review file, quoted]

--- Signals & Trades ---
| # | Strategy      | Dir   | Entry    | PnL      | Outcome | Unfiltered | Filtered | Agent |
|---|---------------|-------|----------|----------|---------|------------|----------|-------|
| 1 | OR Acceptance | LONG  | 21,050.0 | +$505    | WIN     | YES        | YES      | TAKE  |
| 2 | 20P IB Ext    | LONG  | 21,120.0 | -$19     | LOSS    | YES        | YES      | TAKE  |

--- Agent Evidence (per signal) ---
Signal 1 — OR Acceptance LONG:
  Gate: PASS (CRI = READY)
  Evidence: [list cards with category/direction/strength]
  Confluence: 0.65 → TAKE

--- System vs Your Analysis ---
| Observation             | You | System | Status      |
|-------------------------|-----|--------|-------------|
| IB extension to upside  | YES | YES    | ALIGNED     |
| London low sweep on ES  | YES | NO     | SYSTEM GAP  |
| SMT divergence clue     | YES | NO     | SYSTEM GAP  |
| OR Acceptance signal    | NO  | YES    | USER GAP    |
| Bullish bias            | YES | YES    | ALIGNED     |

--- Key Takeaways ---
1. [What the system confirmed about the user's read]
2. [What the user saw that the system can't track yet — potential improvement areas]
3. [What the system caught that the user might want to watch for next time]
4. [Any disagreements and how to reconcile them]
```

### Step 9: Update User's Review File

After presenting the analysis, **append** system-generated context to the user's review file at `brainstorm/review-sessions/{YYYY.MM.DD}.md`.

Add a `## System Analysis` section with:
- Market structure summary (day type, bias, IB range, key levels)
- Signals that fired (strategy, direction, entry, PnL, outcome)
- Agent evaluation summary
- Alignment analysis summary
- Key observations for future reference

Use the Edit tool to append — do NOT overwrite the user's original notes.

If the review file doesn't exist, create it with a template:
```markdown
# Session Review: {DATE}

## My Notes
[No notes yet — add your observations here]

## System Analysis
[Generated content]
```

## Notes
- All commands use `uv run` (not bare python)
- Always use `encoding='utf-8'` for file I/O
- `sys.path.insert(0, 'packages/rockit-core/src')` before importing rockit_core
- Session dates in DuckDB are normalized (no " 00:00:00" suffix)
- Default instrument is NQ unless user specifies otherwise
- The `--llm` flag is opt-in because each LLM call takes ~70s
- If Pass A returns 0 trades, the session had no strategy signals — still report market structure
- For `today`, use Python `datetime.now().strftime('%Y-%m-%d')` to resolve
