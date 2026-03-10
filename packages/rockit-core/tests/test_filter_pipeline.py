"""
Tests for the configurable filter pipeline (bias, day_type_gate, anti_chase).
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml

from rockit_core.filters.anti_chase_filter import AntiChaseFilter
from rockit_core.filters.bias_filter import BiasAlignmentFilter
from rockit_core.filters.composite import CompositeFilter
from rockit_core.filters.day_type_gate_filter import DayTypeGateFilter
from rockit_core.filters.pipeline import build_filter_pipeline
from rockit_core.strategies.signal import Signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(direction="LONG", strategy_name="Test", day_type="neutral"):
    return Signal(
        timestamp=pd.Timestamp("2025-11-21 10:30:00"),
        direction=direction,
        entry_price=21000.0,
        stop_price=20900.0,
        target_price=21200.0,
        strategy_name=strategy_name,
        setup_type="TEST",
        day_type=day_type,
    )


def _make_bar():
    return pd.Series({"close": 21000.0, "high": 21050.0, "low": 20950.0, "vwap": 21000.0})


# ---------------------------------------------------------------------------
# BiasAlignmentFilter tests
# ---------------------------------------------------------------------------

class TestBiasAlignmentFilter:
    def test_blocks_counter_long(self):
        f = BiasAlignmentFilter(neutral_passes=True)
        sig = _make_signal(direction="LONG")
        ctx = {"session_bias": "Bearish"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_blocks_counter_short(self):
        f = BiasAlignmentFilter(neutral_passes=True)
        sig = _make_signal(direction="SHORT")
        ctx = {"session_bias": "Bullish"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_allows_aligned_long(self):
        f = BiasAlignmentFilter(neutral_passes=True)
        sig = _make_signal(direction="LONG")
        ctx = {"session_bias": "Bullish"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_allows_aligned_short(self):
        f = BiasAlignmentFilter(neutral_passes=True)
        sig = _make_signal(direction="SHORT")
        ctx = {"session_bias": "Bearish"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_neutral_passes(self):
        f = BiasAlignmentFilter(neutral_passes=True)
        sig = _make_signal(direction="LONG")
        ctx = {"session_bias": "NEUTRAL"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_neutral_blocks_when_configured(self):
        f = BiasAlignmentFilter(neutral_passes=False)
        sig = _make_signal(direction="LONG")
        ctx = {"session_bias": "Flat"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_missing_bias_passes(self):
        f = BiasAlignmentFilter(neutral_passes=True)
        sig = _make_signal(direction="LONG")
        ctx = {}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_very_bullish_blocks_short(self):
        f = BiasAlignmentFilter(neutral_passes=True)
        sig = _make_signal(direction="SHORT")
        ctx = {"session_bias": "Very Bullish"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_name(self):
        f = BiasAlignmentFilter()
        assert f.name == "BiasAlignment"


# ---------------------------------------------------------------------------
# DayTypeGateFilter tests
# ---------------------------------------------------------------------------

class TestDayTypeGateFilter:
    def test_blocks_configured_day_type(self):
        rules = [{"strategy": "B-Day", "blocked_day_types": ["trend_down", "trend_up"]}]
        f = DayTypeGateFilter(rules=rules)
        sig = _make_signal(strategy_name="B-Day")
        ctx = {"day_type": "trend_down"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_allows_non_blocked_day_type(self):
        rules = [{"strategy": "B-Day", "blocked_day_types": ["trend_down", "trend_up"]}]
        f = DayTypeGateFilter(rules=rules)
        sig = _make_signal(strategy_name="B-Day")
        ctx = {"day_type": "neutral"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_unmatched_strategy_passes(self):
        rules = [{"strategy": "B-Day", "blocked_day_types": ["trend_down"]}]
        f = DayTypeGateFilter(rules=rules)
        sig = _make_signal(strategy_name="Opening Range Rev")
        ctx = {"day_type": "trend_down"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_case_insensitive_day_type(self):
        rules = [{"strategy": "80P Rule", "blocked_day_types": ["Neutral Range"]}]
        f = DayTypeGateFilter(rules=rules)
        sig = _make_signal(strategy_name="80P Rule")
        ctx = {"day_type": "neutral range"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_empty_rules(self):
        f = DayTypeGateFilter(rules=[])
        sig = _make_signal()
        ctx = {"day_type": "trend_down"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_name(self):
        f = DayTypeGateFilter(rules=[])
        assert f.name == "DayTypeGate"


# ---------------------------------------------------------------------------
# AntiChaseFilter tests
# ---------------------------------------------------------------------------

class TestAntiChaseFilter:
    def test_blocks_long_on_bullish(self):
        rules = [{"strategy": "80P Rule",
                   "block_long_when_bias": ["Bullish", "BULL"],
                   "block_short_when_bias": ["Bearish", "BEAR"]}]
        f = AntiChaseFilter(rules=rules)
        sig = _make_signal(direction="LONG", strategy_name="80P Rule")
        ctx = {"session_bias": "Bullish"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_blocks_short_on_bearish(self):
        rules = [{"strategy": "80P Rule",
                   "block_long_when_bias": ["Bullish"],
                   "block_short_when_bias": ["Bearish"]}]
        f = AntiChaseFilter(rules=rules)
        sig = _make_signal(direction="SHORT", strategy_name="80P Rule")
        ctx = {"session_bias": "Bearish"}
        assert f.should_trade(sig, _make_bar(), ctx) is False

    def test_allows_long_on_flat(self):
        rules = [{"strategy": "80P Rule",
                   "block_long_when_bias": ["Bullish"]}]
        f = AntiChaseFilter(rules=rules)
        sig = _make_signal(direction="LONG", strategy_name="80P Rule")
        ctx = {"session_bias": "Flat"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_unmatched_strategy_passes(self):
        rules = [{"strategy": "80P Rule",
                   "block_long_when_bias": ["Bullish"]}]
        f = AntiChaseFilter(rules=rules)
        sig = _make_signal(direction="LONG", strategy_name="OR Rev")
        ctx = {"session_bias": "Bullish"}
        assert f.should_trade(sig, _make_bar(), ctx) is True

    def test_name(self):
        f = AntiChaseFilter(rules=[])
        assert f.name == "AntiChase"


# ---------------------------------------------------------------------------
# Pipeline builder tests
# ---------------------------------------------------------------------------

class TestBuildFilterPipeline:
    def test_build_from_yaml(self, tmp_path):
        config = {
            "pipeline": {
                "bias_alignment": {"enabled": True, "neutral_passes": True},
                "day_type_gate": {
                    "enabled": True,
                    "rules": [{"strategy": "B-Day", "blocked_day_types": ["trend_down"]}],
                },
                "anti_chase": {
                    "enabled": True,
                    "rules": [{"strategy": "80P Rule", "block_long_when_bias": ["Bullish"]}],
                },
            }
        }
        config_path = tmp_path / "filters.yaml"
        config_path.write_text(yaml.dump(config))

        pipeline = build_filter_pipeline(str(config_path))
        assert pipeline is not None
        assert "Composite" in pipeline.name
        assert len(pipeline._filters) == 3

    def test_all_disabled_returns_none(self, tmp_path):
        config = {
            "pipeline": {
                "bias_alignment": {"enabled": False},
                "day_type_gate": {"enabled": False},
                "anti_chase": {"enabled": False},
            }
        }
        config_path = tmp_path / "filters.yaml"
        config_path.write_text(yaml.dump(config))

        pipeline = build_filter_pipeline(str(config_path))
        assert pipeline is None

    def test_missing_file_returns_none(self):
        pipeline = build_filter_pipeline("/nonexistent/path.yaml")
        assert pipeline is None

    def test_pipeline_composites_correctly(self, tmp_path):
        config = {
            "pipeline": {
                "bias_alignment": {"enabled": True, "neutral_passes": True},
                "day_type_gate": {
                    "enabled": True,
                    "rules": [{"strategy": "B-Day", "blocked_day_types": ["trend_down"]}],
                },
            }
        }
        config_path = tmp_path / "filters.yaml"
        config_path.write_text(yaml.dump(config))

        pipeline = build_filter_pipeline(str(config_path))

        # B-Day on trend_down should be blocked by day_type_gate
        sig = _make_signal(direction="LONG", strategy_name="B-Day")
        ctx = {"session_bias": "Bullish", "day_type": "trend_down"}
        assert pipeline.should_trade(sig, _make_bar(), ctx) is False

        # B-Day on neutral with aligned bias should pass
        ctx2 = {"session_bias": "Bullish", "day_type": "neutral"}
        assert pipeline.should_trade(sig, _make_bar(), ctx2) is True

    def test_partial_pipeline(self, tmp_path):
        """Only bias_alignment enabled."""
        config = {
            "pipeline": {
                "bias_alignment": {"enabled": True, "neutral_passes": True},
            }
        }
        config_path = tmp_path / "filters.yaml"
        config_path.write_text(yaml.dump(config))

        pipeline = build_filter_pipeline(str(config_path))
        assert pipeline is not None
        assert len(pipeline._filters) == 1
