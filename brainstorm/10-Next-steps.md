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

> **Status**: TODO — HIGH PRIORITY (user uses trendline 3rd touch as a core entry signal)
> **Date updated**: 2026-03-12
> **Evidence**: User identified "3rd touch of trendline" as a key reversal signal on 2026-03-12 (London Low rejection). Flagged as SYSTEM GAP in session reviews for both 2026-03-11 and 2026-03-12.

**What**: Algorithmic trendline detection and interaction tracking. Key events: 3rd touch (confirmation/reversal), backside test (support becomes resistance), and break + retest.

**How the user draws trendlines** (this is what we need to replicate):
- Connect **wicks** (highs or lows), NOT closes — the extremes matter, not the bodies
- **Ascending trendline**: Connect 2+ higher lows (wick lows) → draw line through them → project forward
- **Descending trendline**: Connect 2+ lower highs (wick highs) → draw line through them → project forward
- **Timeframes**: 5-min, 15-min, 1H, 4H, daily — all valid. Intraday trendlines on 5/15min are most actionable for day trading. HTF (1H, 4H, daily) provide context/confluence.
- **3rd touch = the trade**: When price approaches the trendline for the 3rd time, it's either a high-probability bounce (continuation) or a high-probability break (reversal). Either way, it's actionable.

#### The 3rd Touch Study (Backtest Research)

> **Goal**: Quantify the edge of trendline 3rd touches across 270 sessions. Does the 3rd touch predict reversals or continuations? What's the WR by timeframe?

**Study design**:
1. Detect all trendlines on 5min, 15min, 1H timeframes across 270 NQ sessions
2. For each trendline that reaches 3+ touches, record:
   - Touch number (3rd, 4th, 5th...)
   - Outcome: **bounce** (continuation in trendline direction) or **break** (price closes through)
   - If bounce: how far did price move in the bounce direction? (MFE)
   - If break: how far did price move through? Was there a backside retest?
   - Context at touch time: day type, bias, IB range, delta, time of day
3. Build a "3rd touch signal" and backtest:
   - Entry: At trendline touch with rejection candle confirmation
   - Direction: Same as trendline direction (ascending TL → LONG on 3rd touch, descending TL → SHORT)
   - Stop: Beyond the trendline (break would invalidate)
   - Target: Prior swing high/low or fixed R:R

**Key questions**:
- What % of 3rd touches produce bounces vs breaks? (hypothesis: >60% bounce)
- Does timeframe matter? (15min trendline 3rd touch more reliable than 5min?)
- Does confluence with other levels improve accuracy? (3rd touch AT London High = stronger signal)
- Can we combine 3rd touch with IB Retracement? (retracement to 50-61.8% zone that ALSO aligns with a trendline = high conviction)

#### Detection Approach

**Step 1: Swing Point Detection** (dependency on 2.6)
- Detect swing highs and swing lows using N-bar lookback fractals
- Use WICKS (high for swing highs, low for swing lows), not closes
- Configurable lookback: 3 bars for 5min, 5 bars for 15min, 8 bars for 1H
- Minimum swing size: > 0.3× ATR to filter noise

**Step 2: Trendline Fitting**
```python
def detect_trendlines(swing_points, timeframe, direction):
    """
    Connect swing lows (ascending) or swing highs (descending).
    Use wick prices, not closes.

    Algorithm (swing-to-swing, simplest and most accurate for this use case):
    1. For each pair of swing lows (ascending) or swing highs (descending):
       a. Draw a line through the two points
       b. Project forward
       c. Check if any subsequent swing points touch the line (within tolerance)
       d. Count touches
       e. Reject if any candle CLOSES beyond the line between touches (broken)
    2. Rank trendlines by: touch_count (more = stronger), recency, slope consistency
    3. Keep top N active trendlines (avoid clutter)

    Tolerance for "touch":
    - Price wick within 0.2× ATR of the projected trendline value at that bar
    - OR within 5 points (NQ), whichever is larger
    - Must not double-count: touches must be separated by >= 3 bars
    """
```

**Step 3: Touch Event Tracking**
```python
@dataclass
class TrendlineTouch:
    trendline_id: str
    touch_number: int          # 1st, 2nd, 3rd...
    touch_time: str
    touch_price: float         # wick price that touched
    trendline_price: float     # projected line value at that time
    distance_pts: float        # how close the wick got
    outcome: str               # 'bounce' | 'break' | 'pending'
    bounce_mfe: float          # max move in bounce direction (pts)
    break_distance: float      # if broke, how far through (pts)
    rejection_candle: bool     # was the touch bar a rejection pattern?
    context: dict              # day_type, bias, IB status, delta, etc.
```

**Step 4: Real-Time 3rd Touch Alert**
```python
def check_approaching_3rd_touch(bar, active_trendlines):
    """
    At each bar, check if price is approaching any 2-touch trendline.

    Alert when:
    - Trendline has exactly 2 confirmed touches
    - Current price is within 1.0× ATR of projected trendline value
    - Price is moving TOWARD the trendline (closing the distance)

    This is the "3rd touch approaching" signal that the agent pipeline
    can evaluate — should we expect a bounce or a break?
    """
```

**Step 5: No Lookahead (Critical for Backtesting)**
- Trendline is only "valid" after 2nd touch is confirmed
- 3rd touch signal fires when price APPROACHES — decision made before outcome known
- Cannot use future bars to determine if a touch will bounce or break
- Rolling window: at each bar, maintain list of currently-valid trendlines
- Invalidation: trendline broken (close beyond) → remove from active list

#### Multi-Timeframe Approach

The same algorithm runs on different bar sizes:

| Timeframe | Bar Source | Swing Lookback | Min Swing Size | Touch Tolerance | Use Case |
|-----------|-----------|---------------|----------------|-----------------|----------|
| 5-min | Resample 1-min → 5-min | 3 bars (15 min) | 15 pts | 0.15× ATR or 5 pts | Intraday precision entries |
| 15-min | Resample 1-min → 15-min | 5 bars (75 min) | 30 pts | 0.20× ATR or 8 pts | Primary intraday trendlines |
| 1-hour | Resample 1-min → 60-min | 5 bars (5 hours) | 60 pts | 0.25× ATR or 15 pts | Session-level structure |
| 4-hour | Requires multi-session data | 5 bars (20 hours) | 100 pts | 0.30× ATR or 20 pts | Multi-day context |
| Daily | Requires multi-session data | 5 bars (1 week) | 150 pts | 0.30× ATR or 30 pts | Weekly trend structure |

**Intraday priority**: 15-min is likely the sweet spot — long enough to filter noise, short enough to catch intraday trendlines that matter for 10:00-12:00 trading.

#### Output Schema

```python
{
    "active_trendlines": [
        {
            "id": "tl_15m_asc_0945_1015",
            "type": "ascending",              # ascending / descending
            "timeframe": "15min",
            "anchor_points": [
                {"price": 21300, "time": "09:45", "type": "swing_low"},
                {"price": 21380, "time": "10:15", "type": "swing_low"},
            ],
            "slope_per_bar": 5.33,            # points per bar
            "slope_per_hour": 21.33,          # points per hour (normalized)
            "touch_count": 2,
            "current_trendline_price": 21420.0,
            "price_distance": 30.0,           # current wick - trendline
            "price_distance_atr_pct": 0.2,
            "status": "active",               # active / broken / retesting
            "approaching_3rd_touch": True,
            "bars_since_last_touch": 8,
            "strength": 0.75,                 # composite: touches × recency × slope consistency
        }
    ],
    "recent_events": [
        {
            "event": "3rd_touch_approaching",
            "trendline_id": "tl_15m_asc_0945_1015",
            "time": "11:00",
            "projected_touch_price": 21450.0,
            "distance_remaining": 12.0,
        },
        {
            "event": "3rd_touch_confirmed",
            "trendline_id": "tl_15m_asc_0945_1015",
            "time": "11:05",
            "touch_price": 21448.0,
            "rejection_candle": True,
            "outcome": "bounce",
        },
    ],
}
```

