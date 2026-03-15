"""Tests for MACD crossover proof-of-concept strategy."""

from datetime import datetime, time

import numpy as np
import pandas as pd
import pytest

from rockit_core.models.stop_models import ATRStopModel, FixedPointsStop
from rockit_core.models.target_models import RMultipleTarget
from rockit_core.strategies.macd_crossover import MACDCrossover


def _make_bars(n=100, base_price=20000.0, trend=0.0):
    """Generate n bars of synthetic data with optional trend."""
    timestamps = pd.date_range('2025-01-15 09:30', periods=n, freq='1min')
    np.random.seed(42)
    noise = np.random.randn(n) * 5
    closes = base_price + np.cumsum(noise) + np.arange(n) * trend
    return pd.DataFrame({
        'timestamp': timestamps,
        'open': closes - 1,
        'high': closes + 3,
        'low': closes - 3,
        'close': closes,
        'volume': np.random.randint(100, 1000, n),
    })


def _ctx(ib_range=100.0, vwap=20000.0, bar_time=time(10, 35)):
    return {
        'ib_range': ib_range,
        'ib_high': vwap + 50,
        'ib_low': vwap - 50,
        'ib_mid': vwap,
        'atr14': 80.0,
        'vwap': vwap,
        'day_type': 'neutral',
        'trend_strength': 'moderate',
        'bar_time': bar_time,
    }


class TestMACDCrossoverInit:
    def test_default_models(self):
        strat = MACDCrossover()
        assert strat._stop_model.name == '2.0_atr'
        assert strat._target_model.name == '2r'

    def test_custom_models(self):
        strat = MACDCrossover(
            stop_model=FixedPointsStop(10),
            target_model=RMultipleTarget(3.0),
        )
        assert strat._stop_model.name == 'fixed_10pts'
        assert strat._target_model.name == '3r'

    def test_name(self):
        assert MACDCrossover().name == "MACD Crossover"

    def test_applicable_day_types_empty(self):
        assert MACDCrossover().applicable_day_types == []


class TestMACDDetection:
    def test_no_signal_before_warmup(self):
        """Need MACD_SLOW + MACD_SIGNAL = 26 + 9 = 35 bars minimum."""
        strat = MACDCrossover()
        bars_df = _make_bars(60)
        ib_bars = bars_df.head(60)
        ctx = _ctx()
        ctx['ib_bars'] = ib_bars

        strat.on_session_start('2025-01-15', 20050, 19950, 100, ctx)

        # With 60 IB bars pre-loaded, we have enough for MACD warmup
        # but first bar still needs to establish prev_macd
        bar = bars_df.iloc[0]
        signal = strat.on_bar(bar, 0, ctx)
        # First bar after warmup establishes prev values, returns None
        assert signal is None

    def test_signals_fire_with_enough_data(self):
        """Run through enough bars that at least one crossover should happen."""
        strat = MACDCrossover()

        # Create trending then reverting data to force crossover
        n_ib = 60
        n_post = 100
        np.random.seed(123)

        # IB bars: flat
        ib_closes = 20000 + np.random.randn(n_ib) * 2
        ib_bars = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-15 09:30', periods=n_ib, freq='1min'),
            'open': ib_closes - 1,
            'high': ib_closes + 2,
            'low': ib_closes - 2,
            'close': ib_closes,
            'volume': np.ones(n_ib) * 500,
        })

        # Post-IB: trend up then sharply down (force MACD crossover)
        up = np.linspace(0, 80, 50)
        down = np.linspace(80, -40, 50)
        post_closes = 20000 + np.concatenate([up, down]) + np.random.randn(n_post) * 1

        post_bars = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-15 10:30', periods=n_post, freq='1min'),
            'open': post_closes - 1,
            'high': post_closes + 2,
            'low': post_closes - 2,
            'close': post_closes,
            'volume': np.ones(n_post) * 500,
        })

        ctx = _ctx(vwap=20000.0)
        ctx['ib_bars'] = ib_bars

        strat.on_session_start('2025-01-15', 20050, 19950, 100, ctx)

        signals = []
        for i in range(len(post_bars)):
            bar = post_bars.iloc[i]
            # Update VWAP based on price for realistic confirmation
            ctx['vwap'] = float(bar['close']) - 5  # Slightly below for LONG passes
            ctx['bar_time'] = bar['timestamp'].time()
            sig = strat.on_bar(bar, i, ctx)
            if sig is not None:
                signals.append(sig)

        # Should get at least one signal from the trend reversal
        assert len(signals) > 0

    def test_time_cutoff_blocks_signals(self):
        """No signals after 14:00."""
        strat = MACDCrossover()
        ib_bars = _make_bars(60)
        ctx = _ctx(bar_time=time(14, 5))
        ctx['ib_bars'] = ib_bars
        strat.on_session_start('2025-01-15', 20050, 19950, 100, ctx)

        # Even with enough warmup, time gate should block
        for i in range(50):
            bar = pd.Series({
                'timestamp': datetime(2025, 1, 15, 14, 5 + (i % 55)),
                'open': 20000, 'high': 20010, 'low': 19990,
                'close': 20000 + i * 2, 'volume': 500,
            })
            sig = strat.on_bar(bar, i, ctx)
            assert sig is None


