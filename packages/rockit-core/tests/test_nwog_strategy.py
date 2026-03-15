"""
Tests for the NWOG Gap Fill strategy.
"""

from datetime import time as _time

import pandas as pd
import pytest

from rockit_core.strategies.nwog_gap_fill import NWOGGapFill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ib_bars(open_price, count=60, vwap=None, fill_side="below"):
    """Create mock IB bars for testing.

    Args:
        open_price: Opening price of the session (first bar open)
        count: Number of bars (default 60 for IB)
        vwap: VWAP value for all bars
        fill_side: "below" means bars close below CE, "above" means above
    """
    bars = []
    for i in range(count):
        # For "below" fill side, close below open (simulating down gap fill)
        if fill_side == "below":
            close = open_price - 30 - (i * 0.5)
        else:
            close = open_price + 30 + (i * 0.5)

        minute = 30 + i
        hour = 9 + minute // 60
        minute = minute % 60

        bar = {
            "timestamp": pd.Timestamp(f"2025-11-24 {hour:02d}:{minute:02d}:00"),
            "open": open_price,
            "high": max(open_price, close) + 5,
            "low": min(open_price, close) - 5,
            "close": close,
            "volume": 1000,
        }
        if vwap is not None:
            bar["vwap"] = vwap
        bars.append(bar)

    return pd.DataFrame(bars)


def _make_ib_bars_at(open_price, close_at, count=60, vwap=None):
    """Create mock IB bars with bars closing at a specific price level.

    Args:
        open_price: Opening price of session (first bar open)
        close_at: Price where bars close (for acceptance check)
        count: Number of bars (default 60 for IB)
        vwap: VWAP value for all bars
    """
    bars = []
    for i in range(count):
        minute = 30 + i
        hour = 9 + minute // 60
        minute = minute % 60

        close = close_at + (i * 0.1)  # Slight variation

        bar = {
            "timestamp": pd.Timestamp(f"2025-11-24 {hour:02d}:{minute:02d}:00"),
            "open": open_price if i == 0 else close - 1,
            "high": max(open_price, close) + 5,
            "low": min(open_price, close) - 5,
            "close": close,
            "volume": 1000,
        }
        if vwap is not None:
            bar["vwap"] = vwap
        bars.append(bar)

    return pd.DataFrame(bars)


def _make_bar(close, timestamp, vwap=None):
    data = {
        "timestamp": pd.Timestamp(timestamp),
        "open": close - 1,
        "high": close + 5,
        "low": close - 5,
        "close": close,
        "volume": 500,
    }
    if vwap is not None:
        data["vwap"] = vwap
    return pd.Series(data)


