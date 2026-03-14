"""
Unit tests for the agent framework.

Tests: EvidenceCard, CRIGateAgent, ProfileObserver, MomentumObserver,
       DeterministicOrchestrator, AgentPipeline, DebateResult,
       AdvocateAgent, SkepticAgent, debate pipeline.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from rockit_core.agents.debate.advocate import AdvocateAgent
from rockit_core.agents.debate.skeptic import SkepticAgent
from rockit_core.agents.evidence import (
    AgentDecision,
    ConfluenceResult,
    DebateResult,
    EvidenceCard,
)
from rockit_core.agents.gate import CRIGateAgent
from rockit_core.agents.llm_client import OllamaClient
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
        assert cards[0].direction == "neutral"  # CRI scoring disabled — always neutral

    def test_stand_down_passthrough(self):
        """STAND_DOWN is pass-through — CRI scoring disabled."""
        ctx = {"tape_row": {"cri_status": "STAND_DOWN"}}
        assert self.gate.passes(ctx) is True
        cards = self.gate.evaluate(ctx)
        assert cards[0].direction == "neutral"
        assert cards[0].strength == 0.0

    def test_missing_data_passes(self):
        ctx = {"tape_row": {}}
        assert self.gate.passes(ctx) is True

    def test_empty_context_passes(self):
        assert self.gate.passes({}) is True

    def test_caution_passthrough(self):
        """CAUTION produces neutral pass-through (CRI scoring disabled)."""
        ctx = {"tape_row": {"cri_status": "CAUTION"}}
        assert self.gate.passes(ctx) is True
        cards = self.gate.evaluate(ctx)
        assert cards[0].direction == "neutral"
        assert cards[0].strength == 0.0


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

    def test_standdown_passthrough_evidence(self):
        """STAND_DOWN CRI is neutral pass-through — doesn't influence scoring."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "STAND_DOWN (pass-through)", "neutral", 0.0),
            EvidenceCard("c1", "obs", "certainty", "bullish signal", "bullish", 0.8),
        ]
        decision = self.orch.decide({"direction": "LONG"}, cards, gate_passed=True)
        # CRI neutral doesn't affect scoring — bullish signal passes through
        assert decision.decision == "TAKE"
        assert decision.gate_passed is True

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

    def test_pipeline_stand_down_runs_observers(self):
        """STAND_DOWN CRI → observers still run, CRI is soft evidence."""
        pipeline = AgentPipeline()
        session_ctx = {
            "cri_status": "STAND_DOWN",
            "tpo_shape": "b_shape",
            "session_bias": "Bullish",
            "trend_strength": "strong_bull",
            "current_poc": 20000,
            "current_vah": 20050,
            "current_val": 19950,
            "current_price": 19980,
        }
        signal_dict = {"direction": "LONG", "strategy_name": "OR Rev"}

        decision = pipeline.evaluate_signal(signal_dict, session_context=session_ctx)
        # CRI is soft — observers run, more than just gate card
        assert len(decision.evidence_cards) > 1
        assert decision.gate_passed is True

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


# ---------------------------------------------------------------------------
# DebateResult
# ---------------------------------------------------------------------------


class TestDebateResult:
    def test_creation(self):
        result = DebateResult(
            agent="advocate",
            admit=["c1", "c2"],
            reject=["c3"],
            thesis="Bullish case based on IB acceptance",
            direction="bullish",
            confidence=0.75,
        )
        assert result.agent == "advocate"
        assert len(result.admit) == 2
        assert result.confidence == 0.75

    def test_confidence_clamped(self):
        result = DebateResult(agent="skeptic", confidence=1.5)
        assert result.confidence == 1.0

    def test_invalid_direction_defaults_neutral(self):
        result = DebateResult(agent="advocate", direction="UP")
        assert result.direction == "neutral"

    def test_to_dict(self):
        card = EvidenceCard(
            card_id="adv_0", source="debate_advocate", layer="instinct",
            observation="test", direction="bullish", strength=0.6,
        )
        result = DebateResult(
            agent="advocate",
            admit=["c1"],
            reject=["c2"],
            instinct_cards=[card],
            thesis="test thesis",
            direction="bullish",
            confidence=0.7,
            warnings=["overconfidence"],
        )
        d = result.to_dict()
        assert d["agent"] == "advocate"
        assert len(d["instinct_cards"]) == 1
        assert d["warnings"] == ["overconfidence"]


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------


