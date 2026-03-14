"""Tests for the domain expert framework: base class, TpoExpert, VwapExpert, EmaExpert."""

import pytest

from rockit_core.agents.base import AgentBase
from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert
from rockit_core.agents.experts.tpo import TpoExpert
from rockit_core.agents.experts.vwap import VwapExpert
from rockit_core.agents.experts.ema import EmaExpert


# ── Base class tests ──


def test_domain_expert_is_agent_base():
    assert issubclass(DomainExpert, AgentBase)


def test_domain_expert_cannot_be_instantiated():
    with pytest.raises(TypeError):
        DomainExpert()


def test_domain_expert_name_defaults_to_domain():
    expert = TpoExpert()
    assert expert.name == "expert_tpo"
    assert expert.domain == "tpo"


def test_evaluate_delegates_to_scorecard():
    expert = TpoExpert()
    context = {
        "signal": {"direction": "LONG"},
        "tape_row": {"tpo_shape": "b_shape"},
        "session_context": {},
    }
    # evaluate() and scorecard() should return same result
    assert expert.evaluate(context) == expert.scorecard(context)


def test_historical_query_default():
    expert = TpoExpert()
    assert expert.historical_query(None, {}) == {}


# ── TpoExpert tests ──


class TestTpoExpert:
    def _ctx(self, signal_dir="LONG", tpo_shape=None, vah=None, val=None, poc=None, price=None, poor_high=False, poor_low=False):
        tape_row = {}
        if tpo_shape:
            tape_row["tpo_shape"] = tpo_shape
        if vah is not None:
            tape_row["current_vah"] = vah
        if val is not None:
            tape_row["current_val"] = val
        if poc is not None:
            tape_row["current_poc"] = poc
        if price is not None:
            tape_row["close"] = price
        if poor_high or poor_low:
            tape_row["snapshot_json"] = {"tpo_profile": {"poor_high": poor_high, "poor_low": poor_low}}
        return {
            "signal": {"direction": signal_dir},
            "tape_row": tape_row,
            "session_context": {},
        }

    def test_b_shape_long_bullish(self):
        cards = TpoExpert().scorecard(self._ctx(tpo_shape="b_shape"))
        shape_cards = [c for c in cards if c.card_id == "tpo_shape"]
        assert len(shape_cards) == 1
        assert shape_cards[0].direction == "bullish"
        assert shape_cards[0].strength == 0.7

    def test_b_shape_short_opposed(self):
        cards = TpoExpert().scorecard(self._ctx(signal_dir="SHORT", tpo_shape="b_shape"))
        shape_cards = [c for c in cards if c.card_id == "tpo_shape"]
        assert shape_cards[0].direction == "bullish"
        assert shape_cards[0].strength == 0.3

    def test_p_shape_short_bearish(self):
        cards = TpoExpert().scorecard(self._ctx(signal_dir="SHORT", tpo_shape="p_shape"))
        shape_cards = [c for c in cards if c.card_id == "tpo_shape"]
        assert shape_cards[0].direction == "bearish"
        assert shape_cards[0].strength == 0.7

    def test_d_shape_neutral(self):
        cards = TpoExpert().scorecard(self._ctx(tpo_shape="d_shape"))
        shape_cards = [c for c in cards if c.card_id == "tpo_shape"]
        assert shape_cards[0].direction == "neutral"
        assert shape_cards[0].strength == 0.5

    def test_va_position_above_vah(self):
        cards = TpoExpert().scorecard(self._ctx(vah=21000, val=20800, price=21050))
        va_cards = [c for c in cards if c.card_id == "tpo_va_position"]
        assert len(va_cards) == 1
        assert va_cards[0].direction == "bullish"

    def test_va_position_below_val(self):
        cards = TpoExpert().scorecard(self._ctx(signal_dir="SHORT", vah=21000, val=20800, price=20750))
        va_cards = [c for c in cards if c.card_id == "tpo_va_position"]
        assert va_cards[0].direction == "bearish"

    def test_va_position_inside(self):
        cards = TpoExpert().scorecard(self._ctx(vah=21000, val=20800, price=20900))
        va_cards = [c for c in cards if c.card_id == "tpo_va_position"]
        assert va_cards[0].direction == "neutral"

    def test_poc_value_play_long(self):
        cards = TpoExpert().scorecard(self._ctx(poc=21000, price=20950))
        poc_cards = [c for c in cards if c.card_id == "tpo_poc_position"]
        assert poc_cards[0].direction == "bullish"
        assert poc_cards[0].strength == 0.65

    def test_poc_chasing_long(self):
        cards = TpoExpert().scorecard(self._ctx(poc=21000, price=21050))
        poc_cards = [c for c in cards if c.card_id == "tpo_poc_position"]
        assert poc_cards[0].direction == "neutral"
        assert poc_cards[0].strength == 0.35

    def test_poor_low_long(self):
        cards = TpoExpert().scorecard(self._ctx(poor_low=True))
        poor_cards = [c for c in cards if c.card_id == "tpo_poor_extremes"]
        assert poor_cards[0].direction == "bullish"

    def test_poor_high_short(self):
        cards = TpoExpert().scorecard(self._ctx(signal_dir="SHORT", poor_high=True))
        poor_cards = [c for c in cards if c.card_id == "tpo_poor_extremes"]
        assert poor_cards[0].direction == "bearish"

    def test_no_data_returns_empty(self):
        cards = TpoExpert().scorecard({"signal": {"direction": "LONG"}, "tape_row": {}, "session_context": {}})
        assert len(cards) == 0

    def test_source_is_expert_tpo(self):
        cards = TpoExpert().scorecard(self._ctx(tpo_shape="b"))
        assert all(c.source == "expert_tpo" for c in cards)

    def test_all_cards_are_evidence_cards(self):
        cards = TpoExpert().scorecard(self._ctx(
            tpo_shape="b_shape", vah=21000, val=20800, poc=20900, price=20850, poor_low=True
        ))
        assert len(cards) == 4
        assert all(isinstance(c, EvidenceCard) for c in cards)


