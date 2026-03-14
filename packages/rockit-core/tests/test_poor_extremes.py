"""
Tests for Poor High/Low Session-Level Detection
================================================

Tests both detection methods (A: enhanced bar analysis, B: TPO period count)
and the combined detection logic.
"""

import pandas as pd
import numpy as np
import pytest

from rockit_core.indicators.poor_extremes import (
    detect_poor_extremes,
    compute_prior_poor_extremes,
    _method_a_detect_high,
    _method_a_detect_low,
    _method_b_detect_high,
    _method_b_detect_low,
    _get_tpo_period,
)
from datetime import time as _time


# ── Helpers ────────────────────────────────────────────────

def _make_bars(rows, columns=('high', 'low', 'close', 'timestamp')):
    """Create a DataFrame of bars from list of tuples."""
    return pd.DataFrame(rows, columns=columns)


def _make_session_bars_poor_high():
    """
    Session with a poor high: bars near session high all close near their highs
    (no rejection wick). Session high = 100.0.
    """
    return _make_bars([
        # Earlier bars away from extreme
        (95.0, 93.0, 94.5, '10:00'),
        (97.0, 95.0, 96.5, '10:30'),
        # Bars near session high -- close at top of range (poor)
        (100.0, 98.0, 99.8, '11:00'),  # close pos = (99.8-98)/(100-98) = 0.9
        (100.0, 98.5, 99.9, '11:30'),  # close pos = (99.9-98.5)/(1.5) = 0.93
        (99.5, 97.5, 99.3, '12:00'),   # not near high (99.5 < 100 - 0.5)
        # Later bars pulling back
        (97.0, 95.0, 96.0, '13:00'),
    ])


def _make_session_bars_good_high():
    """
    Session with a good high (proper rejection): bars near session high close
    well below their highs (long upper wicks). Session high = 100.0.
    """
    return _make_bars([
        (95.0, 93.0, 94.5, '10:00'),
        (97.0, 95.0, 96.0, '10:30'),
        # Bars near session high -- close far from high (rejection)
        (100.0, 97.0, 97.5, '11:00'),  # close pos = (97.5-97)/(100-97) = 0.167
        (100.0, 97.5, 97.8, '11:30'),  # close pos = (97.8-97.5)/(2.5) = 0.12
        (97.0, 95.0, 95.5, '12:00'),
    ])


def _make_session_bars_poor_low():
    """
    Session with a poor low: bars near session low close near their lows
    (no rejection wick). Session low = 90.0.
    """
    return _make_bars([
        (97.0, 95.0, 96.0, '10:00'),
        (95.0, 93.0, 93.5, '10:30'),
        # Bars near session low -- close at bottom of range (poor)
        (92.0, 90.0, 90.2, '11:00'),  # close pos = (90.2-90)/(92-90) = 0.1
        (92.5, 90.0, 90.3, '11:30'),  # close pos = (90.3-90)/(2.5) = 0.12
        # Later recovery
        (95.0, 93.0, 94.5, '13:00'),
    ])


def _make_session_bars_good_low():
    """
    Session with a good low (proper rejection): bars near session low close
    well above their lows (long lower wicks). Session low = 90.0.
    """
    return _make_bars([
        (97.0, 95.0, 96.0, '10:00'),
        (95.0, 93.0, 94.5, '10:30'),
        # Bars near session low -- close far from low (rejection)
        (93.0, 90.0, 92.8, '11:00'),  # close pos = (92.8-90)/(93-90) = 0.93
        (92.5, 90.0, 92.3, '11:30'),  # close pos = (92.3-90)/(2.5) = 0.92
        (95.0, 93.0, 94.5, '12:00'),
    ])


# ── Method A Tests ─────────────────────────────────────────

class TestMethodAHigh:
    def test_poor_high_detected(self):
        bars = _make_session_bars_poor_high()
        is_poor, quality = _method_a_detect_high(bars, 100.0, 0.25)
        assert is_poor is True
        assert quality > 0.5

    def test_good_high_not_detected(self):
        bars = _make_session_bars_good_high()
        is_poor, quality = _method_a_detect_high(bars, 100.0, 0.25)
        assert is_poor is False
        assert quality < 0.5

    def test_empty_bars(self):
        bars = _make_bars([])
        is_poor, quality = _method_a_detect_high(bars, 100.0, 0.25)
        assert is_poor is False
        assert quality == 0.0

    def test_no_bars_near_high(self):
        """Bars exist but none are within proximity of session high."""
        bars = _make_bars([
            (95.0, 93.0, 94.0, '10:00'),
            (96.0, 94.0, 95.0, '10:30'),
        ])
        is_poor, quality = _method_a_detect_high(bars, 100.0, 0.25)
        assert is_poor is False
        assert quality == 0.0


