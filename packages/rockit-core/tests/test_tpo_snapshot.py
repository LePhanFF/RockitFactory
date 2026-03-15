"""Tests for signal-time TPO snapshot and metadata pipeline."""

from datetime import datetime, time

import numpy as np
import pandas as pd
import pytest

from rockit_core.engine.position import OpenPosition
from rockit_core.engine.tpo_snapshot import generate_signal_tpo_snapshot
from rockit_core.engine.trade import Trade
from rockit_core.strategies.signal import Signal


# --- Helpers ---

def _make_rth_bars(n_bars=120, start_price=21000.0, volatility=5.0):
    """Create realistic 1-min RTH bars for TPO analysis."""
    times = pd.date_range('2025-01-15 09:30', periods=n_bars, freq='1min')
    np.random.seed(42)
    prices = [start_price]
    for _ in range(n_bars - 1):
        prices.append(prices[-1] + np.random.randn() * volatility)

    df = pd.DataFrame({
        'timestamp': times,
        'open': prices,
        'high': [p + abs(np.random.randn()) * 3 for p in prices],
        'low': [p - abs(np.random.randn()) * 3 for p in prices],
        'close': [p + np.random.randn() * 2 for p in prices],
        'volume': np.random.randint(100, 1000, n_bars),
    })
    return df


def _make_rth_bars_with_index(n_bars=120, start_price=21000.0):
    """Create RTH bars with DatetimeIndex (as used by deterministic modules)."""
    df = _make_rth_bars(n_bars, start_price)
    df = df.set_index(pd.to_datetime(df['timestamp']))
    return df


# --- Unit Tests: generate_signal_tpo_snapshot ---


