# Testing Strategy, Baselines, & Autonomous MLOps

## Overview

Four layers of testing, a baseline system to know if you're improving, a 6-layer evaluation framework (Design Principle #5), and a fully automated MLOps pipeline that minimizes human interaction. Claude Code can be the human-in-the-loop for code changes.

### 6-Layer Evaluation Framework (Design Principle #5)

Every layer of the system emits metrics to DuckDB. No change ships without measurable comparison:

| Layer | What | Example Metric | When |
|-------|------|---------------|------|
| 1. Component | Module-level output | FVG detection precision, CRI score distribution | Phase 1 |
| 2. Strategy | Per-strategy trading | Win rate, PF, expectancy per strategy | Phase 1 |
| 3. Data Quality | Schema compliance | Snapshot field coverage, schema validation pass rate | Phase 1 |
| 4. LLM Quality | Model accuracy | Day type accuracy pre/post training | Phase 4 |
| 5. Agent Quality | Agent value-added | Consensus override accuracy, skeptic save rate | Phase 5 |
| 6. System | End-to-end trading | Net P&L, Sharpe, rolling drawdown | Phase 5 |

See [roadmap/10-evaluation.md](../roadmap/10-evaluation.md) for implementation timeline.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TESTING PYRAMID                               │
│                                                                 │
│                    ┌───────────┐                                │
│                    │ Live      │ ← Shadow mode, then real       │
│                    │ Validation│   (manual gate first)          │
│                   ┌┴───────────┴┐                               │
│                   │ Multi-Agent  │ ← Agent integration tests    │
│                   │ Integration  │   (90-day replay)            │
│                  ┌┴──────────────┴┐                              │
│                  │ Component       │ ← Integration tests         │
│                  │ Integration     │   (strategy + filter chain) │
│                 ┌┴────────────────┴┐                             │
│                 │ Unit Tests        │ ← Every function, pure     │
│                 │ (rockit-core)     │   Python, fast, CI         │
│                 └───────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Unit Tests

Every package has unit tests. Fast, deterministic, run on every push.

### What Gets Unit-Tested

```
packages/rockit-core/tests/
├── strategies/
│   ├── test_base.py              # StrategyBase contract tests
│   ├── test_trend_bull.py        # Signal conditions, edge cases
│   ├── test_trend_bear.py
│   ├── test_p_day.py
│   ├── test_b_day.py
│   ├── test_edge_fade.py
│   ├── test_or_reversal.py
│   ├── test_day_type.py          # Day type classification
│   └── test_day_confidence.py    # Confidence scorer calibration
├── filters/
│   ├── test_composite.py         # Filter chain composition
│   ├── test_order_flow.py        # Delta/CVD thresholds
│   ├── test_regime.py            # Regime gate logic
│   ├── test_time.py              # Session window boundaries
│   └── test_volatility.py        # Volatility gates
├── indicators/
│   ├── test_ict.py               # FVG, IFVG, BPR detection
│   ├── test_volume_profile.py    # POC, VAH, VAL computation
│   └── test_tpo.py               # TPO profile generation
└── data/
    ├── test_loader.py            # CSV parsing, edge cases
    ├── test_features.py          # Feature engineering
    └── test_session.py           # Session boundary logic

packages/rockit-pipeline/tests/
├── backtest/
│   ├── test_engine.py            # Backtest runner correctness
│   ├── test_execution.py         # Slippage, commission calcs
│   ├── test_position.py          # Trailing stop logic
│   └── test_equity.py            # Equity curve tracking
├── reflection/
│   ├── test_outcome_logger.py    # Outcome computation
│   ├── test_scorecard.py         # Scorecard aggregation
│   ├── test_version_manager.py   # Version promotion/rollback
│   ├── test_ab_test.py           # A/B test statistical logic
│   └── test_auto_adjust.py       # Safe adjustment bounds
└── deterministic/
    ├── test_generator.py         # Snapshot generation
    └── test_annotator.py         # Annotation accuracy
```

### Unit Test Principles