#### Integration with Agent Pipeline

The 3rd touch approaching event feeds directly into the agent pipeline:

```
Trendline module detects "3rd touch approaching" on 15-min descending trendline
  → Creates evidence card: {category: "trendline", direction: "bearish", strength: 0.8,
     summary: "3rd touch of 15-min descending trendline at 24903, price 12 pts away"}
  → If aligned with IB Retracement zone: confluence boost (+0.2 strength)
  → If aligned with London level: confluence boost (+0.15 strength)
  → Advocate/Skeptic debate: "3rd touch + London rejection + IB retrace zone = high conviction SHORT"
```

**This is the missing piece from 2026-03-12**: You saw the 3rd touch of the descending trendline at London Low, the system saw nothing. With this module, the agent would have generated a bearish evidence card that could have helped SKIP the losing 20P trade (which was trying to extend SHORT past an exhaustion point where the trendline said "no more").

#### Research Agent Findings (2026-03-12)

> Research complete. Key recommendations below. Full pseudocode and references in research output.

**Best Algorithm: Iterative Swing-to-Swing (Recommended)**

The research evaluated 3 approaches:
1. **Iterative swing-to-swing** — RECOMMENDED. Maps directly to how you draw trendlines. Connect each pair of swing lows (ascending) or swing highs (descending), validate no close breaches in between, count touches. O(S²×N) where S=10-30 swings per session. Fast enough (~2-3 sec/session).
2. **RANSAC (sklearn)** — Good for noisy data, finds best-fit line ignoring outliers. But finds ONE line at a time, needs iterative removal.
3. **Hough Transform (trendln library)** — Finds ALL lines at once. But operates on full series = **lookahead bias**. Not safe for bar-by-bar backtesting.

**Swing Detection: Causal Rolling Window (No Lookahead)**

```python
def detect_swing_points_causal(df, left=5, right=2):
    """
    Uses WICKS (high/low), not closes.
    left=5: looks back 5 bars. right=2: needs 2 bars of confirmation.
    Swing at bar i is confirmed and actionable at bar i+right.
    NO lookahead.
    """
    for i in range(left, len(df) - right):
        window_high = df['high'].values[i - left : i + right + 1]
        if df['high'].values[i] == window_high.max():
            swing_highs.append(i)  # confirmed at bar i+right

        window_low = df['low'].values[i - left : i + right + 1]
        if df['low'].values[i] == window_low.min():
            swing_lows.append(i)  # confirmed at bar i+right
```

**Tuning by timeframe**:

| Timeframe | swing_left | swing_right | min_touch_gap | touch_tolerance | TF weight |
|-----------|-----------|-------------|---------------|-----------------|-----------|
| 5-min | 5 (25 min) | 2 (10 min) | 3 bars (15 min) | 0.15× ATR or 5 pts | 0.5 |
| 15-min | 4 (60 min) | 2 (30 min) | 2 bars (30 min) | 0.20× ATR or 8 pts | 0.7 |
| 1-hour | 3 (3 hr) | 2 (2 hr) | 2 bars (2 hr) | 0.25× ATR or 15 pts | 1.0 |
| 4-hour | 2 (8 hr) | 1 (4 hr) | 1 bar (4 hr) | 0.30× ATR or 20 pts | 1.3 |
| Daily | 3 (3 day) | 2 (2 day) | 1 bar (1 day) | 0.30× ATR or 30 pts | 1.5 |

**Touch Counting Anti-Double-Count**: Touches within `min_touch_gap` bars are merged. Prevents counting 3 bars hugging the line as 3 separate touches.

**Bounce vs Break Classification**: After touch detected, wait `confirm_bars=2` bars. All closes stay on the right side = bounce. All closes cross = break. Mixed = contested (wait).

**Rejection Pattern Scoring** at 3rd touch:
- Long lower wick (>50% of range) at ascending trendline = +0.4
- Close near bar high = +0.3
- Bullish engulfing = +0.3
- Score > 0.6 = strong rejection confirmation

**Avoiding Lookahead — Critical Rules**:

| Concern | Solution |
|---------|----------|
| Swing confirmation | Swing at bar `i` actionable at bar `i + swing_right` only |
| Trendline creation | Only when 2nd anchor swing is confirmed |
| Touch detection | Bar-by-bar, only data up to current bar |
| Higher TF data | Only process after bar closes (15-min bar at :15, :30, :45, :00) |
| **trendln / pytrendline** | **NOT safe** for backtesting — operate on full series |

**Implementation Target**: New deterministic module at `rockit_core/deterministic/modules/trendline_detection.py`. Same pattern as `fvg_detection.py` — resample internally to 5min/15min/1H, run detection, return dict.

**Libraries**: Only need numpy + pandas + scipy (already in stack). `trendln` useful for offline visualization only, NOT for backtest.

**Performance**: ~2-3 sec/session for 270 sessions across all timeframes. Not blocking.

**Trendline Ranking** (when multiple valid lines exist):
- Touch count × 20 (more touches = stronger)
- Recency bonus: max(0, 50 - age_in_bars)
- Timeframe weight multiplier (daily=1.5×, 15min=0.7×)
- Regularity: evenly-spaced touches score higher (coefficient of variation penalty)
- Moderate slope bonus (very steep or very flat = weaker)

