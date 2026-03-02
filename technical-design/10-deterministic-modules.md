# Technical Design: Deterministic Orchestrator & Modules

> **Package:** `rockit-core/deterministic/`
> **Type:** MIGRATE from rockit-framework/ + DEDUP with BookMap profile/indicators
> **Source files:** orchestrator.py (359 LOC) + 38 modules (~9,293 LOC)
> **Tests:** See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#deterministic)

---

## Purpose

The deterministic orchestrator generates point-in-time market snapshots by calling all 38 analysis modules in dependency order and merging their outputs into a single JSON object. These snapshots serve as inputs for LLM training data and real-time inference. The orchestrator ensures module failures do not crash the snapshot — each module is isolated and errors are logged.

---

## Source Files (Being Migrated)

| File | LOC | Destination | Type |
|------|-----|-------------|------|
| `rockit-framework/orchestrator.py` | 359 | `deterministic/orchestrator.py` | MIGRATE |
| `rockit-framework/modules/` (38 files) | 9,293 | `deterministic/modules/` | MIGRATE |
| `rockit-framework/config/schema.json` | ~200 | `deterministic/schema.json` | MIGRATE |

---

## Interface: orchestrator.py

```python
# packages/rockit-core/src/rockit_core/deterministic/orchestrator.py

"""Deterministic snapshot orchestrator.

Source: rockit-framework/orchestrator.py (359 LOC)
Migration: MIGRATE — add metrics, use shared profile/indicator modules

Calls all modules in dependency order, merges outputs into a single
JSON-serializable dict, validates against schema.json.

Dependencies: all modules in deterministic/modules/, profile/, indicators/
"""

from pathlib import Path
from typing import Any

import pandas as pd

from rockit_core.metrics import MetricsCollector, MetricEvent, NullCollector


def generate_snapshot(
    df: pd.DataFrame,
    snapshot_time: str,
    config: dict | None = None,
    metrics: MetricsCollector | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Generate a complete deterministic snapshot.

    Calls all modules in dependency order:
    1. Data modules (premarket, ib_location, volume_profile, tpo_profile, ...)
    2. Signal composition modules (inference_engine, decision_engine, cri, dalton)
    3. Setup generation modules (playbook_engine, edge_fade, or_reversal, ...)
    4. Training modules (enhanced_reasoning, outcome_labeling, ...)

    Each module is wrapped in try/except. On failure, the module's output
    is {"error": str, "status": "failed"} and the snapshot continues.

    Args:
        df: DataFrame with full session bar data (OHLCV + volumetric).
        snapshot_time: ISO timestamp for this snapshot (e.g., "2026-03-01T11:00:00").
        config: Optional config dict overriding module parameters.
        metrics: Optional metrics collector.
        validate: If True, validate output against schema.json.

    Returns:
        Dict with all module outputs merged under their respective keys.
        Top-level keys match module names: "premarket", "volume_profile", etc.
    """
    collector = metrics or NullCollector()
    snapshot: dict[str, Any] = {
        "metadata": {
            "session_date": _extract_session_date(df),
            "snapshot_time": snapshot_time,
            "instrument": config.get("instrument", "NQ") if config else "NQ",
            "schema_version": "2.0",
        },
    }

    # Execute modules in dependency order
    for module_name, module_fn, dependencies in MODULE_EXECUTION_ORDER:
        snapshot = _run_module(
            snapshot, module_name, module_fn, df, snapshot_time,
            config=config, metrics=collector,
        )

    # Validate if requested
    if validate:
        _validate_snapshot(snapshot)

    return snapshot


def _run_module(
    snapshot: dict,
    module_name: str,
    module_fn: callable,
    df: pd.DataFrame,
    snapshot_time: str,
    config: dict | None = None,
    metrics: MetricsCollector | None = None,
) -> dict:
    """Execute a single module with error isolation.

    Args:
        snapshot: Current snapshot dict (modules may read prior module outputs).
        module_name: Module name for the output key.
        module_fn: The module function to call.
        df: Bar data.
        snapshot_time: Snapshot timestamp.
        config: Optional config overrides.
        metrics: Metrics collector.

    Returns:
        Updated snapshot dict with module output added.
    """
    import time

    start = time.monotonic()
    try:
        result = module_fn(df, snapshot_time, snapshot=snapshot, config=config)
        elapsed = (time.monotonic() - start) * 1000

        snapshot[module_name] = result
        if metrics:
            metrics.record(MetricEvent(
                timestamp=snapshot_time,
                layer="module",
                component=module_name,
                metric="module_duration_ms",
                value=elapsed,
                context={"field_count": len(result) if isinstance(result, dict) else 0},
            ))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        snapshot[module_name] = {"error": str(e), "status": "failed"}
        if metrics:
            metrics.record(MetricEvent(
                timestamp=snapshot_time,
                layer="module",
                component=module_name,
                metric="module_error",
                value=1.0,
                context={"error": str(e), "elapsed_ms": elapsed},
            ))

    return snapshot


def _validate_snapshot(snapshot: dict) -> None:
    """Validate snapshot against schema.json.

    Raises jsonschema.ValidationError if invalid.
    """
    import json
    import jsonschema

    schema_path = Path(__file__).parent / "schema.json"
    with open(schema_path) as f:
        schema = json.load(f)
    jsonschema.validate(snapshot, schema)


def _extract_session_date(df: pd.DataFrame) -> str:
    """Extract session date from DataFrame timestamps."""
    ...
```

