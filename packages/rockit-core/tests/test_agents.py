"""
Unit tests for the agent framework.

Tests: EvidenceCard, CRIGateAgent, ProfileObserver, MomentumObserver,
       DeterministicOrchestrator, AgentPipeline.
"""

import pytest

from rockit_core.agents.evidence import AgentDecision, ConfluenceResult, EvidenceCard
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.observers.momentum import MomentumObserver
from rockit_core.agents.observers.profile import ProfileObserver
from rockit_core.agents.orchestrator import DeterministicOrchestrator
from rockit_core.agents.pipeline import AgentPipeline


# ---------------------------------------------------------------------------
# EvidenceCard
# ---------------------------------------------------------------------------


class TestEvidenceCard:
    def test_creation(self):
        card = EvidenceCard(
            card_id="test_1",
            source="test",
            layer="certainty",
            observation="Test obs",
            direction="bullish",
            strength=0.8,
        )
        assert card.card_id == "test_1"
        assert card.direction == "bullish"
        assert card.strength == 0.8

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="Invalid direction"):
            EvidenceCard(
                card_id="x", source="x", layer="x",
                observation="x", direction="UP", strength=0.5,
            )

    def test_strength_clamped(self):
        card = EvidenceCard(
            card_id="x", source="x", layer="x",
            observation="x", direction="bullish", strength=1.5,
        )
        assert card.strength == 1.0

        card2 = EvidenceCard(
            card_id="x", source="x", layer="x",
            observation="x", direction="bearish", strength=-0.3,
        )
        assert card2.strength == 0.0


# ---------------------------------------------------------------------------
# CRIGateAgent
# ---------------------------------------------------------------------------


class TestCRIGateAgent:
    def setup_method(self):
        self.gate = CRIGateAgent()

    def test_passes_ready(self):
        ctx = {"tape_row": {"cri_status": "READY"}}
        assert self.gate.passes(ctx) is True
        cards = self.gate.evaluate(ctx)
        assert len(cards) == 1
        assert cards[0].strength == 1.0

    def test_blocks_stand_down(self):
        ctx = {"tape_row": {"cri_status": "STAND_DOWN"}}
        assert self.gate.passes(ctx) is False
        cards = self.gate.evaluate(ctx)
        assert cards[0].strength == 0.0

    def test_missing_data_passes(self):
        ctx = {"tape_row": {}}
        assert self.gate.passes(ctx) is True

    def test_empty_context_passes(self):
        assert self.gate.passes({}) is True

    def test_caution_passes_reduced(self):
        ctx = {"tape_row": {"cri_status": "CAUTION"}}
        assert self.gate.passes(ctx) is True
        cards = self.gate.evaluate(ctx)
        assert cards[0].strength == 0.5


# ---------------------------------------------------------------------------
# ProfileObserver
# ---------------------------------------------------------------------------