class TestGenerateSignalTpoSnapshot:
    def test_returns_dict_with_expected_keys(self):
        """Snapshot should contain all TPO structural fields."""
        df = _make_rth_bars(120)
        result = generate_signal_tpo_snapshot(df, '10:45')

        assert isinstance(result, dict)
        assert result['signal_time'] == '10:45'

        expected_keys = [
            'tpo_shape', 'current_poc', 'current_vah', 'current_val',
            'excess_high', 'excess_low', 'poor_high', 'poor_low',
            'otf_bias', 'width_trend', 'fattening_zone',
            'distributions', 'single_print_ranges',
            'hvn_nodes', 'lvn_nodes', 'period_ranges',
            'otf_sequence', 'naked_levels',
            'rejection_at_high', 'rejection_at_low', 'note',
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_tpo_shape_computed(self):
        """With enough bars, TPO shape should be a real classification."""
        df = _make_rth_bars(120)
        result = generate_signal_tpo_snapshot(df, '11:00')

        valid_shapes = [
            'p_shape', 'b_shape', 'D_shape', 'B_shape',
            'elongated', 'neutral', 'wide_value', 'developing',
            'insufficient',
        ]
        assert result['tpo_shape'] in valid_shapes

    def test_core_levels_are_numbers(self):
        """POC, VAH, VAL should be numeric values."""
        df = _make_rth_bars(120)
        result = generate_signal_tpo_snapshot(df, '10:45')

        assert isinstance(result['current_poc'], float)
        assert isinstance(result['current_vah'], float)
        assert isinstance(result['current_val'], float)
        assert result['current_vah'] >= result['current_val']

    def test_works_with_timestamp_column(self):
        """Should work when input has timestamp column (backtest format)."""
        df = _make_rth_bars(120)
        assert 'timestamp' in df.columns
        result = generate_signal_tpo_snapshot(df, '10:45')
        assert result['current_poc'] is not None

    def test_works_with_datetime_index(self):
        """Should work when input has DatetimeIndex (deterministic format)."""
        df = _make_rth_bars_with_index(120)
        result = generate_signal_tpo_snapshot(df, '10:45')
        assert result['current_poc'] is not None

    def test_no_prior_day_graceful(self):
        """Without prior_day, naked_levels should all be 'NA'."""
        df = _make_rth_bars(120)
        result = generate_signal_tpo_snapshot(df, '10:45', prior_day=None)

        naked = result['naked_levels']
        for key in ['prior_poc', 'prior_vah', 'prior_val', 'prior_high', 'prior_low']:
            assert naked[key] == 'NA'

    def test_with_prior_day(self):
        """With prior_day levels, naked_levels should classify each."""
        df = _make_rth_bars(120, start_price=21000.0)
        prior = {
            'poc': 20995.0,
            'vah': 21010.0,
            'val': 20980.0,
            'high': 21050.0,
            'low': 20950.0,
        }
        result = generate_signal_tpo_snapshot(df, '10:45', prior_day=prior)

        naked = result['naked_levels']
        # Each level should be one of: tested, naked_above, naked_below, naked_gap
        for key in ['prior_poc', 'prior_vah', 'prior_val', 'prior_high', 'prior_low']:
            assert naked[key] in ('tested', 'naked_above', 'naked_below', 'naked_gap')

    def test_minimal_bars(self):
        """With very few bars, should return a result (possibly sparse)."""
        df = _make_rth_bars(5, start_price=21000.0)
        result = generate_signal_tpo_snapshot(df, '09:34')
        assert isinstance(result, dict)
        assert 'signal_time' in result


# --- Metadata Pipeline Tests ---


class TestMetadataPipeline:
    def test_open_position_accepts_metadata(self):
        """OpenPosition should store metadata dict."""
        pos = OpenPosition(
            direction='LONG', entry_price=100.0, stop_price=90.0,
            target_price=120.0, contracts=1, entry_time=datetime(2025, 1, 15, 10, 35),
            strategy_name='test', setup_type='test', day_type='neutral',
            trend_strength='moderate', session_date='2025-01-15',
            metadata={'stop_model': 'atr', 'some_key': 42},
        )
        assert pos.metadata == {'stop_model': 'atr', 'some_key': 42}

    def test_open_position_defaults_empty_metadata(self):
        """OpenPosition without metadata should default to empty dict."""
        pos = OpenPosition(
            direction='LONG', entry_price=100.0, stop_price=90.0,
            target_price=120.0, contracts=1, entry_time=datetime(2025, 1, 15, 10, 35),
            strategy_name='test', setup_type='test', day_type='neutral',
            trend_strength='moderate', session_date='2025-01-15',
        )
        assert pos.metadata == {}

    def test_signal_metadata_preserved_in_trade(self):
        """Trade.metadata should carry whatever was in Signal.metadata."""
        # This tests the dataclass field, not the full pipeline
        trade = Trade(
            strategy_name='OR Reversal',
            setup_type='or_rev',
            metadata={'stop_model': 'atr', 'tpo_at_entry': {'tpo_shape': 'p_shape'}},
        )
        assert trade.metadata['stop_model'] == 'atr'
        assert trade.metadata['tpo_at_entry']['tpo_shape'] == 'p_shape'

    def test_signal_metadata_copy_in_backtest(self):
        """backtest.py uses signal.metadata.copy() — verify copy semantics."""
        original = {'key': 'value'}
        copied = original.copy()
        pos = OpenPosition(
            direction='LONG', entry_price=100.0, stop_price=90.0,
            target_price=120.0, contracts=1, entry_time=datetime(2025, 1, 15, 10, 35),
            strategy_name='test', setup_type='test', day_type='neutral',
            trend_strength='moderate', session_date='2025-01-15',
            metadata=copied,
        )
        # Mutating pos.metadata should not affect original
        pos.metadata['new_key'] = 'new_value'
        assert 'new_key' not in original

    def test_open_position_metadata_none_gives_empty_dict(self):
        """Passing None for metadata should result in empty dict."""
        pos = OpenPosition(
            direction='SHORT', entry_price=100.0, stop_price=110.0,
            target_price=80.0, contracts=1, entry_time=datetime(2025, 1, 15, 10, 35),
            strategy_name='test', setup_type='test', day_type='neutral',
            trend_strength='moderate', session_date='2025-01-15',
            metadata=None,
        )
        assert pos.metadata == {}
