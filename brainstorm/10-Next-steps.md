# 10 — Next Steps: Backtest Framework → Research DB → Agent Intelligence

> **Purpose**: Concrete, ordered execution plan to go from "working backtest engine" to "autonomous agent intelligence grounded in data."
>
> **Principle**: Prove the ground before training the LLM. Data warehouse + agents first, LLM training second. The LLM gets another layer of analysis on top of a proven, data-driven foundation.
>
> **Roles**: Claude = brainstormer + coder. User = reviewer + domain expert. Every phase ends with a user review gate.
>
> **Status**: Active plan
> **Date**: 2026-03-07

---

## Where We Are Now (Honest Assessment)

### What's SOLID

| Component | Status | Evidence |
|-----------|--------|----------|
| **Backtest Engine** | Production-ready | 266 sessions, 393 trades, 55% WR, 2.46 PF, +$149K |
| **4 active strategies** | Proven profitable | OR Rev (64.4%), OR Accept (59.9%), 80P (42.3%), B-Day (46.4%) |
| **Execution model** | Correct | Slippage, commission, position sizing, risk limits all working |
| **38 deterministic modules** | ~80% production-ready | 9,200 LOC, 47 integration tests, <10ms per snapshot |
| **Pluggable stop/target models** | Framework built | 15 stops, 14 targets, registry, bridge, ComboRunner — all tested (413 tests pass) |
| **MACD proof-of-concept** | Validates pluggable pattern | Strategy delegates to injected stop/target models |
| **JSON results output** | Functional | Per-run JSON with summary + per-trade detail + baseline comparison |

### What's MISSING (Gaps to Close)

| Gap | Impact | Blocking? |
|-----|--------|-----------|
| **No DuckDB persistence** | Can't query across runs, can't correlate | YES — blocks everything |
| **No MAE/MFE tracking** | Can't study "stopped out then right" or "left money on table" | YES — essential for stop/target tuning |
| **All 4 strategies hardcode stop/target** | Can't test alternative models without code changes | YES — must retrofit |
| **FVG lifecycle tracking** | Filled FVGs disappear, lose correlation signal | YES — P0 data quality fix |
| **No data validation pipeline** | Bad data (NaN, impossible values) could enter warehouse | YES — P0 fix |
| **TPO letter granularity** | Can't answer "which periods rejected at highs?" | No — P1, can enrich later |
| **ComboRunner results ephemeral** | Run combos, lose results after script exits | YES — must persist to DB |
| **No automated report generation** | Manual terminal reading only | No — nice to have early |
| **No correlation engine** | Can't join trades with deterministic context automatically | YES — core value prop |
| **No per-trade equity snapshots** | Equity curve only records session-end, not per-trade | No — P2 enhancement |

---

## The Phases

```
Phase 1: FOUNDATION          Phase 2: RETROFIT + BASELINE     Phase 3: RESEARCH DB + COMBO
─────────────────────         ──────────────────────────       ─────────────────────────────
• MAE/MFE in Trade            • Publish .md baseline reports   • DuckDB schema + init
• FVG lifecycle fix            • Retrofit 4 strategies          • Persist backtest runs
• Data validation              • Verify zero regression         • Persist combo results
• Deterministic tape gen       • ComboRunner for all 4          • Correlation engine
                               • Persist to DB                  • /optimize skill
                                                                • Report generation

Phase 4: AGENT FRAMEWORK     Phase 5: LLM TRAINING
─────────────────────────     ────────────────────
• Bayesian calibration         • LoRA training on proven data
• Strategy specialists         • Agent + LLM layer
• 50/50 train/test split       • Live inference
• Annotate + improve
```

---

## Phase 1: Foundation Fixes (Before Anything Else)

> **Goal**: Close the gaps that would pollute everything downstream. Don't build on bad data or incomplete trade tracking.

### 1.1 Add MAE/MFE + Extended Metrics to Trade Tracking

**Why**: Without MAE (Maximum Adverse Excursion) and MFE (Maximum Favorable Excursion), we can't study:
- "How often do trades touch the stop before winning?" → stop too tight
- "How much profit did we leave on the table?" → target too conservative
- "What's the average pullback before a winner runs?" → entry timing
- "Are losses clustered?" → need serial correlation + cluster analysis

#### Per-Trade Fields (add to Trade dataclass)