```python
# Example: Strategy unit test with known-good fixture

def test_trend_bull_signal_basic():
    """TrendBull emits long signal when IB acceptance + strong delta."""
    context = SessionContext(
        ib_high=21850, ib_low=21780, ib_range=70,
        current_price=21860,          # Above IBH (acceptance)
        delta=450,                    # Strong positive delta
        cvd_trend="up",
        vwap=21820,
        day_type_prob={"TREND": 0.7, "P_DAY": 0.2},
    )
    strategy = TrendDayBull()
    signals = strategy.evaluate(context)
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert signals[0].confidence > 0.6

def test_trend_bull_no_signal_weak_delta():
    """TrendBull does NOT signal when delta is weak."""
    context = SessionContext(
        ib_high=21850, ib_low=21780, ib_range=70,
        current_price=21860,
        delta=50,                     # Weak delta
        cvd_trend="flat",
        vwap=21820,
        day_type_prob={"TREND": 0.4, "P_DAY": 0.3},
    )
    strategy = TrendDayBull()
    signals = strategy.evaluate(context)
    assert len(signals) == 0
```

### Coverage Targets

```yaml
# pyproject.toml (root)
[tool.pytest.ini_options]
addopts = "--cov=packages --cov-report=html --cov-fail-under=80"

# Coverage targets by package:
# rockit-core:     90%+ (pure logic, no excuses)
# rockit-pipeline: 80%+ (some I/O boundaries)
# rockit-serve:    75%+ (API layer, some mocking needed)
# rockit-train:    70%+ (training has GPU-dependent paths)
```

---

## Layer 2: Component Integration Tests

Test strategy + filter chain + execution pipeline working together. Uses real historical data fixtures.

```python
# packages/rockit-pipeline/tests/integration/test_strategy_pipeline.py

class TestStrategyPipeline:
    """Integration: strategy evaluation through full filter chain."""

    @pytest.fixture
    def known_trend_day_data(self):
        """2026-01-15: Clear trend day. Load actual historical data."""
        return load_session_data("fixtures/2026-01-15_NQ.csv")

    @pytest.fixture
    def known_bday_data(self):
        """2026-01-22: Clear B-Day. Load actual historical data."""
        return load_session_data("fixtures/2026-01-22_NQ.csv")

    def test_trend_day_produces_long_signal(self, known_trend_day_data):
        """On a known trend day, the pipeline should produce a long signal."""
        pipeline = StrategyPipeline(
            strategies=CORE_STRATEGIES,
            filters=CompositeFilter.default(),
        )
        signals = pipeline.evaluate_session(known_trend_day_data)

        # At least one trend strategy should fire
        trend_signals = [s for s in signals if "trend" in s.strategy.lower()]
        assert len(trend_signals) > 0
        assert all(s.direction == "long" for s in trend_signals)

    def test_bday_does_not_produce_trend_signal(self, known_bday_data):
        """On a known B-Day, trend strategies should NOT fire."""
        pipeline = StrategyPipeline(
            strategies=CORE_STRATEGIES,
            filters=CompositeFilter.default(),
        )
        signals = pipeline.evaluate_session(known_bday_data)

        trend_signals = [s for s in signals if "trend" in s.strategy.lower()]
        assert len(trend_signals) == 0

    def test_filter_chain_blocks_low_quality(self, known_trend_day_data):
        """Filters should block signals with poor order flow quality."""
        # Modify data to have weak order flow
        weak_data = known_trend_day_data.copy()
        weak_data["delta"] = 10  # Very weak
        weak_data["cvd_trend"] = "flat"

        pipeline = StrategyPipeline(
            strategies=CORE_STRATEGIES,
            filters=CompositeFilter.default(),
        )
        signals = pipeline.evaluate_session(weak_data)
        assert len(signals) == 0  # All filtered out
```

### Deterministic Snapshot Tests

