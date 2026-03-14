"""Tests for all 8 domain experts + ConflictDetector + pipeline integration."""

import pytest

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert
from rockit_core.agents.experts.ict import IctExpert
from rockit_core.agents.experts.scalper import ScalperExpert
from rockit_core.agents.experts.order_flow import OrderFlowExpert
from rockit_core.agents.experts.divergence import DivergenceExpert
from rockit_core.agents.experts.mean_reversion import MeanReversionExpert
from rockit_core.agents.experts.conflict import ConflictDetector, ConflictPair


# ── IctExpert tests ──


class TestIctExpert:
    def _ctx(self, signal_dir="LONG", fvg_bull=False, fvg_bear=False, in_bpr=False,
             fvg_bull_15m=False, fvg_bear_15m=False, snapshot=None):
        bar = {"fvg_bull": fvg_bull, "fvg_bear": fvg_bear, "in_bpr": in_bpr,
               "fvg_bull_15m": fvg_bull_15m, "fvg_bear_15m": fvg_bear_15m}
        tape_row = {}
        if snapshot:
            tape_row["snapshot_json"] = snapshot
        return {"signal": {"direction": signal_dir}, "bar": bar, "session_context": {}, "tape_row": tape_row}

    def test_domain_name(self):
        assert IctExpert().domain == "ict"
        assert IctExpert().name == "expert_ict"

    def test_fvg_bull_long(self):
        cards = IctExpert().scorecard(self._ctx(fvg_bull=True))
        fvg_cards = [c for c in cards if c.card_id == "ict_fvg_support"]
        assert len(fvg_cards) == 1
        assert fvg_cards[0].direction == "bullish"
        assert fvg_cards[0].strength == 0.65

    def test_fvg_bear_short(self):
        cards = IctExpert().scorecard(self._ctx(signal_dir="SHORT", fvg_bear=True))
        fvg_cards = [c for c in cards if c.card_id == "ict_fvg_support"]
        assert fvg_cards[0].direction == "bearish"

    def test_fvg_bull_short_warns(self):
        cards = IctExpert().scorecard(self._ctx(signal_dir="SHORT", fvg_bull=True))
        fvg_cards = [c for c in cards if c.card_id == "ict_fvg_support"]
        assert fvg_cards[0].direction == "bullish"
        assert fvg_cards[0].strength == 0.4

    def test_bpr_zone(self):
        cards = IctExpert().scorecard(self._ctx(in_bpr=True))
        bpr_cards = [c for c in cards if c.card_id == "ict_bpr_zone"]
        assert len(bpr_cards) == 1
        assert bpr_cards[0].direction == "neutral"

    def test_htf_fvg_bull_15m_long(self):
        cards = IctExpert().scorecard(self._ctx(fvg_bull_15m=True))
        htf_cards = [c for c in cards if c.card_id == "ict_htf_fvg"]
        assert len(htf_cards) == 1
        assert htf_cards[0].direction == "bullish"
        assert htf_cards[0].strength == 0.7

    def test_htf_fvg_bear_15m_short(self):
        cards = IctExpert().scorecard(self._ctx(signal_dir="SHORT", fvg_bear_15m=True))
        htf_cards = [c for c in cards if c.card_id == "ict_htf_fvg"]
        assert htf_cards[0].direction == "bearish"

    def test_gap_status_ndog_unfilled(self):
        snapshot = {"fvg_detection": {"ndog": {
            "status": "unfilled", "direction": "gap_down", "fill_pct": 0.1, "gap_type": "NDOG"
        }}}
        cards = IctExpert().scorecard(self._ctx(snapshot=snapshot))
        gap_cards = [c for c in cards if c.card_id == "ict_gap_status"]
        assert len(gap_cards) == 1
        assert gap_cards[0].direction == "bullish"

    def test_no_data_returns_empty(self):
        cards = IctExpert().scorecard(self._ctx())
        assert len(cards) == 0

    def test_source_is_expert_ict(self):
        cards = IctExpert().scorecard(self._ctx(fvg_bull=True))
        assert all(c.source == "expert_ict" for c in cards)


# ── ScalperExpert tests ──


