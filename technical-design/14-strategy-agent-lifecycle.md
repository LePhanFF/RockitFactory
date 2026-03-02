# Strategy & Agent Lifecycle Workflows

> **Status:** Draft
> **Purpose:** End-to-end workflows for developing strategies and improving agents.
> **Fills gaps from:** FAQ Q6 (strategy dev workflow), FAQ Q17 (walk-forward validation),
> shadow mode spec, CORE_STRATEGIES graduation criteria, agent prompt development workflow.
> **Cross-references:** [04-strategy-framework.md](04-strategy-framework.md), [08-agent-system](../architecture/08-agent-system.md),
> [08-self-learning](../architecture/08-self-learning.md), [11-testing](../architecture/11-testing-and-automation.md),
> [12-training-mlops](12-training-mlops.md), [13-automation-infrastructure](13-automation-infrastructure.md)

---

## Part 1: Strategy Lifecycle (Idea → Live)

### Visual Overview

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Stage 1  │───▶│   Stage 2    │───▶│   Stage 3    │───▶│   Stage 4    │
│ Research │    │ Implement    │    │ Backtest     │    │ Walk-Forward │
│ & Hypo-  │    │              │    │ Validation   │    │ Validation   │
│ thesis   │    │              │    │              │    │              │
└──────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
                                                               │
                                                               ▼
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Stage 7  │◀───│   Stage 6    │◀───│   Stage 5    │◀───│   Gate:      │
│ Live     │    │ Promotion to │    │ Shadow Mode  │    │ All 3 folds  │
│ Monitor  │    │ Production   │    │ (Paper)      │    │ positive?    │
│ & Retire │    │ (Human only) │    │              │    │              │
└──────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

Gate symbols:
- Stage 2 → 3: PR passes CI (lint, type-check, unit tests)
- Stage 3 → 4: BaselineComparator gates pass
- Stage 4 → 5: All out-of-sample folds positive
- Stage 5 → 6: 20 sessions, meets WR/PF/loss criteria
- Stage 6 → 7: Human checklist approval

---

### Stage 1 — Research & Hypothesis

**Entry:** A trading idea or observed edge.

**Activities:**

1. **Identify the edge.** What market structure pattern produces alpha?
   - Day type classification (e.g., "B-Days with narrow IB consistently revert to VAH/VAL")
   - Order flow signal (e.g., "CVD divergence at IBH predicts failed breakout")
   - Structural pattern (e.g., "DPOC migration + delta > 300 = reliable trend continuation")

2. **Run diagnostic scripts.** Use rockit-core deterministic modules to scan historical sessions:
   ```bash
   make analyze MODULES=ib_analysis,volume_profile,tpo SESSIONS=all
   ```
   Filter for sessions matching the hypothesized conditions.

3. **Document the hypothesis.** Write it down before coding:
   ```
   Hypothesis: [Name]
   Edge: [What pattern creates the opportunity]
   Day types: [Which Dalton day types this applies to]
   Instruments: [NQ, ES, etc.]
   Expected win rate: [Based on historical scan]
   Expected R:R: [Risk/reward estimate]
   Similar existing strategy: [If any — avoid duplication]
   ```

**Exit criteria:** Written hypothesis document with expected day types, instruments, and edge description. Reviewed by trader (human) to confirm the pattern is grounded in Dalton/auction market theory.

---

### Stage 2 — Implementation

**Entry:** Approved hypothesis.

**Activities:**

1. **Create a feature branch:**
   ```bash
   git checkout -b strategy/new-strat-name main
   ```

2. **Implement the StrategyBase subclass** in `packages/rockit-core/src/rockit_core/strategies/`:
   ```python
   class NewStratName(StrategyBase):
       @property
       def name(self) -> str:
           return "NewStratName"

       @property
       def applicable_day_types(self) -> list[str]:
           return ["b_day"]  # From hypothesis

       def on_session_start(self, session_date, ib_high, ib_low, ib_range, session_context):
           # Store IB levels, compute session-level state
           ...

       def on_bar(self, bar, bar_index, session_context) -> Signal | None:
           # Check conditions, return Signal or None
           ...
   ```

