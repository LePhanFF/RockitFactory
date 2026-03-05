"""Tests for the tape_context deterministic module."""
import pytest
import pandas as pd
import numpy as np
from datetime import time

from rockit_core.deterministic.modules.tape_context import (
    get_tape_context,
    _get_ib_touch_counter,
    _get_c_period_classification,
    _get_session_open_type,
    _get_va_entry_depth,
    _get_dpoc_retention,
    _cluster_touches,
)


# ── Fixtures ──────────────────────────────────────────────────

def _make_df(bars, start_time="09:30", freq="5min"):
    """Create a test DataFrame from a list of (open, high, low, close, volume) tuples."""
    dates = pd.date_range(
        f"2026-03-04 {start_time}",
        periods=len(bars),
        freq=freq,
    )
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close", "volume"], index=dates)
    df["vwap"] = df["close"]  # simplified
    return df


def _make_ib_data(ib_high=25400, ib_low=25300, ib_status="complete", atr14=185.0):
    """Create a mock ib_data dict."""
    ib_range = ib_high - ib_low
    return {
        "ib_high": ib_high,
        "ib_low": ib_low,
        "ib_range": ib_range,
        "ib_mid": (ib_high + ib_low) / 2,
        "ib_status": ib_status,
        "current_close": 25350.0,
        "atr14": atr14,
    }


def _make_premarket():
    """Create mock premarket data."""
    return {
        "london_high": 25380.0,
        "london_low": 25280.0,
        "asia_high": 25370.0,
        "asia_low": 25260.0,
        "overnight_high": 25390.0,
        "overnight_low": 25250.0,
        "previous_day_high": 25450.0,
        "previous_day_low": 25200.0,
    }


# ── IB Touch Counter Tests ──────────────────────────────────

class TestIBTouchCounter:
    def test_ib_not_complete(self):
        """Returns zeros when IB is not complete."""
        ib_data = _make_ib_data(ib_status="partial")
        df = _make_df([(25350, 25360, 25340, 25355, 100)] * 5)
        result = _get_ib_touch_counter(df, ib_data, time(10, 15))
        assert result["touch_count_ibh"] == 0
        assert result["touch_count_ibl"] == 0

    def test_no_post_ib_data(self):
        """Returns zeros when no data exists after 10:30."""
        ib_data = _make_ib_data()
        df = _make_df([(25350, 25360, 25340, 25355, 100)] * 12, start_time="09:30")
        result = _get_ib_touch_counter(df, ib_data, time(10, 25))
        assert result["touch_count_ibh"] == 0
        assert result["note"] == "No post-IB data yet"

    def test_single_ibh_touch(self):
        """Detects a single touch of IBH."""
        ib_data = _make_ib_data(ib_high=25400, ib_low=25300)
        # Build bars: some at 10:30+ with one bar touching IBH
        bars = []
        # 12 bars from 9:30 to 10:25 (pre-IB)
        for _ in range(12):
            bars.append((25350, 25360, 25340, 25355, 100))
        # 6 bars from 10:30 to 10:55 (post-IB)
        bars.append((25355, 25365, 25350, 25360, 100))
        bars.append((25360, 25375, 25355, 25370, 100))
        bars.append((25370, 25398, 25365, 25390, 100))  # touches IBH (within tolerance)
        bars.append((25390, 25395, 25380, 25385, 100))
        bars.append((25385, 25390, 25375, 25380, 100))
        bars.append((25380, 25385, 25370, 25375, 100))
        df = _make_df(bars, start_time="09:30", freq="5min")
        result = _get_ib_touch_counter(df, ib_data, time(11, 0))
        assert result["touch_count_ibh"] >= 1
        assert result["first_touch_ibh_time"] is not None

    def test_single_ibl_touch(self):
        """Detects a single touch of IBL."""
        ib_data = _make_ib_data(ib_high=25400, ib_low=25300)
        bars = []
        for _ in range(12):
            bars.append((25350, 25360, 25340, 25355, 100))
        # Post-IB bars: one approaches IBL
        bars.append((25340, 25345, 25335, 25338, 100))
        bars.append((25338, 25340, 25302, 25310, 100))  # touches IBL
        bars.append((25310, 25320, 25305, 25315, 100))
        bars.append((25315, 25330, 25310, 25325, 100))
        bars.append((25325, 25340, 25320, 25335, 100))
        bars.append((25335, 25345, 25330, 25340, 100))
        df = _make_df(bars, start_time="09:30", freq="5min")
        result = _get_ib_touch_counter(df, ib_data, time(11, 0))
        assert result["touch_count_ibl"] >= 1
        assert result["first_touch_ibl_time"] is not None