# ── VwapExpert tests ──


class TestVwapExpert:
    def _ctx(self, signal_dir="LONG", price=None, vwap=None, bb_upper=None, bb_lower=None, prev_close=None):
        bar = {}
        if price is not None:
            bar["close"] = price
        if vwap is not None:
            bar["vwap"] = vwap
        if bb_upper is not None:
            bar["bb_upper"] = bb_upper
        if bb_lower is not None:
            bar["bb_lower"] = bb_lower
        if prev_close is not None:
            bar["prev_close"] = prev_close
        return {
            "signal": {"direction": signal_dir},
            "bar": bar,
            "session_context": {},
        }

    def test_above_vwap_long_bullish(self):
        cards = VwapExpert().scorecard(self._ctx(price=21050, vwap=21000))
        trend_cards = [c for c in cards if c.card_id == "vwap_trend"]
        assert len(trend_cards) == 1
        assert trend_cards[0].direction == "bullish"
        assert trend_cards[0].strength >= 0.6

    def test_below_vwap_short_bearish(self):
        cards = VwapExpert().scorecard(self._ctx(signal_dir="SHORT", price=20950, vwap=21000))
        trend_cards = [c for c in cards if c.card_id == "vwap_trend"]
        assert trend_cards[0].direction == "bearish"

    def test_above_vwap_short_warns(self):
        cards = VwapExpert().scorecard(self._ctx(signal_dir="SHORT", price=21050, vwap=21000))
        trend_cards = [c for c in cards if c.card_id == "vwap_trend"]
        assert trend_cards[0].direction == "bullish"
        assert trend_cards[0].strength < 0.5  # Warning, not support

    def test_mean_revert_lower_bb_long(self):
        cards = VwapExpert().scorecard(self._ctx(
            price=20800, vwap=21000, bb_upper=21200, bb_lower=20800
        ))
        mr_cards = [c for c in cards if c.card_id == "vwap_mean_revert"]
        assert len(mr_cards) == 1
        assert mr_cards[0].direction == "bullish"

    def test_mean_revert_upper_bb_short(self):
        cards = VwapExpert().scorecard(self._ctx(
            signal_dir="SHORT", price=21200, vwap=21000, bb_upper=21200, bb_lower=20800
        ))
        mr_cards = [c for c in cards if c.card_id == "vwap_mean_revert"]
        assert mr_cards[0].direction == "bearish"

    def test_no_mean_revert_in_middle(self):
        cards = VwapExpert().scorecard(self._ctx(
            price=21000, vwap=21000, bb_upper=21200, bb_lower=20800
        ))
        mr_cards = [c for c in cards if c.card_id == "vwap_mean_revert"]
        assert len(mr_cards) == 0

    def test_vwap_reclaim_long(self):
        cards = VwapExpert().scorecard(self._ctx(
            price=21010, vwap=21000, prev_close=20990
        ))
        reclaim_cards = [c for c in cards if c.card_id == "vwap_reclaim"]
        assert len(reclaim_cards) == 1
        assert reclaim_cards[0].direction == "bullish"
        assert reclaim_cards[0].strength == 0.7

    def test_vwap_lost_short(self):
        cards = VwapExpert().scorecard(self._ctx(
            signal_dir="SHORT", price=20990, vwap=21000, prev_close=21010
        ))
        reclaim_cards = [c for c in cards if c.card_id == "vwap_reclaim"]
        assert reclaim_cards[0].direction == "bearish"

    def test_no_vwap_returns_empty(self):
        cards = VwapExpert().scorecard({"signal": {"direction": "LONG"}, "bar": {}, "session_context": {}})
        assert len(cards) == 0

    def test_source_is_expert_vwap(self):
        cards = VwapExpert().scorecard(self._ctx(price=21050, vwap=21000))
        assert all(c.source == "expert_vwap" for c in cards)