**What Claude does**:
- [ ] Add `mae_price`, `mfe_price` fields (worst/best price during trade life)
- [ ] Add `mae_points`, `mfe_points` (distance from entry in points)
- [ ] Add `mae_pct_of_stop` (mae_points / risk_points — 0.8 = "touched 80% of stop distance")
- [ ] Add `mfe_pct_of_target` (mfe_points / reward_points — 1.2 = "went 20% past target")
- [ ] Add `entry_efficiency` ((mfe - mae) / (mfe + mae) — 1.0 = perfect entry, 0.0 = terrible)
- [ ] Add `heat` (mae_points / risk_points — >1.0 means price went past stop level but didn't fill)
- [ ] Add `mae_bar`, `mfe_bar` (which bar number hit the worst/best point)
- [ ] Add `entry_hour` (hour of entry_time for time-of-day analysis)
- [ ] Track running min/max in `BacktestEngine._manage_position()` bar-by-bar
- [ ] Record all fields when position closes → stored in Trade
- [ ] Add to JSON output

#### Aggregate Metrics (add to metrics.py)

We already have 38 metrics. Adding ~25 more across 4 categories:

**Risk-adjusted ratios** (beyond existing Sharpe/Sortino/Calmar):
- [ ] `recovery_factor` — net_pnl / max_drawdown. Higher = more resilient. Target: >3
- [ ] `gain_to_pain_ratio` — sum(all_pnl) / abs(sum(negative_pnl)). Better than PF for comparing strategies
- [ ] `ulcer_index` — sqrt(mean(drawdown²)). Captures depth AND duration of drawdowns
- [ ] `kelly_fraction` — WR - ((1 - WR) / payoff_ratio). Optimal position sizing signal

**Trade quality metrics** (powered by MAE/MFE):
- [ ] `stop_out_rate` — count(exit='STOP') / total. High = stop too tight
- [ ] `target_hit_rate` — count(exit='TARGET') / total. Low = target too ambitious
- [ ] `edge_ratio` — avg(mfe_points) / avg(mae_points). >1.0 = favorable edge. <1.0 = stop-hunting
- [ ] `avg_mae_pct_of_stop` — average heat across all trades
- [ ] `avg_mfe_pct_of_target` — how much of target is captured on average
- [ ] `r_multiple_median` — median R (more robust than mean for skewed distributions)
- [ ] `r_multiple_stddev` — R variance (tight = consistent, wide = unpredictable)
- [ ] `pct_trades_above_2r` — % of trades with R > 2 (tail wins)
- [ ] `pct_trades_below_neg1r` — % of trades with R < -1 (full stop-outs)

**Cluster & sequence metrics** (answers "are losses clustered?"):
- [ ] `serial_correlation` — autocorrelation of returns at lag 1. >0 = clustered, <0 = mean-reverting
- [ ] `max_cluster_loss` — worst sum of consecutive losing trades in $
- [ ] `max_cluster_loss_count` — how many trades in that worst cluster
- [ ] `drawdown_duration_sessions` — sessions from peak equity to recovery
- [ ] `daily_pnl_volatility` — stddev of daily net PnL (emotional difficulty metric)

**Session-level metrics**:
- [ ] `session_win_rate` — % of sessions with positive daily PnL (better predictor of live experience)
- [ ] `pct_flat_sessions` — % of sessions with 0 trades
- [ ] `intraday_max_dd` — worst point within any single session (captures "terrible morning, recovered by close")
- [ ] `wr_by_entry_hour` — dict of win rate per hour bucket (9, 10, 11, 12, 13, 14, 15)

**Tests**:
- [ ] Add tests: known bar sequence → known MAE/MFE values
- [ ] Add tests: known trade list → known cluster metrics, edge ratio, Kelly
- [ ] Verify serial correlation = 0 for random win/loss sequence

**User reviews**: Trade dataclass changes, verify MAE/MFE values make sense on a few sample trades. Check that cluster metrics flag known bad streaks.

### 1.2 FVG Lifecycle Tracking (P0 Data Quality)

**Why**: Currently filled FVGs disappear from snapshots. We lose the signal "an FVG existed and was filled" which is critical for correlation ("was there a recently-filled FVG at entry time?").

**What Claude does**:
- [ ] Modify `fvg_detection.py`: add `fvg_id`, `created_time`, `filled_time`, `status`, `fill_pct`
- [ ] Filled FVGs stay in output with `status='filled'` + `filled_time` instead of being removed
- [ ] Add `recently_filled` list (FVGs filled in last 5 bars — still relevant context)
- [ ] Update tests: verify FVG appears, gets filled, stays in output with correct timestamps

**Timeframe coverage** (per user):
- [ ] Verify FVG detection covers: daily, 4h, 1h, 90min, 30min, 15min (current code already does 6 TFs — verify all working)
- [ ] 5-min FVGs: include but flag as `timeframe_priority='low'` — too many to track as primary signals, but useful for precision entry confirmation
- [ ] **Overnight data for HTF candles**: Multi-session FVGs (daily, 4h) must include ETH/overnight bars when building the candle. A daily FVG spans 6:00 PM previous → 5:00 PM current (full futures session), NOT just 9:30-4:00 RTH. Verify `fvg_detection.py` uses full-session data for daily/4h timeframes, not just RTH bars.
- [ ] **Add NWOG (New Week Opening Gap)**: Gap between Friday close and Sunday/Monday open. Compute: `nwog_high = max(friday_close, monday_open)`, `nwog_low = min(friday_close, monday_open)`. Track fill status (partially filled, fully filled, unfilled).
- [ ] **Add NDOG (New Day Opening Gap)**: Gap between prior session close and current session open. Compute: `ndog_high = max(prior_close, current_open)`, `ndog_low = min(prior_close, current_open)`. Track fill status per session.
- [ ] NWOG/NDOG are separate from FVG (they're opening gaps, not 3-candle gaps) but follow the same lifecycle: created at open → tracked for fill → eventually filled or not. Store alongside FVGs with `gap_type='NWOG'/'NDOG'/'FVG'`.

**User reviews**: Spot-check a few sessions — do the FVGs match what you'd see on a chart? Verify NWOG/NDOG gaps match what you see on weekly/daily charts.

### 1.3 Data Validation Pipeline (P0 Data Quality)

**Why**: Before generating 20,000+ deterministic rows, we need guardrails against bad data.

**What Claude does**:
- [ ] Create `validate_snapshot()` function:
  - POC within VAH/VAL
  - VAH > VAL
  - IB high >= IB low
  - ATR > 0
  - No NaN/Inf in numeric fields
  - Valid day_type enum
- [ ] Integrate into orchestrator: validate every snapshot before output
- [ ] Log warnings for violations, reject corrupt snapshots
- [ ] Add tests with intentionally bad data → verify warnings fire

**Prior session & premarket level validation** (per user):
- [ ] Validate PDH (prior day high) and PDL (prior day low) are present and non-null
- [ ] Validate previous weekly high/low are present (these are key HTF levels)
- [ ] Validate Asia session high/low (typically 6PM-midnight ET futures)
- [ ] Validate London session high/low (typically 2AM-5AM ET)
- [ ] **Holiday/half-day handling**: When prior session was a holiday or half-day, some levels may be legitimately missing. Log as `warning` (not rejection) with reason: `"prior_session_holiday"`. Use last available full session's levels as fallback and flag `"prior_levels_stale": true` in snapshot.
- [ ] **Weekend gaps**: Friday → Monday spans may have different overnight ranges. Validate that Monday sessions reference Friday's close (not Saturday/Sunday which don't exist).
- [ ] **Short sessions** (day before Thanksgiving, Christmas Eve): Flag with `"short_session": true`. IB may be different (fewer bars). Don't reject — just annotate.

**User reviews**: Validation rules — are these the right sanity checks? Review any sessions flagged as holiday/stale to confirm correct handling.

### 1.4 Generate Deterministic Tape (259+ sessions)

**Why**: This is the foundational data layer. Everything correlates against it.

**What Claude does**:
- [ ] Create `scripts/generate_deterministic_tape.py`:
  - Loads each session CSV from `data/sessions/`
  - Runs deterministic orchestrator
  - Validates each snapshot
  - Outputs to `data/json_snapshots/deterministic_{date}.jsonl` (one file per session)
- [ ] Run for all 259+ sessions
- [ ] Report: sessions processed, snapshots generated, validation warnings

**User reviews**: Spot-check 5 random sessions — does the data match reality?

**Deliverable**: `data/json_snapshots/` populated with 259+ session files, ~20,000 snapshots total.

#### Regime Classification: Do We Have Enough?

Great question. Here's what we HAVE vs what we NEED for regime identification:

**What we already capture for regime classification:**

| Regime Dimension | Current Source | Status |
|-----------------|---------------|--------|
| IB width (narrow/normal/wide) | `ib_location.py` — IB range vs ATR14 ratio | ✓ Have it |
| Day type (trend/p-day/b-day/neutral) | `balance_classification.py` — dynamic classification | ✓ Have it |
| Trend strength (none/moderate/strong) | `ib_location.py` — ADX(14) | ✓ Have it |
| Gap status (above/inside/below prior VA) | `globex_va_analysis.py` — gap classification | ✓ Have it |
| Overnight range | `premarket.py` — ON high/low, compression ratio | ✓ Have it |
| OR context (sweep up/down/both/rotation) | `or_reversal.py` — opening range sweep detection | ✓ Have it |
| Opening drive (drive up/drive down/rotation) | `or_reversal.py` — first 15-min direction | ✓ Have it |
| DPOC behavior (trending/stabilizing/reversal) | `dpoc_migration.py` — 30-min POC tracking | ✓ Have it |
| CRI readiness (GO/CAUTION/STAND_DOWN) | `cri.py` — terrain/identity/permission | ✓ Have it |

**What we're MISSING for regime — need to add:**

| Regime Dimension | Why It Matters | Action |
|-----------------|----------------|--------|
| **ATR on daily timeframe** | Intraday ATR14 (on 1-min bars) is different from daily ATR14. Daily ATR tells you "is this a high-vol week?" not just "is this a high-vol minute." | Add `atr14_daily` to premarket/session context — compute from prior 14 daily bars |
| **ATR on 5-min** | 5-min ATR captures intraday volatility regime changes mid-session. A session can start calm and go volatile after FOMC. | Add `atr14_5min` as rolling calculation in tape context |
| **VIX at session open** | VIX < 15 vs VIX > 25 is a completely different trading environment. Tight stops work in low VIX, get destroyed in high VIX. | Currently a stub (`vix_regime.py` is empty). Need VIX data source — likely from a daily VIX CSV or API. Add `vix_open`, `vix_close` to session_context. **This is a data dependency** — we need historical VIX data for 259+ sessions. |
| **Weekly structure** | Is this week's range expanding or contracting vs prior weeks? Are we in a trend week or rotation week? | Add `weekly_range`, `weekly_atr`, `weekly_direction` to session context. Compute from prior 5 daily bars. |
| **Prior day's classification** | Was yesterday a trend day or balance day? Yesterday's behavior influences today's open. | Add `prior_day_type` to session context (already available from prior session's final day_type) |
| **Session count in range** | How many consecutive balance days? 3+ balance days often precede breakouts. | Add `consecutive_balance_days` counter |