class TestOllamaClient:
    def test_creation(self):
        client = OllamaClient(base_url="http://localhost:11434/v1", model="test")
        assert client.model == "test"
        assert client.timeout == 180

    def test_parse_response_valid(self):
        body = {
            "choices": [{"message": {"content": "hello", "reasoning": "thought"}}],
            "usage": {"total_tokens": 100},
            "model": "test",
        }
        result = OllamaClient._parse_response(body)
        assert result["content"] == "hello"
        assert result["reasoning"] == "thought"

    def test_parse_response_missing_fields(self):
        result = OllamaClient._parse_response({})
        assert result["content"] == ""
        assert "error" in result


# ---------------------------------------------------------------------------
# AdvocateAgent (mocked LLM)
# ---------------------------------------------------------------------------


def _mock_advocate_response() -> dict:
    """Mock a valid Advocate LLM response."""
    return {
        "content": json.dumps({
            "admit": ["profile_tpo_shape", "momentum_bias_alignment"],
            "reject": ["momentum_extension"],
            "instinct_cards": [
                {
                    "observation": "Classic OR Rev setup with IB acceptance confirming",
                    "direction": "bullish",
                    "strength": 0.7,
                    "reasoning": "IB acceptance + b-shape = high probability continuation",
                }
            ],
            "thesis": "Strong bullish case: IB acceptance, b-shape TPO, bias aligned LONG.",
            "direction": "bullish",
            "confidence": 0.75,
            "warnings": ["Late session, momentum may fade"],
        }),
        "reasoning": "think chain here",
        "usage": {"total_tokens": 500},
    }


def _mock_skeptic_response() -> dict:
    """Mock a valid Skeptic LLM response."""
    return {
        "content": json.dumps({
            "admit": ["profile_tpo_shape"],
            "reject": ["momentum_bias_alignment", "momentum_extension"],
            "instinct_cards": [
                {
                    "observation": "Extension is overextended at 2.1x, mean reversion risk",
                    "direction": "bearish",
                    "strength": 0.6,
                    "reasoning": "Historical 2x+ extensions revert 65% of the time",
                }
            ],
            "thesis": "Overextended move with weak late-session momentum. Risk of retrace.",
            "direction": "neutral",
            "confidence": 0.4,
            "warnings": ["Overextension at 2.1x IB", "Late session after 13:00"],
        }),
        "reasoning": "skeptic think chain",
        "usage": {"total_tokens": 450},
    }


class TestAdvocateAgent:
    def setup_method(self):
        self.mock_client = MagicMock(spec=OllamaClient)
        self.advocate = AdvocateAgent(self.mock_client)

    def test_debate_returns_result(self):
        self.mock_client.chat.return_value = _mock_advocate_response()
        context = {
            "evidence_cards": [
                EvidenceCard("c1", "obs", "certainty", "test", "bullish", 0.8),
            ],
            "signal": {"direction": "LONG", "strategy_name": "OR Rev"},
            "session_context": {"day_type": "Trend Up", "session_bias": "Bullish"},
        }
        result = self.advocate.debate(context)
        assert result.agent == "advocate"
        assert result.direction == "bullish"
        assert result.confidence == 0.75
        assert len(result.instinct_cards) == 1
        assert result.instinct_cards[0].source == "debate_advocate"
        assert result.instinct_cards[0].layer == "instinct"

    def test_evaluate_returns_instinct_cards(self):
        self.mock_client.chat.return_value = _mock_advocate_response()
        context = {
            "evidence_cards": [
                EvidenceCard("c1", "obs", "certainty", "test", "bullish", 0.8),
            ],
            "signal": {"direction": "LONG", "strategy_name": "OR Rev"},
            "session_context": {},
        }
        cards = self.advocate.evaluate(context)
        assert len(cards) == 1
        assert cards[0].card_id == "advocate_instinct_0"

    def test_llm_error_returns_empty_result(self):
        self.mock_client.chat.return_value = {"content": "", "error": "timeout"}
        context = {
            "evidence_cards": [],
            "signal": {"direction": "LONG"},
            "session_context": {},
        }
        result = self.advocate.debate(context)
        assert result.agent == "advocate"
        assert len(result.instinct_cards) == 0

    def test_invalid_json_returns_empty_result(self):
        self.mock_client.chat.return_value = {"content": "not json at all"}
        context = {
            "evidence_cards": [],
            "signal": {"direction": "LONG"},
            "session_context": {},
        }
        result = self.advocate.debate(context)
        assert len(result.instinct_cards) == 0