# ── C-Period Classification Tests ────────────────────────────

class TestCPeriodClassification:
    def test_ib_not_complete(self):
        """Returns NA when IB is not complete."""
        ib_data = _make_ib_data(ib_status="partial")
        df = _make_df([(25350, 25360, 25340, 25355, 100)] * 5)
        result = _get_c_period_classification(df, ib_data, time(10, 15))
        assert result["classification"] == "na"

    def test_c_period_developing(self):
        """Shows developing status when C-period is still forming."""
        ib_data = _make_ib_data(ib_high=25400, ib_low=25300)
        # Bars through 10:45 only
        bars = []
        for _ in range(12):  # 9:30-10:25
            bars.append((25350, 25360, 25340, 25355, 100))
        bars.append((25360, 25410, 25355, 25405, 100))  # 10:30 — above IBH
        bars.append((25405, 25415, 25400, 25410, 100))  # 10:35
        bars.append((25410, 25420, 25405, 25415, 100))  # 10:40
        df = _make_df(bars, start_time="09:30", freq="5min")
        result = _get_c_period_classification(df, ib_data, time(10, 45))
        assert result["classification"] == "developing"
        assert result["developing_position"] == "above_ibh"

    def test_c_period_above_ibh(self):
        """Classifies C-period close above IBH."""
        ib_data = _make_ib_data(ib_high=25400, ib_low=25300)
        bars = []
        for _ in range(12):  # 9:30-10:25
            bars.append((25350, 25360, 25340, 25355, 100))
        # C-period bars (10:30-10:55): all above IBH
        for _ in range(6):
            bars.append((25410, 25420, 25405, 25415, 100))
        # After C-period
        bars.append((25415, 25425, 25410, 25420, 100))  # 11:00
        df = _make_df(bars, start_time="09:30", freq="5min")
        result = _get_c_period_classification(df, ib_data, time(11, 5))
        assert result["classification"] == "above_ibh"
        assert result["implication"] == "70-75% continuation UP"
        assert result["c_period_close"] > 25400

    def test_c_period_below_ibl(self):
        """Classifies C-period close below IBL."""
        ib_data = _make_ib_data(ib_high=25400, ib_low=25300)
        bars = []
        for _ in range(12):
            bars.append((25350, 25360, 25340, 25355, 100))
        for _ in range(6):
            bars.append((25290, 25295, 25280, 25285, 100))  # below IBL
        bars.append((25285, 25290, 25280, 25288, 100))
        df = _make_df(bars, start_time="09:30", freq="5min")
        result = _get_c_period_classification(df, ib_data, time(11, 5))
        assert result["classification"] == "below_ibl"
        assert "continuation DOWN" in result["implication"]

    def test_c_period_inside_ib(self):
        """Classifies C-period close inside IB."""
        ib_data = _make_ib_data(ib_high=25400, ib_low=25300)
        bars = []
        for _ in range(12):
            bars.append((25350, 25360, 25340, 25355, 100))
        for _ in range(6):
            bars.append((25345, 25355, 25340, 25350, 100))  # inside IB
        bars.append((25350, 25355, 25345, 25348, 100))
        df = _make_df(bars, start_time="09:30", freq="5min")
        result = _get_c_period_classification(df, ib_data, time(11, 5))
        assert result["classification"] == "inside_ib"
        assert "reversal" in result["implication"]


# ── Session Open Type Tests ──────────────────────────────────

