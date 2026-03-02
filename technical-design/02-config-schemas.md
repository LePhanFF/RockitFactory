# Technical Design: Configuration Schemas

> **Package:** `configs/` (YAML/JSON) + `rockit-core/config/` (loaders)
> **Type:** NEW — standardize existing hardcoded values into validated config files
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#config)

---

## Purpose

All runtime configuration lives in `configs/` as YAML or JSON files. Python code loads and validates these files at startup using pydantic models. No strategy parameters, instrument specs, or evaluation thresholds are hardcoded in Python — they come from config.

---

## Source Files (Being Replaced)

| File | LOC | Issue | Action |
|------|-----|-------|--------|
| `BookMapOrderFlowStudies/config/constants.py` | 72 | Hardcoded thresholds, session times | Extract to YAML |
| `BookMapOrderFlowStudies/config/instruments.py` | 42 | Hardcoded instrument specs | Extract to YAML |
| `rockit-framework/config/config.yaml` | ~50 | Standalone config, not integrated | Absorb into unified configs |
| `rockit-framework/config/schema.json` | ~200 | Snapshot validation schema | Move to `configs/snapshot-schema.json` |

---

## Schema: configs/strategies.yaml

```yaml
# configs/strategies.yaml
# Defines every strategy, its instruments, models, filters, and thresholds.
# Loaded by: rockit_core.config.load_strategies_config()

strategies:
  trend_bull:
    enabled: true
    class: TrendDayBull                         # maps to ALL_STRATEGIES registry
    instruments: [NQ, ES]                       # InstrumentSpec names
    applicable_day_types: [trend_up, super_trend_up]

    entry_models: [unicorn_ict, orderflow_cvd]  # ordered by priority
    stop_model: 1_atr
    target_model: 2r
    trail_rules:
      - trigger: fvg_formed_5m
        action: move_to_breakeven
      - trigger: 2r_reached
        action: trail_by_1_atr

    filters:
      order_flow:
        min_delta: 200
        min_cvd_slope: positive
      time:
        earliest: "09:45"
        latest: "14:30"
      volatility:
        min_ib_range: 25

    confidence_threshold: 0.65
    max_daily_signals: 3
    pyramid_enabled: false
    max_pyramid_levels: 0

  # ... additional strategies follow same schema
```

### Pydantic Validation Model

```python
# packages/rockit-core/src/rockit_core/config/schemas.py

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class TrailRuleConfig(BaseModel):
    trigger: str                    # e.g., "fvg_formed_5m", "2r_reached"
    action: str                     # e.g., "move_to_breakeven", "trail_by_1_atr"
    params: dict = Field(default_factory=dict)


class FilterOverrideConfig(BaseModel):
    """Per-strategy filter overrides. Merged with global filter defaults."""
    order_flow: dict = Field(default_factory=dict)
    regime: dict = Field(default_factory=dict)
    time: dict = Field(default_factory=dict)
    trend: dict = Field(default_factory=dict)
    volatility: dict = Field(default_factory=dict)


class StrategyConfig(BaseModel):
    enabled: bool = True
    class_name: str = Field(alias="class")
    instruments: list[str]
    applicable_day_types: list[str] = Field(default_factory=list)

    entry_models: list[str] = Field(default_factory=list)
    stop_model: str = ""
    target_model: str = ""
    trail_rules: list[TrailRuleConfig] = Field(default_factory=list)

    filters: FilterOverrideConfig = Field(default_factory=FilterOverrideConfig)

    confidence_threshold: float = 0.60
    max_daily_signals: int = 5
    pyramid_enabled: bool = False
    max_pyramid_levels: int = 0
    note: str = ""

    @field_validator("instruments")
    @classmethod
    def validate_instruments(cls, v: list[str]) -> list[str]:
        valid = {"NQ", "MNQ", "ES", "MES", "YM", "MYM"}
        for name in v:
            if name not in valid:
                raise ValueError(f"Unknown instrument: {name}. Valid: {valid}")
        return v


class StrategiesFileConfig(BaseModel):
    strategies: dict[str, StrategyConfig]
```

---