**What Claude does** (additional tasks for 1.4):
- [ ] Add `atr14_daily` to session context (compute from prior 14 daily OHLC bars)
- [ ] Add `atr14_5min` as rolling metric in tape context module
- [ ] Add `prior_day_type` to session context
- [ ] Add `consecutive_balance_days` counter
- [ ] Add `weekly_range`, `weekly_direction` to session context
- [ ] Create `regime_classification()` function that outputs a composite regime label:
  - `"low_vol_balance"` (ADX < 20, normal IB, balance day)
  - `"high_vol_trend"` (ADX > 25, wide IB, trend day)
  - `"compressed_pre_breakout"` (narrow IB, 3+ balance days, ON range < 50% of avg)
  - etc. — 6-8 regime buckets that strategies can filter on
- [x] **VIX data**: CBOE historical CSV downloaded to `data/vix/VIX_History.csv` (9,137 rows, 1990–2026-03-06, updated daily from `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`). VIX regime module created at `deterministic/modules/vix_regime.py` — provides `vix_open`, `vix_close`, `vix_regime` (low/moderate/elevated/high/extreme), `vix_5d_avg`, `vix_change_pct`. Covers all 259+ backtest sessions. Yahoo Finance (`https://finance.yahoo.com/quote/%5EVIX/`) available for real-time but requires HTML parsing — defer to Phase 5 (live trading).

