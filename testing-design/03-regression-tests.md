# Regression Tests

> **Purpose:** Detect unintended output changes when code is modified
> **Scope:** Backtest results, deterministic snapshots, per-strategy trade lists
> **CI gate:** Every PR (fast subset), nightly (full 259-session run)

---

## Overview

Regression testing ensures that code changes do not silently alter system output.
In a quantitative trading platform, even small changes to indicator calculations
or filter thresholds can cascade into different trade decisions. The regression
test suite locks known-good outputs and fails loudly when they change.

Three categories of regression:
1. **Backtest regression** -- The 259-session backtest produces identical trades.
2. **Snapshot regression** -- Deterministic module output matches reference JSONs.
3. **Baseline comparison** -- Performance metrics stay within tolerance of the frozen baseline.

---

## Backtest Regression

### Reference Artifacts

The backtest regression suite depends on two reference files:

```
configs/baselines/
├── current.json               # Frozen performance metrics (see architecture/11-testing-and-automation.md)
└── reference_trades.json      # Complete trade list: [{session_date, strategy_name, direction, entry_price, ...}]
```

`current.json` contains aggregate metrics:

```json
{
    "version": "v1.0.0",
    "created_date": "2026-03-15",
    "det_win_rate": 0.555,
    "det_profit_factor": 1.58,
    "det_total_trades": 283,
    "det_net_pnl": 19500.0,
    "det_max_drawdown": -3200.0,
    "det_sharpe": 1.45,
    "strategy_baselines": {
        "trend_bull": {"trades": 42, "win_rate": 0.62, "profit_factor": 1.85},
        "p_day": {"trades": 38, "win_rate": 0.58, "profit_factor": 1.65},
        "b_day": {"trades": 35, "win_rate": 0.51, "profit_factor": 1.42}
    }
}
```

`reference_trades.json` contains the full trade list (283 trades):

```json
[
    {
        "session_date": "2025-03-03",
        "strategy_name": "trend_bull",
        "direction": "LONG",
        "entry_price": 21856.25,
        "stop_price": 21816.25,
        "target_price": 21936.25,
        "exit_price": 21928.50,
        "exit_reason": "target_hit",
        "pnl": 72.25
    }
]
```

### How to Run

```bash
# Fast regression (compares aggregate metrics only, < 30 seconds)
uv run pytest packages/ -m regression -k "not trade_list" -v

# Full regression (compares every trade, ~ 5 minutes)
uv run pytest packages/ -m regression -v

# Nightly: full backtest from raw data
uv run python -m rockit_pipeline.backtest.engine \
    --config configs/strategies.yaml \
    --sessions 259 \
    --compare configs/baselines/current.json
```

### Implementation

```python
# packages/rockit-pipeline/tests/regression/test_backtest_regression.py

import json
import pytest
from pathlib import Path

from rockit_pipeline.baseline.comparator import BaselineComparator, Baseline


BASELINE_DIR = Path("configs/baselines")


def load_baseline() -> Baseline:
    """Load the current frozen baseline."""
    data = json.loads((BASELINE_DIR / "current.json").read_text())
    return Baseline(**data)


@pytest.mark.regression
class TestBacktestRegression:
    """Backtest output must match the frozen baseline."""

    @pytest.fixture(scope="module")
    def result(self):
        """Run full backtest once for the module."""
        from rockit_pipeline.backtest.runner import run_full_backtest
        return run_full_backtest(config_path="configs/strategies.yaml")

    @pytest.fixture(scope="module")
    def baseline(self) -> Baseline:
        return load_baseline()

    def test_total_trades_exact(self, result, baseline) -> None:
        """Trade count must be identical. Any difference means logic changed."""
        assert result.total_trades == baseline.det_total_trades, (
            f"Trade count changed: {result.total_trades} != {baseline.det_total_trades}. "
            "This means strategy logic, filter logic, or data changed."
        )

    def test_win_rate_within_tolerance(self, result, baseline) -> None:
        """Win rate must match within floating-point tolerance."""
        assert abs(result.win_rate - baseline.det_win_rate) < 0.001

    def test_profit_factor_within_tolerance(self, result, baseline) -> None:
        """Profit factor must match within tolerance."""
        assert abs(result.profit_factor - baseline.det_profit_factor) < 0.01

    def test_max_drawdown_not_worse(self, result, baseline) -> None:
        """Max drawdown must not be worse (more negative) than baseline."""
        assert result.max_drawdown >= baseline.det_max_drawdown, (
            f"Drawdown worsened: {result.max_drawdown} < {baseline.det_max_drawdown}"
        )

    @pytest.mark.slow
    def test_trade_list_identical(self, result) -> None:
        """Every trade must match the reference trade list exactly."""
        ref_trades = json.loads(
            (BASELINE_DIR / "reference_trades.json").read_text()
        )
        assert len(result.trades) == len(ref_trades), (
            f"Trade count mismatch: {len(result.trades)} vs {len(ref_trades)}"
        )
        for i, (actual, expected) in enumerate(zip(result.trades, ref_trades)):
            assert actual.session_date == expected["session_date"], (
                f"Trade {i}: date {actual.session_date} != {expected['session_date']}"
            )
            assert actual.strategy_name == expected["strategy_name"], (
                f"Trade {i}: strategy {actual.strategy_name} != {expected['strategy_name']}"
            )
            assert actual.direction == expected["direction"], (
                f"Trade {i}: direction {actual.direction} != {expected['direction']}"
            )
            assert abs(actual.entry_price - expected["entry_price"]) < 0.01, (
                f"Trade {i}: entry {actual.entry_price} != {expected['entry_price']}"
            )

    def test_per_strategy_trade_counts(self, result, baseline) -> None:
        """Each strategy's trade count must match baseline."""
        for name, strat_bl in baseline.strategy_baselines.items():
            actual_count = result.strategy_stats.get(name, {}).get("trades", 0)
            assert actual_count == strat_bl["trades"], (
                f"{name}: {actual_count} trades vs baseline {strat_bl['trades']}"
            )
```