3. **Add YAML config entry** in `configs/strategies.yaml`:
   ```yaml
   new_strat_name:
     enabled: false  # Always start disabled
     class: NewStratName
     instruments: [NQ]
     applicable_day_types: [b_day]
     entry_models: [...]
     stop_model: ...
     target_model: ...
     filters:
       ...
     confidence_threshold: 0.65
   ```

4. **Register in strategy registry** — add to `ALL_STRATEGIES` in `strategies/__init__.py`.

5. **Write unit tests** in `packages/rockit-core/tests/strategies/test_new_strat_name.py`:
   - Contract tests (StrategyBase compliance — name, applicable_day_types, on_bar return type)
   - Signal emission tests with known-good fixtures
   - No-signal tests (conditions not met)
   - Edge cases (IB range = 0, missing context fields, boundary values)

6. **Open PR** to feature branch. CI runs lint, type-check, unit tests.

**Exit criteria:** PR passes CI. Strategy code, YAML config (disabled), registry entry, and unit tests all committed.

---

### Stage 3 — Backtest Validation

**Entry:** PR with passing CI.

**Activities:**

1. **Run the 259-session backtest:**
   ```bash
   make backtest STRATEGY=new_strat_name
   ```
   This runs `rockit_pipeline.backtest.engine` against the full historical dataset.

2. **Review per-strategy metrics:**
   - Win rate, profit factor, total trades, max drawdown
   - Trade distribution by day type (confirm it only trades expected day types)
   - Average R:R achieved vs hypothesized R:R

3. **BaselineComparator regression gates** (enforced by CI):

   | Metric | Gate | Threshold |
   |--------|------|-----------|
   | Win rate | Must not drop | ≤ 5% below baseline |
   | Profit factor | Must not drop | ≤ 0.15 below baseline |
   | Max drawdown | Must not increase | ≤ $500 above baseline |

4. **Portfolio-level check:** Run backtest with the new strategy added to the full portfolio:
   ```bash
   make backtest-portfolio INCLUDE=new_strat_name
   ```
   The new strategy must not degrade portfolio metrics. Verify no signal conflicts with existing strategies on the same day types.

**Exit criteria:** BaselineComparator passes. Portfolio-level metrics not degraded. Backtest report committed to PR.

---

### Stage 4 — Walk-Forward Validation

> **This section fills a gap — FAQ Q17 referenced walk-forward validation but no spec existed.**

**Entry:** Backtest gates passed.

**Purpose:** Confirm the strategy is not overfit to the in-sample data. Walk-forward validation uses temporal splits to simulate out-of-sample performance.

**Spec: 3-Fold Temporal Walk-Forward**

```
Fold 1:  Train on months 1-6  ──▶  Test on month 7
Fold 2:  Train on months 1-7  ──▶  Test on month 8
Fold 3:  Train on months 1-8  ──▶  Test on month 9

              │◄── In-Sample ──►│◄─ OOS ─►│
Fold 1:       [=================][========]
Fold 2:       [======================][========]
Fold 3:       [===========================][========]
```

**Implementation:**

```python
class WalkForwardValidator:
    """3-fold temporal walk-forward validation for strategies."""

    def validate(self, strategy: StrategyBase, sessions: list[Session]) -> WalkForwardResult:
        sessions_by_month = group_by_month(sessions)
        months = sorted(sessions_by_month.keys())

        folds = []
        for i in range(3):
            train_end = 6 + i  # months 1-6, 1-7, 1-8
            test_month = train_end + 1  # month 7, 8, 9

            train_sessions = flatten([sessions_by_month[m] for m in months[:train_end]])
            test_sessions = sessions_by_month[months[test_month - 1]]

            # Run backtest on train set (for parameter calibration if any)
            train_result = backtest(strategy, train_sessions)

            # Run backtest on test set (out-of-sample)
            test_result = backtest(strategy, test_sessions)

            folds.append(FoldResult(
                fold=i + 1,
                train_months=months[:train_end],
                test_month=months[test_month - 1],
                train_metrics=train_result.metrics,
                oos_metrics=test_result.metrics,
            ))

        return WalkForwardResult(folds=folds)
```

**Gates:**

