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

### 1.3 Data Validation Pipeline (P0 Data Quality) — DONE (2026-03-08)

**Why**: Before generating 20,000+ deterministic rows, we need guardrails against bad data.

**What Claude does**:
- [x] Create `validate_snapshot_data()` in `data_validator.py`:
  - POC within VAH/VAL (warn if outside)
  - VAH > VAL (error if violated)
  - IB high >= IB low (error if violated)
  - ATR > 0 (warn if non-positive)
  - No NaN/Inf in critical numeric fields (error)
  - Valid day_type enum (warn if unexpected)
- [x] Integrated into orchestrator: validates every snapshot, adds `_validation` dict to output
- [x] Log warnings for violations (non-fatal), log errors to ErrorLogger
- [x] 31 tests with intentionally bad data → verify warnings/errors fire

**Prior session & premarket level validation** (per user):
- [x] Validate PDH (prior day high) and PDL (prior day low) are present and non-null
- [x] Validate Asia session high/low
- [x] Validate London session high/low
- [x] Validate overnight high/low
- [x] **Holiday/half-day handling**: Missing levels logged as `warning` (not rejection)

### 1.4 Generate Deterministic Tape (259+ sessions) — DONE (2026-03-08)

**Why**: This is the foundational data layer. Everything correlates against it.

**What Claude does**:
- [x] Create `scripts/generate_deterministic_tape.py`:
  - Loads each session CSV from `data/sessions/`
  - Runs deterministic orchestrator with regime context + data validation
  - Validates each snapshot
  - Outputs to `data/json_snapshots/deterministic_{date}.jsonl` (one file per session)
  - Skips already-generated sessions (`--force` to regenerate)
  - Reports: sessions processed, snapshots generated, validation stats
  - Saves `tape_generation_report.json` summary
- [x] Regime context module (`regime_context.py`) with:
  - `atr14_daily` from prior 14 daily bars
  - `atr14_5min` rolling 5-min ATR
  - `prior_day_type` classification from prior session
  - `consecutive_balance_days` counter
  - `weekly_range`, `weekly_direction`, `weekly_atr`
  - VIX integration (from `vix_regime.py`)
  - Composite regime label (7 regimes: low_vol_balance, low_vol_trend, high_vol_trend, high_vol_range, compressed_pre_breakout, expansion, transitional)
- [x] 22 tests for regime context module
- [ ] Run for all 268 sessions (script ready, needs execution)

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

**What Claude does** (additional tasks for 1.4) — ALL DONE (2026-03-08):
- [x] Add `atr14_daily` to session context — `regime_context.py` computes from prior 14 daily OHLC bars
- [x] Add `atr14_5min` as rolling metric — `regime_context.py` computes from 5-min resampled bars
- [x] Add `prior_day_type` to session context — classifies prior day from IB extension ratio
- [x] Add `consecutive_balance_days` counter — looks back through daily bars
- [x] Add `weekly_range`, `weekly_direction` to session context — from prior 5 daily bars
- [x] Create `_classify_regime()` function that outputs a composite regime label:
  - `"low_vol_balance"` — quiet market, rangebound
  - `"low_vol_trend"` — steady directional move, low volatility
  - `"high_vol_trend"` — strong directional move, volatile
  - `"high_vol_range"` — volatile but no direction (chop)
  - `"compressed_pre_breakout"` — narrow IB, 3+ balance days, low vol
  - `"expansion"` — wide IB, high vol
  - `"transitional"` — mixed signals, regime changing
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

### 2.4 Signal-Time TPO Histogram (Backtest + Live)

**Why**: The 5-min deterministic snapshots capture general session state but lack the depth needed for full Dalton TPO analysis. When a strategy signal fires, we generate a **complete TPO histogram** at that exact moment — this is the deep dive the agent needs to evaluate the signal. Not every 5-min slice (overkill), but always at signal time (both backtest replay and live trading).