**User reviews**: Do the regime buckets make sense? Are there regime conditions you trade differently that we're not capturing?

---

## Phase 2: Retrofit Strategies + Baseline Reports

> **Goal**: Publish .md baseline reports for all 4 strategies BEFORE any code changes. Then retrofit to use pluggable models. Then verify zero regression.

### 2.1 Publish Baseline Reports (BEFORE ANY CHANGES)

**Why**: We need a benchmark to prove the new framework produces identical results. If we change code first, we lose the reference point.

**What Claude does**:
- [ ] Run current backtest for NQ, 266 sessions, all 4 active strategies
- [ ] Generate per-strategy .md reports:
  - `data/results/reports/baseline_or_reversal.md`
  - `data/results/reports/baseline_or_acceptance.md`
  - `data/results/reports/baseline_80p_rule.md`
  - `data/results/reports/baseline_b_day.md`
- [ ] Each report contains:
  - Total trades, WR, PF, net PnL, max DD, avg win, avg loss, expectancy
  - Win rate by day type, by IB width class
  - Exit reason breakdown (STOP, TARGET, EOD, DAILY_LOSS, VWAP_BREACH)
  - Top 5 best/worst trades with session date + context
  - Monthly/quarterly trade distribution
  - Equity curve summary
- [ ] Save baseline JSON: `data/results/baselines/baseline_NQ.json`

**User reviews**: Do these reports match your understanding of each strategy's performance?

#### Entry/Stop/Exit/Target Model Mapping (per user request)

Each baseline report must document the EXACT execution models currently hardcoded, so we know what to extract into pluggable models:

| Strategy | Entry Model | Stop Model | Target Model | Exit Rules |
|----------|------------|------------|--------------|------------|
| **OR Rev** | 50% retest of OR sweep extreme, ±0.5×ATR tolerance | 2.0 × ATR14 beyond entry | 2R (2× risk distance) | Stop, Target, EOD 3:30, VWAP breach PM, Trail BE after 1PM |
| **OR Accept** | 2 consecutive 5-min closes beyond OR level, 30-bar retest window | 0.5 × ATR14 beyond acceptance level (capped 3-40 pts) | 2R | Stop, Target, EOD, VWAP breach PM |
| **80P Rule** | 30-bar (30-min) candle acceptance inside prior VA | Fixed 10pts beyond VA edge (VAH for short, VAL for long) | 2R (configurable: 2R/4R/opposite_va/POC) | Stop, Target, EOD, Cutoff 1PM |
| **B-Day** | First touch of IBL within 5pt tolerance | IBL - 10% of IB range | IB midpoint (fixed level target) | Stop, Target, EOD, Cutoff 2PM |
| **20P (IB Extension)** | 3x consecutive 5-min closes beyond IB boundary (IBH for LONG, IBL for SHORT) | 2.0 × ATR14 from entry | 2R (2× risk = 4× ATR from entry) | Stop, Target only (0 EOD exits in study — trades resolve intraday) |

**Gap check**: Before retrofitting, verify each strategy's entry/stop/target can map to existing model classes OR identify new models needed. For example:
- OR Rev's "50% retest with tolerance band" is a specific entry model not yet in our registry
- B-Day's "IB midpoint target" maps to `LevelTarget('ib_mid')`
- 80P's "VA edge + fixed buffer" needs a `VAEdgeStop` model class

Each baseline report will include this mapping table + flag any gaps.

### 2.2 Retrofit 4 Core Strategies to Pluggable Models

**Why**: Strategies currently hardcode stop/target. To test alternative models, we need them to accept injected stop/target models via constructor (like MACD does).

**What Claude does** (per strategy):
- [ ] Add `stop_model` and `target_model` constructor parameters (default to current hardcoded values)
- [ ] Extract current stop/target logic into model classes if needed (e.g., `VAEdgeStop(buffer_pts=10)` for 80P)
- [ ] Use `bridge.py` to convert Signal direction → EntrySignal → stop_model.compute() → target_model.compute()
- [ ] When no custom models injected → behavior is IDENTICAL to current hardcoded logic

Retrofit order (5 core strategies):
- [ ] **B-Day** first (simplest: IB-range stop, IB-mid target)
- [ ] **80P Rule** second (VA-edge stop, 2R target)
- [ ] **OR Reversal** third (2 ATR stop, 2R target)
- [ ] **OR Acceptance** fourth (0.5 ATR stop, 2R target)
- [ ] **20P IB Extension** fifth (2 ATR stop, 2R target — already uses same models as MACD PoC)

### 2.3 Verify Zero Regression

**What Claude does**:
- [ ] Run backtest with retrofitted strategies (default models)
- [ ] Compare against Phase 2.1 baseline: trade count, WR, PF, net PnL must be **identical**
- [ ] Run full test suite (413+ tests must pass)
- [ ] Generate comparison .md report showing baseline vs retrofitted (should be identical)

**User reviews**: Confirm regression report shows zero diff.

**Deliverable**: 5 strategies using pluggable models, identical results to baseline.

#### The 20P Strategy — FIXED (2026-03-08)

The 20P (IB Extension / Twenty Percent Rule) strategy was broken at 7.1% WR due to 4 extra filters NOT in the source study. Same root cause as the 80P fix.

**What was wrong** (4 filters not in the study):
1. `IB_EXTENSION_THRESHOLD = 0.20` — Required 20% IB extension BEFORE acceptance counting. Study just wants 3 closes beyond IBH/IBL.
2. `trend_strength != 'weak'` filter — Rejected valid setups in weak-trend environments
3. Delta confirmation filter — Rejected valid setups when delta didn't confirm
4. `MIN_IB_RANGE = 30` — Filtered out narrow IB sessions