# ---------------------------------------------------------------------------
# SkepticAgent (mocked LLM)
# ---------------------------------------------------------------------------


class TestSkepticAgent:
    def setup_method(self):
        self.mock_client = MagicMock(spec=OllamaClient)
        self.skeptic = SkepticAgent(self.mock_client)

    def test_debate_returns_result(self):
        self.mock_client.chat.return_value = _mock_skeptic_response()
        advocate_result = DebateResult(
            agent="advocate", direction="bullish", confidence=0.75,
            thesis="Strong bullish case",
        )
        context = {
            "evidence_cards": [
                EvidenceCard("c1", "obs", "certainty", "test", "bullish", 0.8),
            ],
            "signal": {"direction": "LONG", "strategy_name": "OR Rev"},
            "session_context": {},
            "advocate_result": advocate_result,
        }
        result = self.skeptic.debate(context)
        assert result.agent == "skeptic"
        assert result.direction == "neutral"
        assert len(result.warnings) == 2
        assert len(result.instinct_cards) == 1
        assert result.instinct_cards[0].source == "debate_skeptic"

    def test_evaluate_returns_counter_evidence(self):
        self.mock_client.chat.return_value = _mock_skeptic_response()
        context = {
            "evidence_cards": [],
            "signal": {"direction": "LONG"},
            "session_context": {},
            "advocate_result": DebateResult(agent="advocate"),
        }
        cards = self.skeptic.evaluate(context)
        assert len(cards) == 1
        assert cards[0].direction == "bearish"


# ---------------------------------------------------------------------------
# Orchestrator.decide_with_debate
# ---------------------------------------------------------------------------


class TestOrchestratorWithDebate:
    def setup_method(self):
        self.orch = DeterministicOrchestrator()

    def test_both_agree_admit(self):
        """Both Advocate and Skeptic admit a card → full weight."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "bullish signal", "bullish", 0.8),
        ]
        adv = DebateResult(agent="advocate", admit=["c1"], reject=[], direction="bullish", confidence=0.8)
        skp = DebateResult(agent="skeptic", admit=["c1"], reject=[], direction="bullish", confidence=0.6)

        decision = self.orch.decide_with_debate(
            {"direction": "LONG"}, cards, True, adv, skp
        )
        # c1 should be admitted at full strength (0.8)
        assert cards[1].admitted is True
        assert cards[1].strength == 0.8

    def test_both_agree_reject(self):
        """Both reject → card excluded from scoring."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "weak signal", "bullish", 0.8),
            EvidenceCard("c2", "obs", "certainty", "strong signal", "bullish", 0.9),
        ]
        adv = DebateResult(agent="advocate", admit=["c2"], reject=["c1"], direction="bullish", confidence=0.7)
        skp = DebateResult(agent="skeptic", admit=["c2"], reject=["c1"], direction="bullish", confidence=0.5)

        decision = self.orch.decide_with_debate(
            {"direction": "LONG"}, cards, True, adv, skp
        )
        assert cards[1].admitted is False  # c1 rejected by both
        assert cards[2].admitted is True   # c2 admitted by both

    def test_disputed_card_reduced_weight(self):
        """Advocate admits, Skeptic rejects → 0.7× weight."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "disputed", "bullish", 1.0),
        ]
        adv = DebateResult(agent="advocate", admit=["c1"], reject=[], direction="bullish", confidence=0.8)
        skp = DebateResult(agent="skeptic", admit=[], reject=["c1"], direction="neutral", confidence=0.4)

        decision = self.orch.decide_with_debate(
            {"direction": "LONG"}, cards, True, adv, skp
        )
        assert cards[1].admitted is True
        assert cards[1].strength == pytest.approx(0.7, abs=0.01)  # 1.0 * 0.7

    def test_standdown_with_debate_flows_through(self):
        """STAND_DOWN with debate → neutral CRI card, doesn't influence scoring."""
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "STAND_DOWN (pass-through)", "neutral", 0.0),
            EvidenceCard("c1", "obs", "certainty", "bullish", "bullish", 0.8),
        ]
        adv = DebateResult(agent="advocate", admit=["c1"], direction="bullish", confidence=0.8)
        skp = DebateResult(agent="skeptic", admit=["c1"], direction="bullish", confidence=0.6)

        decision = self.orch.decide_with_debate(
            {"direction": "LONG"}, cards, True, adv, skp
        )
        # CRI bearish card participates in scoring but doesn't hard-block
        assert decision.decision in ("TAKE", "SKIP", "REDUCE_SIZE")
        assert decision.gate_passed is True

    def test_debate_instinct_cards_admitted(self):
        """Instinct cards from debate agents are always admitted."""
        instinct = EvidenceCard(
            "advocate_instinct_0", "debate_advocate", "instinct",
            "Classic setup", "bullish", 0.7,
        )
        cards = [
            EvidenceCard("gate", "gate_cri", "certainty", "READY", "neutral", 1.0),
            EvidenceCard("c1", "obs", "certainty", "bullish", "bullish", 0.8),
            instinct,
        ]
        adv = DebateResult(agent="advocate", admit=["c1"], instinct_cards=[instinct], direction="bullish", confidence=0.8)
        skp = DebateResult(agent="skeptic", admit=["c1"], direction="bullish", confidence=0.6)

        decision = self.orch.decide_with_debate(
            {"direction": "LONG"}, cards, True, adv, skp
        )
        assert instinct.admitted is True
        assert "Debate:" in decision.reasoning