**What gets generated at signal time**:
- Full TPO letter-by-letter histogram (per-period letter profile at every traded price level)
- Volume-at-price histogram (VRVP overlay) with HVN/LVN zones from 5-day visible range
- Per-period letter ranges with OTF sequence up to signal bar
- Distribution analysis (single/double/morphing at signal time)
- Excess, poor high/low, single print ranges
- FVG lifecycle context at signal time (active/recently filled nearby)
- All naked prior levels with distance to current price

**When it runs**:
- **Backtest**: BacktestEngine triggers `generate_signal_tpo_snapshot()` when a strategy emits a Signal
- **Live**: Strategy runner triggers the same function when a signal fires in real-time
- Same function, same output — consistent analysis across backtest and live

**Storage**: Persist alongside the trade record in DuckDB → enables:
- "What did the TPO histogram look like when this winning trade was taken?"
- "Are trades taken during P-shape profiles more profitable?"
- "Do LVN-entry trades have better MAE characteristics?"
- Agent deep analysis: Advocate/Skeptic can reference the full histogram when debating a signal
- Post-trade correlation: deterministic context × TPO structure × outcome

**What Claude does**:
- [ ] Create `generate_signal_tpo_snapshot()` function — full TPO histogram at signal bar
- [ ] Hook into BacktestEngine: when strategy emits signal, capture TPO snapshot
- [ ] Hook into strategy runner (live): same function triggered at signal time
- [ ] Store in trade metadata or separate `signal_snapshots` DuckDB table
- [ ] Include in baseline reports: TPO structure at entry for top/worst trades

**User reviews**: Does the deep snapshot capture enough for Dalton-style analysis?

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

---

## Future Deterministic Modules: Core Price Action Intelligence

> **Goal**: Train agents to SEE price action the way a professional tape reader does. These are NOT strategy signals — they are pure observations that feed the LLM's understanding of market structure.

### 2.5 SMT Divergence Detection (Multi-Timeframe, Multi-Instrument)

**What**: ICT Smart Money Technique — detect when correlated instruments diverge at key levels. A big reversal signal when one makes a new high/low but the other doesn't confirm.

**Instruments**: NQ vs ES, NQ vs YM, ES vs YM (all 3 pairs)

**Timeframes**:
- **Premarket/HTF**: Daily, 4H, 1H (prior session and current day context)
- **Intraday**: 5min, 15min, 60min (real-time divergence detection)

**Detection Logic** (needs deep research):
- Compare swing highs/lows across correlated instruments at the same timestamp
- NQ makes new high but ES doesn't confirm → bearish SMT divergence
- NQ makes new low but YM holds → bullish SMT divergence
- Weight by timeframe: daily SMT >> 15min SMT
- Track: divergence_pair, timeframe, direction, timestamp, price_gap, confirmation_status

**Output fields per divergence**:
```python
{
    "pair": "NQ_ES",
    "timeframe": "15min",
    "type": "bearish",         # NQ new high, ES didn't confirm
    "leader": "NQ",
    "leader_price": 21550.0,
    "laggard_price": 5420.0,
    "swing_type": "high",       # high or low
    "detected_at": "10:15",
    "bars_since": 3,
    "confirmed": True,          # Did price reverse after divergence?
}
```

**Challenges**:
- Need synchronized data across instruments (same timestamps)
- Swing point detection required first (see 2.6)
- Must handle different tick sizes (NQ=0.25, ES=0.25, YM=1.0)
- False positives common on small timeframes — need minimum swing size filter

**Dependencies**: Requires swing point detection (2.6) and multi-instrument data loader.

### 2.6 Price Swing Point Detection (HH/HL/LH/LL Channels)

**What**: Identify swing highs and swing lows algorithmically. This is THE fundamental price action observation — all other pattern recognition builds on it.

