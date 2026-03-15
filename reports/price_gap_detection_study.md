# True Price Gap (Zero-Print) Detection Study

**Date**: 2026-03-14
**Instrument**: NQ
**Sessions**: 260
**Branch**: `claude/live-dashboard`

## Objective

Investigate whether "true price gaps" (price levels with ZERO TPO prints within a session) exist in 1-minute bar data and, if so, whether they produce a stronger fill signal than single prints (1 TPO print).

## Background

- **Single prints** (1 TPO): Price levels where exactly one TPO period traded. The market visited once and never returned -- "thin" areas in the profile. Currently detected by `detect_single_print_zones()`.
- **True price gaps** (0 TPO): Price levels between the session high and low where NO TPO period traded at all. The market moved so fast it literally skipped those prices -- a "vacuum" that should be an even stronger fill magnet.

## Detection Algorithm

Added `detect_price_gap_zones()` to `single_prints.py`:

1. Build the TPO profile using existing `_build_tpo_profile()` (price_level -> set of TPO periods)
2. Determine session high/low from the bar data
3. Generate ALL price levels from session low to session high at 0.25 tick granularity
4. Find levels that exist in the session range but are NOT in the profile (zero prints)
5. Group contiguous zero-print levels into zones
6. Filter by `min_zone_ticks=4` (1 point on NQ)
7. Classify location relative to Value Area (above_vah / below_val / within_va)

## Key Finding: Zero-Print Gaps Do Not Exist in 1-Minute Bar Data

| Metric | Single Prints (1 TPO) | Price Gaps (0 TPO) |
|--------|----------------------|-------------------|
| Sessions with zones | 259/260 (99.6%) | 0/260 (0.0%) |
| Avg zones/session | 2.2 | 0.0 |
| Total zones found | 572 | 0 |
| Min zone threshold | 10 ticks (2.5 pts) | 1 tick (0.25 pts) |

**Even with a 1-tick minimum threshold, ZERO price gap zones were found across all 260 sessions.**

### Why This Happens

Each 1-minute bar in the data records a high and low price. The TPO profile builder (`_build_tpo_profile`) generates all price levels between each bar's low and high at tick granularity (0.25). With ~390 bars per RTH session (6.5 hours x 60 minutes), consecutive bars almost always overlap or are contiguous. The market simply does not skip entire price levels between consecutive 1-minute bars on NQ futures.

A bar-by-bar analysis confirmed this: across 30 sessions, only 1 instance of a bar-to-bar gap was found (0.50 points / 2 ticks). NQ futures are too liquid for intraday price vacuums at 1-minute resolution.

### When Would Zero-Print Gaps Exist?

- **Higher time resolution** (e.g., 5-minute or 30-minute bars): Coarser bars create artificial gaps because each bar only covers one price range per period, leaving spaces between non-adjacent periods.
- **Less liquid instruments**: Thinly traded futures or after-hours sessions might show genuine skipped prices.
- **Different gap definition**: The RTH Gap Fill strategy already captures the inter-session gap (overnight gap between prior close and current open), which IS a meaningful "price gap."

## Backtest Results (Combined Run)

Running the strategy with both zone types enabled:

| Metric | Value |
|--------|-------|
| Trades | 146 |
| Win Rate | 30.1% |
| Profit Factor | 0.97 |
| Net P&L | -$1,397.60 |
| Zone types | 146 single_print, 0 price_gap |

All 146 trades came from single print zones (as expected given 0 price gap zones detected). The 30.1% WR matches the known SP Gap Fill detection algorithm mismatch documented previously.

## Implementation Summary

### Files Modified

- `packages/rockit-core/src/rockit_core/indicators/single_prints.py`
  - Added `detect_price_gap_zones()` function
  - Added `zone_type: "single_print"` field to existing `detect_single_print_zones()` output
  - Updated `compute_prior_session_single_prints()` to compute and include both zone types
- `packages/rockit-core/src/rockit_core/indicators/session_enrichment.py`
  - Updated to also call `detect_price_gap_zones()` and merge results
- `packages/rockit-core/src/rockit_core/strategies/single_print_gap_fill.py`
  - Preserved `zone_type` through extraction pipeline
  - Added `zone_type` to signal metadata
- `packages/rockit-core/tests/test_single_prints.py`
  - Added 8 new tests for `detect_price_gap_zones()` (7 unit + 1 integration)
  - Updated existing test to verify `zone_type` field on single print zones

### Test Results

30/30 tests passing (22 existing + 8 new).

## Recommendation

**Do NOT pursue true price gap detection for NQ with 1-minute bar data.** The signal simply does not exist at this data resolution. The implementation is correct and well-tested -- it would work if the data produced gaps -- but the market microstructure of NQ futures prevents zero-print levels from occurring intraday.

**Alternative directions for strengthening SP Gap Fill:**
1. Fix the existing single print detection algorithm mismatch (30.4% WR vs 69.2% study WR) -- this is the higher priority.
2. Consider zone quality scoring (e.g., zones created during fast one-directional moves vs. rotational moves).
3. Use the `zone_type` infrastructure for future zone type variants (e.g., "thin zone" = 2-3 TPO levels, between single print and normal).