def _monday_context(prior_close, ib_bars, **kwargs):
    """Build session context for a Monday session."""
    ctx = {
        "prior_close": prior_close,
        "ib_bars": ib_bars,
        "ib_high": float(ib_bars["high"].max()),
        "ib_low": float(ib_bars["low"].min()),
        "ib_range": float(ib_bars["high"].max() - ib_bars["low"].min()),
        "ib_mid": float((ib_bars["high"].max() + ib_bars["low"].min()) / 2),
        "day_type": "neutral",
        "bar_time": _time(10, 30),
    }
    ctx.update(kwargs)
    return ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNWOGGapFill:
    def test_skips_non_monday(self):
        """NWOG should only fire on Mondays."""
        s = NWOGGapFill()
        # Tuesday = 2025-11-25
        ib_bars = _make_ib_bars(21000, vwap=20950, fill_side="below")
        ctx = _monday_context(prior_close=21100, ib_bars=ib_bars)

        s.on_session_start(
            session_date="2025-11-25",  # Tuesday
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )

        bar = _make_bar(20970, "2025-11-25 10:30:00")
        result = s.on_bar(bar, 0, ctx)
        assert result is None

    def test_skips_small_gap(self):
        """NWOG should skip gaps < 20 pts."""
        s = NWOGGapFill()
        # Gap of only 10 pts
        ib_bars = _make_ib_bars(21010, vwap=20990, fill_side="below")
        ctx = _monday_context(prior_close=21000, ib_bars=ib_bars)

        s.on_session_start(
            session_date="2025-11-24",  # Monday
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )

        bar = _make_bar(20970, "2025-11-24 10:30:00")
        result = s.on_bar(bar, 0, ctx)
        assert result is None

    def test_vwap_filter_blocks(self):
        """NWOG should block when VWAP doesn't confirm fill direction."""
        s = NWOGGapFill()
        # UP gap (open 21100, prior close 21000) → fill direction is DOWN
        # VWAP at 20900 (below price) = VWAP NOT on fill side (price should be below VWAP for UP gap)
        # But bars close above CE → fill side is wrong
        ib_bars = _make_ib_bars(21100, vwap=21200, fill_side="above")
        ctx = _monday_context(prior_close=21000, ib_bars=ib_bars)

        s.on_session_start(
            session_date="2025-11-24",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )

        bar = _make_bar(21150, "2025-11-24 10:30:00")
        result = s.on_bar(bar, 0, ctx)
        assert result is None

    def test_emits_signal_on_qualified_monday_down_gap(self):
        """NWOG should emit LONG on a qualified DOWN gap Monday."""
        s = NWOGGapFill()
        # DOWN gap: open 20900, prior close 21000 → gap = -100 pts
        # CE = (20900 + 21000) / 2 = 20950
        # For DOWN gap fill UP: bars should close ABOVE CE (20950)
        # VWAP should be below price (price above VWAP for DOWN gap = fill side)
        # Use close_at=20960 so bars are above CE (20950)
        ib_bars = _make_ib_bars_at(20900, close_at=20960, vwap=20940)
        ctx = _monday_context(prior_close=21000, ib_bars=ib_bars)

        s.on_session_start(
            session_date="2025-11-24",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )

        bar = _make_bar(20960, "2025-11-24 10:30:00", vwap=20940)
        ctx["bar_time"] = _time(10, 30)
        result = s.on_bar(bar, 0, ctx)

        assert result is not None
        assert result.direction == "LONG"
        assert result.strategy_name == "NWOG Gap Fill"
        assert result.target_price == 21000.0  # Friday close
        assert result.metadata["gap_direction"] == "DOWN"

    def test_emits_signal_on_qualified_monday_up_gap(self):
        """NWOG should emit SHORT on a qualified UP gap Monday."""
        s = NWOGGapFill()
        # UP gap: open 21100, prior close 21000 → gap = +100 pts
        # CE = (21100 + 21000) / 2 = 21050
        # For UP gap fill DOWN: bars should close BELOW CE (21050)
        # VWAP should be above price (price below VWAP for UP gap = fill side)
        # Use close_at=21030 so bars are below CE (21050)
        ib_bars = _make_ib_bars_at(21100, close_at=21030, vwap=21060)
        ctx = _monday_context(prior_close=21000, ib_bars=ib_bars)

        s.on_session_start(
            session_date="2025-11-24",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )

        bar = _make_bar(21030, "2025-11-24 10:30:00", vwap=21060)
        ctx["bar_time"] = _time(10, 30)
        result = s.on_bar(bar, 0, ctx)

        assert result is not None
        assert result.direction == "SHORT"
        assert result.target_price == 21000.0  # Friday close
        assert result.metadata["gap_direction"] == "UP"

    def test_only_emits_once(self):
        """Should only emit one signal per session."""
        s = NWOGGapFill()
        ib_bars = _make_ib_bars_at(21100, close_at=21030, vwap=21060)
        ctx = _monday_context(prior_close=21000, ib_bars=ib_bars)

        s.on_session_start(
            session_date="2025-11-24",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )

        bar = _make_bar(21030, "2025-11-24 10:30:00", vwap=21060)
        ctx["bar_time"] = _time(10, 30)
        result1 = s.on_bar(bar, 0, ctx)
        result2 = s.on_bar(bar, 1, ctx)

        assert result1 is not None
        assert result2 is None

    def test_name(self):
        s = NWOGGapFill()
        assert s.name == "NWOG Gap Fill"

    def test_applicable_day_types_all(self):
        s = NWOGGapFill()
        assert s.applicable_day_types == []  # Empty = all

    def test_metadata_contains_gap_info(self):
        """Signal metadata should contain gap analysis details."""
        s = NWOGGapFill()
        ib_bars = _make_ib_bars_at(21100, close_at=21030, vwap=21060)
        ctx = _monday_context(prior_close=21000, ib_bars=ib_bars)

        s.on_session_start(
            session_date="2025-11-24",
            ib_high=ctx["ib_high"],
            ib_low=ctx["ib_low"],
            ib_range=ctx["ib_range"],
            session_context=ctx,
        )

        bar = _make_bar(21030, "2025-11-24 10:30:00", vwap=21060)
        ctx["bar_time"] = _time(10, 30)
        result = s.on_bar(bar, 0, ctx)

        assert result is not None
        meta = result.metadata
        assert "gap_size" in meta
        assert meta["gap_size"] == 100.0
        assert "ce_level" in meta
        assert meta["ce_level"] == 21050.0
        assert "acceptance_pct" in meta
        assert "friday_close" in meta
        assert meta["friday_close"] == 21000.0
