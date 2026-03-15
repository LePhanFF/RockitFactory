# Double Distribution Strategy Tuning Report
**Date**: 2026-03-14
**Instrument**: NQ (274 sessions, 2025-02 to 2026-03)

## Baseline
- 31 trades, 35.5% WR, PF 1.30, +$3,753, $121/trade
- LONG: 14t, 28.6% WR, PF 0.95, -$337 (net loser)
- SHORT: 17t, 41.2% WR, PF 1.66, +$4,090

## Parameter Sweep Results

| Config | Direction | POC Spread | Stop | Target | PB Window | Trail | Trades | WR | PF | Net P&L | Avg/Trade |
|--------|-----------|-----------|------|--------|-----------|-------|--------|-----|------|---------|-----------|
| A: Baseline | both | 75 | 30 | 2.5R | 60 | no | 31 | 35.5% | 1.30 | $3,753 | $121 |
| B: SHORT-only | short | 75 | 30 | 2.5R | 60 | no | 17 | 41.2% | 1.66 | $4,090 | $241 |
| C: SHORT+tighter | short | 100 | 30 | 2.0R | 30 | no | 12 | 33.3% | 0.94 | -$289 | -$24 |
| D: SHORT+tighter+trail | short | 100 | 30 | 2.0R | 30 | yes | 12 | 50.0% | 0.92 | -$306 | -$26 |
| E: SHORT+aggressive | short | 125 | 30 | 2.0R | 30 | no | 9 | 33.3% | 0.94 | -$217 | -$24 |
| F: Both+high spread | both | 125 | 30 | 2.0R | 30 | no | 13 | 38.5% | 1.18 | $887 | $68 |
| G: SHORT+trail orig | short | 75 | 30 | 2.5R | 60 | yes | 17 | 52.9% | 1.02 | $81 | $5 |
| H: SHORT+2R | short | 75 | 30 | 2.0R | 60 | no | 17 | 41.2% | 1.32 | $1,990 | $117 |
| **I: SHORT+3R** | **short** | **75** | **30** | **3.0R** | **60** | **no** | **17** | **41.2%** | **1.99** | **$6,190** | **$364** |
| J: SHORT+poc90 | short | 90 | 30 | 2.5R | 60 | no | 17 | 41.2% | 1.66 | $4,090 | $241 |
| K: SHORT+pb45 | short | 75 | 30 | 2.5R | 45 | no | 15 | 40.0% | 1.58 | $3,239 | $216 |
| L: SHORT+stop25 | short | 75 | 25 | 2.5R | 60 | no | 17 | 29.4% | 0.97 | -$160 | -$9 |

## R-Multiple Sensitivity (SHORT-only, original params)

| Target R | Trades | WR | PF | Net P&L | Avg Win | Avg Loss |
|----------|--------|-----|------|---------|---------|----------|
| 2.0R | 17 | 41.2% | 1.32 | $1,990 | $1,176 | -$624 |
| 2.5R | 17 | 41.2% | 1.66 | $4,090 | $1,476 | -$624 |
| **3.0R** | **17** | **41.2%** | **1.99** | **$6,190** | **$1,776** | **-$624** |
| 3.5R | 17 | 35.3% | 1.99 | $6,195 | $2,076 | -$569 |
| 4.0R | 17 | 35.3% | 2.28 | $7,995 | $2,376 | -$569 |

## Key Findings

1. **SHORT-only is the dominant filter**: LONG side is PF 0.95 (-$337). Removing LONG instantly improves portfolio from PF 1.30 to 1.66.

2. **3R target is optimal**: At 3.0R, 7 of 17 winners still hit target (41.2% WR preserved). At 3.5R, one winner falls short and WR drops to 35.3%. The 3.0R sweet spot gives PF 1.99 with WR above 40%.

3. **Trailing stops destroy performance**: Trail converts PF 1.66 to PF 1.02 (Config G). Winners need the full room to run -- trail exits too early.

4. **Tighter POC spread thresholds hurt**: Increasing from 75 to 100/125 reduces trade count without improving per-trade quality. The removed trades were actually winners.

5. **Shorter pullback window loses trades**: PB 45 loses 2 trades (15 vs 17), PB 30 loses 5 trades (12 vs 17). The original 60-bar window captures more valid setups.

6. **Tighter stops kill WR**: 25pt stop drops WR from 41.2% to 29.4% (stops get clipped before reversal).

## Direction Analysis

**Why LONG fails**: Double distribution LONGs enter at separation with price pulling back from above. In practice, when price is above separation and pulls back, it often continues through (the pullback becomes a trend reversal). SHORT setups work because the pullback from below separation is a natural retracement in a declining trend.

## Statistical Caveat

17 trades is a small sample. The 41.2% WR has a wide confidence interval (~20-65% at 95% CI). However, the win/loss ratio of 2.85:1 ($1,776 avg win vs $624 avg loss) provides a margin of safety -- the strategy remains profitable even at 30% WR.

## Recommendation

**ENABLE with Config I: SHORT-only + 3R target**

| Metric | Before | After | Benchmark |
|--------|--------|-------|-----------|
| Trades | 31 | 17 | - |
| Win Rate | 35.5% | 41.2% | > 40% (soft) |
| Profit Factor | 1.30 | 1.99 | > 1.5 (hard) |
| Net P&L | $3,753 | $6,190 | positive |
| Avg Trade | $121 | $364 | positive |
| Max DD | 4.81% | 2.03% | - |

Changes applied:
- `configs/strategies.yaml`: `enabled: true`, `direction: short`, `trail: {enabled: false}`
- `double_distribution.py`: `DEFAULT_TARGET_R = 3.0`, `short_only=True` parameter with direction gate
