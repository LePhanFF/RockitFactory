#!/usr/bin/env python3
"""
Combinatorial backtest runner — test strategy × stop × target combinations.

Usage:
    # Test existing strategy with different stops/targets
    uv run python scripts/run_combo_backtest.py \
        --strategy or_reversal \
        --stops 1_atr,2_atr,level_buffer_10pct \
        --targets 2r,3r,ib_1.5x \
        --instrument NQ

    # Test MACD strategy
    uv run python scripts/run_combo_backtest.py \
        --strategy macd_crossover \
        --stops 1_atr,2_atr,fixed_15pts \
        --targets 2r,3r,4r \
        --instrument NQ

    # List available stops and targets
    uv run python scripts/run_combo_backtest.py --list-models
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "packages" / "rockit-core" / "src"))

from rockit_core.config.instruments import get_instrument
from rockit_core.data.features import compute_all_features
from rockit_core.data.manager import SessionDataManager
from rockit_core.execution.combo_report import combo_report
from rockit_core.execution.combo_runner import ComboRunner
from rockit_core.models.registry import (
    STOP_MODEL_FACTORIES,
    TARGET_MODEL_FACTORIES,
    get_stop_model,
    get_target_model,
)

# Strategy name → loader
STRATEGY_MAP = {
    'or_reversal': 'rockit_core.strategies.or_reversal.OpeningRangeReversal',
    'or_acceptance': 'rockit_core.strategies.or_acceptance.OpeningRangeAcceptance',
    'b_day': 'rockit_core.strategies.b_day.BDayStrategy',
    '80p': 'rockit_core.strategies.eighty_percent_rule.EightyPercentRule',
    'mean_reversion': 'rockit_core.strategies.mean_reversion_vwap.MeanReversionVWAP',
    'ema_trend': 'rockit_core.strategies.ema_trend_follow.EMATrendFollow',
    'macd_crossover': 'rockit_core.strategies.macd_crossover.MACDCrossover',
}


def load_strategy(name: str):
    """Load a strategy by name."""
    fqn = STRATEGY_MAP.get(name)
    if fqn is None:
        print(f"Unknown strategy '{name}'. Available: {list(STRATEGY_MAP.keys())}")
        sys.exit(1)

    module_path, class_name = fqn.rsplit('.', 1)
    import importlib
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls()


def parse_args():
    parser = argparse.ArgumentParser(description="Run combinatorial backtest")
    parser.add_argument('--strategy', '-s', type=str, help="Strategy name")
    parser.add_argument('--stops', type=str, help="Comma-separated stop model keys")
    parser.add_argument('--targets', type=str, help="Comma-separated target model keys")
    parser.add_argument('--instrument', '-i', default='NQ', choices=['NQ', 'ES', 'YM'])
    parser.add_argument('--data-dir', type=str, default='data/sessions')
    parser.add_argument('--list-models', action='store_true', help="List available models")
    parser.add_argument('--no-original', action='store_true', help="Skip original combo")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_models:
        print("Stop models:")
        for k in sorted(STOP_MODEL_FACTORIES.keys()):
            print(f"  {k}")
        print("\nTarget models:")
        for k in sorted(TARGET_MODEL_FACTORIES.keys()):
            print(f"  {k}")
        return

    if not args.strategy:
        print("Error: --strategy is required (use --list-models to see options)")
        sys.exit(1)
    if not args.stops:
        print("Error: --stops is required")
        sys.exit(1)
    if not args.targets:
        print("Error: --targets is required")
        sys.exit(1)

    # Load data
    instrument = get_instrument(args.instrument)
    data_dir = project_root / args.data_dir
    manager = SessionDataManager(data_dir)
    df = manager.load_sessions(instrument.symbol)

    if df is None or df.empty:
        print(f"No data found in {data_dir} for {instrument.symbol}")
        sys.exit(1)

    df = compute_all_features(df, instrument)
    print(f"Loaded {len(df)} bars for {instrument.symbol}")

    # Load strategy and models
    strategy = load_strategy(args.strategy)
    stop_models = [get_stop_model(k.strip()) for k in args.stops.split(',')]
    target_models = [get_target_model(k.strip()) for k in args.targets.split(',')]

    print(f"Strategy: {strategy.name}")
    print(f"Stops:    {[s.name for s in stop_models]}")
    print(f"Targets:  {[t.name for t in target_models]}")
    print(f"Combos:   {len(stop_models) * len(target_models)}")
    print()

    # Run combo backtest
    runner = ComboRunner(
        instrument=instrument,
        strategy=strategy,
        stop_models=stop_models,
        target_models=target_models,
    )
    results = runner.run(
        df,
        include_original=not args.no_original,
        verbose=True,
    )

    # Print report
    report_df = combo_report(results)
    print(f"\n{'='*80}")
    print("COMBO BACKTEST RESULTS")
    print(f"{'='*80}")
    print(report_df.to_string(index=False))
    print()


if __name__ == '__main__':
    main()
