"""
Tests for single print zone detection.
"""

import pandas as pd
import pytest

from rockit_core.indicators.single_prints import (
    _assign_tpo_period,
    _build_tpo_profile,
    detect_single_print_zones,
    compute_prior_session_single_prints,
)
from datetime import time as _time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bars(entries: list[tuple[str, float, float]]) -> pd.DataFrame:
    """
    Build a minimal session_bars DataFrame.

    entries: list of (timestamp_str, high, low)
    """
    return pd.DataFrame(
        {
            "timestamp": [e[0] for e in entries],
            "high": [e[1] for e in entries],
            "low": [e[2] for e in entries],
            "open": [e[2] for e in entries],
            "close": [e[1] for e in entries],
            "volume": [100] * len(entries),
        }
    )


def _make_multi_session_df(
    sessions: dict[str, list[tuple[str, float, float]]],
) -> pd.DataFrame:
    """Build a multi-session DataFrame with session_date column."""
    frames = []
    for session_date, entries in sessions.items():
        df = _make_bars(entries)
        df["session_date"] = session_date
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# TPO period assignment
# ---------------------------------------------------------------------------

class TestTPOPeriodAssignment:
    def test_period_a(self):
        assert _assign_tpo_period(_time(9, 30)) == "A"
        assert _assign_tpo_period(_time(9, 59)) == "A"

    def test_period_b(self):
        assert _assign_tpo_period(_time(10, 0)) == "B"
        assert _assign_tpo_period(_time(10, 29)) == "B"

    def test_period_m(self):
        assert _assign_tpo_period(_time(15, 30)) == "M"
        assert _assign_tpo_period(_time(15, 59)) == "M"

    def test_outside_rth(self):
        assert _assign_tpo_period(_time(9, 0)) is None
        assert _assign_tpo_period(_time(16, 0)) is None
        assert _assign_tpo_period(_time(8, 0)) is None


# ---------------------------------------------------------------------------
# TPO profile building
# ---------------------------------------------------------------------------

class TestBuildTPOProfile:
    def test_single_bar_single_period(self):
        bars = _make_bars([("2026-03-10 09:31:00", 100.50, 100.00)])
        profile = _build_tpo_profile(bars, tick_size=0.25)
        # All levels from 100.00 to 100.50 should have period A
        assert 100.0 in profile
        assert 100.25 in profile
        assert 100.50 in profile
        assert profile[100.0] == {"A"}

    def test_two_bars_same_period_overlap(self):
        bars = _make_bars([
            ("2026-03-10 09:31:00", 100.50, 100.00),
            ("2026-03-10 09:35:00", 100.75, 100.25),
        ])
        profile = _build_tpo_profile(bars, tick_size=0.25)
        # 100.25 and 100.50 should still only have A (same period)
        assert profile[100.25] == {"A"}
        assert profile[100.50] == {"A"}
        # 100.75 only in second bar
        assert profile[100.75] == {"A"}

    def test_two_periods(self):
        bars = _make_bars([
            ("2026-03-10 09:31:00", 100.50, 100.00),  # A
            ("2026-03-10 10:01:00", 100.50, 100.00),  # B
        ])
        profile = _build_tpo_profile(bars, tick_size=0.25)
        # All levels should have both A and B
        assert profile[100.0] == {"A", "B"}
        assert profile[100.25] == {"A", "B"}
        assert profile[100.50] == {"A", "B"}

    def test_empty_bars(self):
        bars = pd.DataFrame(columns=["timestamp", "high", "low", "open", "close", "volume"])
        profile = _build_tpo_profile(bars, tick_size=0.25)
        assert profile == {}


# ---------------------------------------------------------------------------
# Zone detection
# ---------------------------------------------------------------------------

