# Coding Conventions & Standards

> Every coding agent must follow these conventions. Opus 4.6 reviews will check compliance.

---

## Python Standards

### Version & Tooling
- Python 3.11+
- Package manager: `uv`
- Linter/formatter: `ruff` (replaces black, isort, flake8)
- Type checker: `mypy` (strict mode for rockit-core)
- Test framework: `pytest` with `pytest-cov`

### Import Order
```python
# 1. Standard library
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# 2. Third-party
import pandas as pd
import duckdb

# 3. Local (rockit packages)
from rockit_core.strategies.base import StrategyBase
from rockit_core.strategies.signal import Signal
```

### Naming
```python
# Modules: snake_case
rockit_core/strategies/trend_bull.py

# Classes: PascalCase
class TrendDayBull(StrategyBase):

# Functions/methods: snake_case
def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Optional[Signal]:

# Constants: UPPER_SNAKE_CASE
DEFAULT_MAX_RISK_PER_TRADE = 400.0

# Dataclasses over dicts for structured data
@dataclass
class Signal:
    direction: str
    entry_price: float
```

### Type Hints
```python
# Always use type hints on public interfaces
def evaluate(self, context: SessionContext) -> list[Signal]:
    ...

# Use | None instead of Optional for Python 3.11+
def on_bar(self, bar: pd.Series) -> Signal | None:
    ...

# Use dataclasses, not TypedDicts, for return types
@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: EquityCurve
```

### Error Handling
```python
# Use specific exceptions, not bare except
class StrategyError(Exception): pass
class DataLoadError(Exception): pass

# Modules in orchestrator: fail gracefully, log error, continue
try:
    result = get_volume_profile(df)
except Exception as e:
    logger.error(f"volume_profile failed: {e}")
    result = {"error": str(e), "status": "failed"}

# Strategy code: never catch silently
# If something is wrong, emit no signal (return None)
```

### Docstrings
```python
# Google-style docstrings on all public classes and functions
class TrendDayBull(StrategyBase):
    """Trend continuation strategy for bullish sessions.

    Signals long when price accepts above IBH with strong delta
    confirmation. Applicable to Trend and Super Trend day types.

    Source: BookMapOrderFlowStudies/strategy/trend_bull.py
    Migration: MIGRATE with metrics emission added
    """

    def on_bar(self, bar: pd.Series, bar_index: int, session_context: dict) -> Signal | None:
        """Evaluate current bar for trend continuation entry.

        Args:
            bar: Current OHLCV bar with volume/delta columns.
            bar_index: 0-based index within post-IB bars.
            session_context: Dict with ib_high, ib_low, day_type_confidence, etc.

        Returns:
            Signal if entry conditions met, None otherwise.
        """
```

---

## Package Structure

```
packages/{name}/
├── pyproject.toml          # Package dependencies
├── src/
│   └── {name}/
│       ├── __init__.py     # Public API exports
│       ├── module.py       # Implementation
│       └── _internal.py    # Private helpers (underscore prefix)
└── tests/
    ├── conftest.py         # Shared fixtures
    ├── test_module.py      # Unit tests
    └── fixtures/           # Test data files
```

### pyproject.toml Template
```toml
[project]
name = "rockit-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.0",
    "numpy>=1.24",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "ruff>=0.4",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "ANN"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing"

[tool.mypy]
python_version = "3.11"
strict = true
```

---

## Metrics Convention

Every public module must support optional metrics emission:

```python
from rockit_core.metrics import MetricsCollector, MetricEvent, NullCollector

class SomeModule:
    def __init__(self, metrics: MetricsCollector | None = None):
        self._metrics = metrics or NullCollector()

    def do_work(self, data) -> Result:
        result = self._compute(data)
        self._metrics.record(MetricEvent(
            timestamp=datetime.now().isoformat(),
            layer="component",
            component="some_module",
            metric="items_processed",
            value=len(result),
            context={"session_date": data.date},
        ))
        return result
```

---

## Git Conventions

- Branch naming: `{type}/{description}` — e.g., `feat/entry-models`, `fix/backtest-regression`
- Commit messages: imperative mood, reference the component — e.g., "Add unicorn ICT entry model"
- PRs: link to the technical design doc being implemented
- One component per PR when possible

---

## What NOT to Do

- Do not add type annotations to migrated code you didn't change (add them only to new/modified code)
- Do not add docstrings to migrated functions you didn't change
- Do not refactor migrated code unless the design doc explicitly says to
- Do not create helper/utility modules unless the design doc specifies them
- Do not add error handling beyond what the design doc specifies
- Do not use `Any` type — be specific or use a TypeVar