**Patterns to detect**:
1. **Swing highs/lows**: Local extremes confirmed by N bars on each side (fractals)
2. **3-drive pattern**: Three successive pushes to new high/low with diminishing momentum
3. **Channel structure**: Higher highs + higher lows (uptrend), lower highs + lower lows (downtrend)
4. **Trend breaks**: First lower high in an uptrend, first higher low in a downtrend
5. **Equal highs/lows**: Liquidity pools (ICT concept — price will sweep these)

**Detection approach** (research needed):
- Zigzag with configurable lookback (5, 13, 21 bars)
- Minimum swing size filter (ATR-based: swing must be > 0.5 ATR to count)
- Multi-timeframe: 5min swings, 15min swings, 1H swings, 4H swings
- Track swing sequence: HH, HL, HH, HL = confirmed uptrend

**Output per timeframe**:
```python
{
    "timeframe": "15min",
    "current_structure": "uptrend",     # uptrend / downtrend / consolidation
    "swing_sequence": ["HL", "HH", "HL", "HH"],  # last 4 swing labels
    "last_swing_high": {"price": 21550.0, "time": "10:30", "type": "HH"},
    "last_swing_low": {"price": 21420.0, "time": "10:00", "type": "HL"},
    "three_drive": {
        "detected": True,
        "direction": "up",
        "drives": [21500, 21530, 21545],  # diminishing pushes
        "momentum_declining": True,
    },
    "equal_highs": [{"price": 21550.0, "count": 2, "tolerance": 3.0}],
    "equal_lows": [{"price": 21400.0, "count": 3, "tolerance": 3.0}],
    "structure_break": None,  # or {"type": "bearish", "broken_level": 21420.0, "time": "11:15"}
}
```

**Why this is critical**: Every tape reader classifies "are we making HH/HL or LH/LL?" before anything else. Without this, the LLM has no concept of trend structure.

### 2.7 Trendline Analysis (3rd Touch, Backside, Break + Retest)

**What**: Algorithmic trendline detection and interaction tracking. Key events: 3rd touch (confirmation), backside test (support becomes resistance), and break + retest.

**Detection approach** (research needed):
- Connect 2+ swing lows (ascending trendline) or 2+ swing highs (descending trendline)
- Use linear regression on swing points with tolerance band
- Track touch count — 3rd touch is the classic confirmation/reversal point
- After a break: monitor for "backside" test (old support → new resistance)

**Key events to detect**:
1. **Trendline formation**: 2 swing points connected, slope calculated
2. **3rd touch approaching**: Price within 0.3 ATR of trendline
3. **3rd touch confirmed**: Price touched and bounced (continuation) or broke through (reversal)
4. **Trendline break**: Price closes beyond trendline (not just wick)
5. **Backside retest**: After break, price returns to test the trendline from the other side

**Output**:
```python
{
    "active_trendlines": [
        {
            "type": "ascending",        # ascending / descending
            "anchor_points": [
                {"price": 21300, "time": "09:45"},
                {"price": 21380, "time": "10:15"},
            ],
            "slope_per_bar": 2.67,      # points per 5-min bar
            "touch_count": 2,
            "current_trendline_price": 21420.0,  # projected current value
            "price_distance": 30.0,     # current price - trendline price
            "price_distance_atr_pct": 0.2,  # distance as % of ATR
            "status": "active",         # active / broken / retesting
            "approaching_3rd_touch": True,
        }
    ],
    "recent_events": [
        {"event": "3rd_touch_approaching", "trendline_idx": 0, "time": "11:00"},
    ],
}
```

**Dependencies**: Requires swing point detection (2.6) for anchor points.

**Research questions**:
- Best algorithm for real-time trendline fitting (Hough transform? Iterative RANSAC? Simple swing-to-swing?)
- How to handle multiple valid trendlines (pick steepest? most touches?)
- Timeframe: probably 15min and 1H only (5min too noisy, 4H too slow for intraday)
- Tolerance for "touch" — wick vs close vs within N ticks?