---

## Module Interface Pattern

Every module follows this signature:

```python
def get_<module_name>(
    df: pd.DataFrame,
    current_time: str,
    snapshot: dict | None = None,
    config: dict | None = None,
    **kwargs,
) -> dict:
    """Module description.

    Args:
        df: Session bar data.
        current_time: Snapshot timestamp.
        snapshot: Current snapshot dict (for reading prior module outputs).
        config: Optional config overrides.

    Returns:
        Dict with module-specific fields.
    """
```

Modules that wrap shared `profile/` or `indicators/` code convert dataclass results to dicts:

```python
# deterministic/modules/volume_profile.py (wrapper)

from rockit_core.profile.volume_profile import compute_volume_profile

def get_volume_profile(df, current_time, snapshot=None, config=None, **kwargs):
    """Volume profile module — wraps profile/volume_profile.py for orchestrator."""
    result = compute_volume_profile(df)
    return {
        "poc": result.poc,
        "vah": result.vah,
        "val": result.val,
        "hvn_levels": result.hvn_levels,
        "lvn_levels": result.lvn_levels,
        "total_volume": result.total_volume,
    }
```

---

## Module Dependency Chain

```
Phase 1: Core Data (no inter-module dependencies)
    ├── premarket          (Asia/London/overnight ranges)
    ├── ib_location        (IB placement, price vs IB)
    ├── volume_profile     (POC/VAH/VAL/HVN/LVN)
    ├── tpo_profile        (TPO shape, single prints)
    ├── dpoc_migration     (DPOC tracking) [depends on: volume_profile]
    ├── wick_parade        (extremes analysis)
    ├── fvg_detection      (multi-TF FVGs)
    ├── ninety_min_pd_arrays (premium/discount zones)
    └── cross_market       (ES/YM cross-market — stub)

Phase 2: Signal Composition (reads Phase 1 outputs from snapshot dict)
    ├── core_confluences   [depends on: volume_profile, tpo_profile, fvg_detection]
    ├── vix_regime         (VIX regime — stub)
    ├── inference_engine   [depends on: all Phase 1 modules]
    ├── decision_engine    [depends on: inference_engine, ib_location]
    ├── cri                [depends on: decision_engine, volume_profile, tpo_profile]
    └── dalton             [depends on: decision_engine, ib_location]

Phase 3: Setup Generation (reads Phase 1 + Phase 2 outputs)
    ├── playbook_engine    [depends on: decision_engine, cri]
    ├── playbook_engine_v2 [depends on: playbook_engine]
    ├── balance_classification [depends on: decision_engine]
    ├── mean_reversion_engine  [depends on: volume_profile, tpo_profile]
    ├── or_reversal        [depends on: ib_location, inference_engine]
    ├── edge_fade          [depends on: volume_profile, decision_engine]
    ├── va_edge_fade       [depends on: volume_profile]
    ├── globex_va_analysis [depends on: volume_profile, premarket]
    └── twenty_percent_rule [depends on: ib_location]

Phase 4: Training/Reasoning (reads all prior outputs)
    ├── enhanced_reasoning [depends on: all prior modules]
    ├── cri_psychology_voice [depends on: cri]
    ├── market_structure_events [depends on: fvg_detection, volume_profile]
    ├── outcome_labeling   [depends on: all setups]
    ├── intraday_sampling  [depends on: all prior]
    └── setup_annotator    [depends on: playbook_engine]

Infrastructure (called by orchestrator, not in snapshot output):
    ├── loader             (CSV loading)
    ├── config_validator   (config validation)
    ├── schema_validator   (snapshot schema validation)
    ├── dataframe_cache    (caching for 30% speedup)
    ├── error_logger       (centralized error logging)
    └── acceptance_test    (acceptance test harness)
```