class TestMethodALow:
    def test_poor_low_detected(self):
        bars = _make_session_bars_poor_low()
        is_poor, quality = _method_a_detect_low(bars, 90.0, 0.25)
        assert is_poor is True
        assert quality > 0.5

    def test_good_low_not_detected(self):
        bars = _make_session_bars_good_low()
        is_poor, quality = _method_a_detect_low(bars, 90.0, 0.25)
        assert is_poor is False
        assert quality < 0.5

    def test_empty_bars(self):
        bars = _make_bars([])
        is_poor, quality = _method_a_detect_low(bars, 90.0, 0.25)
        assert is_poor is False
        assert quality == 0.0


# ── Method B Tests ─────────────────────────────────────────

class TestMethodBHigh:
    def test_poor_high_single_period(self):
        """Only 1 TPO period touches the high → poor."""
        bars = _make_bars([
            (95.0, 93.0, 94.0, '10:00'),  # Period B
            (95.0, 93.0, 94.0, '10:15'),  # Period B
            (100.0, 98.0, 99.0, '10:30'),  # Period C — only period at high
            (96.0, 94.0, 95.0, '11:00'),  # Period C
            (95.0, 93.0, 94.0, '11:30'),  # Period D
        ])
        is_poor, quality = _method_b_detect_high(bars, 100.0)
        assert is_poor is True
        assert quality > 0.5

    def test_good_high_many_periods(self):
        """4 TPO periods touch the high → excess/tail → not poor."""
        bars = _make_bars([
            (100.0, 98.0, 99.0, '10:00'),  # Period B
            (100.0, 98.5, 99.5, '10:30'),  # Period C
            (100.0, 98.0, 98.5, '11:00'),  # Period C
            (99.5, 97.0, 98.0, '11:30'),   # Period D (within 2pts)
            (100.0, 98.0, 99.0, '12:00'),  # Period E
            (95.0, 93.0, 94.0, '13:00'),   # Period G, away
        ])
        is_poor, quality = _method_b_detect_high(bars, 100.0)
        assert is_poor is False
        assert quality < 0.5

    def test_borderline_two_periods(self):
        """Exactly 2 periods touching → still poor (threshold is <=2)."""
        bars = _make_bars([
            (100.0, 98.0, 99.0, '10:00'),  # Period B
            (100.0, 98.0, 99.0, '10:30'),  # Period C
            (95.0, 93.0, 94.0, '11:00'),   # Period C, away
            (95.0, 93.0, 94.0, '11:30'),   # Period D, away
        ])
        is_poor, quality = _method_b_detect_high(bars, 100.0)
        assert is_poor is True

    def test_three_periods_not_poor(self):
        """Exactly 3 periods touching → not poor."""
        bars = _make_bars([
            (100.0, 98.0, 99.0, '10:00'),  # Period B
            (100.0, 98.0, 99.0, '10:30'),  # Period C
            (99.0, 97.0, 98.0, '11:00'),   # Period C (within 2pts of 100)
            (99.5, 97.0, 98.0, '11:30'),   # Period D (within 2pts of 100)
            (95.0, 93.0, 94.0, '12:00'),   # Period E, away
        ])
        is_poor, quality = _method_b_detect_high(bars, 100.0)
        assert is_poor is False


class TestMethodBLow:
    def test_poor_low_single_period(self):
        """Only 1 TPO period touches the low → poor."""
        bars = _make_bars([
            (97.0, 95.0, 96.0, '10:00'),  # Period B
            (90.0, 88.0, 89.0, '10:30'),  # Period C — only period at low
            (95.0, 93.0, 94.0, '11:00'),  # Period C
            (96.0, 94.0, 95.0, '11:30'),  # Period D
        ])
        is_poor, quality = _method_b_detect_low(bars, 88.0)
        assert is_poor is True
        assert quality > 0.5

    def test_good_low_many_periods(self):
        """Multiple periods at the low → not poor."""
        bars = _make_bars([
            (90.0, 88.0, 89.0, '10:00'),  # Period B
            (90.0, 88.0, 89.5, '10:30'),  # Period C
            (89.5, 88.0, 89.0, '11:00'),  # Period C
            (89.0, 88.0, 88.5, '11:30'),  # Period D
            (95.0, 93.0, 94.0, '12:00'),  # Period E, away
        ])
        is_poor, quality = _method_b_detect_low(bars, 88.0)
        assert is_poor is False