### 2.8 Implementation Priority

These three modules build on each other:

```
2.6 Swing Points  ──→  2.7 Trendlines  ──→  feeds into all pattern detection
        │
        └──→  2.5 SMT Divergence (requires swing points on multiple instruments)
```

**Recommended order**:
1. **Swing points first** (2.6) — foundational, everything else needs it
2. **Trendlines second** (2.7) — depends on swing points
3. **SMT last** (2.5) — depends on swing points + multi-instrument data

**Data requirements**:
- Swing points: Current instrument only, uses existing 1-min bars
- Trendlines: Current instrument only, uses swing points
- SMT: Needs ES + YM data loaded alongside NQ (requires multi-instrument loader enhancement)

---

## PRIORITY: Migrate Ollama → vLLM for Concurrent Inference

> **Status**: TODO — HIGH PRIORITY
> **Date added**: 2026-03-11
> **Why**: Ollama serves requests sequentially. A single debate (Advocate + Skeptic) takes ~2 min. Full 270-session backtest takes ~3-4 hours. vLLM supports continuous batching and concurrent requests, enabling parallelized backtests.

### Current State (Ollama)
- **Host**: spark-ai (DGX Spark, 128GB)
- **Model**: qwen3.5:35b-a3b via Ollama
- **Config**: `num_ctx 131072` (128K context), `num_predict 8000` (8K max output)
- **Throughput**: ~50-60s per LLM call, ~2 min per signal (Advocate + Skeptic sequential)
- **Concurrency**: None — requests queue behind each other
- **Full backtest**: ~3-4 hours for 270 sessions (sequential)

### Target State (vLLM)
- **Same host**: spark-ai (DGX Spark, 128GB)
- **Model**: Same qwen3.5:35b-a3b weights
- **API**: OpenAI-compatible (same as Ollama — `OllamaClient` works as-is, just change `base_url`)
- **Key advantage**: Continuous batching — multiple requests processed concurrently on GPU
- **Concurrency target**: 2-3 parallel backtest streams, each firing LLM calls independently

### Parallelization Strategy

**Option A: Parallel backtests (simplest)**
- Run 2-3 instances of `ab_test_agents.py` simultaneously (e.g., split sessions into chunks)
- Each instance fires LLM calls independently → vLLM batches them on GPU
- Estimated speedup: 2-3x (3-4 hours → 1-1.5 hours)
- Implementation: Add `--session-range 0-90`, `--session-range 90-180`, `--session-range 180-270` args
- Merge results after all chunks complete