## Schema: configs/instruments.yaml

```yaml
# configs/instruments.yaml
# Instrument specifications for all supported futures contracts.
# Loaded by: rockit_core.config.load_instruments_config()

instruments:
  NQ:
    full_name: "E-mini NASDAQ 100"
    point_value: 20.0
    tick_size: 0.25
    tick_value: 5.0
    commission_per_contract: 2.05
    slippage_ticks: 1
    exchange: CME
    session:
      rth_start: "09:30"
      rth_end: "16:00"
      ib_duration_minutes: 60
    risk_defaults:
      max_contracts: 30
      max_daily_loss: 2000.0
      max_risk_per_trade: 400.0

  MNQ:
    full_name: "Micro E-mini NASDAQ 100"
    point_value: 2.0
    tick_size: 0.25
    tick_value: 0.50
    commission_per_contract: 0.62
    slippage_ticks: 1
    exchange: CME
    session:
      rth_start: "09:30"
      rth_end: "16:00"
      ib_duration_minutes: 60
    risk_defaults:
      max_contracts: 100
      max_daily_loss: 500.0
      max_risk_per_trade: 100.0

  ES:
    full_name: "E-mini S&P 500"
    point_value: 50.0
    tick_size: 0.25
    tick_value: 12.50
    commission_per_contract: 2.05
    slippage_ticks: 1
    exchange: CME
    session:
      rth_start: "09:30"
      rth_end: "16:00"
      ib_duration_minutes: 60
    risk_defaults:
      max_contracts: 20
      max_daily_loss: 2000.0
      max_risk_per_trade: 500.0

  # MES, YM, MYM follow same schema
```

### Pydantic Validation Model

```python
# packages/rockit-core/src/rockit_core/config/schemas.py (continued)

class SessionTimesConfig(BaseModel):
    rth_start: str              # "HH:MM" ET
    rth_end: str                # "HH:MM" ET
    ib_duration_minutes: int = 60

    @field_validator("rth_start", "rth_end")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError(f"Invalid time format: {v}. Expected HH:MM")
        return v


class RiskDefaultsConfig(BaseModel):
    max_contracts: int = 30
    max_daily_loss: float = 2000.0
    max_risk_per_trade: float = 400.0


class InstrumentConfig(BaseModel):
    full_name: str
    point_value: float
    tick_size: float
    tick_value: float
    commission_per_contract: float
    slippage_ticks: int = 1
    exchange: str = "CME"
    session: SessionTimesConfig
    risk_defaults: RiskDefaultsConfig


class InstrumentsFileConfig(BaseModel):
    instruments: dict[str, InstrumentConfig]
```

---

## Schema: configs/eval/gates.yaml

```yaml
# configs/eval/gates.yaml
# Evaluation gate thresholds. Used by rockit-train evaluator and CI.
# A model/strategy must pass ALL gates before promotion.

gates:
  backtest_regression:
    description: "Strategy performance must not regress vs baseline"
    thresholds:
      min_win_rate: 0.50
      min_profit_factor: 1.30
      max_drawdown_pct: 15.0
      min_trade_count: 50
      max_win_rate_delta: -0.05       # max allowed regression from baseline
      max_profit_factor_delta: -0.20

  snapshot_quality:
    description: "Deterministic snapshots must pass schema and coverage"
    thresholds:
      min_field_coverage: 0.95        # 95% of schema fields must be non-null
      max_error_rate: 0.02            # max 2% of modules can fail
      required_modules:
        - volume_profile
        - tpo_profile
        - ib_location
        - premarket
        - inference_engine

  training_data:
    description: "Training data quality checks"
    thresholds:
      min_samples: 200
      max_duplicate_rate: 0.01
      min_avg_output_tokens: 500
      max_schema_violations: 0

  model_eval:
    description: "LLM model output quality"
    thresholds:
      min_rouge_l: 0.40
      min_section_completeness: 0.90  # 90% of 11 analysis sections present
      max_hallucination_rate: 0.05
      min_day_type_accuracy: 0.70
```

### Pydantic Validation Model