---

## Snapshot Regression

### Reference Artifacts

Deterministic snapshot references are stored per session and per time slice:

```
packages/rockit-core/tests/fixtures/snapshots/
├── 2026-01-15_1030_NQ.json
├── 2026-01-15_1100_NQ.json
├── 2026-01-15_1145_NQ.json
├── 2026-01-15_1300_NQ.json
├── 2026-01-15_1430_NQ.json
├── 2026-01-22_1145_NQ.json     # B-Day reference
├── 2026-01-28_1145_NQ.json     # P-Day reference
└── ...
```

Each file is the complete JSON output of `Orchestrator.generate_snapshot()` for
that session/time combination.

### Implementation

```python
# packages/rockit-core/tests/regression/test_snapshot_regression.py

import json
import pytest
from pathlib import Path

from rockit_core.deterministic.orchestrator import Orchestrator


SNAPSHOT_DIR = Path(__file__).parent.parent / "fixtures" / "snapshots"
SESSION_DIR = Path(__file__).parent.parent / "fixtures" / "sessions"


def snapshot_reference_files() -> list[Path]:
    """Discover all reference snapshot JSON files."""
    return sorted(SNAPSHOT_DIR.glob("*.json"))


def parse_snapshot_filename(path: Path) -> tuple[str, str, str]:
    """Parse '2026-01-15_1145_NQ.json' into (date, time, instrument)."""
    stem = path.stem  # '2026-01-15_1145_NQ'
    parts = stem.split("_")
    date = parts[0]
    time_str = parts[1][:2] + ":" + parts[1][2:]  # '1145' -> '11:45'
    instrument = parts[2]
    return date, time_str, instrument


@pytest.mark.regression
@pytest.mark.parametrize(
    "ref_file",
    snapshot_reference_files(),
    ids=[f.stem for f in snapshot_reference_files()],
)
def test_snapshot_matches_reference(ref_file: Path) -> None:
    """Each snapshot must match its reference JSON."""
    date, time_str, instrument = parse_snapshot_filename(ref_file)
    session_csv = SESSION_DIR / f"{date}_{instrument}.csv"

    if not session_csv.exists():
        pytest.skip(f"Session CSV not found: {session_csv}")

    input_data = pd.read_csv(session_csv, parse_dates=["timestamp"])
    orchestrator = Orchestrator()
    actual = orchestrator.generate_snapshot(
        input_data, config={"time": time_str, "instrument": instrument},
    )
    reference = json.loads(ref_file.read_text())

    compare_snapshot_dicts(actual, reference, path_prefix="")


def compare_snapshot_dicts(actual: dict, expected: dict, path_prefix: str) -> None:
    """Recursively compare two snapshot dicts with type-aware tolerance."""
    for key in expected:
        full_path = f"{path_prefix}.{key}" if path_prefix else key
        assert key in actual, f"Missing key in actual: {full_path}"

        exp_val = expected[key]
        act_val = actual[key]

        if isinstance(exp_val, dict):
            compare_snapshot_dicts(act_val, exp_val, full_path)
        elif isinstance(exp_val, float):
            assert abs(act_val - exp_val) < 1e-6, (
                f"{full_path}: {act_val} != {exp_val} (diff={abs(act_val - exp_val)})"
            )
        elif isinstance(exp_val, list):
            assert len(act_val) == len(exp_val), (
                f"{full_path}: list length {len(act_val)} != {len(exp_val)}"
            )
        else:
            assert act_val == exp_val, f"{full_path}: {act_val} != {exp_val}"
```

---

## Baseline Comparison Gates

### Evaluation Gates