# ── EmaExpert tests ──


class TestEmaExpert:
    def _ctx(self, signal_dir="LONG", price=None, ema_20=None, ema_50=None, low=None, high=None):
        bar = {}
        if price is not None:
            bar["close"] = price
        if ema_20 is not None:
            bar["ema_20"] = ema_20
        if ema_50 is not None:
            bar["ema_50"] = ema_50
        if low is not None:
            bar["low"] = low
        if high is not None:
            bar["high"] = high
        return {
            "signal": {"direction": signal_dir},
            "bar": bar,
            "session_context": {},
        }

    def test_bullish_stack_long(self):
        cards = EmaExpert().scorecard(self._ctx(price=21100, ema_20=21050, ema_50=21000))
        align_cards = [c for c in cards if c.card_id == "ema_alignment"]
        assert len(align_cards) == 1
        assert align_cards[0].direction == "bullish"
        assert align_cards[0].strength == 0.75

    def test_bearish_stack_short(self):
        cards = EmaExpert().scorecard(self._ctx(signal_dir="SHORT", price=20900, ema_20=20950, ema_50=21000))
        align_cards = [c for c in cards if c.card_id == "ema_alignment"]
        assert align_cards[0].direction == "bearish"
        assert align_cards[0].strength == 0.75

    def test_bullish_stack_short_opposed(self):
        cards = EmaExpert().scorecard(self._ctx(signal_dir="SHORT", price=21100, ema_20=21050, ema_50=21000))
        align_cards = [c for c in cards if c.card_id == "ema_alignment"]
        assert align_cards[0].direction == "bullish"
        assert align_cards[0].strength == 0.3

    def test_mixed_emas_neutral(self):
        cards = EmaExpert().scorecard(self._ctx(price=21025, ema_20=21050, ema_50=21000))
        align_cards = [c for c in cards if c.card_id == "ema_alignment"]
        assert align_cards[0].direction == "neutral"

    def test_dynamic_support_bounce(self):
        # Price bounced off EMA20 from below: low touched, close above
        cards = EmaExpert().scorecard(self._ctx(
            price=21055, ema_20=21050, ema_50=21000, low=21045
        ))
        sr_cards = [c for c in cards if c.card_id == "ema_dynamic_sr"]
        assert len(sr_cards) == 1
        assert sr_cards[0].direction == "bullish"
        assert sr_cards[0].raw_data["type"] == "support"

    def test_dynamic_resistance_rejection(self):
        # Price rejected at EMA20 from above: high touched, close below
        cards = EmaExpert().scorecard(self._ctx(
            signal_dir="SHORT", price=21045, ema_20=21050, ema_50=21000, high=21055
        ))
        sr_cards = [c for c in cards if c.card_id == "ema_dynamic_sr"]
        assert len(sr_cards) == 1
        assert sr_cards[0].direction == "bearish"
        assert sr_cards[0].raw_data["type"] == "resistance"

    def test_no_dynamic_sr_when_far(self):
        # Price far from EMA20 — no card
        cards = EmaExpert().scorecard(self._ctx(price=21200, ema_20=21050, ema_50=21000))
        sr_cards = [c for c in cards if c.card_id == "ema_dynamic_sr"]
        assert len(sr_cards) == 0

    def test_compression_detected(self):
        # EMAs within 10 pts
        cards = EmaExpert().scorecard(self._ctx(price=21055, ema_20=21050, ema_50=21045))
        comp_cards = [c for c in cards if c.card_id == "ema_compression"]
        assert len(comp_cards) == 1
        assert comp_cards[0].direction == "neutral"

    def test_no_compression_when_wide(self):
        cards = EmaExpert().scorecard(self._ctx(price=21100, ema_20=21050, ema_50=21000))
        comp_cards = [c for c in cards if c.card_id == "ema_compression"]
        assert len(comp_cards) == 0

    def test_no_data_returns_empty(self):
        cards = EmaExpert().scorecard({"signal": {"direction": "LONG"}, "bar": {}, "session_context": {}})
        assert len(cards) == 0

    def test_source_is_expert_ema(self):
        cards = EmaExpert().scorecard(self._ctx(price=21100, ema_20=21050, ema_50=21000))
        assert all(c.source == "expert_ema" for c in cards)