```python
class GateThresholds(BaseModel):
    """Flexible threshold container. Keys vary by gate type."""
    model_config = {"extra": "allow"}


class GateConfig(BaseModel):
    description: str
    thresholds: dict


class GatesFileConfig(BaseModel):
    gates: dict[str, GateConfig]
```

---

## Schema: configs/baselines/v1.0.0.json

```json
{
  "version": "1.0.0",
  "created_at": "2026-03-01T00:00:00Z",
  "source": "BookMapOrderFlowStudies backtest (259 sessions)",
  "global": {
    "total_trades": 283,
    "total_sessions": 259,
    "win_rate": 0.555,
    "profit_factor": 1.58,
    "max_drawdown_pct": 12.3,
    "sharpe_ratio": 1.42,
    "expectancy_per_trade": 18.5
  },
  "per_strategy": {
    "trend_bull": {
      "trades": 67,
      "win_rate": 0.61,
      "profit_factor": 1.85,
      "avg_winner": 42.3,
      "avg_loser": -28.1
    }
  },
  "per_day_type": {
    "trend_up": { "trades": 89, "win_rate": 0.63, "profit_factor": 2.01 },
    "b_day": { "trades": 72, "win_rate": 0.51, "profit_factor": 1.22 }
  }
}
```

### Pydantic Validation Model

```python
class BaselineGlobal(BaseModel):
    total_trades: int
    total_sessions: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    expectancy_per_trade: float


class BaselineStrategyMetrics(BaseModel):
    trades: int
    win_rate: float
    profit_factor: float
    avg_winner: float = 0.0
    avg_loser: float = 0.0


class BaselineFile(BaseModel):
    version: str
    created_at: str
    source: str
    global_metrics: BaselineGlobal = Field(alias="global")
    per_strategy: dict[str, BaselineStrategyMetrics] = Field(default_factory=dict)
    per_day_type: dict[str, BaselineStrategyMetrics] = Field(default_factory=dict)
```

---

## Schema: configs/snapshot-schema.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["metadata", "premarket", "ib_location", "volume_profile", "tpo_profile"],
  "properties": {
    "metadata": {
      "type": "object",
      "required": ["session_date", "snapshot_time", "instrument", "schema_version"],
      "properties": {
        "session_date": { "type": "string", "format": "date" },
        "snapshot_time": { "type": "string" },
        "instrument": { "type": "string" },
        "schema_version": { "type": "string" }
      }
    },
    "premarket": { "type": "object" },
    "ib_location": { "type": "object" },
    "volume_profile": { "type": "object" },
    "tpo_profile": { "type": "object" },
    "dpoc_migration": { "type": "object" },
    "wick_parade": { "type": "object" },
    "fvg_detection": { "type": "object" },
    "core_confluences": { "type": "object" },
    "inference_engine": { "type": "object" },
    "decision_engine": { "type": "object" },
    "cri": { "type": "object" },
    "dalton": { "type": "object" },
    "playbook_engine": { "type": "object" }
  }
}
```

---

## Config Loader Functions

```python
# packages/rockit-core/src/rockit_core/config/loader.py

from pathlib import Path
from typing import Any

import yaml

