# Testing Strategy

> **Scope:** All packages in the Rockit monorepo
> **Audience:** Coding agents (Qwen 3.5) implementing test suites, reviewers (Opus 4.6) validating coverage
> **Golden rule:** Migrated code must produce identical output to the original repositories

---

## Testing Pyramid

```
                    ┌───────────┐
                    │   Live    │  Shadow mode, then real capital
                    │ Validation│  (manual gate, weekly)
                   ┌┴───────────┴┐
                   │ Multi-Agent  │  Agent integration tests
                   │ Integration  │  (90-day replay, nightly)
                  ┌┴──────────────┴┐
                  │   Component     │  Strategy + filter chain
                  │   Integration   │  (backtest regression, per-PR)
                 ┌┴────────────────┴┐
                 │    Unit Tests     │  Every function, pure Python
                 │   (all packages)  │  (every push, < 60 seconds)
                 └───────────────────┘
```

Each layer is described in its own document. This document defines the overall
approach, tooling, and policies that apply across all layers.

---

## Tooling

| Tool | Purpose | Config location |
|------|---------|-----------------|
| `pytest` | Test runner | `pyproject.toml` per package |
| `pytest-cov` | Coverage measurement | `--cov-fail-under` per package |
| `pytest-xdist` | Parallel execution (nightly) | `-n auto` |
| `ruff` | Linting and formatting | Root `pyproject.toml` |
| `mypy` | Static type checking (strict for rockit-core) | Per-package `pyproject.toml` |
| `hypothesis` | Property-based testing (indicators, filters) | In test files |

### pytest Configuration (Root)

```toml
# pyproject.toml (workspace root)
[tool.pytest.ini_options]
testpaths = ["packages"]
markers = [
    "slow: marks tests that take > 5 seconds (deselect with '-m not slow')",
    "integration: component integration tests",
    "regression: backtest/snapshot regression tests",
    "agent: multi-agent pipeline tests (requires LLM)",
    "gpu: requires GPU (training pipeline)",
]
filterwarnings = [
    "ignore::DeprecationWarning:pandas",
]
```

---

## Coverage Targets

| Package | Target | Rationale |
|---------|--------|-----------|
| `rockit-core` | 90% | Pure logic: strategies, filters, indicators, models. No I/O excuses. |
| `rockit-pipeline` | 80% | Backtest engine, reflection loop. Some file I/O at boundaries. |
| `rockit-serve` | 75% | FastAPI routes, WebSocket. Mocking needed for HTTP layer. |
| `rockit-train` | 70% | LoRA training has GPU-dependent code paths that cannot run in CI. |
| `rockit-ingest` | 75% | CSV parsing, GCS upload. Mock GCS client for unit tests. |

Coverage is enforced in CI per package:

```bash
uv run pytest packages/rockit-core/tests/ --cov=packages/rockit-core/src --cov-fail-under=90
uv run pytest packages/rockit-pipeline/tests/ --cov=packages/rockit-pipeline/src --cov-fail-under=80
uv run pytest packages/rockit-serve/tests/ --cov=packages/rockit-serve/src --cov-fail-under=75
uv run pytest packages/rockit-train/tests/ --cov=packages/rockit-train/src --cov-fail-under=70
uv run pytest packages/rockit-ingest/tests/ --cov=packages/rockit-ingest/src --cov-fail-under=75
```

---

## Test Categories

### 1. Contract Tests

Verify that every implementation of an abstract base class honors its contract.
Every `StrategyBase` subclass must have a `name`, `applicable_day_types`, and
return `Signal | None` from `on_bar()`. Every `EntryModel` must implement
`detect()`. These tests are parameterized across ALL registered implementations.

```python
# Example: test every registered strategy
@pytest.mark.parametrize("name,cls", ALL_STRATEGIES.items())
def test_strategy_contract(name: str, cls: type) -> None:
    """Every strategy must satisfy the StrategyBase contract."""
    instance = cls()
    assert isinstance(instance.name, str)
    assert len(instance.name) > 0
    assert isinstance(instance.applicable_day_types, list)
```

### 2. Regression Tests

Lock known-good outputs so changes are detected immediately.
- **Backtest regression:** 259-session backtest produces identical trade list.
- **Snapshot regression:** `generate_snapshot()` output matches reference JSON.

See [03-regression-tests.md](03-regression-tests.md) for full details.

### 3. Snapshot Tests (pytest-snapshot or inline)

Smaller-scope output locking. Individual deterministic modules produce the same
dict output for a given input. Stored as JSON files in `tests/fixtures/snapshots/`.

### 4. Property-Based Tests (Hypothesis)

Used for indicators, filters, and trade models where we can define invariants:
- ATRStop always places stop on the correct side of entry price.
- RMultipleTarget target is always farther from entry than stop.
- CompositeFilter returns `False` if any sub-filter returns `False`.

```python
from hypothesis import given, strategies as st

@given(
    entry_price=st.floats(min_value=100, max_value=30000),
    atr=st.floats(min_value=1, max_value=500),
    direction=st.sampled_from(["LONG", "SHORT"]),
)
def test_atr_stop_correct_side(entry_price: float, atr: float, direction: str) -> None:
    """ATR stop is always on the losing side of entry."""
    stop = ATRStop(1.0)
    entry = EntrySignal(model="test", direction=direction, entry_price=entry_price, confidence=0.5)
    ctx = make_context(atr14=atr)
    stop_price = stop.compute(entry, ctx)
    if direction == "LONG":
        assert stop_price < entry_price
    else:
        assert stop_price > entry_price
```