**What was fixed**:
- [x] Removed all 4 extra filters
- [x] Simplified to single-phase: watch for 3 consecutive 5-min closes beyond IBH (LONG) or IBL (SHORT)
- [x] Keep: 2×ATR stop, 2R target, 1 trade/session max
- [x] Enabled in `configs/strategies.yaml`
- [x] Study target: 45.5% WR, 1.78 PF, 3.7 trades/month

**The 5 core strategies** (all active):
1. Opening Range Reversal (OR Rev) — 64.4% WR, best first-hour strategy
2. OR Acceptance — 59.9% WR
3. 80P Rule — 42.3% WR (fixed 2026-03-02)
4. B-Day — 46.4% WR
5. 20P IB Extension — fixed 2026-03-08, study target 45.5% WR

#### Strategy Configuration

**Where to configure**:
- **Enable/disable**: `configs/strategies.yaml` — each strategy has `enabled: true/false`
- **Strategy loader**: `strategies/loader.py` — maps config keys to class names
- **Constants**: `config/constants.py` — risk limits, slippage, account size
- **Per-strategy params**: Currently hardcoded in each strategy file (ATR multipliers, buffer points, etc.)

**Example** (`configs/strategies.yaml`):
```yaml
b_day:
  enabled: true
  # After retrofit, will also accept:
  # stop_model: "ib_edge_10pct"
  # target_model: "level_ib_mid"

twenty_percent_rule:
  enabled: true  # Fixed 2026-03-08 — ported from source study
```

**Skill need**: Yes — a `/add-strategy` skill already exists. After retrofit, we should also add:
- [ ] `/configure-strategy` skill — change stop/target model, enable/disable, set params via CLI
- [ ] Strategy config validation — verify model keys exist in registry before running

---

## Phase 3: Research DB + Combo Optimization + Correlation

> **Goal**: DuckDB warehouse operational. Backtests auto-persist. Combo studies run and persist. Correlation engine connects trades to deterministic context.

### 3.1 Research DB Schema + Init

**What Claude does**:
- [ ] Create `packages/rockit-core/src/rockit_core/research/` package:
  - `schema.py` — DDL definitions for all tables (from brainstorm/09)
  - `db.py` — `connect()`, `persist_backtest()`, `persist_combo()`, `query()`
  - `deterministic.py` — `persist_deterministic_tape()` (load JSONL → DuckDB)
  - `correlate.py` — post-trade correlation workflow
- [ ] Create `scripts/init_research_db.py` — creates `data/research.duckdb`
- [ ] Tables: `backtest_runs`, `trades`, `combo_runs`, `combo_trades`, `session_context`, `deterministic_tape`, `observations`, `tags`, `experiments`, `regime_rules`

**User reviews**: Schema looks right? Column types make sense?

#### Schema Use Case Coverage — Point-by-Point Assessment

Your 11 requirements, each mapped to schema support:

**1. "Backtest with variety of model configuration for entry/stop/exit/target"**
- ✓ `backtest_runs.config` (JSON) — stores full config: which models, which params
- ✓ `combo_runs` — tracks which stop/target models were tested
- ✓ `combo_trades` — per-trade results for each model combo
- ✓ `trades.metadata` (JSON) — stores `stop_model`, `target_model`, `entry_model` names
- **Gap**: Need to add `entry_model` column to `combo_trades` (currently only stop + target). Will add.

**2. "Being able to annotate each run by Claude"**
- ✓ `backtest_runs.notes` (TEXT) — Claude writes summary annotation after each run
- ✓ `observations` table — structured findings linked to `run_id`
- **Enhancement**: Add `backtest_runs.report_md` (TEXT) — full .md report as blob, so every run has its own self-contained report. Will add.

**3. "Being able to correlate with deterministic dataset"**
- ✓ `deterministic_tape` — 5-min snapshots of all 38 modules
- ✓ `session_context` — session-level summary
- ✓ `v_trade_context` view — trades JOIN session_context
- ✓ `v_trade_tape` view — trades JOIN deterministic_tape at entry_time
- ✓ Join key: `session_date` + `snapshot_time` matches `entry_time` rounded to 5-min

**4. "Being able to correlate with LLM output from deterministic dataset"**
- ✓ `tape_annotations` table — LLM tape readings linked to `deterministic_tape` via (session_date, snapshot_time)
- ✓ Once LLM is trained, its output goes here. Can join: `trades → deterministic_tape → tape_annotations`
- ✓ `annotator` column distinguishes 'qwen3.5' vs 'opus' vs 'claude_review' vs 'human'

**5. "Claude should have a skill to optimize the strategy via self improvement loop"**
- ✓ `experiments` table — tracks hypothesis → method → finding → next_hypothesis → parent_id (chains)
- ✓ Each `/optimize` iteration creates a new `backtest_runs` entry linked to an `experiment`
- ✓ `experiments.status` tracks: planned → running → complete → abandoned
- **Enhancement**: Add `experiments.iteration_number` (INT) and `experiments.improvement_pct` (DOUBLE) to quantify each loop's delta. Will add.

**6. "Remarks and observations why a trade worked, worked well, barely profitable, or loss"**
- ✓ `observations` table — free-text observations with structured tags + confidence levels
- ✓ Can link to specific trades via `observations.trade_id` (need to add this FK)
- **Enhancement**: Add `trade_assessments` table for per-trade Claude analysis:
  ```sql
  trade_assessments (
    trade_id INTEGER, run_id VARCHAR,
    outcome_quality VARCHAR,  -- 'strong_win', 'lucky_win', 'barely_profitable', 'expected_loss', 'avoidable_loss'
    why_worked TEXT, why_failed TEXT,
    deterministic_support TEXT,  -- "CRI=GO, delta=positive, DPOC trending up"
    deterministic_warning TEXT,  -- "wick_parade=4, HTF supply overhead"
    improvement_suggestion TEXT  -- "wider stop would have held; try 2.5 ATR"
  )
  ```