---

## All 38 Modules — Function Signatures

### Core Data Modules

```python
def get_premarket(df, current_time, **kw) -> dict:
    """Asia/London/overnight ranges, compression flag, SMT preopen."""
    # Returns: asia_high, asia_low, london_high, london_low, overnight_high,
    #          overnight_low, compression_flag, smt_preopen

def get_ib_location(df, current_time, **kw) -> dict:
    """IB placement, price vs IB, technicals, ATR."""
    # Returns: ib_high, ib_low, ib_range, ib_midpoint, location_vs_prior,
    #          ema20, ema50, atr14, price_vs_ib

def get_volume_profile(df, current_time, **kw) -> dict:
    """POC/VAH/VAL/HVN/LVN for current + prior sessions."""
    # Returns: poc, vah, val, hvn_levels, lvn_levels, prior_poc, prior_vah, prior_val

def get_tpo_profile(df, current_time, **kw) -> dict:
    """TPO shape, fattening zones, single prints, poor highs/lows."""
    # Returns: shape, tpo_count, single_prints_above, single_prints_below,
    #          poor_high, poor_low, fattening_zones

def get_dpoc_migration(df, current_time, **kw) -> dict:
    """30-min DPOC slices, migration direction/magnitude."""
    # Returns: slices, net_direction, migration_magnitude, is_migrating

def get_wick_parade(df, current_time, **kw) -> dict:
    """Bullish/bearish wick counts in rolling window."""
    # Returns: bullish_wicks, bearish_wicks, net_direction

def get_fvg_detection(df, current_time, **kw) -> dict:
    """Multi-timeframe FVG detection (5m/15m/1H/90min/daily)."""
    # Returns: fvgs_5m, fvgs_15m, fvgs_1h, fvgs_90m, fvgs_daily, total_count

def get_ninety_min_pd_arrays(df, current_time, **kw) -> dict:
    """90-min premium/discount zones, expansion status."""
    # Returns: premium_zone, discount_zone, equilibrium, expansion_status

def get_cross_market(df, current_time, **kw) -> dict:
    """ES/YM cross-market analysis (stub)."""
    # Returns: {} (stub — future implementation)

def get_vix_regime(df, current_time, **kw) -> dict:
    """VIX regime classification (stub)."""
    # Returns: {} (stub — future implementation)
```

### Signal Composition Modules

```python
def get_core_confluences(df, current_time, snapshot=None, **kw) -> dict:
    """Boolean signal merge from all raw modules."""
    # Returns: confluence_count, zones, strongest_zone, support_levels, resistance_levels

def get_inference_engine(df, current_time, snapshot=None, **kw) -> dict:
    """8 high-priority deterministic rules."""
    # Returns: day_type, bias, confidence, rules_triggered, rule_details

def get_decision_engine(df, current_time, snapshot=None, **kw) -> dict:
    """Day type classification (Trend/Balance/Open Drive)."""
    # Returns: primary_type, secondary_type, confidence, evidence

def get_cri(df, current_time, snapshot=None, **kw) -> dict:
    """Contextual Readiness Index (412 LOC)."""
    # Returns: terrain, identity, permission, trap_detection, cri_score, narrative

def get_dalton(df, current_time, snapshot=None, **kw) -> dict:
    """Trend strength quantification (360 LOC)."""
    # Returns: strength, classification, ib_extension_multiple, evidence
```