| Check | Requirement |
|-------|-------------|
| Positive expectancy | ALL 3 out-of-sample folds must show positive expectancy (PF > 1.0) |
| No look-ahead bias | Strategy must not access future data (enforced by backtest engine) |
| Consistency | OOS win rate must be within 15% of in-sample win rate |
| Minimum trades | Each OOS fold must have ≥ 5 trades (enough to be meaningful) |

**Exit criteria:** All 3 folds pass. Walk-forward report committed to PR.

---

### Stage 5 — Shadow Mode (Paper Trading)

> **This section fills a gap — shadow mode was mentioned but never defined.**

**Entry:** Walk-forward validation passed.

**Purpose:** Validate strategy performance against live market data without risking capital. The strategy runs during market hours, emits signals, but signals are logged rather than executed.

**Configuration:**

```yaml
# configs/strategies.yaml
new_strat_name:
  enabled: true
  mode: shadow  # "live" | "shadow" — shadow = log only, do not execute
  shadow_start_date: "2026-03-15"
```

**How shadow mode works:**

1. Strategy runs in the live pipeline during RTH (9:30-16:00 ET).
2. Signals are emitted and logged to `signal_outcomes` table with `consensus_decision: "SHADOW"`.
3. The Outcome Logger computes what *would have happened* — MFE, MAE, outcome, P&L.
4. No signals are sent to clients or executed.

**Minimum duration:** 20 trading sessions (~4 calendar weeks).

**Shadow Mode Gates:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Win rate | ≥ 50% | Must be profitable in live conditions |
| Profit factor | ≥ 1.2 | Conservative — lower than CORE threshold |
| Worst single-day loss | ≤ 2x 14-day ATR | No outsized losing days |
| Minimum signals | ≥ 10 total | Strategy must actually fire |
| Day type alignment | ≥ 80% | Signals should occur on expected day types |

**Shadow mode dashboard view:**

```
┌────────────────────────────────────────────────────┐
│  SHADOW MODE: NewStratName                          │
│  Sessions: 14/20              Status: RUNNING       │
│                                                     │
│  WR: 57%  |  PF: 1.45  |  Signals: 7               │
│  Worst day: -$180 (0.8x ATR)  |  Best: +$420       │
│  Day type alignment: 86% (6/7 on B-Day)             │
│                                                     │
│  [View signals]  [View outcomes]  [Stop shadow]      │
└────────────────────────────────────────────────────┘
```

**Exit criteria:** 20 sessions completed. All shadow mode gates pass.

---

### Stage 6 — Promotion to Production

> **This is always a Tier 3 (human-only) decision.** The system never autonomously enables a strategy for live trading.

**Entry:** Shadow mode passed.

**Promotion checklist:**

- [ ] Backtest regression gates passed (Stage 3)
- [ ] Walk-forward validation passed — all 3 folds positive (Stage 4)
- [ ] Shadow mode passed — 20 sessions, WR ≥ 50%, PF ≥ 1.2 (Stage 5)
- [ ] Reviewed by trader — hypothesis validated against live behavior
- [ ] No conflicting strategies on the same day types (checked in Stage 3)
- [ ] Risk parameters appropriate — stop/target distances within account limits

**Actions on promotion:**

1. Update YAML config:
   ```yaml
   new_strat_name:
     enabled: true
     mode: live  # Switch from shadow to live
   ```

2. Merge feature branch to `main`.
3. Strategy begins emitting live signals on next trading session.

---

### CORE_STRATEGIES Graduation Criteria

> **This section fills a gap — CORE_STRATEGIES was listed but graduation criteria were not documented.**

A strategy starts as "enabled" (live). To be promoted to `CORE_STRATEGIES` (the production-validated portfolio), it must meet **all** of the following over its live history:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Live sessions | ≥ 60 | ~3 months of trading data |
| Win rate | ≥ 55% | Above the current portfolio baseline (55.5%) |
| Profit factor | ≥ 1.3 | Below current portfolio PF (1.58) but meaningful |
| Max consecutive losses | ≤ 5 | No extended losing streaks |
| Rolling 30-day Sharpe | > 0 (positive) | Consistently positive risk-adjusted returns |
| No single-day loss | ≤ 3x ATR | No catastrophic individual losses |

**Graduation is a human decision.** The system generates a CORE_STRATEGIES candidacy report when thresholds are met, but a trader reviews and approves.