**7. "Publish strategy optimized report / findings for variety of market regime"**
- ✓ `regime_rules` table — stores regime-conditional recommendations (stop/target per regime)
- ✓ `v_strategy_by_regime` view — strategy WR/PF broken out by regime dimensions
- ✓ Reports can be generated per (strategy × regime) and stored in `backtest_runs.report_md`
- ✓ Publish workflow (brainstorm/09 §10) gates on: 30+ trades, PF > 1.2, regime-tested

**8. "Is data useful for advocate/skeptic/orchestrator agents via Bayesian model?"**
- ✓ `calibration_tables` (planned for Phase 4) — per-specialist accuracy per regime
- ✓ `session_context` provides regime dimensions for Bayesian conditioning
- ✓ `deterministic_tape` provides CRI/DPOC/delta at signal time for specialist evidence
- ✓ Agent-facing views can pre-compute: "strategy X in regime Y has Z% WR from N trades"
- **Key**: The advocate for a strategy needs `trades` filtered by (strategy, regime) → WR/PF. The skeptic needs `trades` where (strategy, regime) LOST → common failure patterns. Both are simple SQL from our schema.
- **Orchestrator**: Reads all specialist outputs + Bayesian P → stored in `agent_decisions` table (Phase 4)

**9. "Run backtest with agents and observe how they respond and record analysis"**
- ✓ `agent_annotations` (production DB) — stores per-trade agent analysis
- **Enhancement for research DB**: Add `agent_decisions` table:
  ```sql
  agent_decisions (
    decision_id INTEGER, session_date VARCHAR, signal_timestamp TIMESTAMP,
    strategy_name VARCHAR, direction VARCHAR,
    bayesian_probability DOUBLE,
    specialist_reports JSON,  -- each specialist's structured output
    decision VARCHAR,  -- 'TAKE', 'SKIP', 'REDUCE'
    debate_summary TEXT,  -- if ambiguous zone triggered debate
    actual_outcome VARCHAR, actual_pnl DOUBLE,
    was_correct BOOLEAN  -- did the decision beat naive strategy?
  )
  ```

**10. "Will datawarehouse provide rich info for unseen time periods? (2025 train → 2026 forward test)"**
- ✓ Schema is time-indexed — all tables have `session_date`. Easy to split: `WHERE session_date < '2026-01-01'` (train) vs `>= '2026-01-01'` (test)
- ✓ Calibration tables can be built from training period only, then tested on forward period
- ✓ Regime drift detection queries (brainstorm/09 §9) compare recent vs historical performance
- **Key test**: After Phase 4, we run this exact experiment:
  1. Build calibration from 2025 sessions only
  2. Run agents on 2026 sessions with 2025 calibration
  3. Measure: does the calibration generalize? If regime changed, where did it break?
  4. This is THE validation gate before going live

**11. "Once validated, ready to go live!"**
- ✓ Production DB schema (brainstorm/09 §10) is designed for exactly this
- ✓ Publish workflow gates on statistical thresholds
- ✓ Production agents read from `strategy_configs` + `calibration_tables`
- ✓ Production agents write to `agent_annotations` + `trade_history`
- The warehouse doesn't just store data — it's the **proof** that the system works. No proof, no go-live.


### 3.2 Persist Backtest Runs to DuckDB

**What Claude does**:
- [ ] Hook `run_backtest.py` → auto-persist run + all trades after every backtest
- [ ] Each trade gets: MAE, MFE, entry_time, exit_time, bars_held, exit_reason, direction, all prices, net PnL, r_multiple
- [ ] Each run gets: git_branch, git_commit, config JSON, strategy list, summary metrics
- [ ] Run a backtest → verify data appears in DuckDB → run SQL queries against it
- [ ] Seed existing `data/results/*.json` → `backtest_runs` + `trades`

### 3.3 Load Deterministic Tape into DuckDB

**What Claude does**:
- [ ] Parse `data/json_snapshots/deterministic_*.jsonl` → extract key fields → `deterministic_tape` table
- [ ] Also populate `session_context` (session-level summary per date)
- [ ] Verify: `SELECT COUNT(*), COUNT(DISTINCT session_date) FROM deterministic_tape`
- [ ] Create `v_trade_context` view (trades JOIN session_context)
- [ ] Create `v_trade_tape` view (trades JOIN deterministic_tape at entry_time)

### 3.4 Combo Studies for All 4 Strategies

**What Claude does**:
- [ ] Run ComboRunner for each strategy with stop/target variants:
  - Stops: `1_atr`, `2_atr`, `fixed_10pts`, `fixed_15pts`, `fixed_20pts`, `ib_edge_10pct`, `level_buffer_10pct`
  - Targets: `2r`, `3r`, `4r`, `ib_1.5x`, `ib_2.0x`, `level_ib_mid`, `adaptive`
  - = 7 stops × 7 targets = 49 combos per strategy × 4 strategies = ~196 combos
- [ ] Persist all combo results to `combo_runs` + `combo_trades`
- [ ] Hook `run_combo_backtest.py` → auto-persist
- [ ] Identify best combos per strategy: which stop/target beats "original"?

**MY COMMENTS**: Remember there are 5 core strategies


### 3.5 Post-Trade Correlation Engine

**What Claude does**:
- [ ] For each trade in `trades`, query `deterministic_tape` at entry time:
  - CRI status, DPOC migration, delta trend, TPO shape, price vs IB, IB extension %