### Setup Generation Modules

```python
def get_playbook_engine(df, current_time, snapshot=None, **kw) -> dict:
    """10 fundamental playbooks (setup generation)."""
    # Returns: setups, active_playbook, playbook_confidence

def get_playbook_engine_v2(df, current_time, snapshot=None, **kw) -> dict:
    """Enhanced playbook version."""
    # Returns: setups_v2, enhancements

def get_balance_classification(df, current_time, snapshot=None, **kw) -> dict:
    """Balance day specific analysis."""
    # Returns: is_balance, balance_type, range_width, expected_resolution

def get_mean_reversion_engine(df, current_time, snapshot=None, **kw) -> dict:
    """Mean reversion target generation."""
    # Returns: targets, reversion_probability, entry_zone

def get_or_reversal(df, current_time, snapshot=None, **kw) -> dict:
    """Opening Range Reversal setup."""
    # Returns: or_high, or_low, reversal_triggered, direction, entry, stop, target

def get_edge_fade(df, current_time, snapshot=None, **kw) -> dict:
    """Edge Fade mean reversion (10:00-13:30)."""
    # Returns: fade_active, direction, entry_zone, target, stop

def get_va_edge_fade(df, current_time, snapshot=None, **kw) -> dict:
    """VA Edge Fade (poke beyond VA, fail, fade) (334 LOC)."""
    # Returns: setup_active, direction, va_boundary, entry, stop, target

def get_globex_va_analysis(df, current_time, snapshot=None, **kw) -> dict:
    """80% Rule (Globex gap rejection)."""
    # Returns: rule_active, direction, gap_size, target

def get_twenty_percent_rule(df, current_time, snapshot=None, **kw) -> dict:
    """20% IB extension breakout."""
    # Returns: triggered, direction, extension_pct, target
```

### Training/Reasoning Modules

```python
def get_enhanced_reasoning(df, current_time, snapshot=None, **kw) -> dict:
    """9-step reasoning chain for LLM training output."""
    # Returns: steps (list of 9 reasoning step dicts)

def get_cri_psychology_voice(df, current_time, snapshot=None, **kw) -> dict:
    """Trader voice interpretation of CRI."""
    # Returns: narrative, confidence_statement, action_recommendation

def get_market_structure_events(df, current_time, snapshot=None, **kw) -> dict:
    """Market structure event detection."""
    # Returns: events (list of structure break/shift events)

def get_outcome_labeling(df, current_time, snapshot=None, **kw) -> dict:
    """Training outcome labels."""
    # Returns: labels, outcome_type, pnl_if_taken

def get_intraday_sampling(df, current_time, snapshot=None, **kw) -> dict:
    """Intraday sampling and smoothing."""
    # Returns: sampled_data, smoothed_indicators

def get_setup_annotator(df, current_time, snapshot=None, **kw) -> dict:
    """Annotation setup for charting."""
    # Returns: annotations (list of chart annotation dicts)
```

### Infrastructure Modules

```python
def load_nq_csv(filepath: str) -> pd.DataFrame:
    """CSV data loading for NinjaTrader volumetric format."""

def validate_config(config: dict) -> bool:
    """Validate orchestrator config."""

def validate_schema(snapshot: dict) -> bool:
    """Validate snapshot against schema.json."""

class DataFrameCache:
    """DataFrame caching for 30% speedup on repeated orchestrator runs."""
    def get(self, key: str) -> pd.DataFrame | None: ...
    def put(self, key: str, df: pd.DataFrame) -> None: ...
```

---

## Schema Validation

```python
# deterministic/schema.json is migrated from rockit-framework/config/schema.json
# See 02-config-schemas.md for the full schema definition.
# The orchestrator calls _validate_snapshot() after all modules complete.
```

---

## DEDUP: Overlapping Modules