class TestScalperExpert:
    def _ctx(self, signal_dir="LONG", rsi=None, adx=None, volume_spike=None):
        bar = {}
        if rsi is not None: bar["rsi14"] = rsi
        if adx is not None: bar["adx14"] = adx
        if volume_spike is not None: bar["volume_spike"] = volume_spike
        return {"signal": {"direction": signal_dir}, "bar": bar, "session_context": {}}

    def test_domain_name(self):
        assert ScalperExpert().domain == "scalper"

    def test_bullish_momentum_long(self):
        cards = ScalperExpert().scorecard(self._ctx(rsi=62))
        mom_cards = [c for c in cards if c.card_id == "scalper_momentum"]
        assert len(mom_cards) == 1
        assert mom_cards[0].direction == "bullish"

    def test_bearish_momentum_short(self):
        cards = ScalperExpert().scorecard(self._ctx(signal_dir="SHORT", rsi=38))
        mom_cards = [c for c in cards if c.card_id == "scalper_momentum"]
        assert mom_cards[0].direction == "bearish"

    def test_adx_boost(self):
        cards_no_adx = ScalperExpert().scorecard(self._ctx(rsi=62))
        cards_with_adx = ScalperExpert().scorecard(self._ctx(rsi=62, adx=30))
        mom_no = [c for c in cards_no_adx if c.card_id == "scalper_momentum"][0]
        mom_yes = [c for c in cards_with_adx if c.card_id == "scalper_momentum"][0]
        assert mom_yes.strength > mom_no.strength

    def test_overbought_exhaustion(self):
        cards = ScalperExpert().scorecard(self._ctx(rsi=80))
        exh_cards = [c for c in cards if c.card_id == "scalper_exhaustion"]
        assert len(exh_cards) == 1
        assert exh_cards[0].direction == "bearish"

    def test_oversold_exhaustion(self):
        cards = ScalperExpert().scorecard(self._ctx(signal_dir="SHORT", rsi=20))
        exh_cards = [c for c in cards if c.card_id == "scalper_exhaustion"]
        assert exh_cards[0].direction == "bullish"

    def test_volume_spike(self):
        cards = ScalperExpert().scorecard(self._ctx(volume_spike=3.5))
        vol_cards = [c for c in cards if c.card_id == "scalper_volume_spike"]
        assert len(vol_cards) == 1
        assert vol_cards[0].direction == "neutral"

    def test_no_volume_spike_below_threshold(self):
        cards = ScalperExpert().scorecard(self._ctx(volume_spike=1.5))
        vol_cards = [c for c in cards if c.card_id == "scalper_volume_spike"]
        assert len(vol_cards) == 0

    def test_no_data_returns_empty(self):
        cards = ScalperExpert().scorecard(self._ctx())
        assert len(cards) == 0


# ── OrderFlowExpert tests ──


class TestOrderFlowExpert:
    def _ctx(self, signal_dir="LONG", cvd=None, cvd_ma=None, cvd_div_bull=False,
             cvd_div_bear=False, delta_zscore=None):
        bar = {}
        if cvd is not None: bar["cumulative_delta"] = cvd
        if cvd_ma is not None: bar["cumulative_delta_ma"] = cvd_ma
        if cvd_div_bull: bar["cvd_div_bull"] = True
        if cvd_div_bear: bar["cvd_div_bear"] = True
        if delta_zscore is not None: bar["delta_zscore"] = delta_zscore
        return {"signal": {"direction": signal_dir}, "bar": bar, "session_context": {}}

    def test_domain_name(self):
        assert OrderFlowExpert().domain == "order_flow"

    def test_cvd_bullish_long(self):
        cards = OrderFlowExpert().scorecard(self._ctx(cvd=5000))
        cvd_cards = [c for c in cards if c.card_id == "flow_cvd_trend"]
        assert len(cvd_cards) == 1
        assert cvd_cards[0].direction == "bullish"
        assert cvd_cards[0].strength == 0.7

    def test_cvd_bearish_short(self):
        cards = OrderFlowExpert().scorecard(self._ctx(signal_dir="SHORT", cvd=-5000))
        cvd_cards = [c for c in cards if c.card_id == "flow_cvd_trend"]
        assert cvd_cards[0].direction == "bearish"

    def test_cvd_vs_ma(self):
        # CVD > CVD_MA = bullish
        cards = OrderFlowExpert().scorecard(self._ctx(cvd=3000, cvd_ma=2000))
        cvd_cards = [c for c in cards if c.card_id == "flow_cvd_trend"]
        assert cvd_cards[0].direction == "bullish"

    def test_bullish_divergence_long(self):
        cards = OrderFlowExpert().scorecard(self._ctx(cvd_div_bull=True))
        div_cards = [c for c in cards if c.card_id == "flow_cvd_divergence"]
        assert len(div_cards) == 1
        assert div_cards[0].direction == "bullish"
        assert div_cards[0].strength == 0.7

    def test_bearish_divergence_short(self):
        cards = OrderFlowExpert().scorecard(self._ctx(signal_dir="SHORT", cvd_div_bear=True))
        div_cards = [c for c in cards if c.card_id == "flow_cvd_divergence"]
        assert div_cards[0].direction == "bearish"

    def test_extreme_buying_delta(self):
        cards = OrderFlowExpert().scorecard(self._ctx(delta_zscore=2.5))
        imb_cards = [c for c in cards if c.card_id == "flow_delta_imbalance"]
        assert len(imb_cards) == 1
        assert imb_cards[0].direction == "bullish"

    def test_extreme_selling_delta(self):
        cards = OrderFlowExpert().scorecard(self._ctx(signal_dir="SHORT", delta_zscore=-2.5))
        imb_cards = [c for c in cards if c.card_id == "flow_delta_imbalance"]
        assert imb_cards[0].direction == "bearish"

    def test_normal_delta_no_card(self):
        cards = OrderFlowExpert().scorecard(self._ctx(delta_zscore=1.0))
        imb_cards = [c for c in cards if c.card_id == "flow_delta_imbalance"]
        assert len(imb_cards) == 0