class TestSessionOpenType:
    def test_too_early(self):
        """Returns too_early before 9:45."""
        df = _make_df([(25350, 25360, 25340, 25355, 100)] * 3)
        premarket = _make_premarket()
        result = _get_session_open_type(df, premarket, time(9, 40))
        assert result["classification"] == "too_early"

    def test_rotation_open(self):
        """Rotation when no levels swept or accepted."""
        # Open at 25350, all bars between 25340-25360 (no level breaches)
        bars = [(25350, 25360, 25340, 25355, 100)] * 6
        df = _make_df(bars, start_time="09:30", freq="5min")
        premarket = _make_premarket()
        result = _get_session_open_type(df, premarket, time(10, 0))
        assert result["classification"] == "rotation"

    def test_acceptance_open(self):
        """Acceptance when price opens above a level and stays there."""
        premarket = _make_premarket()  # london_high=25380
        # Price opens ABOVE london_high and never comes back — pure acceptance
        bars = [
            (25385, 25395, 25382, 25390, 100),  # 9:30 — opens above LDN high
            (25390, 25400, 25388, 25395, 100),  # 9:35 — still above
            (25395, 25405, 25392, 25402, 100),  # 9:40 — holding
            (25402, 25410, 25398, 25408, 100),  # 9:45 — still above
            (25408, 25415, 25405, 25412, 100),  # 9:50
            (25412, 25420, 25410, 25418, 100),  # 9:55
        ]
        df = _make_df(bars, start_time="09:30", freq="5min")
        result = _get_session_open_type(df, premarket, time(10, 0))
        assert result["classification"] == "acceptance"
        assert len(result["accepted_levels"]) > 0


# ── VA Entry Depth Tests ─────────────────────────────────────

class TestVAEntryDepth:
    def test_inside_va_from_above(self):
        """Price inside VA, closer to VAH."""
        ib_data = {"current_close": 25180.0}
        vol_profile = {"previous_day": {"vah": 25200.0, "val": 25100.0}}
        result = _get_va_entry_depth(ib_data, vol_profile)
        assert result["depth_pct"] == 20.0  # 20pts from VAH / 100pt width
        assert result["position"] == "inside_from_above"
        assert result["quality"] == "low"  # < 30%

    def test_inside_va_deep(self):
        """Deep inside VA — high quality (study: winners at 45%)."""
        ib_data = {"current_close": 25150.0}
        vol_profile = {"previous_day": {"vah": 25200.0, "val": 25100.0}}
        result = _get_va_entry_depth(ib_data, vol_profile)
        assert result["depth_pct"] == 50.0  # 50pts from VAH / 100pt width
        assert result["quality"] == "high"  # >= 45%

    def test_above_va(self):
        """Price above VA — negative depth."""
        ib_data = {"current_close": 25220.0}
        vol_profile = {"previous_day": {"vah": 25200.0, "val": 25100.0}}
        result = _get_va_entry_depth(ib_data, vol_profile)
        assert result["depth_pct"] < 0
        assert result["position"] == "above_va"
        assert result["quality"] == "outside_va"

    def test_below_va(self):
        """Price below VA — negative depth."""
        ib_data = {"current_close": 25080.0}
        vol_profile = {"previous_day": {"vah": 25200.0, "val": 25100.0}}
        result = _get_va_entry_depth(ib_data, vol_profile)
        assert result["depth_pct"] < 0
        assert result["position"] == "below_va"

    def test_missing_data(self):
        """Handles missing VA data gracefully."""
        ib_data = {"current_close": 25150.0}
        vol_profile = {"previous_day": {}}
        result = _get_va_entry_depth(ib_data, vol_profile)
        assert result["depth_pct"] is None


# ── DPOC Retention Tests ─────────────────────────────────────