**Current CORE_STRATEGIES:** `trend_bull`, `p_day`, `b_day`, `edge_fade`, `ibh_sweep`, `bear_accept`, `or_reversal`, `ib_retest`

---

### Stage 7 — Live Monitoring & Retirement

**Entry:** Strategy is live (enabled: true).

**Continuous monitoring:**

- BaselineComparator runs after every session, comparing strategy performance against baseline.
- Auto-rollback guards from `configs/safety.yaml` apply to strategies via the agent system.
- Rolling 20-day metrics displayed on the agent monitoring dashboard.

**Strategy demotion criteria:**

If a strategy's rolling 20-session metrics fall below thresholds, it is flagged:

| Metric | Demotion Threshold | Action |
|--------|--------------------|--------|
| Win rate | < 40% over 20 sessions | Alert + flag for review |
| Profit factor | < 0.8 over 20 sessions | Alert + flag for review |
| Max drawdown | > $1,000 (strategy-level) | Alert + flag for review |
| Consecutive losing sessions | ≥ 5 | Alert + flag for review |

**Demotion is a two-step process:**

1. **Alert:** Dashboard notification + Slack alert. Trader reviews.
2. **Disable:** If metrics remain below threshold for 20+ sessions total, or if trader decides earlier:
   ```yaml
   strat_name:
     enabled: false
     disabled_date: "2026-06-15"
     disabled_reason: "WR dropped to 35% over 25 sessions. Market regime change."
   ```

**Retirement (removal from codebase):** Only if a strategy has been disabled for 90+ days and no plans to re-enable. The code and tests remain in git history.

---

## Part 2: Agent Improvement Lifecycle

### Visual Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DAILY CYCLE                                   │
│                                                                     │
│  ┌───────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │ Market    │──▶│ Outcome      │──▶│ Daily        │──▶ Tier 1     │
│  │ Hours     │   │ Logger       │   │ Reflection   │   auto-adjust │
│  │ (Agents   │   │ (4:15 PM)    │   │ (Qwen3.5     │               │
│  │ run live) │   │ No LLM       │   │  4:30 PM)    │               │
│  └───────────┘   └──────────────┘   └──────┬───────┘               │
│                                             │                       │
└─────────────────────────────────────────────┼───────────────────────┘
                                              │
                        ┌─────────────────────▼───────────────────┐
                        │           MULTI-DAY CYCLE                │
                        │                                          │
                        │  ┌──────────────┐   ┌────────────────┐  │
                        │  │ Meta-Review   │──▶│ A/B Test or    │  │
                        │  │ (Opus 4.6     │   │ Direct Change  │  │
                        │  │ every 1-3d)   │   │ (on branch)    │  │
                        │  └──────────────┘   └───────┬────────┘  │
                        │                              │           │
                        │  ┌──────────────┐   ┌───────▼────────┐  │
                        │  │ Promote or   │◀──│ Evaluate       │  │
                        │  │ Rollback     │   │ (20 sessions)  │  │
                        │  └──────────────┘   └────────────────┘  │
                        │                                          │
                        └──────────────────────────────────────────┘
                                              │
                        ┌─────────────────────▼───────────────────┐
                        │           MONTHLY CYCLE                  │
                        │                                          │
                        │  ┌──────────────┐   ┌────────────────┐  │
                        │  │ Performance  │──▶│ LoRA Retrain   │  │
                        │  │ plateau?     │   │ (if needed)    │  │
                        │  └──────────────┘   └────────────────┘  │
                        └──────────────────────────────────────────┘
```

---

### Stage 1 — Prompt Development

> **This section fills a gap — prompt versioning structure was defined, but the development workflow was not.**

**When to write a new agent prompt:**
- Initial agent creation (advocate, skeptic, orchestrator)
- Meta-review recommends a structural prompt rewrite
- A/B test requires a new variant

**Prompt template structure:**

```text
# Agent: [Advocate | Skeptic | Orchestrator]
# Version: v01
# Date: 2026-03-15
# Author: [human | opus-meta-review-2026-03-14]
# Changelog: Initial version

## System Context
You are the [role] agent in the Rockit trading system.
[Domain context: Dalton Market Profile, day types, IB, order flow]