**Option B: Async Advocate + Skeptic (medium effort)**
- Currently Skeptic waits for Advocate (sees Advocate's thesis)
- For INDEPENDENT signals across sessions, fire Advocate calls concurrently via asyncio
- Skeptic still sequential per signal, but multiple signals debated in parallel
- Requires: async `OllamaClient`, `BacktestEngine` refactor for parallel session processing

**Option C: Full async pipeline (most effort)**
- Async backtest engine processes multiple sessions concurrently
- Each session's signals fire LLM calls as they arise
- vLLM batches all concurrent requests
- Estimated speedup: 3-5x depending on GPU memory / KV cache capacity
- Requires: significant refactor of BacktestEngine + AgentPipeline

**Recommended path**: Option A first (trivial to implement), then Option B if more speed needed.

**Option D: Skip obvious signals (biggest bang for buck)**
- If mechanical filters already passed with high confidence AND deterministic agents score > 0.7 → skip LLM debate, auto-TAKE
- Only debate ambiguous signals (agent score 0.3-0.7) where LLM nuance matters
- Could cut LLM calls by 50-70% — most signals are clear-cut
- Implementation: Add `debate_threshold` to pipeline config. Score below threshold = auto-decide, above = debate
- This is orthogonal to vLLM — do both for compounding speedup

### vLLM Deployment Notes
- Install: `pip install vllm` on DGX Spark
- Launch: `vllm serve qwen3.5:35b-a3b --max-model-len 131072 --max-num-seqs 8 --gpu-memory-utilization 0.90`
- `--max-num-seqs 8` allows up to 8 concurrent requests (KV cache shared)
- Monitor: vLLM exposes `/metrics` endpoint (Prometheus format) — request queue depth, tokens/sec, batch size
- **No code changes needed** in `OllamaClient` — just change `base_url` from Ollama to vLLM endpoint
- Thinking tokens: vLLM handles Qwen3 thinking natively via `--enable-reasoning`

### Model Benchmarking Framework

> **Key question**: Do we need a 35B model? If an 8B model makes the same TAKE/SKIP decisions, use the 8B and get 4x speed.

**Benchmark protocol**:
1. Pick 5-10 validated sessions with known good/bad signals (from Run E results)
2. Run each model through the same Advocate/Skeptic prompts
3. Compare: decision match rate, reasoning quality, structured JSON compliance, latency
4. Score: decision_accuracy (vs baseline) × speed = efficiency score

**Candidate models** (all Ollama-compatible):

| Model | Active Params | Est. Speed | Thinking Mode | Notes |
|-------|--------------|-----------|---------------|-------|
| Qwen3.5:35b-a3b | 3B active | ~55s | Yes (eats tokens) | Current baseline |
| GLM-4.7 NFVP4 | TBD | TBD | No | No thinking overhead, clean JSON |
| Qwen3:8B | 8B | ~15s | Yes | 4x faster, may be sufficient |
| Qwen3:14B | 14B | ~25s | Yes | Potential sweet spot |
| Phi-4 14B | 14B | ~20s | No | Strong reasoning, no thinking tax |
| Gemma 3 12B | 12B | ~20s | No | Good structured output |
| Llama 4 Scout | 17B active | ~30s | No | MoE, strong reasoning |

**What to measure per model**:
- Decision agreement with 35B baseline (TAKE/SKIP match rate)
- JSON compliance (valid structured output without repair)
- Reasoning quality (does it cite the right evidence?)
- Latency per call (Advocate + Skeptic round-trip)
- Token efficiency (does it waste tokens on irrelevant thinking?)

**Implementation**: `scripts/benchmark_models.py` — runs N sessions across M models, produces comparison table.

### Training vs Pure Agentic — Decision Framework

> **Core question**: If prompt engineering + DuckDB retrieval + good system prompts get 90% of the way there, is LoRA training worth the complexity?

**When training IS worth it**:
- Base model consistently misinterprets domain patterns (P-shape, B-shape, Dalton theory)
- Prompt is too long (>4K tokens of domain knowledge) and you want to compress into weights
- Need faster inference (knowledge baked in vs read from prompt every call)
- Want consistency — trained model gives more deterministic responses to same input

**When training is NOT worth it**:
- Agentic approach (system prompts + retrieval) produces equivalent decisions
- A smaller untrained model + good prompts matches a larger trained model
- Domain knowledge changes frequently (retrain cost > prompt update cost)
- The LLM is just "rubber-stamping" deterministic agent decisions anyway

### The Raw Snapshot Gap — Architecture Insight (2026-03-11)

> **Current state**: Advocate/Skeptic only see pre-digested scorecard (evidence cards + 6 context fields + DuckDB stats). They NEVER see the raw deterministic JSON from the 38 modules.

**What the LLM sees today**:
```
evidence_cards: [
  {source: "profile_observer", direction: "bullish", strength: 0.7, observation: "Price above POC..."},
  {source: "momentum_observer", direction: "bearish", strength: 0.4, observation: "Delta declining..."},
]
session_context: {day_type: "p_day", session_bias: "Bullish", trend_strength: "moderate", ...}
historical_stats: {strategy_overall: {trades: 55, win_rate: 76.4, profit_factor: 5.39}}
```

**What the LLM does NOT see**:
- Raw VA levels (VAH=21550, VAL=21420, POC=21490) and price distance from each
- IB extension % (currently 1.3× IB range — how far has price extended?)
- FVG positions (unfilled bearish FVG at 21580-21600 — overhead supply)
- Wick parade count (4 wicks rejected at 21550 — sellers active)
- DPOC migration path (POC moved from 21470 → 21490 in last 3 periods)
- Delta cumulative flow + delta divergence signals
- TPO letter-by-letter distribution shape
- Prior session VA overlap % with current session
- CRI sub-scores (terrain, identity, permission) — only GO/CAUTION status passed

**The gap**: Observers reduce 38 modules → ~9 cards. Information is LOST. A trained LLM could spot patterns across the raw fields that no single observer captures. For example:
- "Price at POC + 4 wick rejections + FVG overhead + declining delta = SHORT setup strengthening" — this requires seeing 4 fields simultaneously, not 4 separate cards.
- "IB extension 1.8× + prior VA overlap 85% + DPOC stable = rotation day, fade the extension" — cross-module pattern.

**Two approaches to fix this**:

**Approach A: Pass raw snapshot alongside scorecard (no training needed)**
- Add `snapshot_json` to the debate context (already available in `session_context.snapshot_json`)
- LLM gets scorecard + raw data → can do its own synthesis
- Pro: No training. Works with any model. Easy to implement.
- Con: Adds ~2-4K tokens to prompt. Base model may not understand domain-specific fields without training.

**Approach B: Train LLM to interpret raw snapshots, then pass them (training justified)**
- Train on (raw_snapshot → analysis) pairs — teach it what the fields mean and how they interact
- Then in production: LLM sees scorecard + raw snapshot → trained understanding + observer scores
- Pro: LLM genuinely understands the data, spots cross-module patterns observers miss
- Con: Training cost + maintenance. Need to retrain when modules change.

**Approach C: Hybrid — train a small "interpreter" model**
- Train a small model (8B) specifically to read raw snapshots → produce a "deep analysis" summary
- Feed that summary (not raw JSON) into the Advocate/Skeptic alongside scorecard
- Pro: Fast (8B), specialized, doesn't slow down debate. Separates "understanding" from "arguing."
- Con: Two models in the pipeline. More complexity.

**Recommendation**: Approach D (below) supersedes A/B/C based on production architecture insight.

### Approach D: Use Existing LLM Analysis Stream (Best Path — 2026-03-11)

> **Key insight**: The production Rockit platform ALREADY runs LLM analysis every 5 min on raw deterministic data. By signal time, there are 3-12 slices of pre-computed LLM analysis available. Advocate/Skeptic don't need raw JSON — they need the LLM's own analysis output.

**Production architecture (already running)**:
```
Every 5 min:  Raw deterministic (38 modules) → Qwen3.5 → LLM analysis → GCS bucket
              ↓
RockitUI:     Dashboard visualizes LLM analysis (12 tabs: Brief, Logic, Intraday, etc.)
              ↓
Gemini:       Reviews accumulated LLM outputs → HTF analysis + trade ideas
```

**What the agent pipeline should tap into**:
```
Signal fires at 10:15 →
  Scorecard: evidence cards (9 cards, ~500 tokens)
  + LLM analyses from 9:35, 9:40, 9:45, 9:50, 9:55, 10:00, 10:05, 10:10, 10:15
    (each is a pre-digested summary, not raw JSON)
  + DuckDB historical stats
  → Advocate/Skeptic debate
```

**Why this is the right path**:
1. **LLM work is amortized** — analysis happens on a timer, not on the signal's critical path
2. **Context is small** — LLM summaries are 500-1K tokens each, vs 4K+ raw JSON
3. **No training needed** — the LLM output IS the interpretation of raw data
4. **Progressive context** — agents see HOW analysis evolved over the session (bullish at 9:35, weakening by 10:00, bearish by 10:15)
5. **Already proven** — this is what the production dashboard shows and what Gemini synthesizes from

**What Advocate/Skeptic need from LLM stream**:
- Last 3-6 snapshot analyses (not all — most recent captures the evolving picture)
- Key fields: market_structure_assessment, bias_direction, key_levels, risk_factors, trade_ideas
- NOT the full ROCKIT_v5.6 output — trimmed to decision-relevant fields

**Two-tier model strategy for agents**:
- **Tier 1 (Qwen3.5 local)**: Produces 5-min analysis stream (already running). Also powers Advocate/Skeptic debate (fast, local)
- **Tier 2 (Gemini/Opus API)**: Periodic synthesis of accumulated analyses → meta-observations, HTF analysis, trade ideas. This is the "frontier review" layer — not per-signal, but per-session or per-hour

**Implementation plan**:
1. Add LLM analysis stream to backtest replay — simulate what production generates every 5 min
   - Option: Pre-generate analysis for all 270 sessions (like training pairs), store in DuckDB `llm_analyses` table
   - Option: Pull from existing GCS bucket if historical analyses exist
2. In `pipeline.py:_run_debate()`, inject last N LLM analyses into debate context
3. Advocate/Skeptic prompts get: scorecard + LLM analysis trail + historical stats
4. Benchmark: does LLM analysis stream improve decision quality over scorecard-only?

**Training decision (revised)**:
- Training Qwen3.5 to better interpret deterministic data → improves the 5-min analysis stream quality
- Better stream → better context for Advocate/Skeptic → better decisions
- So training is about improving the ANALYST, not the DEBATERS
- Decision: If base Qwen3.5 analysis quality is already good enough for agents to make correct decisions, skip training. If analysis misses important patterns (e.g., doesn't flag wick parades, misreads TPO shapes), train to fix those gaps.

### The Courtroom Analogy — Agent Pipeline as Legal Process (2026-03-11)

> **Principle**: Don't make the lawyers read forensic reports. Train expert witnesses. Lawyers argue from testimony.

| Legal Role | Pipeline Role | What They Do | Speed |
|------------|--------------|--------------|-------|
| **Domain Experts** | Deterministic modules (38) | Specialized factual testimony: "IB extended 1.8×", "4 wick rejections at VAH", "DPOC migrating up" | <10ms |
| **Observer / Eyewitness** | Trained Qwen3.5 (trader's voice) | Interprets what experts report: "I see a P-shape forming, sellers trapped above POC, this is a fade setup" — trained on USER's analysis style, captures nuance + caution | ~5s/snapshot |
| **Advocate Lawyer** | Advocate Agent (LLM) | Argues FOR the trade using expert data + eyewitness account | ~50s |
| **Defense Lawyer** | Skeptic Agent (LLM) | Challenges the case: "But the eyewitness noted declining delta, and the IB expert says extension is weak" | ~60s |
| **Judge** | Orchestrator (deterministic) | Rules based on both arguments, scorecard-based | <10ms |

**Key distinction**:
- **Domain experts** = facts (objective, deterministic, authoritative, fast)
- **Analyst** = trained interpretation (domain expert + trader's voice — knows Dalton theory, Market Profile, 8 strategies, caution-over-conviction). Trained on user's analysis style via LoRA.
- **Lawyers** = argumentation (don't need to be domain experts OR analysts — argue from testimony)
- Training the LLM = training the analyst to interpret data the way the trader does
- The training data IS the trader's voice — "here's what I see and what it means" with nuance and caution

**Efficiency principle — "Court convenes on demand"**:
```
ALWAYS RUNNING (timer, amortized, cheap):
  Every 5 min: Deterministic experts (38 modules, <10ms)
             → Trained LLM analyst (your voice, ~5s)
             → Analysis cached (DuckDB / GCS)
  By 10:30: 12 analyst reports already filed, session context built

ON-DEMAND ONLY (signal trigger OR user query):
  Signal fires at 10:15 → Court convenes
    Cached analyst testimony (last 3-6 reports) + Scorecard
    → Advocate argues FOR → Skeptic challenges → Judge rules
    → TAKE / SKIP / REDUCE_SIZE
    Total: ~2 min

  User asks at 10:45 "what do you see?" → Court convenes on demand
    Same flow, but no signal — pure analysis response
    15 analyst reports already in the file
    → Rich synthesis without waiting for fresh LLM inference

  No signal, no query → No trial. Court is idle. Zero cost.
```

**Why this is efficient**:
- Analyst work is amortized (runs on 5-min timer regardless)
- Advocate/Skeptic/Judge only spin up when there's a case
- ~80% of sessions have 0-2 signals → court convenes 0-2 times
- UI can query the analyst stream directly without convening court (dashboard use case)
- Court can also convene for user queries (not just signals) — "should I take this setup?" gets the full debate treatment on demand

**Key insight**: The expert witness (trained LLM) does its work on a TIMER (every 5 min), not on the signal's critical path. By the time a signal fires, the expert has already produced 3-12 reports covering the session's evolution. The lawyers just reference those reports.

**Phased execution (chicken-and-egg resolved)**:

```
Phase A (NOW — in progress):
  Run E backtest: Agents with scorecard ONLY (no LLM analysis stream)
  Question: Do agents add alpha over mechanical filters?
  ↓
Phase B (NEXT):
  Train Qwen3.5 as expert witness (LoRA on deterministic → analysis pairs)
  Generate 5-min LLM analysis for all 270 backtest sessions
  Store in DuckDB: llm_analyses table (session_date, snapshot_time, analysis_json)
  ↓
Phase C (THEN):
  Re-run backtest with agents seeing scorecard + expert witness testimony
  Advocate/Skeptic prompts get last 3-6 LLM analyses alongside evidence cards
  ↓
Phase D (COMPARE):
  Run E (scorecard only) vs Run F (scorecard + expert witness)
  Quantify: does expert testimony improve agent decisions?
  If delta < 2% → expert witness adds noise, keep scorecard-only
  If delta > 5% → expert witness is essential, training justified
  If delta 2-5% → benchmark smaller/faster expert models
```

**What NOT to do**:
- Don't feed raw deterministic JSON to lawyers (too much context, too slow)
- Don't train the lawyers (Advocate/Skeptic) — they argue from prompts, not training
- Don't use one model for everything — separate expert witness (trained, fast, 5-min timer) from lawyers (untrained, prompted, signal-time only)
- Don't burden lawyers with full expert reports — trim to key findings relevant to the signal

**Decision gate**: After Run E results + model benchmark:
1. If LLM debate adds <2% WR over deterministic-only → skip training, focus on mechanical filters
2. If LLM debate adds 2-5% WR AND a smaller model matches → use smaller model, no training
3. If LLM debate adds >5% WR AND quality degrades with smaller models → train the smallest model that preserves quality
4. If training a smaller model (8B) matches untrained 35B quality → train the 8B, get speed + quality

**Recommendation**: Run E results first, then model benchmark, then decide. Don't train until the data justifies it.

### Migration Checklist
- [ ] Install vLLM on spark-ai
- [ ] Download/convert qwen3.5:35b-a3b weights for vLLM (GGUF → HF format, or pull from HuggingFace directly)
- [ ] Launch vLLM with 128K context + 8K max output
- [ ] Validate: run same 5-session test, compare debate quality to Ollama baseline
- [ ] Add `--session-range` arg to `ab_test_agents.py` (Option A parallelization)
- [ ] Run parallel backtest: 3 chunks × 90 sessions → merge results
- [ ] Update `configs/filters.yaml` with vLLM endpoint
- [ ] Update deploy script (replace `deploy-128k.sh` with vLLM systemd service)