class TestDPOCRetention:
    def test_strong_retention(self):
        """High retention = conviction strong."""
        dpoc_data = {
            "relative_retain_percent": 85.0,
            "net_migration_pts": 15.0,
            "dpoc_regime": "trending_on_the_move",
            "prior_exhausted": False,
        }
        result = _get_dpoc_retention(dpoc_data)
        assert result["retention_pct"] == 85.0
        assert result["status"] == "strong"

    def test_exhaustion(self):
        """Low retention = exhaustion."""
        dpoc_data = {
            "relative_retain_percent": 25.0,
            "net_migration_pts": 5.0,
            "dpoc_regime": "balancing_choppy",
            "prior_exhausted": True,
        }
        result = _get_dpoc_retention(dpoc_data)
        assert result["retention_pct"] == 25.0
        assert result["status"] == "exhaustion"

    def test_moderate_retention(self):
        """Mid-range retention."""
        dpoc_data = {
            "relative_retain_percent": 55.0,
            "net_migration_pts": 10.0,
            "dpoc_regime": "trending_fading_momentum",
            "prior_exhausted": False,
        }
        result = _get_dpoc_retention(dpoc_data)
        assert result["status"] == "moderate"

    def test_unavailable(self):
        """Handles missing DPOC data."""
        dpoc_data = {}
        result = _get_dpoc_retention(dpoc_data)
        assert result["status"] == "unavailable"

    def test_prior_exhausted_overrides(self):
        """prior_exhausted flag forces exhaustion status even with decent retention."""
        dpoc_data = {
            "relative_retain_percent": 55.0,
            "net_migration_pts": 10.0,
            "dpoc_regime": "stabilizing_hold forming_floor",
            "prior_exhausted": True,
        }
        result = _get_dpoc_retention(dpoc_data)
        assert result["status"] == "exhaustion"


# ── Cluster Touches Tests ────────────────────────────────────

class TestClusterTouches:
    def test_empty_index(self):
        """Returns empty list for no touches."""
        result = _cluster_touches(pd.DatetimeIndex([]), min_gap_bars=5)
        assert result == []

    def test_single_touch(self):
        """Single touch returns single event."""
        idx = pd.DatetimeIndex(["2026-03-04 10:35:00"])
        result = _cluster_touches(idx, min_gap_bars=5)
        assert len(result) == 1

    def test_consecutive_touches_cluster(self):
        """Consecutive bars touching = one event."""
        idx = pd.DatetimeIndex([
            "2026-03-04 10:35:00",
            "2026-03-04 10:40:00",
            "2026-03-04 10:45:00",
        ])
        result = _cluster_touches(idx, min_gap_bars=5)
        assert len(result) == 1

    def test_two_separate_touch_events(self):
        """Two distinct touch events separated by gap."""
        idx = pd.DatetimeIndex([
            "2026-03-04 10:35:00",
            "2026-03-04 10:40:00",
            # gap
            "2026-03-04 11:10:00",
            "2026-03-04 11:15:00",
        ])
        # With min_gap=2, indices 0,1 are one cluster and 2,3 are another
        result = _cluster_touches(idx, min_gap_bars=2)
        assert len(result) == 2


# ── Integration: get_tape_context ────────────────────────────

class TestGetTapeContext:
    def test_full_integration(self):
        """Full tape context call returns all 5 sections."""
        bars = []
        for _ in range(12):  # 9:30-10:25
            bars.append((25350, 25360, 25340, 25355, 100))
        for _ in range(12):  # 10:30-11:25
            bars.append((25345, 25355, 25340, 25348, 100))
        df = _make_df(bars, start_time="09:30", freq="5min")

        intraday = {
            "ib": _make_ib_data(),
            "dpoc_migration": {
                "relative_retain_percent": 65.0,
                "net_migration_pts": 12.0,
                "dpoc_regime": "trending_fading_momentum",
                "prior_exhausted": False,
            },
            "volume_profile": {
                "previous_day": {"vah": 25200.0, "val": 25100.0},
            },
        }
        premarket = _make_premarket()

        result = get_tape_context(df, intraday, premarket, "11:30")

        assert "ib_touch_counter" in result
        assert "c_period" in result
        assert "session_open_type" in result
        assert "va_entry_depth" in result
        assert "dpoc_retention" in result

    def test_early_session(self):
        """Works for early session (pre-IB) without errors."""
        bars = [(25350, 25360, 25340, 25355, 100)] * 6
        df = _make_df(bars, start_time="09:30", freq="5min")

        intraday = {
            "ib": _make_ib_data(ib_status="partial"),
            "dpoc_migration": {},
            "volume_profile": {"previous_day": {}},
        }
        premarket = _make_premarket()

        result = get_tape_context(df, intraday, premarket, "09:55")

        assert result["ib_touch_counter"]["touch_count_ibh"] == 0
        assert result["c_period"]["classification"] in ("na", "developing")
        assert result["session_open_type"]["classification"] in ("too_early", "rotation", "acceptance", "judas", "both")