class TestProfileObserver:
    def setup_method(self):
        self.obs = ProfileObserver()

    def test_tpo_shape_b_long(self):
        ctx = {
            "tape_row": {"tpo_shape": "b_shape"},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        tpo_card = next((c for c in cards if c.card_id == "profile_tpo_shape"), None)
        assert tpo_card is not None
        assert tpo_card.direction == "bullish"
        assert tpo_card.strength == 0.7

    def test_va_position_above_vah_long(self):
        ctx = {
            "tape_row": {"current_vah": 20000, "current_val": 19900, "close": 20050},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        va_card = next((c for c in cards if c.card_id == "profile_va_position"), None)
        assert va_card is not None
        assert va_card.direction == "bullish"

    def test_poc_value_play_long(self):
        ctx = {
            "tape_row": {"current_poc": 20000, "close": 19950},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        poc_card = next((c for c in cards if c.card_id == "profile_poc_position"), None)
        assert poc_card is not None
        assert poc_card.direction == "bullish"
        assert poc_card.strength == 0.65

    def test_missing_data_skips_cards(self):
        ctx = {
            "tape_row": {},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        # All cards should be None/skipped when data is missing
        assert len(cards) == 0


# ---------------------------------------------------------------------------
# MomentumObserver
# ---------------------------------------------------------------------------


class TestMomentumObserver:
    def setup_method(self):
        self.obs = MomentumObserver()

    def test_dpoc_trending_long(self):
        ctx = {
            "tape_row": {"dpoc_migration": "trending_on_the_move"},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        dpoc_card = next((c for c in cards if c.card_id == "momentum_dpoc_regime"), None)
        assert dpoc_card is not None
        assert dpoc_card.direction == "bullish"
        assert dpoc_card.strength == 0.7

    def test_trend_strong_bull_long(self):
        ctx = {
            "tape_row": {"trend_strength": "strong_bull"},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        trend_card = next((c for c in cards if c.card_id == "momentum_trend_strength"), None)
        assert trend_card is not None
        assert trend_card.direction == "bullish"
        assert trend_card.strength == 0.8

    def test_wick_traps_bear_wicks_long(self):
        ctx = {
            "tape_row": {"snapshot_json": {"wick_parade": {"bear_wick_count": 5, "bull_wick_count": 1}}},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        wick_card = next((c for c in cards if c.card_id == "momentum_wick_traps"), None)
        assert wick_card is not None
        assert wick_card.direction == "bullish"

    def test_extension_overextended(self):
        ctx = {
            "tape_row": {"extension_multiple": 2.5},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        ext_card = next((c for c in cards if c.card_id == "momentum_extension"), None)
        assert ext_card is not None
        assert ext_card.direction == "bearish"  # Warning against LONG
        assert ext_card.strength == 0.3

    def test_bias_bullish_long(self):
        ctx = {
            "tape_row": {"bias": "Bullish"},
            "session_context": {},
            "signal": {"direction": "LONG"},
        }
        cards = self.obs.evaluate(ctx)
        bias_card = next((c for c in cards if c.card_id == "momentum_bias_alignment"), None)
        assert bias_card is not None
        assert bias_card.direction == "bullish"
        assert bias_card.strength == 0.75

    def test_missing_data_returns_empty(self):
        ctx = {"tape_row": {}, "session_context": {}, "signal": {"direction": "LONG"}}
        cards = self.obs.evaluate(ctx)
        assert len(cards) == 0


# ---------------------------------------------------------------------------
# DeterministicOrchestrator
# ---------------------------------------------------------------------------


class TestDeterministicOrchestrator:
    def setup_method(self):
        self.orch = DeterministicOrchestrator()

    def test_take_aligned_evidence(self):
        """Strong bullish evidence + LONG signal → TAKE."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "bullish signal", "bullish", 0.8),
            EvidenceCard("c2", "obs", "certainty", "bullish trend", "bullish", 0.7),
        ]
        decision = self.orch.decide({"direction": "LONG"}, cards, gate_passed=True)
        assert decision.decision == "TAKE"
        assert decision.gate_passed is True

    def test_skip_opposed_evidence(self):
        """Bearish evidence + LONG signal → SKIP."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "bearish", "bearish", 0.8),
            EvidenceCard("c2", "obs", "certainty", "bearish", "bearish", 0.7),
        ]
        decision = self.orch.decide({"direction": "LONG"}, cards, gate_passed=True)
        assert decision.decision == "SKIP"

    def test_skip_weak_conviction(self):
        """Near-equal bull/bear → weak conviction → SKIP."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "bullish", "bullish", 0.5),
            EvidenceCard("c2", "obs", "certainty", "bearish", "bearish", 0.49),
        ]
        decision = self.orch.decide({"direction": "LONG"}, cards, gate_passed=True)
        # Conviction = |0.5 - 0.49| / (0.5 + 0.49) ≈ 0.01 < 0.1 → SKIP
        assert decision.decision == "SKIP"

    def test_gate_blocked_skip(self):
        """Gate blocked → always SKIP."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "STAND_DOWN", "neutral", 0.0),
        ]
        decision = self.orch.decide({"direction": "LONG"}, cards, gate_passed=False)
        assert decision.decision == "SKIP"
        assert decision.confidence == 1.0
        assert decision.gate_passed is False

    def test_confluence_math(self):
        """Verify bull/bear score math."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "bullish", "bullish", 0.8),
            EvidenceCard("c2", "obs", "probabilistic", "bearish", "bearish", 0.5),
        ]
        decision = self.orch.decide({"direction": "LONG"}, cards, gate_passed=True)
        c = decision.confluence
        # Bull: 0.8 * 1.0 = 0.8
        # Bear: 0.5 * 0.8 = 0.4
        assert c.bull_score == pytest.approx(0.8, abs=0.01)
        assert c.bear_score == pytest.approx(0.4, abs=0.01)
        assert c.bull_cards == 1
        assert c.bear_cards == 1

    def test_no_evidence_passthrough(self):
        """Only gate card, no observer evidence → pass-through TAKE."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
        ]
        decision = self.orch.decide({"direction": "LONG"}, cards, gate_passed=True)
        assert decision.decision == "TAKE"
        assert "pass-through" in decision.reasoning.lower()


# ---------------------------------------------------------------------------
# AgentPipeline
# ---------------------------------------------------------------------------


class TestAgentPipeline:
    def test_full_pipeline_take(self):
        """Full pipeline with supportive context → TAKE."""
        pipeline = AgentPipeline()
        session_ctx = {
            "cri_status": "READY",
            "tpo_shape": "b_shape",
            "current_poc": 20000,
            "current_vah": 20050,
            "current_val": 19950,
            "current_price": 19980,
            "session_bias": "Bullish",
            "trend_strength": "strong_bull",
            "dpoc_migration": "trending_on_the_move",
        }
        signal_dict = {"direction": "LONG", "strategy_name": "OR Rev", "entry_price": 19980}

        decision = pipeline.evaluate_signal(signal_dict, session_context=session_ctx)
        assert decision.decision in ("TAKE", "REDUCE_SIZE")
        assert decision.gate_passed is True
        assert len(decision.evidence_cards) > 1

    def test_pipeline_stand_down_skip(self):
        """STAND_DOWN CRI → SKIP regardless of other data."""
        pipeline = AgentPipeline()
        session_ctx = {
            "cri_status": "STAND_DOWN",
            "tpo_shape": "b_shape",
            "session_bias": "Bullish",
        }
        signal_dict = {"direction": "LONG", "strategy_name": "OR Rev"}

        decision = pipeline.evaluate_signal(signal_dict, session_context=session_ctx)
        assert decision.decision == "SKIP"
        assert decision.gate_passed is False

    def test_pipeline_empty_context(self):
        """Empty context → pass-through (don't block on missing data)."""
        pipeline = AgentPipeline()
        decision = pipeline.evaluate_signal(
            {"direction": "LONG", "strategy_name": "Test"}, session_context={}
        )
        assert decision.decision == "TAKE"
        assert "pass-through" in decision.reasoning.lower()


# ---------------------------------------------------------------------------
# AgentDecision serialization
# ---------------------------------------------------------------------------


class TestAgentDecision:
    def test_to_dict(self):
        confluence = ConfluenceResult(
            direction="bullish", conviction=0.7,
            bull_score=1.5, bear_score=0.5,
            bull_cards=2, bear_cards=1,
            total_evidence=4, total_rejected=0,
        )
        decision = AgentDecision(
            decision="TAKE", confidence=0.7, direction="bullish",
            confluence=confluence, reasoning="test",
            gate_passed=True, evidence_cards=[],
        )
        d = decision.to_dict()
        assert d["decision"] == "TAKE"
        assert d["bull_score"] == 1.5
        assert d["conviction"] == 0.7
        assert isinstance(d["evidence_cards"], list)
