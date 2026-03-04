# /quant-study — Strategy Research Lifecycle

Design, test, and validate a new trading strategy through the full quant research lifecycle.

## When to Use
When the user wants to research, design, or validate a new trading strategy. This skill guides through
the complete lifecycle from thesis to backtested results.

## Lifecycle Phases

### Phase 1: Design
1. **Thesis**: What market condition does this strategy exploit? (e.g., "balance days trap price, fade the edge")
2. **Day types**: Which day types is this strategy applicable to? (TREND, P_DAY, B_DAY, NEUTRAL, all)
3. **Direction**: LONG, SHORT, or both?
4. **Time window**: When does the setup form and when can entries occur?
5. **Historical precedent**: Check `research/strategy-studies/README.md` for similar strategies

### Phase 2: Entry Model
Design the entry with structural justification for each gate:

1. **Setup condition**: What must be true before looking for entry? (e.g., "open outside VA")
2. **Acceptance/confirmation**: How do we know the move is real? (e.g., "2x 5-min closes")
3. **Entry type**: Market, limit at structure, or stop order?
4. **Gate chain**: List each filter with WHY it exists:
   - Each gate must have data-backed justification
   - Maximum 3-4 gates total (more = over-filtering)
   - NEVER add a gate without backtesting with/without comparison
5. **Order flow confirmation**: Delta, CVD, volume spike as supporting (not primary) filters

### Phase 3: Stop Model
1. **Structure anchor**: Where is the invalidation level? (e.g., "VA edge", "IB extreme", "swept level")
2. **Buffer**: Add buffer to avoid noise stops (typically 10 pts or 0.5 ATR)
3. **Minimum distance**: Risk floor to avoid noise (3-5 pts minimum)
4. **Maximum distance**: Risk cap to prevent catastrophic single trades
5. **Critical rule**: VA-edge/structure stops > candle-extreme stops (study: 58-66% WR vs 5-14%)

### Phase 4: Target Model
1. **Structure target**: Where is the natural destination? (e.g., "opposite VA", "IB mid", "2R")
2. **R-multiple**: Define target as multiple of risk (1R, 2R, 4R)
3. **Adaptive by day type**: Different targets for different market conditions
4. **R:R check**: Minimum R:R ratio before taking trade (typically 1.5:1)

### Phase 5: Scaffold
Use `/add-strategy` to create the strategy file:
```
/add-strategy {name} --day-types {types} --direction {dir}
```

Implement the entry/stop/target model in the `on_bar()` method following `StrategyBase` interface.

### Phase 6: Backtest
Run isolated backtest to validate:
```bash
uv run python scripts/run_backtest.py --strategies {key} --no-merge
```

Collect metrics:
- Win Rate (target: >45% for trend, >55% for mean-reversion)
- Profit Factor (target: >1.5)
- Trade count (target: >20 for statistical significance)
- Max drawdown (target: <5%)
- Exit reason distribution (stops vs targets vs EOD)

### Phase 7: Reflection
For each losing trade, analyze:
1. What day type was it?
2. What was the extension at entry?
3. Did order flow confirm or contradict?
4. Was the stop too tight or too wide?
5. Was the target unreachable for this day type?

Save reflection to `data/results/reflections/{strategy}_{date}.md`

### Phase 8: Optimize
Rules for optimization:
1. **Single parameter at a time** — never change 2+ things simultaneously
2. **Minimum 20 trades** — never optimize on <20 trades
3. **Structural justification required** — every change must have a market logic reason
4. **Compare with/without** — always run baseline vs modified
5. **Watch for curve fitting** — if WR improves >15pp, it's likely overfit
6. **Re-run full suite** — after any change, run full backtest to check regressions

### Phase 9: Regression Check
After any strategy change:
```bash
uv run python -m pytest packages/rockit-core/tests/ -x -q
uv run python scripts/run_backtest.py --no-merge
```

Compare against saved baseline. Accept only if:
- All tests pass
- No existing strategy regresses >5% WR or >20% PF
- New strategy meets its own targets

## Key Principles (from strategy-studies)
1. **NQ has structural long bias** — default LONG for NQ
2. **5-min timeframe >> 1-min** for quality decisions
3. **Acceptance is the #1 filter** — 30-min or 2x 5-min acceptance provides +28pp edge
4. **Stop placement matters more than entry** — VA-edge stops crush candle-extreme stops
5. **Balance days are 43% of sessions** — detectable at 10:30 via IB POC shape
6. **Never trade P-day SHORT** on NQ — 29% WR, fights bullish skew

## Output
- Strategy file in `packages/rockit-core/src/rockit_core/strategies/`
- Tests in `packages/rockit-core/tests/`
- Registered in `loader.py` and `configs/strategies.yaml`
- Backtest results saved to `data/results/`
- Reflection saved to `data/results/reflections/`