# ---------------------------------------------------------------------------
# Pipeline with debate (mocked LLM)
# ---------------------------------------------------------------------------


class TestPipelineWithDebate:
    def test_debate_enabled_uses_llm(self):
        """Pipeline with debate enabled runs Advocate + Skeptic."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.chat.side_effect = [
            _mock_advocate_response(),
            _mock_skeptic_response(),
        ]

        pipeline = AgentPipeline(llm_client=mock_client, enable_debate=True)
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
        signal = {"direction": "LONG", "strategy_name": "OR Rev", "entry_price": 19980}

        decision = pipeline.evaluate_signal(signal, session_context=session_ctx)
        assert mock_client.chat.call_count == 2  # Advocate + Skeptic
        assert "Debate:" in decision.reasoning

    def test_debate_fallback_on_error(self):
        """If LLM fails, pipeline falls back to deterministic."""
        mock_client = MagicMock(spec=OllamaClient)
        mock_client.chat.side_effect = Exception("Connection refused")

        pipeline = AgentPipeline(llm_client=mock_client, enable_debate=True)
        session_ctx = {
            "cri_status": "READY",
            "tpo_shape": "b_shape",
            "session_bias": "Bullish",
            "trend_strength": "strong_bull",
            "current_poc": 20000,
            "current_vah": 20050,
            "current_val": 19950,
            "current_price": 19980,
        }
        signal = {"direction": "LONG", "strategy_name": "OR Rev"}

        decision = pipeline.evaluate_signal(signal, session_context=session_ctx)
        # Should still get a decision (deterministic fallback)
        assert decision.decision in ("TAKE", "SKIP", "REDUCE_SIZE")
        assert "Debate:" not in decision.reasoning

    def test_debate_disabled_no_llm_calls(self):
        """Pipeline with debate disabled never calls LLM."""
        mock_client = MagicMock(spec=OllamaClient)
        pipeline = AgentPipeline(llm_client=mock_client, enable_debate=False)

        decision = pipeline.evaluate_signal(
            {"direction": "LONG", "strategy_name": "Test"}, session_context={}
        )
        mock_client.chat.assert_not_called()

    def test_no_client_debate_disabled(self):
        """enable_debate=True but no client → debate stays disabled."""
        pipeline = AgentPipeline(llm_client=None, enable_debate=True)
        assert pipeline.enable_debate is False