```python
# packages/rockit-pipeline/tests/integration/test_deterministic.py

def test_deterministic_snapshot_matches_reference():
    """Snapshot output should match known-good reference output."""
    input_data = load_test_data("fixtures/2026-01-15_NQ.csv")
    snapshot = generate_snapshot(input_data, time="11:45")

    reference = load_json("fixtures/reference_snapshot_2026-01-15_1145.json")

    # Core fields must match exactly
    assert snapshot["ib"]["high"] == reference["ib"]["high"]
    assert snapshot["ib"]["low"] == reference["ib"]["low"]
    assert snapshot["volume_profile"]["poc"] == reference["volume_profile"]["poc"]
    assert snapshot["tpo_profile"]["shape"] == reference["tpo_profile"]["shape"]
```

---

## Layer 3: Multi-Agent Integration Tests

Test the full LangGraph agent pipeline. Requires a running LLM (Ollama in CI, or mocked).

```python
# packages/rockit-serve/tests/integration/test_agent_pipeline.py

@pytest.fixture
def mock_llm():
    """Use a small fast model or mock for CI testing."""
    # Option A: Ollama with small model in CI
    return ChatOpenAI(
        base_url="http://localhost:11434/v1",
        model="qwen2.5:1.5b",  # Tiny model for testing
        api_key="not-needed",
    )
    # Option B: Mock with canned responses
    # return MockChatModel(responses=load_canned_responses())

class TestAgentPipeline:

    def test_high_confidence_skips_debate(self, mock_llm):
        """When deterministic confidence > 0.90, skip LLM debate."""
        graph = build_agent_graph(llm=mock_llm)
        result = graph.invoke({
            "time_slice": make_high_confidence_context(),
            "session_date": "2026-01-15",
        })
        # Should go straight to risk check, no debate
        assert result["advocate_argument"] is None
        assert result["consensus_decision"] == "TAKE"

    def test_debate_produces_structured_output(self, mock_llm):
        """When debate triggers, advocate + skeptic produce valid output."""
        graph = build_agent_graph(llm=mock_llm)
        result = graph.invoke({
            "time_slice": make_moderate_confidence_context(),
            "session_date": "2026-01-15",
        })
        assert result["advocate_argument"] is not None
        assert result["skeptic_argument"] is not None
        assert result["consensus_decision"] in ["TAKE", "SKIP", "REDUCE_SIZE"]

    def test_risk_check_blocks_overlimit(self, mock_llm):
        """Risk check blocks signals that exceed position limits."""
        graph = build_agent_graph(llm=mock_llm)
        result = graph.invoke({
            "time_slice": make_moderate_confidence_context(),
            "session_date": "2026-01-15",
            "current_exposure": 4000.0,  # Already at max DD
        })
        assert result["final_signals"] == []
```

---

## Layer 4: Baseline Performance System

### The Problem

> How do we know where we work from and what we do improves over time?

You need a **frozen baseline** that every change is measured against.

### Baseline Definition

```python
# packages/rockit-pipeline/src/rockit_pipeline/baseline/baseline.py

@dataclass
class Baseline:
    """Frozen performance snapshot used as comparison point."""
    version: str                     # "v1.0.0"
    created_date: str                # "2026-03-15"
    description: str                 # "Initial system baseline"

    # Deterministic performance (259 sessions)
    det_win_rate: float              # 0.555
    det_profit_factor: float         # 1.58
    det_total_trades: int            # 283
    det_net_pnl: float               # 19500.0
    det_max_drawdown: float          # -3200.0
    det_sharpe: float                # 1.45

    # Per-strategy baselines
    strategy_baselines: dict[str, StrategyBaseline]

    # Agent performance (from 90-day multi-agent backtest)
    agent_win_rate: float            # 0.58 (after agent filtering)
    agent_profit_factor: float       # 1.72
    agent_day_type_accuracy: float   # 0.68
    agent_calibration_error: float   # 0.12
    agent_consensus_accuracy: float  # 0.65

    # Prompt versions at baseline time
    prompt_versions: dict[str, str]  # {"advocate": "v01", "skeptic": "v01", ...}

@dataclass
class StrategyBaseline:
    strategy: str
    trades: int
    win_rate: float
    profit_factor: float
    avg_rr: float
    max_drawdown: float
```

### Baseline Comparison (CI Gate)