The `BaselineComparator` runs as a CI gate. It loads the current baseline and
compares against the backtest result. The gate fails if ANY regression metric
exceeds its threshold.

```python
# packages/rockit-pipeline/src/rockit_pipeline/baseline/comparator.py (test usage)

REGRESSION_THRESHOLDS = {
    "win_rate":       -0.05,   # 5% absolute drop
    "profit_factor":  -0.15,   # 0.15 drop
    "max_drawdown":   -500.0,  # $500 worse
    "sharpe":         -0.20,   # 0.20 drop
    "total_trades":   -5,      # Losing 5+ trades is suspicious
}

IMPROVEMENT_THRESHOLDS = {
    "win_rate":       0.02,
    "profit_factor":  0.10,
    "sharpe":         0.10,
}
```

The comparator produces a `ComparisonReport`:

```python
@dataclass
class CheckResult:
    metric: str
    current: float
    baseline: float
    delta: float
    threshold: float
    passed: bool

@dataclass
class ComparisonReport:
    regressions: list[CheckResult]
    improvements: list[CheckResult]
    passed: bool  # True only if ALL regression checks pass
```

### What Triggers a Baseline Update

Baselines are **never** updated automatically. They are updated deliberately
when performance genuinely improves. The protocol:

1. A code change produces better backtest results.
2. The developer runs the full 259-session backtest.
3. The `BaselineComparator` confirms improvement on multiple metrics.
4. The developer creates a new baseline version:

```bash
# Generate new baseline from current backtest result
uv run python -m rockit_pipeline.baseline.updater \
    --backtest-result results/latest_backtest.json \
    --version v1.1.0 \
    --description "Added VIX gate to EdgeFade, improved B-Day filtering"

# This creates:
#   configs/baselines/v1.1.0.json
#   configs/baselines/reference_trades_v1.1.0.json
#   Updates configs/baselines/current.json symlink
```

5. The old baseline is archived, never deleted.

### Handling Intentional Changes

When a code change intentionally alters output (new strategy, changed threshold,
removed filter), the regression tests will fail. This is expected. The workflow:

```
1. Make the code change.
2. Run regression tests → they fail (expected).
3. Review the diff:
   - How many trades changed?
   - Did win rate improve or degrade?
   - Are the changed trades sensible?
4. If the change is correct:
   a. Re-generate reference_trades.json from the new backtest.
   b. Update the baseline metrics.
   c. Commit both the code change AND the updated references in the same PR.
5. If the change is wrong:
   a. Fix the code.
   b. Regression tests pass again.
```

The PR review checklist for intentional changes:

```markdown
## Regression Change Checklist

- [ ] I ran the full 259-session backtest
- [ ] The trade count change is explained: ___
- [ ] Win rate change: ___ → ___ (reason: ___)
- [ ] Profit factor change: ___ → ___ (reason: ___)
- [ ] Max drawdown change: ___ → ___ (reason: ___)
- [ ] Updated reference_trades.json
- [ ] Updated configs/baselines/current.json
- [ ] Old baseline archived as configs/baselines/v{old}.json
```

---

## Snapshot Regression Update Protocol

When deterministic modules are modified (bug fix, new module, algorithm change),
snapshot references must be regenerated.

```bash
# Regenerate all snapshot references
uv run python -m rockit_core.deterministic.generate_references \
    --sessions-dir data/sessions/ \
    --output-dir packages/rockit-core/tests/fixtures/snapshots/ \
    --times "10:30,11:00,11:45,13:00,14:30"

# Regenerate a single session
uv run python -m rockit_core.deterministic.generate_references \
    --session data/sessions/2026-01-15_NQ.csv \
    --output-dir packages/rockit-core/tests/fixtures/snapshots/ \
    --times "11:45"
```

The regeneration script is deterministic. Running it twice on the same input
produces identical output. The script itself is tested:

```python
def test_reference_generation_is_deterministic() -> None:
    """Running generate_references twice produces identical files."""
    run_1 = generate_references(session="fixtures/sessions/2026-01-15_NQ.csv", time="11:45")
    run_2 = generate_references(session="fixtures/sessions/2026-01-15_NQ.csv", time="11:45")
    assert run_1 == run_2
```

---

## Summary: What Runs Where

| Test | Scope | Speed | CI Gate |
|------|-------|-------|---------|
| Aggregate metric comparison | Backtest metrics vs baseline | < 30s | Every PR |
| Per-strategy trade count | Strategy-level counts vs baseline | < 30s | Every PR |
| Full trade list comparison | Every trade vs reference | ~ 5 min | Nightly |
| Snapshot regression (5 times) | 1 session x 5 timestamps | < 1 min | Every PR |
| Snapshot regression (full) | All sessions x all timestamps | ~ 10 min | Nightly |
| Baseline improvement check | New metrics vs frozen baseline | < 10s | On request |
