#!/bin/bash
# Run LLM A/B test for all 16 enabled strategies sequentially
# Estimated: ~38 hours total (850+ signals × ~2 min each)
#
# Features:
#   - Resume support: tracks completed strategies in a progress file
#   - Skip already-completed strategies on re-run
#   - Pass --reset to clear progress and start fresh
#   - Pass --baseline-only or --llm-only to run a single arm
#
# Usage:
#   bash scripts/run_ab_test_all.sh                    # Run both A+B (skips completed)
#   bash scripts/run_ab_test_all.sh --baseline-only    # Run only deterministic baseline
#   bash scripts/run_ab_test_all.sh --llm-only         # Run only LLM debate
#   bash scripts/run_ab_test_all.sh --reset            # Clear progress, run all from scratch
#   bash scripts/run_ab_test_all.sh nwog_gap_fill va_edge_fade  # Run specific strategies

PYTHON=".venv/bin/python"
SCRIPT="scripts/backtest_strategy_ab.py"
PROGRESS_FILE="data/results/ab_test_progress.txt"

# All 16 enabled strategies in order of signal count (smallest first)
ALL_STRATEGIES=(
    "nwog_gap_fill"          # ~15 signals, ~30 min
    "double_distribution"    # ~16 signals, ~32 min
    "eighty_percent_rule"    # ~23 signals, ~46 min
    "b_day"                  # ~27 signals, ~54 min
    "ib_edge_fade"           # ~28 signals, ~56 min
    "poor_highlow_repair"    # ~28 signals, ~56 min
    "va_edge_fade"           # ~33 signals, ~66 min
    "twenty_percent_rule"    # ~37 signals, ~74 min
    "trend_bear"             # ~48 signals, ~96 min
    "pdh_pdl_reaction"       # ~51 signals, ~102 min
    "or_reversal"            # ~57 signals, ~114 min
    "trend_bull"             # ~66 signals, ~132 min
    "ndog_gap_fill"          # ~70 signals, ~140 min
    "or_acceptance"          # ~94 signals, ~188 min
    "single_print_gap_fill"  # ~103 signals, ~206 min
    "rth_gap_fill"           # ~260 signals, ~520 min
)

# Parse flags vs strategy names
EXTRA_FLAGS=()
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --reset)
            echo "Clearing progress file..."
            rm -f "$PROGRESS_FILE"
            ;;
        --baseline-only|--llm-only)
            EXTRA_FLAGS+=("$arg")
            ;;
        *)
            POSITIONAL+=("$arg")
            ;;
    esac
done

# Use provided strategies or all
if [ ${#POSITIONAL[@]} -gt 0 ]; then
    STRATEGIES=("${POSITIONAL[@]}")
else
    STRATEGIES=("${ALL_STRATEGIES[@]}")
fi

# Mode label for progress tracking
MODE="both"
for flag in "${EXTRA_FLAGS[@]}"; do
    if [ "$flag" = "--baseline-only" ]; then MODE="baseline"; fi
    if [ "$flag" = "--llm-only" ]; then MODE="llm"; fi
done

# Use mode-specific progress file so baseline and llm runs track separately
PROGRESS_FILE="data/results/ab_test_progress_${MODE}.txt"

# Create progress file if it doesn't exist
touch "$PROGRESS_FILE"

# Count already completed
ALREADY_DONE=0
for strat in "${STRATEGIES[@]}"; do
    if grep -qx "$strat" "$PROGRESS_FILE" 2>/dev/null; then
        ALREADY_DONE=$((ALREADY_DONE + 1))
    fi
done

echo "================================================"
echo "  LLM A/B Test — $(date)"
echo "  Mode: $MODE"
echo "  Strategies: ${#STRATEGIES[@]} total, $ALREADY_DONE already completed"
echo "  Progress file: $PROGRESS_FILE"
echo "================================================"

COMPLETED=0
SKIPPED=0
FAILED=0
TOTAL=${#STRATEGIES[@]}

for strat in "${STRATEGIES[@]}"; do
    COMPLETED=$((COMPLETED + 1))

    # Skip if already completed
    if grep -qx "$strat" "$PROGRESS_FILE" 2>/dev/null; then
        SKIPPED=$((SKIPPED + 1))
        echo "[$COMPLETED/$TOTAL] SKIP $strat (already completed)"
        continue
    fi

    echo ""
    echo "[$COMPLETED/$TOTAL] Starting $strat at $(date '+%H:%M:%S')..."
    START_TIME=$(date +%s)

    $PYTHON $SCRIPT --strategies "$strat" --no-merge ${EXTRA_FLAGS[@]} 2>&1 | tee "data/results/ab_log_${strat}_${MODE}.txt"
    EXIT_CODE=${PIPESTATUS[0]}

    END_TIME=$(date +%s)
    ELAPSED=$(( (END_TIME - START_TIME) / 60 ))

    if [ $EXIT_CODE -eq 0 ]; then
        # Mark as completed
        echo "$strat" >> "$PROGRESS_FILE"
        echo "[$COMPLETED/$TOTAL] DONE $strat (${ELAPSED}m) at $(date '+%H:%M:%S')"
    else
        FAILED=$((FAILED + 1))
        echo "[$COMPLETED/$TOTAL] FAILED $strat (exit code $EXIT_CODE) at $(date '+%H:%M:%S')"
    fi
done

RAN=$((TOTAL - SKIPPED))
echo ""
echo "================================================"
echo "  ALL DONE — $(date)"
echo "  Mode: $MODE | Total: $TOTAL | Ran: $RAN | Skipped: $SKIPPED | Failed: $FAILED"
echo "  Progress: $(wc -l < "$PROGRESS_FILE") strategies completed overall"
echo "================================================"
echo ""
echo "Results in data/results/ab_test_*.json"
echo "Per-strategy reports in data/results/ab_{strategy}_${MODE}_*.json"
echo "Logs in data/results/ab_log_*_${MODE}.txt"
echo "Progress in $PROGRESS_FILE"
echo ""
echo "To resume: bash scripts/run_ab_test_all.sh ${EXTRA_FLAGS[*]}"
echo "To restart: bash scripts/run_ab_test_all.sh --reset ${EXTRA_FLAGS[*]}"