## Role Definition
[Specific instructions for this agent's stance]

## Input Format
You will receive:
- Evidence cards from 4 observers (profile, momentum, structure, setups)
- Pattern Miner results (historical match rates, hidden confluence, similar sessions)
- [For Skeptic: Advocate's argument including admitted/rejected cards]
- [For Orchestrator: Both arguments + computed confluence from admitted cards]

## Output Format
Respond with JSON:
{
  "admit": ["card_id_1", ...],         // Advocate/Skeptic: which cards to admit
  "reject": ["card_id_x", ...],        // Which cards to reject as noise
  "instinct_cards": [...],             // Own soft observations
  "reasoning": "...",
  "decision": "..."                    // Orchestrator only: TAKE | SKIP | REDUCE_SIZE
}

## Guidelines
[Specific behavioral instructions]
```

**Development workflow:**

1. **Draft the prompt** following the template above.
2. **Test against a 10-session sample** — run the agent graph over 10 known historical sessions and review outputs manually.
3. **Check output quality:**
   - Does the agent produce valid JSON with valid card IDs?
   - Is the reasoning grounded in evidence cards (not hallucinated)?
   - Does the confluence score correlate with actual outcomes?
   - [For Advocate] Does it build a coherent case connecting evidence across domains?
   - [For Skeptic] Does it identify genuinely weak evidence vs generic objections?
   - [For Orchestrator] Does it weigh both sides and cite specific evidence in its decision?
4. **Version and commit:**
   ```
   configs/agents/prompts/advocate_v01.txt
   ```
5. **Update changelog:**
   ```yaml
   # configs/agents/prompts/prompt_changelog.yaml
   - version: advocate_v01
     date: "2026-03-15"
     author: human
     changes: "Initial advocate prompt"
     test_results: "10-session sample: 7/10 correct direction, 6/10 calibrated confidence"
   ```

---

### Stage 2 — Self-Learning Loop (Daily)

**Timing:** Runs automatically post-market every trading day.

```
4:15 PM ET → Outcome Logger (Python, no LLM)
4:30 PM ET → Daily Reflection (Qwen3.5)
5:00 PM ET → Auto-Adjustment (Tier 1 only)
```

**What Qwen3.5 reflection covers:**
1. Accuracy review — which observers produced the strongest evidence?
2. Debate quality — did Advocate build a coherent case? Did Skeptic challenge weak evidence? Did Orchestrator weigh both sides?
3. Calibration check — did confluence score (from admitted evidence cards) correlate with outcomes?
4. Pattern observations — which evidence combinations are emerging as reliable? What hidden confluence factors from the Pattern Miner proved predictive?
5. Adjustment proposals — observer weight tweaks, prompt emphasis shifts, pattern miner config

**Tier 1 (Autonomous) — what the system can change on its own:**

| Change Type | Bounds | Example |
|-------------|--------|---------|
| Confidence thresholds | ±10% of current value | `confidence_threshold: 0.65 → 0.60` |
| Filter parameters | Within pre-set bounds per parameter | `min_delta: 200 → 180` |
| Prompt emphasis shifts | No structural rewrite, only emphasis | Add "pay more attention to IB range" |
| A/B variant selection | Following active test protocol | Switch from variant A to B today |
| Historical context window | ±5 days | Historian looks at 15 days instead of 20 |

All Tier 1 changes are:
- Logged with reason and timestamp
- Version-bumped in `param_changelog.yaml`
- Committed to `reflect/{date}` branch (auto-merged to main)
- Subject to auto-rollback if metrics degrade (see Stage 6)

**Tier 2 (Requires Opus review) — proposed but not applied:**

Qwen3.5 can *propose* but not apply:
- Full prompt rewrites
- New filter rules or filter removal
- Strategy enable/disable
- Changes to deterministic calculations
- New A/B test designs

These proposals are stored in `gs://rockit-data/reflection/journals/{date}.json` under `adjustment_proposals` and reviewed during the meta-review.

---

### Stage 3 — A/B Testing

**Entry:** A Tier 2 change is approved by Opus meta-review (or designed by it).

**Protocol:**

1. **Create test config:**
   ```yaml
   # configs/agents/ab_tests/active/skeptic-ib-check.yaml
   test_id: "ab-20260315-skeptic-ib-check"
   hypothesis: "Adding IB range check to skeptic improves day type accuracy"
   variant_a: "skeptic_v08.txt"  # Current prompt
   variant_b: "skeptic_v09.txt"  # New prompt with IB range instruction
   metric: "day_type_accuracy"
   target_improvement: 0.10
   min_sample_size: 20
   allocation: 0.5  # Alternate days
   start_date: "2026-03-15"
   ```

2. **Alternate by day** — not within a day. Trading consistency requires the same agent behavior throughout a session.
   - Odd trading days since start → variant A
   - Even trading days since start → variant B

3. **Minimum 20 sessions** before evaluating (10 per variant).

4. **Statistical test:** Paired t-test on the primary metric.
   - p < 0.05 → statistically significant result
   - p 0.05-0.10 → extend to 40 sessions
   - p > 0.10 after 40 sessions → inconclusive, revert to A

5. **Decision matrix:**

   | Result | p-value | Action |
   |--------|---------|--------|
   | B wins | < 0.05 | Promote B as new default |
   | B wins | 0.05-0.10 | Extend to 40 sessions |
   | A wins | < 0.05 | Keep A, archive test |
   | Inconclusive | > 0.10 @ 40 sessions | Keep A, archive test |

6. **Post-promotion:** If B wins, run full backtest with B to compare against baseline. Archive test results.

---

### Stage 4 — Meta-Review (Opus 4.6)

**Timing:** Every 1-3 days on schedule, or triggered early by:
- `day_type_accuracy < 0.5` for 2 consecutive days
- `win_rate` drops > 10% from 20-day average
- 3+ adjustment proposals accumulated without review
- New regime detected (VIX spike, volume regime shift)

**Input to Opus 4.6:**
1. Last 3-5 daily reflection journals
2. Agent scorecards (rolling 20-day window)
3. Current prompt versions for all agents
4. Current parameter configs
5. Pending adjustment proposals from Qwen3.5
6. Recent backtest results

**Output from Opus 4.6:**
1. APPROVED adjustments (from Qwen3.5 proposals)
2. NEW adjustments Opus identifies
3. A/B test designs for uncertain changes
4. Prompt rewrites (full new versions)
5. Code change suggestions (deterministic calc improvements)

**All changes go to named git branches:**
```
adjust/skeptic-ib-check         ← Prompt change + A/B test config
adjust/bday-threshold-35        ← Parameter tweak
experiment/new-dpoc-weight      ← Larger experiment with code changes
```

**Merge approval:** Tier 2 changes require human review of the branch. At Automation Level 2+ (see [11-testing-and-automation.md](../architecture/11-testing-and-automation.md)), safe parameter adjustments within bounds can auto-merge if CI passes.

---

### Stage 5 — Model Retraining Trigger

**When agent improvements plateau** (prompt/parameter changes no longer yield improvements), the system triggers a LoRA retrain to improve the underlying model.

**Plateau detection:**
- Last 3 A/B tests all inconclusive
- Day type accuracy stagnant (±2%) for 30+ sessions
- Meta-review identifies "the model doesn't understand X" as a root cause

**Retraining process** (cross-reference [12-training-mlops.md](12-training-mlops.md)):

1. Collect new training examples from the self-learning loop:
   - Correct predictions (reinforce good behavior)
   - Failures with reflection-identified corrections (upweighted)
   - Role-specific examples from winning debates
2. Train new LoRA adapter
3. Evaluate against holdout test set
4. Compare against baseline — must match or exceed on all metrics
5. Deploy with 5-day canary period
6. Auto-rollback if live performance degrades

See [13-automation-infrastructure.md](13-automation-infrastructure.md) for the APScheduler jobs and GitHub Actions pipelines that automate this.

---

### Stage 6 — Rollback Guards

**Auto-rollback triggers** (from `configs/safety.yaml`):

| Trigger | Condition | Window | Action |
|---------|-----------|--------|--------|
| Win rate crash | `session_win_rate < 0.30` | 3 sessions after version change | Rollback to previous version |
| Catastrophic loss | `session_pnl < -2x rolling_20d_avg_loss` | 1 session | Rollback + pause agent + alert |
| Day type accuracy collapse | `day_type_accuracy < 0.25` | 5 sessions after version change | Rollback |

**Rollback process:**

1. `AgentVersionManager.rollback(agent_id, reason)` reverts prompt/params to previous known-good version.
2. Version change logged to `version_changes` table in DuckDB.
3. Dashboard notification sent immediately.
4. Slack alert on any rollback.
5. Rollback reason and context stored for the next meta-review to analyze.

**Manual rollback** is always available:
```
POST /api/v1/agents/versions/{version_id}/rollback
```

---

## Part 3: Git Workflow

### Branch Naming Conventions

| Branch Type | Pattern | Example | Use |
|-------------|---------|---------|-----|
| Strategy dev | `strategy/{strat-name}` | `strategy/vwap-fade` | New strategy implementation |
| Agent experiment | `agent/{experiment-name}` | `agent/skeptic-ib-check` | A/B tests, prompt changes |
| Agent adjustment | `adjust/{change-name}` | `adjust/bday-threshold-35` | Parameter tweaks from meta-review |
| Daily reflection | `reflect/{date}` | `reflect/2026-03-15` | Auto-committed daily reflection artifacts |
| Bug fix | `fix/{description}` | `fix/edge-fade-ib-gate` | Bug fixes |

### CI Gates on PR

Every PR to `main` must pass:

```yaml
# Required checks (all must pass):
- lint: uv run ruff check packages/
- type-check: uv run mypy packages/rockit-core/
- unit-tests: uv run pytest packages/ --cov --cov-fail-under=80
- integration-tests: uv run pytest packages/*/tests/integration/
- backtest-regression: make backtest && make baseline-compare
- snapshot-regression: uv run pytest packages/rockit-pipeline/tests/integration/test_deterministic.py
```

### PR Template

```markdown
## What

[One-sentence description of the change]

## Why

[Context: hypothesis, meta-review recommendation, bug report, etc.]

## Type

- [ ] New strategy (Stage 2 → follows full lifecycle)
- [ ] Agent prompt/parameter change (from meta-review or A/B test)
- [ ] Bug fix
- [ ] Infrastructure / tooling
- [ ] Documentation

## Validation

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Backtest regression — no metric degradation
- [ ] Walk-forward validation (new strategies only)
- [ ] Shadow mode results (new strategies only)

## Metrics Impact

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Win rate | | | |
| Profit factor | | | |
| Max drawdown | | | |
```

### Merge Rules

- **`main` = production-eligible.** Anything merged to `main` can run in production.
- **Strategy enable is separate from merge.** A strategy can be merged to `main` with `enabled: false`. Enabling it for live trading is a Stage 6 human decision.
- **`reflect/*` branches auto-merge** after daily reflection (Tier 1 changes only).
- **`adjust/*` branches require review** (Tier 2 changes).
- **`strategy/*` branches require full lifecycle** (Stages 1-6).

---

## Cross-Reference Map

| Topic | Primary Doc | This Doc |
|-------|------------|----------|
| StrategyBase interface | [04-strategy-framework.md](04-strategy-framework.md) | Stage 2 implementation |
| YAML config schema | [02-config-schemas.md](02-config-schemas.md) | Stage 2 config entry |
| BaselineComparator | [11-testing-and-automation.md](../architecture/11-testing-and-automation.md) | Stage 3 gates |
| Agent graph (LangGraph) | [08-agent-system.md](../architecture/08-agent-system.md) | Part 2 context |
| Self-learning loop | [08-self-learning.md](../architecture/08-self-learning.md) | Part 2 Stages 2-4 |
| Self-modification tiers | [08-self-learning.md](../architecture/08-self-learning.md) | Part 2 Stage 2 |
| A/B test framework | [08-agent-system.md](../architecture/08-agent-system.md) / [08-self-learning.md](../architecture/08-self-learning.md) | Part 2 Stage 3 |
| Auto-rollback guards | [08-self-learning.md](../architecture/08-self-learning.md) | Part 2 Stage 6 |
| Training pipeline | [12-training-mlops.md](12-training-mlops.md) | Part 2 Stage 5 |
| CI/CD pipeline | [13-automation-infrastructure.md](13-automation-infrastructure.md) | Part 3 CI gates |
| Automation levels | [11-testing-and-automation.md](../architecture/11-testing-and-automation.md) | Part 2 Stage 4 merge policy |