class TestDetectSinglePrintZones:
    def test_basic_single_print_zone(self):
        """
        Period A trades 100-103, period B trades 106-109.
        Levels 103.25 to 105.75 are untouched — NOT single prints (0 periods).
        But we need a scenario where exactly 1 period passes through quickly.

        Setup: A trades 100-104, B trades 104-108, C only trades 106-108.
        Levels 104.25-105.75 are only in B -> single prints.
        """
        bars = _make_bars([
            # Period A: 100.00 - 104.00
            ("2026-03-10 09:31:00", 102.00, 100.00),
            ("2026-03-10 09:35:00", 104.00, 101.00),
            # Period B: sweeps through 104.00 - 108.00 quickly
            ("2026-03-10 10:01:00", 108.00, 104.00),
            # Period C: only trades 106.00 - 108.00
            ("2026-03-10 10:31:00", 108.00, 106.00),
        ])
        zones = detect_single_print_zones(bars, tick_size=0.25, min_zone_ticks=2)
        # Levels 104.25..105.75 should be single prints (only B)
        assert len(zones) >= 1
        # Find the zone that includes 104.25
        b_only_zone = [z for z in zones if z["low"] <= 104.50 <= z["high"]]
        assert len(b_only_zone) == 1
        assert b_only_zone[0]["period"] == "B"

    def test_min_zone_filter_rejects_small(self):
        """Zones smaller than min_zone_ticks should be excluded."""
        # A trades 100-101, B trades 101.50-103
        # Gap: 101.25 only (1 tick of single print from A's 101.00-101.00 range)
        bars = _make_bars([
            ("2026-03-10 09:31:00", 101.00, 100.00),  # A: 100-101
            ("2026-03-10 10:01:00", 103.00, 101.50),  # B: 101.50-103
        ])
        # With min_zone_ticks=10, small zones should be filtered out
        zones = detect_single_print_zones(bars, tick_size=0.25, min_zone_ticks=10)
        assert len(zones) == 0

    def test_min_zone_filter_accepts_large(self):
        """Zones >= min_zone_ticks should be included."""
        bars = _make_bars([
            # A trades 100-102
            ("2026-03-10 09:31:00", 102.00, 100.00),
            # B sweeps through 100-108 in one bar (fast move up)
            ("2026-03-10 10:01:00", 108.00, 100.00),
            # C trades 106-108
            ("2026-03-10 10:31:00", 108.00, 106.00),
        ])
        # Levels 102.25..105.75 are single prints (only B)
        # That's (105.75 - 102.25) / 0.25 = 14 ticks
        zones = detect_single_print_zones(bars, tick_size=0.25, min_zone_ticks=10)
        assert len(zones) >= 1
        big_zone = [z for z in zones if z["size_ticks"] >= 10]
        assert len(big_zone) >= 1

    def test_zone_location_above_vah(self):
        """Zone midpoint above VAH -> 'above_vah'."""
        bars = _make_bars([
            ("2026-03-10 09:31:00", 102.00, 100.00),  # A
            ("2026-03-10 10:01:00", 110.00, 100.00),  # B sweeps up
            ("2026-03-10 10:31:00", 110.00, 108.00),  # C at top
        ])
        # VA at 100-102ish, single prints around 102.25-107.75
        zones = detect_single_print_zones(
            bars, tick_size=0.25, vah=103.00, val=100.00, min_zone_ticks=5
        )
        above_zones = [z for z in zones if z["location"] == "above_vah"]
        assert len(above_zones) >= 1

    def test_zone_location_below_val(self):
        """Zone midpoint below VAL -> 'below_val'."""
        bars = _make_bars([
            ("2026-03-10 09:31:00", 108.00, 106.00),  # A at top
            ("2026-03-10 10:01:00", 108.00, 100.00),  # B sweeps down
            ("2026-03-10 10:31:00", 102.00, 100.00),  # C at bottom
        ])
        zones = detect_single_print_zones(
            bars, tick_size=0.25, vah=108.00, val=106.00, min_zone_ticks=5
        )
        below_zones = [z for z in zones if z["location"] == "below_val"]
        assert len(below_zones) >= 1

    def test_zone_location_within_va(self):
        """Zone midpoint between VAL and VAH -> 'within_va'."""
        bars = _make_bars([
            ("2026-03-10 09:31:00", 100.50, 100.00),  # A: narrow
            ("2026-03-10 10:01:00", 106.00, 100.00),  # B: sweeps
            ("2026-03-10 10:31:00", 106.00, 105.00),  # C: top
        ])
        zones = detect_single_print_zones(
            bars, tick_size=0.25, vah=108.00, val=98.00, min_zone_ticks=5
        )
        within_zones = [z for z in zones if z["location"] == "within_va"]
        assert len(within_zones) >= 1

    def test_zone_location_unknown_when_no_va(self):
        """Without VAH/VAL, location should be 'unknown'."""
        bars = _make_bars([
            ("2026-03-10 09:31:00", 102.00, 100.00),
            ("2026-03-10 10:01:00", 108.00, 100.00),
            ("2026-03-10 10:31:00", 108.00, 106.00),
        ])
        zones = detect_single_print_zones(bars, tick_size=0.25, min_zone_ticks=5)
        for z in zones:
            assert z["location"] == "unknown"

    def test_no_single_prints_all_double_visited(self):
        """When all levels have 2+ TPO periods, no single prints exist."""
        # A and B both trade the exact same range
        bars = _make_bars([
            ("2026-03-10 09:31:00", 102.00, 100.00),  # A
            ("2026-03-10 10:01:00", 102.00, 100.00),  # B
        ])
        zones = detect_single_print_zones(bars, tick_size=0.25, min_zone_ticks=1)
        assert len(zones) == 0

    def test_contiguous_grouping(self):
        """Adjacent single print levels merge into one zone."""
        # A: 100-100.50, B: 100-105 (fast sweep), C: 104.50-105
        # Levels 100.75..104.25 are only B -> one contiguous zone
        bars = _make_bars([
            ("2026-03-10 09:31:00", 100.50, 100.00),  # A
            ("2026-03-10 10:01:00", 105.00, 100.00),  # B
            ("2026-03-10 10:31:00", 105.00, 104.50),  # C
        ])
        zones = detect_single_print_zones(bars, tick_size=0.25, min_zone_ticks=2)
        # Should be one contiguous zone, not multiple fragmented ones
        b_zones = [z for z in zones if "B" in z["period"]]
        assert len(b_zones) == 1
        assert b_zones[0]["size_ticks"] >= 10  # 100.75 to 104.25 = 14 ticks

    def test_empty_bars_returns_empty(self):
        bars = pd.DataFrame(columns=["timestamp", "high", "low", "open", "close", "volume"])
        zones = detect_single_print_zones(bars, tick_size=0.25)
        assert zones == []

    def test_zone_dict_keys(self):
        """Each zone dict has the required keys."""
        bars = _make_bars([
            ("2026-03-10 09:31:00", 102.00, 100.00),
            ("2026-03-10 10:01:00", 108.00, 100.00),
            ("2026-03-10 10:31:00", 108.00, 106.00),
        ])
        zones = detect_single_print_zones(bars, tick_size=0.25, vah=104.0, val=101.0, min_zone_ticks=5)
        for z in zones:
            assert "high" in z
            assert "low" in z
            assert "size_ticks" in z
            assert "period" in z
            assert "location" in z
            assert isinstance(z["high"], float)
            assert isinstance(z["low"], float)
            assert isinstance(z["size_ticks"], int)