- [ ] Auto-tag trades with deterministic context
- [ ] Generate correlation summary per strategy:
  - "OR Rev has 74% WR when CRI=GO + delta=positive, vs 33% when CRI=CAUTION + delta=negative"
- [ ] Persist correlations as `observations` with tags + confidence levels
- [ ] Generate per-strategy correlation .md report

### 3.6 `/optimize` Skill

**What Claude does**:
- [ ] Create skill that takes a strategy name and:
  1. Runs ComboRunner with all stop/target variants
  2. Persists results to DuckDB
  3. Runs post-trade correlation with deterministic tape
  4. Generates comparison report (.md)
  5. Annotates findings as observations
  6. Suggests parameter adjustments
  7. Optionally iterates: adjust → re-run → compare → annotate
- [ ] Tracks: WR, expectancy, MAE, MFE, PF, net PnL, avg R per combo
- [ ] Each iteration is a new `backtest_runs` entry with link to previous

### 3.7 Report Generation

**What Claude does**:
- [ ] Per-run report (.md): summary + per-trade detail + correlation findings
- [ ] Aggregate report: all combos ranked by PF, with regime breakdown
- [ ] Store report as blob in `backtest_runs.report_md` column
- [ ] Also save to `data/results/reports/`

**Phase 3 Deliverable**: DuckDB with backtest data for 4 strategies, 196+ combo runs, deterministic tape for 259 sessions, correlation findings, per-strategy .md reports. Data queryable via SQL.

---

## Phase 4: Agent Framework + Bayesian Calibration

> **Goal**: Build strategy specialist agents grounded in DuckDB data. Run them through backtest replay. Annotate and improve. This is BEFORE LLM training.

### 4.1 Bayesian Calibration Pipeline

**What Claude does**:
- [ ] Run each strategy's deterministic signals through 259 sessions
- [ ] For each signal, record deterministic context at signal time → outcome
- [ ] Build calibration tables: "when CRI=GO and strategy=OR Rev, WR = X%"
- [ ] Build conditional tables: "when CRI=GO AND delta=positive, WR = Y%"
- [ ] Store calibration tables in DuckDB `calibration_tables`

### 4.2 Strategy Specialist Agents (Deterministic First)

**What Claude does**:
- [ ] Build deterministic specialist per strategy:
  - "Is my setup present? What's my confidence based on calibrated data?"
  - Reads from session context cache (pre-loaded from DuckDB)
- [ ] Each specialist outputs structured JSON (setup_present, direction, confidence, risk_factors)
- [ ] Orchestrator combines specialist outputs + Bayesian probability chain

### 4.3 Backtest Replay with Agents (50/50 Split)

**What Claude does**:
- [ ] Split 259 sessions: 130 training / 129 test (by date, not random)
- [ ] Run agents through training sessions → calibrate, tune, annotate
- [ ] Run agents through test sessions → measure out-of-sample performance
- [ ] Agent annotations: "what worked", "what failed", "missed signals"
- [ ] Compare: agent-filtered WR vs raw strategy WR → does the agent add alpha?

### 4.4 Assessment + Iteration

**What Claude does**:
- [ ] Auto-assess agent performance per strategy:
  - Did agent TAKE decisions outperform agent SKIP decisions?
  - Which risk factors correctly predicted losses?
  - Which calibrations drifted from training to test set?
- [ ] Iterate: adjust thresholds, recalibrate, re-run test set
- [ ] Persist each iteration as an `experiment` in DuckDB

**Phase 4 Deliverable**: Agent framework with Bayesian calibration, tested on 50% unseen data, annotations and assessment in DuckDB.

---

## Phase 5: LLM Training (After Proven Ground)

> **Goal**: Train Qwen3.5 LoRA on proven data. LLM adds tape reading analysis as an additional layer on top of the deterministic + agent foundation.

### 5.1 Training Data from Proven Pipeline

- [ ] Generate training pairs: deterministic snapshot + strategy signal context → analyst output
- [ ] Include agent annotations as training signal (what the deterministic agent saw and decided)
- [ ] Convert to ChatML with `<think>` CoT tags
- [ ] Train LoRA on DGX Spark

### 5.2 LLM as Additional Layer

- [ ] LLM tape readings stored in `tape_annotations` table (layered on `deterministic_tape`)
- [ ] Agents can query LLM analysis alongside deterministic data
- [ ] Bayesian chain gains an additional evidence source (LLM tape read → calibrated accuracy)

**Phase 5 Deliverable**: Trained LLM providing tape reading layer, integrated into agent pipeline, calibrated via Bayesian framework.

---

## Your 6 Review Questions — Answered

### 1. "Do we have sufficient confidence in our deterministic data generation for 250+ sessions?"

**Answer: ~80%, with P0 fixes needed.**

- Volume Profile & HVN/LVN: 95% confidence — true volume-at-price, correct VA calculation
- TPO Profile: 70% — works but lacks 5-min TPO and letter granularity (P1 fix, not blocking)
- FVG Detection: 60% — **P0 fix needed** (filled FVGs disappear, lose lifecycle tracking)
- Data validation: **P0 fix needed** (no NaN/Inf/impossible value guards)
- Everything else (IB, DPOC, premarket, CRI, inference): 80-95%

**Action**: Phase 1.2 + 1.3 close the P0 gaps. After that, confidence rises to ~90%.

### 2. "Do we have sufficient backtest framework?"

**Answer: 85%, with one key gap.**

- Engine: Excellent. 266 sessions, position management, trailing stops, risk limits, EOD handling
- Execution model: Good. Slippage, commission, position sizing
- Pluggable models: Built. 15 stops, 14 targets, ComboRunner, bridge
- Metrics: Rich. 40+ metrics, Sharpe/Sortino/Calmar, exit breakdown

