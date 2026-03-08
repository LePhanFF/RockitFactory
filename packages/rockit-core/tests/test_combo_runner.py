"""Tests for StrategyAdapter, ComboRunner, and combo_report."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from rockit_core.config.instruments import get_instrument
from rockit_core.execution.combo_report import combo_report
from rockit_core.execution.combo_runner import ComboResult, ComboRunner
from rockit_core.execution.strategy_adapter import StrategyAdapter
from rockit_core.models.stop_models import ATRStopModel, FixedPointsStop
from rockit_core.models.target_models import RMultipleTarget
from rockit_core.strategies.macd_crossover import MACDCrossover
from rockit_core.strategies.signal import Signal


# --- Synthetic data helpers ---

def _make_session_data(date_str='2025-01-15', n_bars=390, base=20000.0):
    """Create a full session of synthetic 1-min data (ETH + RTH).

    Returns a DataFrame that looks like real market data:
    - 390 bars (6.5 hours of RTH: 9:30 - 16:00)
    - Has timestamp, OHLCV columns
    - Has session_date column
    """
    np.random.seed(42)
    timestamps = pd.date_range(f'{date_str} 09:30', periods=n_bars, freq='1min')
    noise = np.random.randn(n_bars) * 5
    # Add a trend then reversal to generate signals
    trend = np.concatenate([
        np.linspace(0, 60, n_bars // 3),
        np.linspace(60, -30, n_bars // 3),
        np.linspace(-30, 20, n_bars - 2 * (n_bars // 3)),
    ])
    closes = base + trend + noise

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': closes - np.abs(np.random.randn(n_bars)) * 2,
        'high': closes + np.abs(np.random.randn(n_bars)) * 3 + 1,
        'low': closes - np.abs(np.random.randn(n_bars)) * 3 - 1,
        'close': closes,
        'volume': np.random.randint(200, 2000, n_bars),
        'vol_ask': np.random.randint(100, 1000, n_bars),
        'vol_bid': np.random.randint(100, 1000, n_bars),
    })
    df['vol_delta'] = df['vol_ask'] - df['vol_bid']
    df['session_date'] = date_str
    return df


def _add_indicators(df):
    """Add minimal indicators needed by backtest engine."""
    from rockit_core.indicators.technical import (
        calculate_atr,
        calculate_ema,
        calculate_rsi,
        calculate_vwap,
    )
    df = df.copy()
    df['ema20'] = calculate_ema(df['close'], 20)
    df['ema50'] = calculate_ema(df['close'], 50)
    df['atr14'] = calculate_atr(df, 14)
    df['rsi14'] = calculate_rsi(df['close'], 14)
    df['vwap'] = calculate_vwap(df)
    df['ema5'] = calculate_ema(df['close'], 5)
    df['ema10'] = calculate_ema(df['close'], 10)
    df['adx14'] = 25.0  # Fixed for simplicity
    return df


# --- StrategyAdapter Tests ---

class TestStrategyAdapter:
    def test_adapter_passes_through_name(self):
        strat = MACDCrossover()
        adapter = StrategyAdapter(strat)
        assert adapter.name == strat.name

    def test_adapter_passes_through_day_types(self):
        strat = MACDCrossover()
        adapter = StrategyAdapter(strat)
        assert adapter.applicable_day_types == strat.applicable_day_types

    def test_adapter_captures_detections(self):
        """Adapter should capture signals while passing them through."""
        strat = MACDCrossover()
        adapter = StrategyAdapter(strat)

        df = _add_indicators(_make_session_data())
        ib_bars = df.head(60)
        ctx = {
            'ib_range': 100, 'ib_high': 20050, 'ib_low': 19950,
            'ib_mid': 20000, 'atr14': 80, 'vwap': 20000,
            'day_type': 'neutral', 'trend_strength': 'moderate',
            'ib_bars': ib_bars,
        }

        adapter.on_session_start('2025-01-15', 20050, 19950, 100, ctx)

        signals = []
        for i in range(60, len(df)):
            bar = df.iloc[i]
            ctx['bar_time'] = bar['timestamp'].time()
            ctx['vwap'] = bar.get('vwap', 20000)
            sig = adapter.on_bar(bar, i - 60, ctx)
            if sig is not None:
                signals.append(sig)

        # Detections captured should match signals emitted
        assert len(adapter.detections) == len(signals)

    def test_adapter_returns_same_signal(self):
        """Adapter must return the EXACT same signal as the wrapped strategy."""
        strat = MACDCrossover()
        adapter = StrategyAdapter(strat)

        df = _add_indicators(_make_session_data())
        ib_bars = df.head(60)
        ctx = {
            'ib_range': 100, 'ib_high': 20050, 'ib_low': 19950,
            'ib_mid': 20000, 'atr14': 80, 'vwap': 20000,
            'day_type': 'neutral', 'trend_strength': 'moderate',
            'ib_bars': ib_bars,
        }

        adapter.on_session_start('2025-01-15', 20050, 19950, 100, ctx)

        for i in range(60, len(df)):
            bar = df.iloc[i]
            ctx['bar_time'] = bar['timestamp'].time()
            ctx['vwap'] = bar.get('vwap', 20000)
            sig = adapter.on_bar(bar, i - 60, ctx)
            if sig is not None:
                # The detection should store the exact same signal object
                assert adapter.detections[-1][0] is sig
                break

    def test_reset_detections(self):
        adapter = StrategyAdapter(MACDCrossover())
        adapter.detections.append(("fake", None, {}))
        adapter.reset_detections()
        assert len(adapter.detections) == 0


# --- ComboReport Tests ---

class TestComboReport:
    def test_report_empty(self):
        df = combo_report([])
        assert df.empty

    def test_report_format(self):
        results = [
            ComboResult('TestStrat', '1_atr', '2r', trades=10, wins=6, losses=4,
                        win_rate=60.0, profit_factor=2.0, net_pnl=5000.0, avg_r=1.5),
            ComboResult('TestStrat', '2_atr', '3r', trades=8, wins=5, losses=3,
                        win_rate=62.5, profit_factor=2.5, net_pnl=7000.0, avg_r=1.8),
        ]
        df = combo_report(results)

        assert len(df) == 2
        assert list(df.columns) == ['Strategy', 'Stop', 'Target', 'Trades', 'WR%', 'PF', 'Net P&L', 'Avg R']
        # Should be sorted by Net P&L descending
        assert df.iloc[0]['Net P&L'] >= df.iloc[1]['Net P&L']

    def test_report_rounding(self):
        results = [
            ComboResult('S', 'stop', 'tgt', trades=10, wins=6, losses=4,
                        win_rate=60.12345, profit_factor=2.12345, net_pnl=5000.123, avg_r=1.567),
        ]
        df = combo_report(results)
        assert df.iloc[0]['WR%'] == 60.1
        assert df.iloc[0]['PF'] == 2.12


# --- ComboRunner Integration Tests ---

class TestComboRunnerIntegration:
    @pytest.fixture
    def instrument(self):
        return get_instrument('NQ')

    @pytest.fixture
    def data(self):
        return _add_indicators(_make_session_data())

    def test_combo_runner_produces_results(self, instrument, data):
        """ComboRunner should produce results for each stop × target combo."""
        strategy = MACDCrossover()
        stops = [ATRStopModel(1.0), ATRStopModel(2.0)]
        targets = [RMultipleTarget(2.0), RMultipleTarget(3.0)]

        runner = ComboRunner(
            instrument=instrument,
            strategy=strategy,
            stop_models=stops,
            target_models=targets,
        )
        results = runner.run(data, include_original=True, verbose=False)

        # Should have: 1 original + 2 stops × 2 targets = 5 results
        assert len(results) == 5
        assert results[0].stop_model_name == 'original'

    def test_combo_runner_no_original(self, instrument, data):
        """When include_original=False, no 'original' combo."""
        runner = ComboRunner(
            instrument=instrument,
            strategy=MACDCrossover(),
            stop_models=[ATRStopModel(1.0)],
            target_models=[RMultipleTarget(2.0)],
        )
        results = runner.run(data, include_original=False, verbose=False)
        assert all(r.stop_model_name != 'original' for r in results)

    def test_different_combos_can_produce_different_results(self, instrument, data):
        """Different stop/target combos should (potentially) produce different outcomes."""
        runner = ComboRunner(
            instrument=instrument,
            strategy=MACDCrossover(),
            stop_models=[ATRStopModel(1.0), FixedPointsStop(50.0)],
            target_models=[RMultipleTarget(2.0)],
        )
        results = runner.run(data, include_original=False, verbose=False)

        # With very different stop models, at least trade count or PnL should differ
        # (unless no signals fire, which is possible with synthetic data)
        if results[0].trades > 0 and results[1].trades > 0:
            # Different stops should produce at least some difference
            assert (results[0].net_pnl != results[1].net_pnl or
                    results[0].win_rate != results[1].win_rate or
                    results[0].trades != results[1].trades)