---

## CI Integration

### On Every Push (< 2 minutes)

```yaml
steps:
  - name: lint
    script: uv run ruff check packages/

  - name: type-check
    script: uv run mypy packages/rockit-core/src/

  - name: unit-tests
    script: |
      uv run pytest packages/ -m "not slow and not integration and not agent and not gpu" \
        --cov --cov-fail-under=80 -q
```

### On Every PR (< 10 minutes)

```yaml
steps:
  - name: unit-tests-full
    script: |
      uv run pytest packages/rockit-core/tests/ --cov --cov-fail-under=90
      uv run pytest packages/rockit-pipeline/tests/ --cov --cov-fail-under=80
      uv run pytest packages/rockit-serve/tests/ --cov --cov-fail-under=75

  - name: integration-tests
    script: |
      uv run pytest packages/ -m integration

  - name: backtest-regression
    script: |
      uv run pytest packages/ -m regression
```

### Nightly (< 30 minutes)

```yaml
steps:
  - name: full-backtest
    script: |
      uv run python -m rockit_pipeline.backtest.engine \
        --config configs/strategies.yaml --sessions 259
    gate:
      compare: configs/baselines/current.json
      fail_on_regression: true

  - name: agent-integration
    script: |
      uv run pytest packages/rockit-serve/tests/ -m agent

  - name: snapshot-regression-full
    script: |
      uv run pytest packages/rockit-pipeline/tests/ -m regression --run-all-snapshots
```

---

## Handling LLM-Dependent Tests

Tests in `rockit-serve` that exercise the LangGraph agent pipeline need an LLM.
Three strategies, used at different layers:

### Strategy A: Mock Responses (Unit Tests, Every Push)

```python
class MockChatModel:
    """Deterministic mock that returns canned responses by prompt prefix."""

    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    def invoke(self, messages: list) -> str:
        prompt = messages[-1].content
        for prefix, response in self._responses.items():
            if prefix in prompt:
                return response
        return '{"decision": "SKIP", "reasoning": "mock default"}'
```

### Strategy B: Small Local Model (Integration, Nightly)

Run Ollama with `qwen2.5:1.5b` in CI. Tests validate structure of agent output,
not quality of reasoning. This catches serialization bugs, graph routing errors,
and schema violations.

### Strategy C: Full Model (Manual / Weekly)

Run against the production vLLM endpoint with the actual fine-tuned model.
Used for agent quality evaluation, not for CI gating.

---

## Migration Validation Protocol

When migrating code from the source repositories, every migrated module must pass:

1. **Identical output test:** Given the same input, the migrated code produces
   byte-identical output (or float-close within 1e-9 for numeric values).
2. **Interface compliance:** The migrated code conforms to the interfaces defined
   in `technical-design/`.
3. **No new dependencies:** Migrated code does not introduce dependencies not
   listed in the technical design doc.

```python
def test_migrated_trend_bull_matches_original():
    """Migrated TrendDayBull produces identical signals to original."""
    # Load the same session data used by the original repo
    df = pd.read_csv("tests/fixtures/migration/original_trend_day.csv")
    original_signals = load_json("tests/fixtures/migration/original_trend_bull_signals.json")

    strategy = TrendDayBull()
    migrated_signals = run_strategy_on_session(strategy, df)

    assert len(migrated_signals) == len(original_signals)
    for m, o in zip(migrated_signals, original_signals):
        assert m.direction == o["direction"]
        assert abs(m.entry_price - o["entry_price"]) < 1e-9
        assert abs(m.stop_price - o["stop_price"]) < 1e-9
```

---

## Test File Naming Conventions

```
packages/{name}/tests/
├── conftest.py                    # Shared fixtures for this package
├── fixtures/                      # Test data files (CSV, JSON)
│   ├── sessions/                  # Session CSV data
│   ├── snapshots/                 # Reference snapshot JSONs
│   └── migration/                 # Original repo outputs for comparison
├── test_{module}.py               # Unit tests for {module}
├── strategies/
│   ├── test_base.py               # StrategyBase contract tests
│   └── test_{strategy_name}.py    # Per-strategy tests
├── models/
│   ├── test_entry_{name}.py       # Entry model tests
│   ├── test_stop_{name}.py        # Stop model tests
│   └── test_target_{name}.py      # Target model tests
└── integration/
    ├── test_strategy_pipeline.py  # Strategy + filter chain
    └── test_deterministic.py      # Snapshot regression
```

---

## Running Tests Locally

```bash
# Run all fast tests
uv run pytest packages/ -m "not slow and not agent" -q

# Run a single package
uv run pytest packages/rockit-core/tests/ -v

# Run only strategy tests
uv run pytest packages/rockit-core/tests/strategies/ -v

# Run with coverage report
uv run pytest packages/rockit-core/tests/ --cov=packages/rockit-core/src --cov-report=html

# Run regression tests only
uv run pytest packages/ -m regression -v
```