Every PR and every self-learning adjustment is compared against the baseline:

```python
# packages/rockit-pipeline/src/rockit_pipeline/baseline/comparator.py

class BaselineComparator:
    """Compare current performance against frozen baseline."""

    def __init__(self, baseline: Baseline):
        self.baseline = baseline

    def compare(self, current: PerformanceMetrics) -> ComparisonReport:
        return ComparisonReport(
            # Regression checks (must not get worse)
            regressions=[
                check("win_rate", current.win_rate, self.baseline.det_win_rate, threshold=-0.05),
                check("profit_factor", current.pf, self.baseline.det_profit_factor, threshold=-0.15),
                check("max_drawdown", current.max_dd, self.baseline.det_max_drawdown, threshold=-500),
            ],
            # Improvements (nice to track)
            improvements=[
                check("win_rate", current.win_rate, self.baseline.det_win_rate, threshold=0.02),
                check("sharpe", current.sharpe, self.baseline.det_sharpe, threshold=0.1),
            ],
            passed=all(r.passed for r in regressions),
        )

def check(metric: str, current: float, baseline: float, threshold: float) -> CheckResult:
    delta = current - baseline
    if threshold < 0:  # Regression check
        passed = delta >= threshold
    else:  # Improvement check
        passed = delta >= threshold
    return CheckResult(metric=metric, current=current, baseline=baseline,
                       delta=delta, threshold=threshold, passed=passed)
```

### Baseline Update Protocol

```yaml
# Baselines don't drift — they're updated deliberately:

baseline_update:
  # When to create a new baseline:
  triggers:
    - "Major strategy change merged to main"
    - "Significant performance improvement validated over 30+ sessions"
    - "System architecture change (new agents, new filters)"

  # Process:
  steps:
    1. "Run full 259-session backtest"
    2. "Run 90-day multi-agent backtest"
    3. "Compare against current baseline"
    4. "If improved: create new baseline version (v1.0.0 → v1.1.0)"
    5. "Archive old baseline (never delete)"
    6. "Commit new baseline.json to configs/baselines/"

  # Storage:
  storage:
    path: "configs/baselines/"
    files:
      - "v1.0.0.json"    # Initial baseline
      - "v1.1.0.json"    # After first improvement cycle
      - "current.json"   # Symlink to active baseline
```

---

## Layer 5: A/B Testing as Performance Measurement

A/B tests from the self-learning loop (doc 08) are the primary way to validate improvements.

### A/B Test Results Feed Back to Baseline

```
Self-Learning Loop:
  Day 1-20:  A/B test runs (variant A vs B, alternating days)
  Day 20:    Statistical significance check

  If B wins:
    1. Promote variant B as the default
    2. Run full backtest with B
    3. Compare against baseline
    4. If baseline improvement > threshold → update baseline
    5. Archive A/B test results

  If inconclusive:
    1. Extend test to 40 sessions
    2. Or discard B, keep A
```

### A/B Test Reporting (Dashboard)

```
┌─────────────────────────────────────────────────────────┐
│  A/B TEST: skeptic-ib-check                             │
│  Status: Running (Day 12/20)                            │
│                                                         │
│  Variant A (current):    Variant B (new):               │
│  WR: 56%                 WR: 62%                        │
│  PF: 1.55                PF: 1.78                       │
│  Day Type Acc: 65%       Day Type Acc: 73%              │
│                                                         │
│  p-value: 0.12 (not yet significant)                    │
│  Projected significance at day: 18                      │
│                                                         │
│  [Extend] [Stop - Keep A] [Stop - Promote B]            │
└─────────────────────────────────────────────────────────┘
```

---

## Layer 6: Automated MLOps Pipeline (Minimal Human Interaction)

### The Goal