# ── DivergenceExpert tests ──


class TestDivergenceExpert:
    def _ctx(self, signal_dir="LONG", smt=None, compression=False):
        snapshot = {"premarket": {}}
        if smt:
            snapshot["premarket"]["smt_preopen_signal"] = smt
        if compression:
            snapshot["premarket"]["compression_flag"] = True
        return {
            "signal": {"direction": signal_dir},
            "tape_row": {"snapshot_json": snapshot},
            "session_context": {},
        }

    def test_domain_name(self):
        assert DivergenceExpert().domain == "divergence"

    def test_bullish_smt_long(self):
        cards = DivergenceExpert().scorecard(self._ctx(smt={"type": "bullish", "description": "NQ holds while ES drops"}))
        smt_cards = [c for c in cards if c.card_id == "divergence_smt"]
        assert len(smt_cards) == 1
        assert smt_cards[0].direction == "bullish"

    def test_bearish_smt_short(self):
        cards = DivergenceExpert().scorecard(self._ctx(signal_dir="SHORT", smt={"type": "bearish", "description": "NQ fails while ES holds"}))
        smt_cards = [c for c in cards if c.card_id == "divergence_smt"]
        assert smt_cards[0].direction == "bearish"

    def test_smt_string_format(self):
        cards = DivergenceExpert().scorecard(self._ctx(smt="bullish"))
        smt_cards = [c for c in cards if c.card_id == "divergence_smt"]
        assert len(smt_cards) == 1

    def test_smt_none_type(self):
        cards = DivergenceExpert().scorecard(self._ctx(smt={"type": "none"}))
        smt_cards = [c for c in cards if c.card_id == "divergence_smt"]
        assert len(smt_cards) == 0

    def test_compression_card(self):
        cards = DivergenceExpert().scorecard(self._ctx(compression=True))
        comp_cards = [c for c in cards if c.card_id == "divergence_compression"]
        assert len(comp_cards) == 1
        assert comp_cards[0].direction == "neutral"

    def test_no_data_returns_empty(self):
        cards = DivergenceExpert().scorecard(self._ctx())
        assert len(cards) == 0


# ── MeanReversionExpert tests ──