class TestMACDPluggableModels:
    def test_different_stops_produce_different_signals(self):
        """Same detection, different stop model → different stop prices."""
        strat_tight = MACDCrossover(stop_model=ATRStopModel(1.0), target_model=RMultipleTarget(2.0))
        strat_wide = MACDCrossover(stop_model=ATRStopModel(2.0), target_model=RMultipleTarget(2.0))

        np.random.seed(123)
        n_ib = 60
        ib_closes = 20000 + np.random.randn(n_ib) * 2
        ib_bars = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-15 09:30', periods=n_ib, freq='1min'),
            'open': ib_closes - 1, 'high': ib_closes + 2,
            'low': ib_closes - 2, 'close': ib_closes,
            'volume': np.ones(n_ib) * 500,
        })

        # Trend up then sharply down to force crossovers
        up = np.linspace(0, 80, 50)
        down = np.linspace(80, -40, 50)
        post_closes = 20000 + np.concatenate([up, down]) + np.random.randn(100) * 1

        post_bars = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-15 10:30', periods=100, freq='1min'),
            'open': post_closes - 1, 'high': post_closes + 2,
            'low': post_closes - 2, 'close': post_closes,
            'volume': np.ones(100) * 500,
        })

        ctx = _ctx(vwap=20000.0)
        ctx['ib_bars'] = ib_bars

        strat_tight.on_session_start('2025-01-15', 20050, 19950, 100, dict(ctx))
        strat_wide.on_session_start('2025-01-15', 20050, 19950, 100, dict(ctx))

        signals_tight = []
        signals_wide = []

        for i in range(len(post_bars)):
            bar = post_bars.iloc[i]
            ctx_copy = dict(ctx)
            # Set VWAP to allow both LONG and SHORT through
            ctx_copy['vwap'] = float(bar['close'])
            ctx_copy['bar_time'] = bar['timestamp'].time()

            s1 = strat_tight.on_bar(bar, i, dict(ctx_copy))
            s2 = strat_wide.on_bar(bar, i, dict(ctx_copy))

            if s1:
                signals_tight.append(s1)
            if s2:
                signals_wide.append(s2)

        # Both strategies should detect the same crossovers
        assert len(signals_tight) == len(signals_wide)
        assert len(signals_tight) > 0, "No MACD crossovers detected — adjust test data"

        # But with different stop/target prices
        for s1, s2 in zip(signals_tight, signals_wide):
            assert s1.entry_price == s2.entry_price  # Same detection
            assert s1.stop_price != s2.stop_price  # Different stops
            assert s1.target_price != s2.target_price  # Different targets

    def test_signal_contains_model_names(self):
        """Signal metadata should contain stop/target model names."""
        strat = MACDCrossover(
            stop_model=FixedPointsStop(15),
            target_model=RMultipleTarget(3.0),
        )

        np.random.seed(42)
        n_ib = 60
        ib_closes = 20000 + np.random.randn(n_ib) * 2
        ib_bars = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-15 09:30', periods=n_ib, freq='1min'),
            'open': ib_closes - 1, 'high': ib_closes + 2,
            'low': ib_closes - 2, 'close': ib_closes,
            'volume': np.ones(n_ib) * 500,
        })

        up = np.linspace(0, 80, 50)
        down = np.linspace(80, -40, 50)
        post_closes = 20000 + np.concatenate([up, down]) + np.random.randn(100) * 0.5

        post_bars = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-15 10:30', periods=100, freq='1min'),
            'open': post_closes - 1, 'high': post_closes + 2,
            'low': post_closes - 2, 'close': post_closes,
            'volume': np.ones(100) * 500,
        })

        ctx = _ctx(vwap=20000.0)
        ctx['ib_bars'] = ib_bars
        strat.on_session_start('2025-01-15', 20050, 19950, 100, ctx)

        for i in range(len(post_bars)):
            bar = post_bars.iloc[i]
            ctx['vwap'] = float(bar['close']) - 5
            ctx['bar_time'] = bar['timestamp'].time()
            sig = strat.on_bar(bar, i, ctx)
            if sig is not None:
                assert sig.metadata['stop_model'] == 'fixed_15pts'
                assert sig.metadata['target_model'] == '3r'
                break
        else:
            pytest.skip("No MACD crossover detected in test data")