```
Fully automated:
  Code quality    → CI/CD (pytest, ruff, coverage)
  Backtesting     → Runs on every code change
  Data generation → Triggered by new backtest data
  LoRA training   → Triggered by new training data
  Model eval      → Automated benchmark suite
  Deployment      → Auto-deploy if eval passes

Semi-automated (Claude Code as human-in-the-loop):
  Meta-review     → Opus 4.6 proposes, Claude Code implements
  Code changes    → Claude Code writes code, CI validates
  Baseline update → Claude Code reviews and approves

Manual (human decision):
  Risk limits     → Account parameters, max drawdown
  Strategy enable → Turning on new strategies for live
  Infra changes   → Hardware, model swaps
```

### Automated Retraining Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                AUTOMATED RETRAINING PIPELINE                     │
│                                                                  │
│  Trigger: New reflection data accumulates (every 30 days)        │
│           OR baseline performance drops > 5%                     │
│           OR A/B test concludes with winner                      │
│                                                                  │
│  ┌──────────────┐   ┌───────────────┐   ┌────────────────┐     │
│  │ 1. Collect    │──▶│ 2. Generate   │──▶│ 3. Train       │     │
│  │ reflection    │   │ new training  │   │ new LoRA       │     │
│  │ data          │   │ examples from │   │ adapter        │     │
│  │ (30 days)     │   │ reflection    │   │ (DGX/Vertex)   │     │
│  └──────────────┘   └───────────────┘   └────────┬───────┘     │
│                                                    │             │
│  ┌──────────────┐   ┌───────────────┐   ┌────────▼───────┐     │
│  │ 6. Deploy    │◀──│ 5. Baseline   │◀──│ 4. Evaluate    │     │
│  │ or rollback  │   │ comparison    │   │ on test set    │     │
│  └──────────────┘   └───────────────┘   └────────────────┘     │
│                                                                  │
│  Gate: New model must match or exceed baseline on ALL metrics    │
│  Rollback: If live performance drops within 5 days, revert      │
└─────────────────────────────────────────────────────────────────┘
```

### Retraining Data Sources

```python
# packages/rockit-train/src/rockit_train/data_collector.py

class RetrainingDataCollector:
    """Collect new training examples from the self-learning loop."""

    def collect(self, days: int = 30) -> list[TrainingExample]:
        examples = []

        # Source 1: Original ROCKIT v5.6 dataset (always included)
        examples += self.load_original_dataset()

        # Source 2: Correct predictions (reinforce good behavior)
        for outcome in self.load_outcomes(days):
            if outcome.outcome == "WIN" and outcome.confidence > 0.6:
                examples.append(TrainingExample(
                    input=outcome.market_context,
                    output=self.format_correct_analysis(outcome),
                    weight=1.0,
                ))

        # Source 3: Failures with reflection-identified corrections
        for reflection in self.load_reflections(days):
            for failure in reflection.get("failures_analyzed", []):
                if failure.get("corrected_analysis"):
                    examples.append(TrainingExample(
                        input=failure["market_context"],
                        output=failure["corrected_analysis"],
                        weight=1.5,  # Upweight corrections
                    ))

        # Source 4: Role-specific examples from debates
        for debate in self.load_debates(days):
            if debate["outcome"] == "WIN":
                # Good advocate argument → training example
                examples.append(TrainingExample(
                    input=f"ROLE: ADVOCATE\n{debate['context']}",
                    output=debate["advocate_argument"],
                    weight=0.8,
                ))

        return examples
```

### Pipeline Triggers (Fully Automated)

```yaml
# configs/mlops/retrain_pipeline.yaml
retraining:
  triggers:
    # Time-based: every 30 trading days
    scheduled:
      interval_trading_days: 30
      min_new_examples: 50

    # Performance-based: when system degrades
    performance_drop:
      metric: "rolling_20d_win_rate"
      threshold: -0.08  # 8% drop from baseline
      cooldown_days: 7   # Don't retrain more than once a week

    # A/B test conclusion: winner needs training reinforcement
    ab_test_concluded:
      auto_retrain: true
      include_winning_examples: true

  evaluation:
    test_set: "gs://rockit-data/test/holdout.jsonl"  # Never trained on
    metrics:
      - name: "day_type_accuracy"
        threshold: 0.65           # Must beat
        baseline_compare: true    # Must match or beat baseline
      - name: "analysis_quality"  # LLM-as-judge score
        threshold: 0.70
      - name: "reasoning_coherence"
        threshold: 0.75

  deployment:
    auto_deploy: true              # Deploy if all gates pass
    canary_days: 5                 # Monitor for 5 days
    rollback_trigger: "win_rate < baseline - 0.10"

  notifications:
    on_retrain_start: "dashboard"
    on_retrain_complete: "dashboard + log"
    on_deploy: "dashboard + log"
    on_rollback: "dashboard + alert"