from rockit_core.config.schemas import (
    StrategiesFileConfig,
    InstrumentsFileConfig,
    GatesFileConfig,
    BaselineFile,
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def load_strategies_config(
    path: str | Path = "configs/strategies.yaml",
) -> StrategiesFileConfig:
    """Load and validate strategies configuration.

    Args:
        path: Path to strategies.yaml

    Returns:
        Validated StrategiesFileConfig with all strategy definitions.

    Raises:
        FileNotFoundError: If config file does not exist.
        pydantic.ValidationError: If config fails schema validation.
    """
    raw = load_yaml(path)
    return StrategiesFileConfig.model_validate(raw)


def load_instruments_config(
    path: str | Path = "configs/instruments.yaml",
) -> InstrumentsFileConfig:
    """Load and validate instrument specifications.

    Args:
        path: Path to instruments.yaml

    Returns:
        Validated InstrumentsFileConfig with all instrument specs.

    Raises:
        FileNotFoundError: If config file does not exist.
        pydantic.ValidationError: If config fails schema validation.
    """
    raw = load_yaml(path)
    return InstrumentsFileConfig.model_validate(raw)


def load_gates_config(
    path: str | Path = "configs/eval/gates.yaml",
) -> GatesFileConfig:
    """Load and validate evaluation gate thresholds."""
    raw = load_yaml(path)
    return GatesFileConfig.model_validate(raw)


def load_baseline(
    path: str | Path = "configs/baselines/v1.0.0.json",
) -> BaselineFile:
    """Load and validate a frozen performance baseline."""
    import json
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Baseline file not found: {p}")
    with open(p) as f:
        raw = json.load(f)
    return BaselineFile.model_validate(raw)


def get_instrument(
    name: str,
    config: InstrumentsFileConfig | None = None,
) -> "InstrumentConfig":
    """Get a single instrument spec by symbol name.

    Args:
        name: Instrument symbol (e.g., "NQ", "ES")
        config: Pre-loaded config, or None to load from default path.

    Returns:
        InstrumentConfig for the requested instrument.

    Raises:
        KeyError: If instrument name not found.
    """
    if config is None:
        config = load_instruments_config()
    if name not in config.instruments:
        raise KeyError(
            f"Unknown instrument: {name}. "
            f"Available: {list(config.instruments.keys())}"
        )
    return config.instruments[name]
```

---

## Data Flow

```
configs/strategies.yaml ──► load_strategies_config()
                                │
                                ├──► StrategiesFileConfig (validated)
                                │       │
                                │       └──► BacktestEngine reads strategy list
                                │       └──► Strategy registry instantiates classes
                                │       └──► Filter chain reads per-strategy overrides
                                │
configs/instruments.yaml ──► load_instruments_config()
                                │
                                ├──► InstrumentsFileConfig (validated)
                                │       │
                                │       └──► ExecutionModel reads commission/slippage
                                │       └──► PositionManager reads risk limits
                                │
configs/eval/gates.yaml ──► load_gates_config()
                                │
                                └──► GatesFileConfig (validated)
                                        │
                                        └──► Evaluator checks gate thresholds
                                        └──► CI pipeline gates promotion

configs/baselines/v1.0.0.json ──► load_baseline()
                                        │
                                        └──► Regression gate compares current vs baseline
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `config/loader.py` | `pyyaml`, `pydantic` |
| `config/schemas.py` | `pydantic` |
| All other modules | `config/loader.py` (optional — can be used without config) |

---

## Metrics Emitted

| Metric | Layer | When |
|--------|-------|------|
| `config.loaded` | infra | Config file successfully loaded and validated |
| `config.validation_error` | infra | Config file fails pydantic validation |
| `config.strategy_count` | infra | Number of enabled strategies in config |
| `config.instrument_count` | infra | Number of instruments in config |

---

## Migration Notes

1. **constants.py values move to YAML.** Session times, IB duration, risk defaults, day type thresholds all move from hardcoded Python to `instruments.yaml` and `strategies.yaml`. The Python constants file becomes a thin wrapper that loads from YAML.

2. **instruments.py becomes a loader.** The current `InstrumentSpec` dataclass with hardcoded values is replaced by `InstrumentConfig` pydantic model loaded from YAML.

3. **Backward compatibility.** During migration, `config/constants.py` and `config/instruments.py` continue to work but read from YAML under the hood. Existing code that imports `NQ_SPEC` from `instruments.py` still works.

4. **snapshot-schema.json is moved as-is** from `rockit-framework/config/schema.json`.

---

## Test Contract

1. **Schema validation tests** — valid YAML passes, invalid YAML raises `ValidationError`
2. **Missing file tests** — `load_strategies_config("nonexistent.yaml")` raises `FileNotFoundError`
3. **Instrument lookup tests** — `get_instrument("NQ")` returns correct spec, `get_instrument("INVALID")` raises `KeyError`
4. **Baseline comparison tests** — loading baseline, comparing two baselines for regression
5. **Round-trip tests** — load config, serialize back to YAML, reload, compare equal

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#config)