# ---------------------------------------------------------------------------
# Prior session lookup
# ---------------------------------------------------------------------------

class TestComputePriorSessionSinglePrints:
    def test_prior_session_mapping(self):
        """Zones from session 1 should appear under session 2's key."""
        sessions = {
            "2026-03-09": [
                # Session 1: A tight, B sweeps, C tight at top
                ("2026-03-09 09:31:00", 102.00, 100.00),
                ("2026-03-09 10:01:00", 108.00, 100.00),
                ("2026-03-09 10:31:00", 108.00, 106.00),
            ],
            "2026-03-10": [
                ("2026-03-10 09:31:00", 108.00, 100.00),
                ("2026-03-10 10:01:00", 108.00, 100.00),
            ],
        }
        df = _make_multi_session_df(sessions)
        result = compute_prior_session_single_prints(df, tick_size=0.25, min_zone_ticks=5)
        # Session 2026-03-10 should have zones from 2026-03-09
        assert "2026-03-10" in result
        zones = result["2026-03-10"]
        assert len(zones) >= 1

    def test_first_session_has_no_prior(self):
        """The first session should not appear in the result (no prior)."""
        sessions = {
            "2026-03-09": [
                ("2026-03-09 09:31:00", 102.00, 100.00),
                ("2026-03-09 10:01:00", 108.00, 100.00),
                ("2026-03-09 10:31:00", 108.00, 106.00),
            ],
            "2026-03-10": [
                ("2026-03-10 09:31:00", 108.00, 100.00),
                ("2026-03-10 10:01:00", 108.00, 100.00),
            ],
        }
        df = _make_multi_session_df(sessions)
        result = compute_prior_session_single_prints(df, tick_size=0.25, min_zone_ticks=5)
        assert "2026-03-09" not in result

    def test_empty_df(self):
        df = pd.DataFrame(columns=["session_date", "timestamp", "high", "low", "open", "close", "volume"])
        result = compute_prior_session_single_prints(df)
        assert result == {}
