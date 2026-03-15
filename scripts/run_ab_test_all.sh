#!/bin/bash
# Run LLM A/B test for all 12 strategies sequentially
# Estimated: ~18 hours total (550+ signals × ~2 min each)
#
# Usage: bash scripts/run_ab_test_all.sh
# Or run specific strategies: bash scripts/run_ab_test_all.sh nwog_gap_fill va_edge_fade

PYTHON=".venv/Scripts/python.exe"
SCRIPT="scripts/backtest_strategy_ab.py"

# All 12 strategies in order of signal count (smallest first)
ALL_STRATEGIES=(
    "nwog_gap_fill"          # ~15 signals, ~30 min
    "va_edge_fade"           # ~33 signals, ~66 min
    "eighty_percent_rule"    # ~23 signals, ~46 min
    "twenty_percent_rule"    # ~37 signals, ~74 min
    "trend_bear"             # ~48 signals, ~96 min
    "b_day"                  # ~27 signals, ~54 min
    "pdh_pdl_reaction"       # ~51 signals, ~102 min
    "ib_edge_fade"           # ~28 signals, ~56 min
    "trend_bull"             # ~66 signals, ~132 min
    "ndog_gap_fill"          # ~70 signals, ~140 min
    "or_reversal"            # ~57 signals, ~114 min
    "or_acceptance"          # ~94 signals, ~188 min
)

# Use provided strategies or all
if [ $# -gt 0 ]; then
    STRATEGIES=("$@")
else
    STRATEGIES=("${ALL_STRATEGIES[@]}")
fi

echo "================================================"
echo "  LLM A/B Test — $(date)"
echo "  Strategies: ${#STRATEGIES[@]}"
echo "================================================"

COMPLETED=0
TOTAL=${#STRATEGIES[@]}

for strat in "${STRATEGIES[@]}"; do
    COMPLETED=$((COMPLETED + 1))
    echo ""
    echo "[$COMPLETED/$TOTAL] Starting $strat at $(date '+%H:%M:%S')..."
    $PYTHON $SCRIPT --strategies "$strat" --no-merge 2>&1 | tee "data/results/ab_log_${strat}.txt"
    echo "[$COMPLETED/$TOTAL] Finished $strat at $(date '+%H:%M:%S')"
done

echo ""
echo "================================================"
echo "  ALL DONE — $(date)"
echo "  Completed: $COMPLETED/$TOTAL strategies"
echo "================================================"
echo ""
echo "Results in data/results/ab_test_*.json"
echo "Logs in data/results/ab_log_*.txt"