class TestMeanReversionExpert:
    def _ctx(self, signal_dir="LONG", price=None, bb_upper=None, bb_lower=None,
             adx=None, vwap_upper_2=None, vwap_lower_2=None):
        bar = {}
        if price is not None: bar["close"] = price
        if bb_upper is not None: bar["bb_upper"] = bb_upper
        if bb_lower is not None: bar["bb_lower"] = bb_lower
        if adx is not None: bar["adx14"] = adx
        if vwap_upper_2 is not None: bar["vwap_sigma_upper_2"] = vwap_upper_2
        if vwap_lower_2 is not None: bar["vwap_sigma_lower_2"] = vwap_lower_2
        return {"signal": {"direction": signal_dir}, "bar": bar, "session_context": {}}

    def test_domain_name(self):
        assert MeanReversionExpert().domain == "mean_reversion"

    def test_bb_upper_extreme_short(self):
        cards = MeanReversionExpert().scorecard(self._ctx(
            signal_dir="SHORT", price=21195, bb_upper=21200, bb_lower=20800
        ))
        bb_cards = [c for c in cards if c.card_id == "mr_bb_position"]
        assert len(bb_cards) == 1
        assert bb_cards[0].direction == "bearish"

    def test_bb_lower_extreme_long(self):
        cards = MeanReversionExpert().scorecard(self._ctx(
            price=20810, bb_upper=21200, bb_lower=20800
        ))
        bb_cards = [c for c in cards if c.card_id == "mr_bb_position"]
        assert bb_cards[0].direction == "bullish"

    def test_bb_mid_no_card(self):
        cards = MeanReversionExpert().scorecard(self._ctx(
            price=21000, bb_upper=21200, bb_lower=20800
        ))
        bb_cards = [c for c in cards if c.card_id == "mr_bb_position"]
        assert len(bb_cards) == 0

    def test_adx_range_bound(self):
        cards = MeanReversionExpert().scorecard(self._ctx(adx=15))
        regime_cards = [c for c in cards if c.card_id == "mr_regime"]
        assert len(regime_cards) == 1
        assert "range-bound" in regime_cards[0].observation

    def test_adx_trending(self):
        cards = MeanReversionExpert().scorecard(self._ctx(adx=35))
        regime_cards = [c for c in cards if c.card_id == "mr_regime"]
        assert "trending" in regime_cards[0].observation

    def test_adx_moderate_no_card(self):
        cards = MeanReversionExpert().scorecard(self._ctx(adx=25))
        regime_cards = [c for c in cards if c.card_id == "mr_regime"]
        assert len(regime_cards) == 0

    def test_vwap_upper_stretch_short(self):
        cards = MeanReversionExpert().scorecard(self._ctx(
            signal_dir="SHORT", price=21250, vwap_upper_2=21200
        ))
        stretch_cards = [c for c in cards if c.card_id == "mr_vwap_stretch"]
        assert len(stretch_cards) == 1
        assert stretch_cards[0].direction == "bearish"

    def test_vwap_lower_stretch_long(self):
        cards = MeanReversionExpert().scorecard(self._ctx(
            price=20750, vwap_lower_2=20800
        ))
        stretch_cards = [c for c in cards if c.card_id == "mr_vwap_stretch"]
        assert stretch_cards[0].direction == "bullish"

    def test_no_data_returns_empty(self):
        cards = MeanReversionExpert().scorecard(self._ctx())
        assert len(cards) == 0


# ── ConflictDetector tests ──


