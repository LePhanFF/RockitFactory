---
name: add-strategy
description: Scaffold a new strategy with proper architecture and tests
allowed-tools: ["Bash", "Read", "Glob", "Grep", "Write", "Edit"]
---

Scaffold a new strategy following rockit-core architecture conventions.

## Usage
- `/add-strategy ema_pullback` — Create new strategy with given snake_case name

## Architecture Rules (MUST follow)
1. **Strategies emit signals, they do NOT manage positions** (StrategyBase design)
2. Strategies extend `StrategyBase` from `rockit_core.strategies.base`
3. Lifecycle: `on_session_start()` → `on_bar()` → `on_session_end()`
4. `on_bar()` returns `Signal | None`
5. Signal contains: timestamp, direction, entry_price, stop_price, target_price, strategy_name, setup_type, day_type, confidence

## Steps

1. **Read the base class** to understand the interface:
   ```
   Read packages/rockit-core/src/rockit_core/strategies/base.py
   ```

2. **Read an existing strategy** for the pattern (e.g., trend_bull.py or b_day.py)

3. **Create the strategy file**: `packages/rockit-core/src/rockit_core/strategies/{name}.py`
   - Import StrategyBase, Signal, DayType
   - Implement the 3 lifecycle methods
   - Set `self.name`, `self.applicable_day_types`
   - Return Signal from `on_bar()` when conditions met, else None

4. **Register in loader.py**: Add to `_CONFIG_KEY_TO_MODULE` dict

5. **Add to strategies.yaml**: Under `research_strategies` with `enabled: false`

6. **Create tests**: `packages/rockit-core/tests/test_{name}.py`
   - Test strategy instantiates
   - Test signal generation with mock bar data
   - Test no signal when conditions not met
   - Test correct day_type filtering

7. **Run tests**: `uv run pytest packages/rockit-core/tests/test_{name}.py -v`

8. **Update test_imports.py**: Add new module to import list

## Checklist
- [ ] Strategy extends StrategyBase
- [ ] on_bar returns Signal or None (never raises)
- [ ] Registered in loader.py
- [ ] Added to strategies.yaml (disabled by default)
- [ ] Tests pass
- [ ] Import test updated