# ── Pipeline integration tests ──


class TestPipelineIntegration:
    def test_default_pipeline_uses_legacy_observers(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline()
        # Default = legacy 2-observer pipeline
        assert len(pipeline.observers) == 2
        names = [obs.name for obs in pipeline.observers]
        assert "observer_profile" in names
        assert "observer_momentum" in names
        assert pipeline.conflict_detector is None

    def test_expert_preset_pipeline(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline(preset="experts")
        # Expert preset = 8 domain experts + MomentumObserver = 9
        assert len(pipeline.observers) == 9
        names = [obs.name for obs in pipeline.observers]
        assert "expert_tpo" in names
        assert "observer_momentum" in names
        assert "expert_vwap" in names
        assert "expert_ema" in names
        assert "expert_ict" in names
        assert "expert_scalper" in names
        assert "expert_order_flow" in names
        assert "expert_divergence" in names
        assert "expert_mean_reversion" in names
        assert pipeline.conflict_detector is not None

    def test_legacy_observers_still_work(self):
        from rockit_core.agents.pipeline import AgentPipeline
        from rockit_core.agents.observers.profile import ProfileObserver
        from rockit_core.agents.observers.momentum import MomentumObserver
        pipeline = AgentPipeline(observers=[ProfileObserver(), MomentumObserver()])
        assert len(pipeline.observers) == 2

    def test_mixed_experts_and_observers(self):
        from rockit_core.agents.pipeline import AgentPipeline
        from rockit_core.agents.observers.momentum import MomentumObserver
        pipeline = AgentPipeline(observers=[TpoExpert(), MomentumObserver(), VwapExpert()])
        assert len(pipeline.observers) == 3

    def test_evaluate_signal_with_experts(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline()
        decision = pipeline.evaluate_signal(
            signal_dict={"direction": "LONG", "strategy_name": "OR Rev", "entry_price": 21050},
            bar={"close": 21050, "high": 21060, "low": 21040,
                 "vwap": 21000, "ema_20": 21030, "ema_50": 20980,
                 "bb_upper": 21200, "bb_lower": 20800},
            session_context={
                "tpo_shape": "b_shape",
                "current_vah": 21050, "current_val": 20900,
                "current_poc": 20950,
                "dpoc_migration": "trending_up",
                "trend_strength": "strong_bull",
                "session_bias": "Bullish",
            },
        )
        assert decision.decision in ("TAKE", "SKIP", "REDUCE_SIZE")
        assert len(decision.evidence_cards) > 0

    def test_evaluate_signal_empty_context(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline()
        decision = pipeline.evaluate_signal(
            signal_dict={"direction": "LONG", "strategy_name": "test"},
        )
        # Should still work (gate card at minimum)
        assert decision.decision in ("TAKE", "SKIP", "REDUCE_SIZE")


# ── LLMProvider tests ──


class TestLLMProvider:
    def test_ollama_provider_wraps_client(self):
        from rockit_core.agents.llm_provider import OllamaProvider
        provider = OllamaProvider(base_url="http://localhost:11434/v1")
        assert "ollama" in provider.provider_name
        assert provider.max_context == 128_000
        assert provider.client is not None

    def test_llm_provider_is_abstract(self):
        from rockit_core.agents.llm_provider import LLMProvider
        with pytest.raises(TypeError):
            LLMProvider()