# ── TPO Period Mapping ─────────────────────────────────────

class TestTPOPeriodMapping:
    def test_a_period(self):
        assert _get_tpo_period(_time(9, 30)) == 'A'
        assert _get_tpo_period(_time(9, 45)) == 'A'

    def test_b_period(self):
        assert _get_tpo_period(_time(10, 0)) == 'B'
        assert _get_tpo_period(_time(10, 15)) == 'B'

    def test_c_period(self):
        assert _get_tpo_period(_time(10, 30)) == 'C'

    def test_pre_market(self):
        assert _get_tpo_period(_time(9, 0)) == '?'

    def test_none(self):
        assert _get_tpo_period(None) == '?'


# ── Combined Detection Tests ──────────────────────────────

class TestCombinedDetection:
    def test_poor_high_combined(self):
        bars = _make_session_bars_poor_high()
        result = detect_poor_extremes(bars)
        assert result['poor_high'] is True
        assert result['session_high'] == 100.0
        assert result['high_quality_score'] > 0.0
        # At least one method flagged it
        assert result['method_a_high'] or result['method_b_high']

    def test_good_high_combined(self):
        bars = _make_session_bars_good_high()
        result = detect_poor_extremes(bars)
        # Good high: Method A should NOT flag, Method B depends on period count
        assert result['method_a_high'] is False

    def test_poor_low_combined(self):
        bars = _make_session_bars_poor_low()
        result = detect_poor_extremes(bars)
        assert result['poor_low'] is True
        assert result['session_low'] == 90.0
        assert result['low_quality_score'] > 0.0
        assert result['method_a_low'] or result['method_b_low']

    def test_good_low_combined(self):
        bars = _make_session_bars_good_low()
        result = detect_poor_extremes(bars)
        assert result['method_a_low'] is False

    def test_empty_dataframe(self):
        bars = _make_bars([])
        result = detect_poor_extremes(bars)
        assert result['poor_high'] is False
        assert result['poor_low'] is False
        assert np.isnan(result['session_high'])
        assert np.isnan(result['session_low'])

    def test_both_poor(self):
        """Session with both poor high and poor low."""
        bars = _make_bars([
            # Poor high area: close at top
            (100.0, 98.0, 99.8, '10:00'),
            # Middle bars
            (96.0, 94.0, 95.0, '11:00'),
            # Poor low area: close at bottom
            (92.0, 90.0, 90.2, '12:00'),
        ])
        result = detect_poor_extremes(bars)
        assert result['poor_high'] is True
        assert result['poor_low'] is True

    def test_neither_poor(self):
        """Session with good rejection at both extremes + multi-period activity."""
        bars = _make_bars([
            # Good high: strong rejection wicks across multiple periods
            (100.0, 96.0, 96.5, '10:00'),  # Period B, close near low
            (100.0, 96.0, 96.8, '10:30'),  # Period C
            (99.5, 96.0, 96.5, '11:00'),   # Period C
            (99.0, 96.0, 96.5, '11:30'),   # Period D (within 2pts)
            # Middle
            (96.0, 94.0, 95.0, '12:00'),   # Period E
            # Good low: strong rejection wicks across multiple periods
            (94.0, 90.0, 93.5, '12:30'),   # Period F, close near high
            (94.0, 90.0, 93.8, '13:00'),   # Period G
            (94.0, 90.5, 93.5, '13:30'),   # Period H (within 2pts)
            (94.0, 91.0, 93.5, '14:00'),   # Period I (within 2pts)
        ])
        result = detect_poor_extremes(bars)
        assert result['method_a_high'] is False
        assert result['method_a_low'] is False


# ── Quality Score Tests ────────────────────────────────────