**Gap**: No MAE/MFE tracking. Can't study "was the stop too tight?" or "did we leave money on the table?" This is essential for stop/target optimization.

**Action**: Phase 1.1 closes this gap.

### 3. "Are we going to produce sufficient data for agents to use in Bayesian approach?"

**Answer: Yes, with the right pipeline.**

- 259+ sessions × 4 strategies × ~1-3 trades/session = ~800+ labeled trade outcomes
- Each trade tagged with deterministic context at entry time = calibration data
- ComboRunner adds 49 combos × 4 strategies = ~196 combo studies with per-trade data
- Total: thousands of (context → outcome) pairs for calibration tables

**Risk**: Some (strategy × regime) cells may have <10 trades. Mitigation: cluster similar regimes, use wider confidence intervals.

### 4. "How are we going to correlate backtest data with deterministic data?"

**Answer: Post-trade correlation workflow (brainstorm/09, Section 14).**

1. Every trade gets recorded with entry_time
2. Query `deterministic_tape` at that timestamp → CRI, DPOC, delta, TPO shape
3. Auto-tag trade with deterministic features
4. Compare wins vs losses → which features predict outcomes?
5. Persist findings as `observations` with confidence levels

Claude runs this automatically after every backtest. The `/optimize` skill does it as part of its iteration loop.

### 5. "Make sure we move everything to the new framework (5 core strategies)"

**Answer: Phase 2.2 does this, with zero-regression proof.**

Each strategy gets `stop_model` and `target_model` constructor params. Defaults match current hardcoded values exactly. Baseline report (Phase 2.1) proves pre-retrofit numbers. Post-retrofit backtest must produce identical results.

Order: B-Day → 80P → OR Rev → OR Accept (simplest to most complex).

### 6. "Begin full backtest and build out data to match previous report"

**Answer: Phase 2.1 publishes baseline .md reports FIRST, then Phase 2.3 verifies zero regression after retrofit.**

Baseline reports include: trades, WR, PF, net PnL, max DD, per-day-type breakdown, exit reason breakdown, top/worst trades. This is the benchmark. After retrofit + combo optimization (Phase 3), we compare new results against this baseline to quantify improvement.

---

## Weekend Sprint Target (Realistic Scope)

If we push hard this weekend, realistic deliverables:

| Deliverable | Phase | Confidence |
|-------------|-------|------------|
| MAE/MFE in Trade dataclass | 1.1 | High — straightforward code change |
| FVG lifecycle fix | 1.2 | High — modify one module |
| Data validation pipeline | 1.3 | High — add validation function |
| Baseline .md reports for 4 strategies | 2.1 | High — run backtest + format output |
| Retrofit B-Day + 80P to pluggable models | 2.2 (partial) | Medium — need careful testing |
| DuckDB schema + init script | 3.1 | High — schema already designed in brainstorm/09 |
| Persist backtest runs to DuckDB | 3.2 | Medium — integration work |

**Stretch goals** (if time allows):
- Retrofit OR Rev + OR Accept
- Run first combo study + persist
- Generate deterministic tape for 259 sessions
- First correlation query

**What probably slips to next week**:
- Full combo studies for all 4 strategies (196 combos)
- Correlation engine
- `/optimize` skill
- Report generation
- Agent framework (Phase 4)

---

## Dependency Graph

```
Phase 1.1 (MAE/MFE) ──────────────────────────────────────┐
Phase 1.2 (FVG fix) ──┐                                    │
Phase 1.3 (Validation) ┤                                    │
                       ├→ Phase 1.4 (Deterministic tape) ──┤
                       │                                    │
Phase 2.1 (Baseline)──┤                                    │
                       ├→ Phase 2.2 (Retrofit strategies) ─┤
                       │                                    │
                       ├→ Phase 2.3 (Zero regression) ─────┤
                       │                                    │
                       │        Phase 3.1 (DB schema) ─────┤
                       │                    │               │
                       │                    ├→ Phase 3.2 (Persist backtests) ──┐
                       │                    │                                   │
                       │                    ├→ Phase 3.3 (Load deterministic)──┤
                       │                    │                                   │
                       │                    └→ Phase 3.4 (Combo studies) ──────┤
                       │                                                       │
                       │                              Phase 3.5 (Correlation) ─┤
                       │                                                       │
                       │                              Phase 3.6 (/optimize) ───┤
                       │                                                       │
                       └──────────────────────────── Phase 4 (Agents) ─────────┤
                                                                               │
                                                     Phase 5 (LLM Training) ───┘
```

Key insight: Phases 1 and 2 can be parallelized. Phase 1.1 (MAE/MFE) and Phase 2.1 (baseline reports) have no dependency. Phase 3.1 (DB schema) can start as soon as brainstorm/09 schema is finalized.

---

## Agreement: This Phased Approach Is Correct

Yes — **LLM training comes AFTER proving the ground with data + agents.** The reasoning:

1. **Deterministic data is free** — no API cost, <10ms, runs for 259+ sessions in minutes
2. **Bayesian calibration is deterministic** — pure math from calibration tables, no LLM needed
3. **Agents can be purely deterministic at first** — strategy specialists check Boolean/numeric conditions, Bayesian chain produces calibrated probability, only ambiguous cases need LLM
4. **LLM adds a LAYER, not a foundation** — tape readings, reasoning narratives, novel pattern detection. Valuable but not the base.
5. **50/50 train/test split validates before LLM** — if deterministic agents can't add alpha on 50% unseen data, adding an LLM won't fix the underlying issue

The data warehouse IS the proven ground. Agents calibrated from it have measurable accuracy. LLM training on top of this gives the agents richer reasoning without losing the quantitative foundation.