```

---

## Claude Code as the Autonomous Developer

For code-level changes (not just prompt/param tweaks), Claude Code can act as the human-in-the-loop:

```
Opus 4.6 Meta-Review says:
  "The EdgeFade strategy should add a VIX > 25 gate.
   Reflection data shows 0/4 wins when VIX > 25."

  ↓

Claude Code (automated or invoked):
  1. Reads the meta-review output
  2. Opens packages/rockit-core/src/rockit_core/strategies/edge_fade.py
  3. Adds VIX gate to evaluate() method
  4. Adds unit test for the new gate
  5. Runs pytest → passes
  6. Runs backtest → compares to baseline → no regression
  7. Commits to branch: adjust/edge-fade-vix-gate
  8. Pushes for review (or auto-merges if within safe bounds)
```

### Automation Levels

```
Level 0 (Now):
  Claude Code is used manually by the developer.
  All meta-review proposals require human review.

Level 1 (After baseline established):
  Daily reflection runs automatically.
  Claude Code implements meta-review suggestions on branches.
  Human reviews and merges branches.

Level 2 (After 60+ days of validated operation):
  Safe adjustments auto-merge (parameter tweaks within bounds).
  Claude Code auto-implements code changes on branches.
  CI gate (backtest + baseline comparison) decides merge.
  Human reviews weekly summary.

Level 3 (Aspirational):
  Full loop runs autonomously.
  Human reviews monthly.
  System alerts on anomalies only.
  Claude Code handles all code changes, retraining triggers,
  and deployment decisions within defined safety bounds.
```

---

## CI/CD Pipeline (Updated)

```yaml
# infra/cloudbuild/ci.yaml (updated)
steps:
  # 1. Code quality
  - name: 'lint'
    script: uv run ruff check packages/

  - name: 'type-check'
    script: uv run mypy packages/rockit-core/

  - name: 'unit-tests'
    script: |
      uv run pytest packages/rockit-core/tests/ --cov --cov-fail-under=90
      uv run pytest packages/rockit-pipeline/tests/ --cov --cov-fail-under=80
      uv run pytest packages/rockit-serve/tests/ --cov --cov-fail-under=75

  # 2. Integration tests
  - name: 'integration-tests'
    script: |
      uv run pytest packages/rockit-pipeline/tests/integration/
      uv run pytest packages/rockit-serve/tests/integration/

  # 3. Backtest regression
  - name: 'backtest'
    script: |
      uv run python -m rockit_pipeline.backtest.engine \
        --config configs/strategies.yaml \
        --sessions 259
    gate:
      compare: "configs/baselines/current.json"
      fail_on_regression: true

  # 4. Deterministic snapshot regression
  - name: 'snapshot-regression'
    script: |
      uv run pytest packages/rockit-pipeline/tests/integration/test_deterministic.py
```

---

## Updated Monorepo Additions

```
packages/rockit-pipeline/src/rockit_pipeline/
├── baseline/
│   ├── __init__.py
│   ├── baseline.py              # Baseline dataclass
│   ├── comparator.py            # Baseline comparison logic
│   └── updater.py               # Baseline creation/update

configs/
├── baselines/
│   ├── v1.0.0.json              # Initial baseline
│   └── current.json → v1.0.0.json
├── mlops/
│   └── retrain_pipeline.yaml    # Automated retraining config

packages/rockit-train/src/rockit_train/
├── data_collector.py            # Collect retraining data from reflections
├── retrain_pipeline.py          # Automated retraining orchestration
└── evaluator.py                 # Model evaluation against baseline
```