**Key References**:
- `scipy.signal.argrelextrema` — fast swing detection (needs lookahead offset for backtest use)
- `pytrendline` — exhaustive scan with scoring (study the algorithm, don't use the library in production)
- `freqtrade/technical/trendline.py` — production trendline code in a real trading bot
- `sklearn.linear_model.RANSACRegressor` — robust fitting through noisy swings

**Dependencies**: Requires swing point detection (2.6) for anchor points.

### 2.8 Implementation Priority

These modules build on each other:

```
2.6 Swing Points  ──→  2.7 Trendlines + 3rd Touch Study  ──→  feeds into all pattern detection
        │                        │
        │                        └──→  IB Retracement (trendline confluence)
        │
        └──→  2.5 SMT Divergence (requires swing points on multiple instruments)
```

**Recommended order**:
1. **Swing points first** (2.6) — foundational, everything else needs it
2. **Trendlines + 3rd touch study** (2.7) — depends on swing points. HIGH PRIORITY — user trades this daily
3. **SMT last** (2.5) — depends on swing points + multi-instrument data

**Data requirements**:
- Swing points: Current instrument only, uses existing 1-min bars
- Trendlines: Current instrument only, uses swing points. Needs resampled bars (5min, 15min, 1H)
- SMT: Needs ES + YM data loaded alongside NQ (requires multi-instrument loader enhancement)

---

## NEW STRATEGY: IB Retracement Entry (50-61.8% Fib of IB Range)

> **Status**: TODO — HIGH PRIORITY (user trades this consistently and profitably)
> **Date added**: 2026-03-12
> **Evidence**: User executed this on both 2026-03-11 and 2026-03-12 with winning results. Identified as SYSTEM GAP in session reviews.

### Concept

After the Initial Balance (IB) forms at 10:30, wait for price to retrace 50-61.8% of the IB range in the direction of the impulsive move, then enter in the impulse direction.

**The setup**:
1. IB forms with a clear directional impulse (not a tight rotation)
2. One side of the IB was created by an impulsive move (sweep of London high/low, OR extension, etc.)
3. Price retraces to the 50-61.8% fib of the IB range (or to VAH/VWAP if those levels coincide)
4. Enter in the direction of the impulse, targeting IB low/high extension or lower/higher discovery

**Example (2026-03-11)**:
- IB formed with extreme range (201 pts), impulse was SHORT (London High rejected, swept down)
- User waited for 50% retracement of IB range (price swept above VWAP, failed back down)
- Shorted at 50-61.8% zone → target IB LOW → WIN

**Example (2026-03-12)**:
- IB formed extreme (204 pts), impulse SHORT (London Low break + acceptance)
- 50-61.8% pullback into 5-min FVG tap
- Shorted on retracement → target IB LOW extension

### Entry Logic (Draft)

```
TRIGGER: After IB close (10:30 ET)
DIRECTION: Determined by session directional bias (see below)

IF direction == SHORT:
    entry_zone_high = IB_LOW + 0.618 * IB_RANGE  (upper fib)
    entry_zone_low  = IB_LOW + 0.500 * IB_RANGE  (lower fib)
    ENTRY: Price enters zone AND shows rejection (close back below zone)
    STOP: Above IB HIGH (or above entry_zone_high + buffer)
    TARGET: IB LOW retest → extension below IB LOW (1.5-2x IB range)

IF direction == LONG:
    entry_zone_low  = IB_HIGH - 0.618 * IB_RANGE
    entry_zone_high = IB_HIGH - 0.500 * IB_RANGE
    ENTRY: Price enters zone AND shows rejection (close back above zone)
    STOP: Below IB LOW (or below entry_zone_low - buffer)
    TARGET: IB HIGH retest → extension above IB HIGH
```

### Key Challenge: Determining Session Directional Bias

This strategy ONLY works if you correctly identify the impulse direction. The retracement is a continuation trade — wrong direction = catching a knife.

**Bias determination signals (ranked by reliability)**:

| Signal | Weight | How We Detect It | Status |
|--------|--------|-------------------|--------|
| **London session sweep + rejection** | HIGH | Price swept London High/Low then reversed hard | Have London levels; need sweep detection |
| **OR direction (A+B periods)** | HIGH | Which way did the first 30 min move? Impulse up or down? | Have OR high/low |
| **IB extension direction** | HIGH | Did price extend beyond IBH or IBL first? Which side has the impulse? | Have IB metrics |
| **VWAP slope at IB close** | MEDIUM | Rising VWAP = bullish impulse, falling = bearish | Have VWAP |
| **Delta cumulative direction** | MEDIUM | Net buying vs selling pressure through IB formation | Have delta |
| **Prior day VA gap** | MEDIUM | Open above/below prior VA → directional bias | Have prior VA |
| **Overnight session direction** | MEDIUM | Overnight bearish + London rejection = continuation SHORT | Have ON levels |
| **3-vote regime bias** | LOW | EMA20 vs EMA50 (2x), prior session (1x), price vs VWAP (1x) | Have regime_bias |

**Composite bias score (proposed)**:
```python
def compute_ib_impulse_direction(session_context, ib_data):
    """Determine the impulse direction during IB formation.

    Returns: ('LONG', confidence) or ('SHORT', confidence)
    """
    votes = []

    # 1. Which side of IB was the impulse? (strongest signal)
    #    If price swept IBH first then crashed to IBL → impulse SHORT
    #    If price swept IBL first then rallied to IBH → impulse LONG
    ib_first_extreme = detect_ib_first_extreme(ib_data)  # NEW MODULE NEEDED
    if ib_first_extreme == 'high_first':
        votes.append(('SHORT', 2.0))  # high made first → reversal down = impulse short
    elif ib_first_extreme == 'low_first':
        votes.append(('LONG', 2.0))

    # 2. London sweep direction
    if price_swept_london_high_and_rejected:
        votes.append(('SHORT', 1.5))
    elif price_swept_london_low_and_rejected:
        votes.append(('LONG', 1.5))

    # 3. C-period close direction (first 5-min bar after OR)
    #    C-period close below OR low = bearish impulse emerging
    c_close = session_context.get('c_period_close')
    if c_close < or_low:
        votes.append(('SHORT', 1.0))
    elif c_close > or_high:
        votes.append(('LONG', 1.0))

    # 4. VWAP slope at IB close
    vwap_slope = session_context.get('vwap_slope_at_ib')  # NEW: need to compute
    if vwap_slope < -0.5:
        votes.append(('SHORT', 0.8))
    elif vwap_slope > 0.5:
        votes.append(('LONG', 0.8))

    # 5. Delta cumulative at IB close
    delta = session_context.get('delta_cumulative_at_ib')
    if delta < -threshold:
        votes.append(('SHORT', 0.7))
    elif delta > threshold:
        votes.append(('LONG', 0.7))

    # 6. Overnight + prior VA context
    if overnight_bearish and open_below_prior_val:
        votes.append(('SHORT', 0.5))

    # Weighted vote → direction + confidence
    long_score = sum(w for d, w in votes if d == 'LONG')
    short_score = sum(w for d, w in votes if d == 'SHORT')
    total = long_score + short_score

    if short_score > long_score:
        return ('SHORT', short_score / total if total > 0 else 0)
    else:
        return ('LONG', long_score / total if total > 0 else 0)
```

**Minimum confidence threshold**: Only take the trade if confidence > 0.65 (strong directional agreement).

### Entry Refinements (from user's execution style)

1. **FVG confluence**: User often waits for 50-61.8% zone to align with a 5-min FVG → higher precision entry
2. **VWAP as confirmation**: If VWAP is in the fib zone, price sweeping above/below VWAP and failing back = strong confirmation
3. **2nd push failure filter**: If the 2nd push beyond IB extreme fails to make new lows/highs → DON'T take the extension (2026-03-12 lesson)
4. **Level confluence**: Entry zone near Asia Low, London level, or prior day VA edge = higher conviction

### Filters & Guards

- **IB range minimum**: IB must be > 100 pts (extreme or wide IB). Narrow IB = no clear impulse.
- **Not a rotation day**: If IB formed via tight rotation (both sides tested equally), skip. Need clear one-sided impulse.
- **Time window**: Entry between 10:30 (IB close) and 12:00. After 12:00, the retracement setup loses edge.
- **Max 1 trade/session**: One IB retracement per session.
- **Day type filter**: Works best on trend days and P-days. Avoid on B-days and neutral days (no impulse to retrace).

### What We Need to Build

| Component | Status | Notes |
|-----------|--------|-------|
| IB impulse direction detector | NEW | Which extreme formed first? Sweep + rejection detection |
| London sweep detection module | NEW | Did price sweep London H/L then reverse? (also feeds trendline module) |
| VWAP slope at IB close | NEW | Simple: VWAP value change over IB period |
| Composite bias scorer | NEW | Weighted vote system (code above) |
| 50-61.8% fib zone calculator | EASY | Pure math from IB high/low |
| FVG confluence check | PARTIAL | Have FVG detection; need to check if FVG overlaps fib zone |
| 2nd push failure detection | NEW | Detect failed continuation beyond IB extreme (prevents 20P-style traps) |

### Relationship to Existing Strategies

- **Distinct from 20P IB Extension**: 20P enters on the BREAKOUT (3 closes beyond IB). IB Retracement enters on the PULLBACK after the impulse. Different entry logic, different timing.
- **Distinct from 80P Rule**: 80P is a prior-day VA mean reversion. IB Retracement is an intraday impulse continuation.
- **Complementary to OR Rev**: OR Rev catches the initial reversal at OR extreme. IB Retracement catches the continuation after IB forms. They can fire on the same session (OR Rev at 9:45, IB Retrace at 10:45).
- **Overlaps with disabled P-Day IBH retest**: P-Day's IBH retest (31.2% WR) failed because it retested the IB boundary, not the 50% zone. This strategy targets the deeper pullback zone which has better R:R.

### Backtest Priority

**HIGH** — User trades this consistently on live sessions. If backtested at even 50% WR with 2R target, the expectancy would be strong. The key differentiator is the directional bias determination — if we get that right, this could be one of the highest-conviction strategies.

**Proposed backtest plan**:
1. Build the strategy with the composite bias scorer
2. Backtest on all 270 sessions
3. Compare: IB Retracement WR when bias confidence > 0.65 vs < 0.65
4. If the bias scorer works, this validates the directional bias determination for ALL strategies (not just this one)

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

---

## Run E Results & Findings (2026-03-11)

> **Full 270-session LLM debate backtest completed.** ~6.5 hours sequential on Ollama/Qwen3.5:35b-a3b.
> **Report**: `reports/backtest_NQ_20260311_192328_f401a8.md`
> **Report skill**: `/backtest-report` — consistent post-backtest analysis (12 steps, trade classification, agent decisions, filtered signal analysis, pattern discovery)

### Run E Portfolio Results

| Metric | Run A (No Filter) | Run B (Mech Only) | Run E (Mech+Agent+LLM) |
|--------|-------------------|-------------------|------------------------|
| Trades | 408 | 259 | 179 |
| Win Rate | 56.1% | 61.0% | **66.5%** |
| Profit Factor | 2.45 | 3.07 | **3.58** |
| Net PnL | $159,332 | $125,885 | **$92,909** |
| Expectancy | $390 | $486 | **$519** |
| Max Win Streak | — | — | 10 |
| Max Loss Streak | — | — | 5 |

### Per-Strategy Results (Run E)

| Strategy | Trades | WR | PF | PnL | Study Target | Status |
|----------|--------|-----|-----|------|-------------|--------|
| OR Rev | 52 | **75.0%** | 5.25 | $50,064 | 64.4% | EXCEEDS +10.6pp |
| OR Accept | 74 | **66.2%** | 3.66 | $22,329 | 59.9% | EXCEEDS +6.3pp |
| 20P | 32 | **56.2%** | 2.93 | $16,542 | 45.5% | EXCEEDS +10.7pp |
| B-Day | 20 | 65.0% | 2.01 | $5,655 | 82.0% | BELOW -17pp |
| 80P | 1 | 0.0% | 0.0 | -$1,682 | 42.3% | BROKEN |

### Key Findings

**1. LLM debate adds alpha over mechanical filters**
- Run E (66.5% WR, PF 3.58) vs Run B mechanical-only (61.0% WR, PF 3.07)
- +5.5pp WR improvement, +0.51 PF improvement
- Trade count dropped from 259 → 179 (LLM filtered 80 additional signals)
- Expectancy improved $486 → $519/trade

**2. 80P Rule destroyed by AntiChase filter — MUST FIX**
- AntiChase filter killed 53/72 80P signals BEFORE LLM ever saw them
- Only 1 trade survived all filters (and it lost)
- Filtered trades had $22,286 net profit — left on table
- **Root cause**: AntiChase blocks "contrarian strategies chasing momentum" but 80P SHORT + Bearish bias (67% WR, +$27K in baseline) is legitimate, not chasing
- **Fix**: Remove 80P from AntiChase filter rules in `configs/filters.yaml`

**3. Filters removing $65K in net profitable trades**
- 234 trades filtered (112W / 122L, net $65,371 profit)
- OR Rev: 51 filtered, $25,451 net profit removed
- 80P: 71 filtered, $22,286 net profit removed
- Filters are net positive (removing more losses than wins overall) BUT over-aggressive on certain strategies

**4. Time-of-day pattern: 10:00 hour dominates**
- 10:00 hour: 141 trades, 68.1% WR, $78,281 (84% of total PnL)
- 11:00 hour: 30 trades, 56.7% WR, $9,619
- After 12:00: 8 trades, minimal impact
- Confirms "first hour is the money" principle

**5. Day type performance**
- Trend Down: 11 trades, **90.9% WR**, $12,787 (best regime)
- Trend Up: 12 trades, 75.0% WR, $5,979
- Neutral Range: 114 trades, 64.0% WR, $54,778 (bulk of volume)
- Balance: 15 trades, 60.0% WR, $6,190

**6. MAE/MFE insight: Winners vs Losers**
- Winners: Avg MAE 5.7 pts, Avg MFE 90.7 pts (barely go against you)
- Losers: Avg MAE 58.0 pts, Avg MFE 14.0 pts (go against you hard, never recover)
- Edge ratio is excellent — winners run, losers are identified early

**7. Agent decision persistence gap (FIXED in code, needs re-run)**
- Advocate/Skeptic thesis, confidence, warnings, card admit/reject were NOT being saved to DuckDB
- Added 10 columns to `agent_decisions` table: advocate_thesis, advocate_direction, advocate_confidence, skeptic_thesis, skeptic_direction, skeptic_confidence, skeptic_warnings, debate_cards_admitted, debate_cards_rejected, instinct_cards
- Updated `persist_agent_decision()` to extract from `debate` context dict
- **Next backtest will capture full debate reasoning for post-hoc analysis**

**8. Agent decision data quality issues**
- `strategy_name` showing "unknown" in SKIP decisions — not populated for filtered signals
- `session_date` blank in some SKIP records
- `actual_outcome` / `was_correct` not linked for TAKE decisions (backfill logic needs fix)
- `max_drawdown` stored as $1.41 — clearly a persistence bug in backtest_runs

### Immediate TODO (Before Next Backtest)

- [ ] **Fix AntiChase filter**: Remove 80P from AntiChase rules in `configs/filters.yaml`
- [ ] **Fix agent decision persistence**: Ensure strategy_name, session_date populated for ALL decisions (TAKE + SKIP)
- [ ] **Fix was_correct backfill**: Link agent TAKE decisions to trade outcomes
- [ ] **Fix max_drawdown persistence**: Investigate $1.41 value in backtest_runs
- [ ] **Re-run backtest** with debate context persistence to capture SKIP reasoning
- [ ] **Run `/backtest-report`** on new run to verify debate columns populated

### Next Phase: What Run E Tells Us

1. **LLM debate IS adding alpha** — 5.5pp WR improvement over mechanical filters alone justifies the pipeline
2. **Mechanical filters need tuning** — AntiChase too aggressive on 80P, possibly OR Rev too
3. **Speed is the bottleneck** — 6.5 hours for 270 sessions. vLLM migration + Option D (skip obvious signals) could cut to <1 hour
4. **Debate reasoning must be captured** — can't improve what you can't measure. Schema fix done, needs re-run
5. **Phase B (train analyst)** decision: LLM debate adds >5% WR → training the analyst IS justified (per decision gate above). But first: model benchmark to see if a smaller/faster model matches Qwen3.5:35b quality

---

## Expert Domain Refactoring — Deterministic Intelligence Upgrade

> **Status**: TODO — Planning document
> **Date**: 2026-03-12
> **Depends on**: Run E results (complete), Courtroom Analogy architecture (above)
> **Goal**: Reorganize 38+ deterministic modules into specialized Expert Domains that produce focused, high-signal evidence cards — replacing the current coarse ProfileObserver + MomentumObserver with 6-8 domain-specific expert observers.

### The Problem: Information Loss in the Observer Layer

The current agent pipeline reduces 38 deterministic modules down to **9 evidence cards** through two observers:

```
38 deterministic modules (9,200 LOC, <10ms total)
    ↓
ProfileObserver → 4 cards (TPO shape, VA position, POC position, poor extremes)
MomentumObserver → 5 cards (DPOC regime, trend strength, wick traps, IB extension, bias alignment)
    ↓
Orchestrator sees 9 cards → TAKE/SKIP/REDUCE_SIZE
```

**What gets lost:**
- **Balance classification** (balance type, skew, seam level, morph detection) — not represented in any card
- **Acceptance test** (breakout direction, pullback type, confidence) — not represented
- **CRI sub-components** (volatility, reclaim, breath, trap individually) — CRI gate emits 1 card, loses granularity
- **FVG lifecycle** (fill status, respect/disrespect, proximity to price) — not represented
- **Globex/Prior VA analysis** (Model A/B/C, gap classification, 80P confidence) — not represented
- **Edge fade zones** (proximity to IB edge, historical IB width context) — not represented
- **Regime context** (ATR regime, consecutive balance days, weekly context, VIX) — not represented
- **Core confluences** (price location, delta bias, EMA alignment) — partially in momentum observer but flattened
- **Premarket context** (ON range, London/Asia levels, gap size) — not represented
- **Market structure events** (FVG creation/fill, VA extension, DPOC shift) — not represented

The Advocate and Skeptic argue from **9 cards** when the deterministic layer has computed **38 modules worth of analysis**. That is like asking lawyers to try a case where only 2 of 15 expert witnesses were allowed to testify.

### The Solution: Expert Domain Architecture

Reorganize the 38 modules into **8 Expert Domains**, each a class that:
1. Takes raw module outputs as input
2. Produces 2-5 focused evidence cards (with confidence, not just binary)
3. Can be tested independently (unit tests per domain)
4. Feeds directly into the agent pipeline as an observer replacement
5. Preserves `raw_data` references so the LLM debate can dig deeper if needed

```
38 deterministic modules (unchanged — still run in <10ms)
    ↓
8 Expert Domain Observers (replace ProfileObserver + MomentumObserver)
    ↓
~24-32 evidence cards (vs current 9) — HIGHER quality, FOCUSED signal
    ↓
[Optional] LLM Debate (Advocate/Skeptic argue from richer evidence)
    ↓
Orchestrator (deterministic decision, same as today)
```

### Expert Domain #1: Profile Expert

**Responsibility**: TPO shape, distribution analysis, VA dynamics, structural tells.

**Deterministic modules that feed in**:
- `tpo_profile.py` — TPO shape, period letters, distribution
- `volume_profile.py` — Volume-at-price, POC, VAH, VAL, HVN/LVN
- `balance_classification.py` — Balance type, skew, seam, morph detection

**Evidence cards produced** (3-4):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `profile_shape_alignment` | TPO shape + direction alignment | "b-shape (value building at bottom) aligned with LONG signal — bullish structural tell" |
| `profile_va_dynamics` | VA position + migration + width | "Price above VAH, VA widening upward, 30-min acceptance outside — initiative activity, bullish" |
| `profile_balance_state` | Balance type + skew + morph | "Balance B-Day detected, skew bearish (70%), seam at 21450 — fade upper probe" |
| `profile_structural_tells` | Poor highs/lows + single prints + excess | "Poor high + 3 single prints above POC — unfinished business, upside target remains" |

**Improvement over current ProfileObserver**:
- Current: 4 cards that each look at ONE data point in isolation (shape alone, VA alone, POC alone, poor extremes alone)
- New: Cards that CROSS-REFERENCE module outputs (e.g., balance type + skew together, VA migration + acceptance together)
- New: `profile_balance_state` card is entirely missing today — balance classification output is never seen by agents
- New: Confidence scoring uses multiple signals (VA width + acceptance + shape convergence = higher confidence)

**Confidence scoring approach**:
```python
def _va_dynamics_confidence(self, va_position, acceptance, va_migration, shape_alignment):
    """Multi-factor confidence for VA dynamics card."""
    base = 0.5
    if va_position in ("above_vah", "below_val"):
        base += 0.1  # price outside VA = directional
    if acceptance:
        base += 0.15  # 30-min acceptance confirms
    if va_migration == "aligned":
        base += 0.1  # VA moving same direction as price
    if shape_alignment:
        base += 0.1  # TPO shape confirms direction
    return min(base, 0.95)
```

---

### Expert Domain #2: Order Flow Expert

**Responsibility**: Delta, CVD divergence, volume distribution, absorption signals, wick patterns.

**Deterministic modules that feed in**:
- `wick_parade.py` — Bull/bear wick counts, wick ratios
- `core_confluences.py` — Delta cumulative, delta bias, EMA alignment
- `intraday_sampling.py` — 5-min bar sampling, volume distribution
- `volume_profile.py` — Volume concentration, HVN/LVN proximity

**Evidence cards produced** (3-4):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `flow_delta_divergence` | Price vs CVD alignment/divergence | "Price making new high but CVD flat — sellers absorbing, divergence warns against LONG" |
| `flow_wick_traps` | Wick parade pattern + interpretation | "6 bear wicks in 45 min — sellers repeatedly trapped, LONG has hidden support" |
| `flow_volume_distribution` | Volume concentration + acceptance pattern | "Volume concentrated at session lows (accumulation signature) — bullish" |
| `flow_absorption` | Delta absorption at key levels | "Large negative delta at VAH but price holding — absorption, buyers absorbing selling" |

**Improvement over current MomentumObserver**:
- Current: `momentum_wick_traps` card counts wicks but doesn't consider CONTEXT (wick parade during acceptance vs during rejection means different things)
- New: Wick patterns cross-referenced with price location (wick traps AT a key level = much stronger signal)
- New: CVD divergence card is entirely missing today — the most powerful order flow signal has no representation
- New: Volume distribution pattern (accumulation/distribution) is never surfaced

**New deterministic intelligence needed**:
- CVD divergence detection: Track cumulative delta vs price highs/lows. When price makes HH but CVD doesn't, flag divergence. This is a simple computation on existing delta data but needs a dedicated function.
- Absorption detection: When delta is strongly negative but price holds (or vice versa), flag absorption. Needs threshold calibration from backtest data.

---

### Expert Domain #3: Structure Expert

**Responsibility**: IB classification, extensions, day type evolution, CRI terrain assessment.

**Deterministic modules that feed in**:
- `cri.py` — CRI components (volatility, reclaim, breath, trap, terrain, identity, permission)
- `cri_psychology_voice.py` — CRI-based sizing, terrain-setup conflict detection
- `acceptance_test.py` — Breakout detection, pullback type, acceptance confidence
- `ib_location.py` — IB position within range, ADX, Bollinger Bands
- `decision_engine.py` — Day type classification, trend strength, morph status

**Evidence cards produced** (3-5):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `structure_cri_terrain` | CRI terrain + permission with sub-component detail | "TERRAIN: TRENDING (breath strong, reclaim confirmed). PERMISSION: FULL_SIZE. Trap risk: LOW" |
| `structure_day_evolution` | Day type + morph status + trend strength | "Day type morphing from Balance → Trend Down. Morph confidence 75%. Trend strength: moderate bearish" |
| `structure_ib_extension` | IB extension magnitude + acceptance status | "IB extended 1.8× below — 30-min acceptance confirmed. Not a probe — this is initiative" |
| `structure_acceptance` | Pullback type + acceptance confidence | "Post-breakout: shallow pullback (didn't recross IBL), high acceptance confidence (0.82)" |
| `structure_time_context` | Time-of-day gating for signal relevance | "Signal at 12:30 — late session, confidence time-capped. 84% of PnL comes from 10:00 hour" |

**Improvement over current observers**:
- Current: CRI gate produces 1 binary card (pass/fail). The rich sub-components (volatility, reclaim, breath, trap) are invisible to debate.
- New: CRI terrain card exposes sub-components so Advocate can argue "breath is strong even though trap is moderate" and Skeptic can counter "but reclaim is weak"
- Current: Extension card is oversimplified (just the multiple). New card includes acceptance status, which is the REAL signal.
- New: Day type morphing is never surfaced — critical for avoiding trades that assume one day type when it is changing

---

### Expert Domain #4: Level Expert (NEW — currently missing)

**Responsibility**: Prior session levels, London/Asia levels, VWAP, FVGs, naked levels, and most importantly **level confluence scoring**.

**Deterministic modules that feed in**:
- `globex_va_analysis.py` — Prior VA, gap classification, Model A/B/C
- `premarket.py` — London/Asia high/low, ON range, gap size
- `fvg_detection.py` — FVG locations, fill status, proximity
- `ninety_min_pd_arrays.py` — 90-min arrays, displacement/rebalance zones
- `core_confluences.py` — VWAP, EMA levels
- (NEW) Level confluence scoring function

**Evidence cards produced** (3-5):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `level_confluence_zone` | Cluster of levels near current price | "3 levels within 15 pts of entry: London High (21,540), Prior VAH (21,535), unfilled bearish FVG (21,542). HIGH confluence — strong resistance zone" |
| `level_prior_va_model` | Prior VA model classification + gap status | "Open above prior VA, Model A detected (failed auction above). 80P confidence: 72%" |
| `level_fvg_proximity` | Nearest unfilled FVG + respect/disrespect status | "Unfilled 15-min bearish FVG at 21,480, price 20 pts below. If respected = overhead resistance. 3 prior FVGs in this zone were respected (75% rate)" |
| `level_premarket_context` | London/Asia levels + overnight range + gap | "London Low at 21,350 swept by 12 pts and rejected. ON range: 120 pts (wide). Gap: -45 pts (bearish)" |
| `level_naked_targets` | Untested significant levels (liquidity targets) | "PDH (21,620) untested — liquidity resting. Prior session poor high at 21,615 — likely sweep target" |

**Why this is the highest-value new domain**:
- Level confluence is the #1 missing signal. The user draws levels and looks for clusters — the system sees none of this.
- No observer currently surfaces FVG data, prior VA models, or London/Asia levels to the agent pipeline.
- Level confluence scoring (counting how many levels cluster near an entry price) is pure deterministic math — fast, reliable, high signal.

**Level confluence scoring algorithm (new)**:
```python
def score_level_confluence(entry_price: float, levels: list[dict], atr: float) -> dict:
    """Score how many significant levels cluster near the entry price.

    Args:
        entry_price: Proposed entry price
        levels: List of {"name": str, "price": float, "weight": float}
            weight: 1.0 for major (PDH/PDL, London H/L, Prior VAH/VAL)
                    0.7 for moderate (VWAP, unfilled FVG, 90-min array)
                    0.5 for minor (EMA, ON range edge)
        atr: Current ATR for proximity thresholds

    Returns:
        {"confluence_score": float (0-1),
         "levels_within_10pts": int,
         "levels_within_atr_quarter": int,
         "nearest_level": {"name": str, "price": float, "distance": float},
         "cluster_direction": "support" | "resistance" | "mixed"}
    """
    proximity_threshold = max(atr * 0.25, 10.0)  # Within 25% of ATR or 10 pts
    nearby = [l for l in levels if abs(l["price"] - entry_price) <= proximity_threshold]
    weighted_score = sum(l["weight"] for l in nearby)
    # Normalize: 0 levels = 0.0, 3+ major levels = 1.0
    confluence_score = min(weighted_score / 3.0, 1.0)
    ...
```

---

### Expert Domain #5: Momentum Expert

**Responsibility**: Trend direction, DPOC migration, EMA alignment, momentum velocity and exhaustion.

**Deterministic modules that feed in**:
- `dpoc_migration.py` — DPOC direction, velocity, retention
- `dalton.py` — Trend analysis (EMA20/50, slope, crossover)
- `decision_engine.py` — Trend strength classification, bias cap
- `core_confluences.py` — EMA alignment, delta momentum direction

**Evidence cards produced** (2-3):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `momentum_trend_regime` | Trend direction + strength + EMA alignment | "Strong bullish: EMA20 > EMA50, both rising, price above both. ADX 32 (trending). Aligned with LONG" |
| `momentum_dpoc_velocity` | DPOC migration + velocity + exhaustion detection | "DPOC migrating up 25 pts in 60 min (fast). BUT velocity decelerating — last 30 min only +5 pts. Exhaustion risk" |
| `momentum_bias_composite` | Multi-vote bias + alignment with signal | "Bias: Bullish (4/5 votes). EMA20>50 [2x], prior session bullish [1x], price>VWAP [1x]. Aligned with LONG signal" |

**Improvement over current MomentumObserver**:
- Current: `momentum_dpoc_regime` card classifies DPOC as trending/rotating/migrating but misses VELOCITY and EXHAUSTION — the most actionable signals
- Current: `momentum_trend_strength` card reads a string like "strong bullish" but doesn't report EMA positions, slopes, or ADX
- New: DPOC velocity + deceleration detection catches "momentum fading" which is the key tape reading insight
- New: Composite bias card aggregates the 3-vote system into one clear card with vote breakdown

---

### Expert Domain #6: Regime Expert

**Responsibility**: Macro context — ATR regime, VIX, weekly context, consecutive balance days, session type classification.

**Deterministic modules that feed in**:
- `regime_context.py` — ATR regime, 5-min ATR, prior day type, consecutive balance, weekly context, VIX, composite regime labels
- `vix_regime.py` — VIX level, VIX regime classification

**Evidence cards produced** (2-3):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `regime_volatility` | ATR regime + VIX context + implication | "ATR regime: HIGH (ATR 280 pts, 90th percentile). VIX: 22.5 (elevated). Wide stops needed, reduce size" |
| `regime_pattern` | Consecutive balance + weekly pattern + prior session type | "3 consecutive balance days — breakout probability elevated. Prior session: Trend Down. Weekly context: range-bound Mon-Wed" |
| `regime_sizing_guidance` | Regime-based position sizing recommendation | "High vol + 3rd balance day = REDUCE_SIZE. Historical: 4th balance day breaks out 68% of the time" |

**Why this matters**:
- Regime context is never surfaced to agents today. A 80P trade in a VIX-25 environment needs completely different treatment than VIX-14.
- Consecutive balance days are a powerful predictor (user observation #3: "3rd+ balance day often breaks out") but agents never see this.
- Regime-based sizing guidance is deterministic and should pre-adjust conviction before the LLM debate even starts.

---

### Expert Domain #7: Swing/Trendline Expert (NEW — requires 2.6-2.7 modules)

**Responsibility**: Swing point structure, trendline detection, 3rd touch signals.

**Deterministic modules that feed in**:
- (NEW) `swing_detection.py` — Swing highs/lows, HH/HL/LH/LL classification (see section 2.6)
- (NEW) `trendline_detection.py` — Trendline fitting, touch counting, 3rd touch alerts (see section 2.7)

**Evidence cards produced** (2-3):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `swing_structure` | Current swing sequence + trend classification | "15-min structure: HH, HL, HH, HL — confirmed uptrend. Last swing low at 21,380. Structure break level: 21,380" |
| `trendline_3rd_touch` | 3rd touch approaching/confirmed + rejection pattern | "3rd touch of 15-min descending trendline at 21,490. Rejection candle score: 0.7 (strong). Historical: 3rd touches bounce 64% of the time" |
| `trendline_confluence` | Trendline intersection with other levels | "Descending trendline 3rd touch AT London Low (21,350) — double confluence. Trendline + level alignment = HIGH conviction" |

**Dependencies**: Requires swing point detection (2.6) and trendline analysis (2.7) modules to be implemented first. These are detailed in the "Future Deterministic Modules" section above.

---

### Expert Domain #8: Cross-Instrument Expert (NEW — requires 2.5 module)

**Responsibility**: SMT divergence, ES/NQ/YM correlation, relative strength.

**Deterministic modules that feed in**:
- `cross_market.py` — Existing cross-market analysis
- `smt_detection.py` — Existing SMT detection (basic)
- (NEW) Enhanced multi-instrument swing-based SMT detection (see section 2.5)

**Evidence cards produced** (1-2):

| Card ID | What It Captures | Example Observation |
|---------|-----------------|---------------------|
| `cross_smt_divergence` | SMT divergence across correlated instruments | "NQ making new high but ES did not confirm (15-min). Bearish SMT divergence. Weight: 0.7 (intraday TF)" |
| `cross_relative_strength` | Which instrument is leading/lagging | "NQ leading ES by 0.3% today. YM lagging both. NQ leadership often precedes NQ trend continuation" |

**Dependencies**: Requires multi-instrument data loader enhancement (ES + YM data alongside NQ). Lowest priority — do last.

---

### Evidence Card Architecture (Shared Across All Domains)

Each Expert Domain observer extends `AgentBase` and produces `EvidenceCard` instances with enhanced metadata:

```python
@dataclass
class EvidenceCard:
    card_id: str                    # e.g., "level_confluence_zone"
    source: str                     # e.g., "expert_level"
    layer: str                      # "certainty" | "probabilistic" | "instinct"
    observation: str                # Human-readable summary
    direction: str                  # "bullish" | "bearish" | "neutral"
    strength: float                 # 0.0-1.0 (multi-factor confidence)
    data_points: int = 1            # How many data points back this card
    historical_support: str | None  # DuckDB query result, if available
    admitted: bool | None = None    # None=pre-debate, True/False=post-debate
    raw_data: dict = field(...)     # Full module output for LLM deep-dive

    # NEW fields for Expert Domain architecture:
    category: str = ""              # "profile" | "flow" | "structure" | "level" | ...
    sub_signals: int = 1            # How many sub-signals converged to produce this card
    confidence_factors: list = ...  # What contributed to the strength score
```

**Layer classification guide**:
- `certainty` — Based on hard numbers: IB range, price vs level, day type. No interpretation needed.
- `probabilistic` — Based on patterns with known historical rates: 3rd touch bounce rate, CRI terrain outcomes.
- `instinct` — Based on pattern recognition that lacks hard statistics: wick parade interpretation, FVG respect/disrespect "feel."

**Card count budget**: Each Expert Domain produces 2-5 cards. With 8 domains, worst case is 40 cards, typical case is ~24-28. The Orchestrator scorecard handles this — it already sums bull/bear scores regardless of card count. The LLM debate benefits from richer evidence without being overwhelmed (each card is a single sentence, not a paragraph).

---

### Integration with Agent Pipeline

**Current pipeline** (`pipeline.py`):
```python
self.observers = observers or [ProfileObserver(), MomentumObserver()]
```

**New pipeline**:
```python
self.observers = observers or [
    ProfileExpert(),          # TPO shape, VA dynamics, balance, structural tells
    OrderFlowExpert(),        # Delta divergence, wick traps, volume distribution
    StructureExpert(),        # CRI terrain, day evolution, IB extension, acceptance
    LevelExpert(),            # Confluence scoring, prior VA, FVGs, premarket levels
    MomentumExpert(),         # Trend regime, DPOC velocity, composite bias
    RegimeExpert(),           # Volatility regime, balance pattern, sizing guidance
    # Phase C additions:
    # SwingTrendlineExpert(), # Swing structure, 3rd touch, trendline confluence
    # Phase D additions:
    # CrossInstrumentExpert(),# SMT divergence, relative strength
]
```

**Key architectural decisions**:
1. **Each expert runs independently** — no cross-domain dependencies at the observer level. Cross-domain synthesis happens in the Orchestrator.
2. **Experts consume raw module output** — they read from the snapshot dict, same as current observers. No new data pipeline needed.
3. **Backward compatible** — old `ProfileObserver` + `MomentumObserver` still work. New experts are additive. Can A/B test old vs new.
4. **Same `EvidenceCard` dataclass** — no schema change needed for Orchestrator or debate layer.
5. **Parallelizable** — all 6-8 experts can run concurrently (they are pure functions of the snapshot).

**Impact on LLM debate**:
- Advocate gets ~24 cards instead of ~9 to argue from — richer evidence, more ammunition
- Skeptic gets more surface area to challenge — "the flow_delta_divergence card contradicts the momentum_trend_regime card"
- Disputed card resolution (0.7x weight) becomes more meaningful with fine-grained cards
- Instinct cards from LLM can reference specific expert findings: "Building on the level_confluence_zone card, I notice..."

**Impact on Orchestrator scoring**:
- More cards = more granular bull/bear scores
- But each card has FOCUSED strength (not inflated) — a 3-level confluence zone gets 0.8 strength, not every level individually at 0.5
- Net effect: same scoring mechanics, higher resolution signal

---

### Phasing Plan

#### Phase A: Reorganize Existing Modules into Domains (No New Code)

**Scope**: Create 6 Expert Domain observer classes that consume existing module outputs. No new deterministic modules. No new computations. Pure reorganization.

**Deliverables**:
1. `packages/rockit-core/src/rockit_core/agents/observers/profile_expert.py`
2. `packages/rockit-core/src/rockit_core/agents/observers/order_flow_expert.py`
3. `packages/rockit-core/src/rockit_core/agents/observers/structure_expert.py`
4. `packages/rockit-core/src/rockit_core/agents/observers/level_expert.py`
5. `packages/rockit-core/src/rockit_core/agents/observers/momentum_expert.py`
6. `packages/rockit-core/src/rockit_core/agents/observers/regime_expert.py`
7. Unit tests for each expert (target: 8-12 tests per expert)
8. A/B test script: old observers (9 cards) vs new experts (~24 cards)

**Estimated effort**: 2-3 sessions. Each expert is ~150-250 lines (similar to current ProfileObserver at 217 lines).

**Validation**: Run backtest with new experts. Compare agent decision quality (WR, PF) against Run E baseline (66.5% WR, PF 3.58). The expert domains should produce >= same quality with richer reasoning traces.

**Risk**: More cards could DILUTE signal if poorly calibrated. Mitigate by ensuring each card's strength is conservative (start at 0.5, boost only with multi-factor convergence).

#### Phase B: Add Level Confluence Scoring (New Deterministic Intelligence)

**Scope**: Build the level confluence scoring function and the Level Expert observer.

**Deliverables**:
1. `level_confluence.py` in deterministic modules — score how many levels cluster near a price
2. Update `LevelExpert` observer to use confluence scoring
3. Integration test: verify confluence scores for known sessions (e.g., 2026-03-12 had London Low + descending trendline + FVG = high confluence)

**Estimated effort**: 1-2 sessions. The scoring algorithm is straightforward math.

**Validation**: Compare agent decisions WITH level confluence vs WITHOUT. Hypothesis: level confluence prevents at least 3-5 losing trades per 270 sessions (trades taken at low-confluence entry points).

#### Phase C: Add Swing/Trendline Expert (New Modules from 2.6-2.7)

**Scope**: Implement swing point detection and trendline analysis, then wrap in SwingTrendlineExpert observer.

**Deliverables**:
1. `swing_detection.py` — causal swing point detection (see section 2.6 for full spec)
2. `trendline_detection.py` — trendline fitting + 3rd touch detection (see section 2.7 for full spec)
3. `SwingTrendlineExpert` observer class
4. 3rd touch backtest study across 270 sessions (bounce vs break rates, WR by timeframe)

**Estimated effort**: 3-5 sessions. Swing detection is well-specified (section 2.6). Trendline fitting has more edge cases.

**Dependencies**: Swing detection must work before trendline detection.

**Validation**: Run the 3rd touch study. If bounce rate > 60% and WR improvement > 2pp, trendline expert is justified.

#### Phase D: Add Cross-Instrument Expert (New Module from 2.5)

**Scope**: Enhanced SMT divergence detection across NQ/ES/YM.

**Deliverables**:
1. Enhanced `smt_detection.py` with swing-based divergence (not just price comparison)
2. Multi-instrument data loader (load ES + YM alongside NQ)
3. `CrossInstrumentExpert` observer class

**Estimated effort**: 2-3 sessions. Data loader work is the main effort.

**Dependencies**: Swing detection (Phase C) for swing-based SMT. Multi-instrument CSV data availability.

**Validation**: SMT divergence study across 270 sessions. Historical: how often does SMT divergence precede reversals?

#### Phase E: Benchmark — Expert Domains vs Current Observers

**Scope**: Full A/B backtest comparing:
- **Run F**: Current observers (ProfileObserver + MomentumObserver, 9 cards) + LLM debate
- **Run G**: Expert Domain observers (6-8 experts, ~24-32 cards) + LLM debate

**Key metrics to compare**:
- Win Rate, Profit Factor, Net PnL (must not regress)
- Per-strategy improvement (especially 80P and B-Day which are underperforming)
- Debate quality: Do Advocate/Skeptic produce more nuanced arguments with richer evidence?
- False positive rate: Do expert domains help SKIP more losing trades without filtering winners?

**Decision gate**:
- Run G >= Run F → Expert domains are the new default
- Run G < Run F by > 2pp WR → Experts are diluting signal, reduce card count or recalibrate strengths
- Run G ~ Run F (within 1pp) → Experts add no value at observer level, but may still help LLM debate quality. Assess qualitatively.

---

### Module-to-Domain Mapping (Complete Reference)

| Deterministic Module | Expert Domain | Notes |
|---------------------|---------------|-------|
| `tpo_profile.py` | Profile Expert | TPO shape, periods, distribution |
| `volume_profile.py` | Profile Expert + Order Flow Expert | VA/POC → Profile; volume distribution → Order Flow |
| `balance_classification.py` | Profile Expert | Balance type, skew, seam, morph |
| `wick_parade.py` | Order Flow Expert | Bull/bear wick counts |
| `core_confluences.py` | Order Flow Expert + Momentum Expert | Delta → Order Flow; EMA alignment → Momentum |
| `intraday_sampling.py` | Order Flow Expert | Volume distribution, bar sampling |
| `cri.py` | Structure Expert | CRI terrain, identity, permission, sub-components |
| `cri_psychology_voice.py` | Structure Expert | CRI sizing, conflict detection |
| `acceptance_test.py` | Structure Expert | Breakout, pullback, acceptance |
| `ib_location.py` | Structure Expert | IB position, ADX, Bollinger |
| `decision_engine.py` | Structure Expert + Momentum Expert | Day type → Structure; trend strength/bias → Momentum |
| `globex_va_analysis.py` | Level Expert | Prior VA, gap, Model A/B/C |
| `premarket.py` | Level Expert | London/Asia levels, ON range, gap |
| `fvg_detection.py` | Level Expert | FVG locations, fill status |
| `ninety_min_pd_arrays.py` | Level Expert | 90-min arrays, displacement zones |
| `dpoc_migration.py` | Momentum Expert | DPOC direction, velocity, retention |
| `dalton.py` | Momentum Expert | Trend analysis, EMA crossover |
| `regime_context.py` | Regime Expert | ATR, prior day type, balance streak, weekly |
| `vix_regime.py` | Regime Expert | VIX level, VIX regime |
| `edge_fade.py` | Structure Expert | Edge fade zone proximity |
| `or_reversal.py` | Structure Expert | OR reversal detection |
| `twenty_percent_rule.py` | Level Expert | 20P rule levels |
| `mean_reversion_engine.py` | Momentum Expert | Mean reversion signals |
| `market_structure_events.py` | Profile Expert + Level Expert | VA extension → Profile; FVG events → Level |
| `cross_market.py` | Cross-Instrument Expert | Cross-market correlation |
| `smt_detection.py` | Cross-Instrument Expert | SMT divergence |
| `tape_context.py` | (meta — feeds all experts) | General tape context |
| `enhanced_reasoning.py` | (meta — feeds LLM, not experts) | LLM reasoning prompts |
| `trader_voice.py` | (meta — feeds LLM, not experts) | Trader voice for analysis |
| `setup_annotator.py` | (meta — feeds UI, not experts) | Setup annotations |
| `inference_engine.py` | (meta — orchestrator level) | LLM inference orchestration |
| `playbook_engine.py` | (meta — orchestrator level) | Playbook matching |
| `playbook_engine_v2.py` | (meta — orchestrator level) | Playbook v2 |
| `loader.py` | (infrastructure) | Data loading |
| `dataframe_cache.py` | (infrastructure) | Caching |
| `data_validator.py` | (infrastructure) | Validation |
| `config_validator.py` | (infrastructure) | Config validation |
| `schema_validator.py` | (infrastructure) | Schema validation |
| `error_logger.py` | (infrastructure) | Error logging |
| `outcome_labeling.py` | (infrastructure) | Outcome labeling for training |
| `market_structure_registry.py` | (infrastructure) | Level registry |

**Count**:
- 6 Expert Domain modules: Profile (3 modules), Order Flow (3-4), Structure (5-6), Level (4-5), Momentum (4-5), Regime (2)
- 2 Future Expert Domain modules: Swing/Trendline (2 new), Cross-Instrument (2-3)
- 6 Meta/Orchestrator-level modules: Not consumed by experts, used by LLM inference or UI
- 6 Infrastructure modules: Data loading, caching, validation — unchanged

---

### Courtroom Analogy Integration

This refactoring directly implements the Courtroom Analogy from the architecture section above:

```
BEFORE (current — incomplete courtroom):
  2 witnesses (ProfileObserver, MomentumObserver) testify about 38 experts' work
  → Lawyers hear 9 facts → Judge rules on limited evidence

AFTER (expert domain refactoring):
  8 expert witnesses testify directly, each covering their specialty
  → Lawyers hear ~24 focused facts → Judge rules on comprehensive evidence

FUTURE (with trained LLM analyst):
  8 expert witnesses provide deterministic facts (<10ms)
  → Trained analyst interprets with trader's voice (~5s per snapshot, on timer)
  → Lawyers argue from expert testimony + analyst interpretation
  → Judge rules on facts + nuanced interpretation
```

The expert domain refactoring strengthens the DETERMINISTIC foundation — the expert witnesses become more specialized and articulate. This is prerequisite work before training the LLM analyst (Phase B in the Courtroom phasing). Better expert testimony means better training data for the analyst, which means better arguments for the lawyers, which means better decisions from the judge.

**Key principle**: Train the experts BEFORE training the analyst. The analyst learns from expert output. If expert output is coarse (9 cards), the analyst learns coarse patterns. If expert output is rich (24 cards), the analyst learns nuanced patterns.