| Module | deterministic/modules/ wrapper | Shared implementation in |
|--------|-------------------------------|------------------------|
| volume_profile | `get_volume_profile()` | `profile/volume_profile.py` |
| tpo_profile | `get_tpo_profile()` | `profile/tpo_profile.py` |
| dpoc_migration | `get_dpoc_migration()` | `profile/dpoc_migration.py` |
| wick_parade | `get_wick_parade()` | `profile/wick_parade.py` |
| ib_location | `get_ib_location()` | `profile/ib_analysis.py` |
| core_confluences | `get_core_confluences()` | `profile/confluences.py` |
| fvg_detection | `get_fvg_detection()` | `indicators/ict_models.py` |

The wrapper modules in `deterministic/modules/` are thin functions (~20-30 LOC each) that call the canonical implementation in `profile/` or `indicators/` and convert the dataclass output to a dict matching the snapshot schema.

---

## How Snapshots Feed Training Data

```
Historical CSV data
    │
    ▼
orchestrator.generate_snapshot(df, time)
    │
    ├──► snapshot dict (all 38 module outputs)
    │
    ▼
rockit_train/dataset.py
    │
    ├──► Format as JSONL: {"input": snapshot_json, "output": llm_analysis}
    │
    └──► Training data for LoRA fine-tuning
```

---

## Dependencies

| This module | Depends on |
|-------------|-----------|
| `deterministic/orchestrator.py` | All modules, `metrics/`, `jsonschema` |
| `deterministic/modules/volume_profile.py` | `profile/volume_profile.py` |
| `deterministic/modules/tpo_profile.py` | `profile/tpo_profile.py` |
| `deterministic/modules/fvg_detection.py` | `indicators/ict_models.py` |
| `deterministic/modules/ib_location.py` | `profile/ib_analysis.py`, `indicators/technical.py` |
| `deterministic/modules/cri.py` | `deterministic/modules/decision_engine.py` |
| `deterministic/modules/dalton.py` | `deterministic/modules/decision_engine.py` |
| `deterministic/modules/playbook_engine.py` | `deterministic/modules/decision_engine.py`, `deterministic/modules/cri.py` |

---

## Metrics Emitted

| Metric | Layer | When |
|--------|-------|------|
| `module.<name>.duration_ms` | module | Module execution time |
| `module.<name>.error` | module | Module raised an exception |
| `module.<name>.field_count` | module | Number of fields in module output |
| `orchestrator.snapshot_complete` | module | All modules finished |
| `orchestrator.validation_passed` | module | Snapshot passes schema validation |
| `orchestrator.validation_failed` | module | Snapshot fails schema validation |

---

## Migration Notes

1. **orchestrator.py is migrated as-is** from rockit-framework. The only changes are adding metrics emission and importing from shared `profile/` and `indicators/` modules instead of local copies.

2. **6 modules become thin wrappers** around canonical implementations in `profile/` and `indicators/`. The remaining 32 modules are migrated as-is from rockit-framework/modules/.

3. **Infrastructure modules** (loader, config_validator, schema_validator, dataframe_cache, error_logger, acceptance_test) are internal to the deterministic package. They are not exposed in the public API.

4. **Stubs (cross_market, vix_regime) remain as stubs.** They return empty dicts and are placeholders for future implementation.

5. **MODULE_EXECUTION_ORDER** is a list of `(name, function, dependencies)` tuples defined at module level in `orchestrator.py`. The orchestrator iterates this list sequentially. Future optimization: parallelize independent modules within each phase.

---

## Test Contract

1. **Orchestrator integration test** — generate snapshot from known CSV, verify all module keys present
2. **Module isolation test** — one module failure does not crash snapshot, error captured in output
3. **Schema validation test** — valid snapshot passes, snapshot missing required field fails
4. **Dependency order test** — modules that depend on prior outputs receive correct data
5. **Wrapper equivalence test** — wrapper module output matches direct call to profile/indicator function
6. **Per-module unit tests** — each of the 38 modules tested with known input data
7. **Snapshot determinism test** — same input produces identical output (no random elements)

See [testing-design/01-unit-tests.md](../testing-design/01-unit-tests.md#deterministic)