class TestConflictDetector:
    def _make_card(self, card_id, source, direction, strength):
        return EvidenceCard(
            card_id=card_id, source=source, layer="probabilistic",
            observation=f"{card_id} test", direction=direction, strength=strength,
        )

    def test_detect_simple_conflict(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.65),
        ]
        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(cards)
        assert len(conflicts) == 1
        assert conflicts[0].bull_card.source == "expert_tpo"
        assert conflicts[0].bear_card.source == "expert_vwap"

    def test_no_conflict_same_direction(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("vwap_trend", "expert_vwap", "bullish", 0.65),
        ]
        conflicts = ConflictDetector().detect_conflicts(cards)
        assert len(conflicts) == 0

    def test_no_conflict_same_source(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("tpo_poor", "expert_tpo", "bearish", 0.5),
        ]
        conflicts = ConflictDetector().detect_conflicts(cards)
        assert len(conflicts) == 0

    def test_ignore_weak_cards(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.3),  # Too weak
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.65),
        ]
        conflicts = ConflictDetector().detect_conflicts(cards)
        assert len(conflicts) == 0

    def test_ignore_neutral_cards(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "neutral", 0.7),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.65),
        ]
        conflicts = ConflictDetector().detect_conflicts(cards)
        assert len(conflicts) == 0

    def test_one_conflict_per_domain_pair(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("tpo_va", "expert_tpo", "bullish", 0.6),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.65),
            self._make_card("vwap_mr", "expert_vwap", "bearish", 0.5),
        ]
        conflicts = ConflictDetector().detect_conflicts(cards)
        assert len(conflicts) == 1  # Only one conflict between tpo and vwap

    def test_resolve_by_strength_bull_wins(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.5),
        ]
        resolution = ConflictDetector().resolve_conflicts(cards)
        assert len(resolution) == 1
        assert resolution[0].direction == "bullish"
        assert resolution[0].source == "conflict_resolution"

    def test_resolve_by_strength_bear_wins(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.45),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.7),
        ]
        resolution = ConflictDetector().resolve_conflicts(cards)
        assert len(resolution) == 1
        assert resolution[0].direction == "bearish"

    def test_resolve_equal_strength_neutral(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.6),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.6),
        ]
        resolution = ConflictDetector(min_strength_diff=0.1).resolve_conflicts(cards)
        assert len(resolution) == 1
        assert resolution[0].direction == "neutral"

    def test_no_conflicts_returns_empty(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("vwap_trend", "expert_vwap", "bullish", 0.65),
        ]
        resolution = ConflictDetector().resolve_conflicts(cards)
        assert len(resolution) == 0

    def test_multiple_conflicts_resolved(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("ema_align", "expert_ema", "bullish", 0.65),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.6),
            self._make_card("flow_cvd", "expert_order_flow", "bearish", 0.55),
        ]
        resolution = ConflictDetector().resolve_conflicts(cards)
        # tpo vs vwap, tpo vs order_flow, ema vs vwap, ema vs order_flow
        assert len(resolution) >= 2

    def test_conflict_card_has_metadata(self):
        cards = [
            self._make_card("tpo_shape", "expert_tpo", "bullish", 0.7),
            self._make_card("vwap_trend", "expert_vwap", "bearish", 0.5),
        ]
        resolution = ConflictDetector().resolve_conflicts(cards)
        card = resolution[0]
        assert "bull_domain" in card.raw_data
        assert "bear_domain" in card.raw_data
        assert "resolution_method" in card.raw_data
        assert card.raw_data["resolution_method"] == "strength"


# ── Full pipeline integration tests ──


class TestFullPipelineIntegration:
    def test_default_pipeline_is_legacy(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline()
        assert len(pipeline.observers) == 2
        assert pipeline.conflict_detector is None

    def test_expert_preset_has_9_observers(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline(preset="experts")
        assert len(pipeline.observers) == 9
        domains = [getattr(obs, 'domain', obs.name) for obs in pipeline.observers]
        assert "tpo" in domains
        assert "vwap" in domains
        assert "ema" in domains
        assert "ict" in domains
        assert "scalper" in domains
        assert "order_flow" in domains
        assert "divergence" in domains
        assert "mean_reversion" in domains

    def test_expert_preset_has_conflict_detector(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline(preset="experts")
        assert pipeline.conflict_detector is not None

    def test_full_pipeline_evaluate(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline(preset="experts")
        decision = pipeline.evaluate_signal(
            signal_dict={"direction": "LONG", "strategy_name": "OR Rev", "entry_price": 21050},
            bar={
                "close": 21050, "high": 21060, "low": 21040,
                "vwap": 21000, "ema_20": 21030, "ema_50": 20980,
                "bb_upper": 21200, "bb_lower": 20800,
                "rsi14": 62, "adx14": 28,
                "fvg_bull": True, "fvg_bull_15m": True,
                "cumulative_delta": 5000, "cvd_div_bull": False,
                "volume_spike": 1.2,
            },
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
        # Should have many evidence cards from all experts
        assert len(decision.evidence_cards) >= 5

    def test_pipeline_with_no_bar_data(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline()
        decision = pipeline.evaluate_signal(
            signal_dict={"direction": "SHORT", "strategy_name": "test"},
        )
        assert decision.decision in ("TAKE", "SKIP", "REDUCE_SIZE")

    def test_conflict_detector_disabled(self):
        from rockit_core.agents.pipeline import AgentPipeline
        # Pass False to explicitly disable on expert preset
        pipeline = AgentPipeline(preset="experts", conflict_detector=False)
        assert not pipeline.conflict_detector
        decision = pipeline.evaluate_signal(
            signal_dict={"direction": "LONG", "strategy_name": "test"},
        )
        assert decision.decision in ("TAKE", "SKIP", "REDUCE_SIZE")

    def test_all_experts_are_domain_experts(self):
        from rockit_core.agents.pipeline import AgentPipeline
        pipeline = AgentPipeline(preset="experts")
        for obs in pipeline.observers:
            assert isinstance(obs, DomainExpert) or hasattr(obs, 'evaluate')