class TestQualityScores:
    def test_poor_high_quality_in_range(self):
        bars = _make_session_bars_poor_high()
        result = detect_poor_extremes(bars)
        assert 0.0 <= result['high_quality_score'] <= 1.0

    def test_poor_low_quality_in_range(self):
        bars = _make_session_bars_poor_low()
        result = detect_poor_extremes(bars)
        assert 0.0 <= result['low_quality_score'] <= 1.0

    def test_non_poor_quality_is_zero(self):
        """When not poor, quality should be 0."""
        bars = _make_bars([
            # Good high and good low with many periods touching
            (100.0, 96.0, 96.5, '10:00'),
            (100.0, 96.0, 96.8, '10:30'),
            (99.5, 96.0, 96.5, '11:00'),
            (99.0, 96.0, 96.5, '11:30'),
            (96.0, 94.0, 95.0, '12:00'),
            (94.0, 90.0, 93.5, '12:30'),
            (94.0, 90.0, 93.8, '13:00'),
            (94.0, 90.5, 93.5, '13:30'),
            (94.0, 91.0, 93.5, '14:00'),
        ])
        result = detect_poor_extremes(bars)
        if not result['poor_high']:
            assert result['high_quality_score'] == 0.0
        if not result['poor_low']:
            assert result['low_quality_score'] == 0.0

    def test_extreme_poor_high_quality(self):
        """Bar closes exactly at its high → maximum poorness."""
        bars = _make_bars([
            (100.0, 98.0, 100.0, '11:00'),  # close = high, pos = 1.0
        ])
        result = detect_poor_extremes(bars)
        assert result['poor_high'] is True
        assert result['high_quality_score'] > 0.3  # Should be meaningfully high


# ── Multi-Session (compute_prior_poor_extremes) ───────────

class TestComputePriorPoorExtremes:
    def test_basic_two_sessions(self):
        """Prior session has poor high → maps to next session."""
        df = pd.DataFrame({
            'session_date': ['2026-01-05'] * 3 + ['2026-01-06'] * 3,
            'high': [100.0, 98.0, 95.0, 97.0, 95.0, 93.0],
            'low': [98.0, 96.0, 93.0, 95.0, 93.0, 91.0],
            'close': [99.8, 97.0, 94.0, 96.0, 94.0, 92.0],
            'timestamp': [
                '11:00', '12:00', '13:00',
                '10:00', '11:00', '12:00',
            ],
        })
        result = compute_prior_poor_extremes(df)
        # Result should have entry for 2026-01-06 (containing 2026-01-05 analysis)
        assert '2026-01-06' in result
        assert '2026-01-05' not in result  # First session has no prior
        # Session 2026-01-05 has a bar closing at 99.8 out of (98,100) → poor high
        assert result['2026-01-06']['poor_high'] is True

    def test_no_date_column_raises(self):
        df = pd.DataFrame({'high': [1], 'low': [0], 'close': [0.5]})
        with pytest.raises(ValueError, match="session_date"):
            compute_prior_poor_extremes(df)

    def test_single_session_returns_empty(self):
        df = pd.DataFrame({
            'session_date': ['2026-01-05'] * 3,
            'high': [100.0, 98.0, 95.0],
            'low': [98.0, 96.0, 93.0],
            'close': [99.0, 97.0, 94.0],
            'timestamp': ['10:00', '11:00', '12:00'],
        })
        result = compute_prior_poor_extremes(df)
        assert len(result) == 0

    def test_three_sessions_chain(self):
        """Verify mapping across 3 sessions."""
        df = pd.DataFrame({
            'session_date': (
                ['2026-01-05'] * 2
                + ['2026-01-06'] * 2
                + ['2026-01-07'] * 2
            ),
            'high': [100.0, 95.0, 98.0, 95.0, 97.0, 94.0],
            'low': [98.0, 93.0, 95.0, 93.0, 94.0, 92.0],
            'close': [99.8, 94.0, 96.0, 94.0, 95.0, 93.0],
            'timestamp': [
                '11:00', '12:00',
                '11:00', '12:00',
                '11:00', '12:00',
            ],
        })
        result = compute_prior_poor_extremes(df)
        assert '2026-01-06' in result
        assert '2026-01-07' in result
        assert '2026-01-05' not in result


# ── Tick Size Tests ────────────────────────────────────────

class TestTickSize:
    def test_larger_tick_size_widens_proximity(self):
        """With larger tick size, more bars are considered near the extreme."""
        bars = _make_bars([
            (100.0, 98.0, 99.8, '11:00'),
            (99.0, 97.0, 98.8, '11:30'),  # 1pt from high
            (95.0, 93.0, 94.0, '12:00'),
        ])
        # With tick_size=0.25, proximity = 0.5pts → bar at 99.0 is NOT near 100
        result_small = detect_poor_extremes(bars, tick_size=0.25)
        # With tick_size=1.0, proximity = 2pts → bar at 99.0 IS near 100
        result_large = detect_poor_extremes(bars, tick_size=1.0)
        # Both should detect poor high (the 100 bar itself), but large tick
        # should consider more bars
        assert result_small['poor_high'] is True
        assert result_large['poor_high'] is True
