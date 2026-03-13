"""
Tests for the self-learning feedback loop:
  - session_reviews table persistence
  - TradeReviewer LLM post-trade analysis
  - Observation auto-persistence from reviews
"""

import json
import uuid
from unittest.mock import MagicMock

import pytest

from rockit_core.research.db import (
    connect,
    persist_observation,
    persist_session_review,
    query,
)
from rockit_core.research.schema import TABLES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    c = connect(":memory:")
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Phase A: session_reviews table
# ---------------------------------------------------------------------------

class TestSessionReviewsSchema:
    """Verify session_reviews DDL is in the schema."""

    def test_session_reviews_in_tables(self):
        assert "session_reviews" in TABLES

    def test_session_reviews_ddl_has_key_columns(self):
        ddl = TABLES["session_reviews"]
        for col in ("review_id", "session_date", "reviewer", "user_notes",
                     "signals_fired", "trades_taken", "net_pnl", "alignment_json"):
            assert col in ddl

    def test_table_created(self, conn):
        rows = query(conn, "SELECT COUNT(*) FROM session_reviews")
        assert rows[0][0] == 0


class TestPersistSessionReview:
    """Test persist_session_review() function."""

    def test_basic_insert(self, conn):
        review_id = persist_session_review(conn, {
            "review_id": "rev_test_001",
            "session_date": "2026-03-10",
            "instrument": "NQ",
            "reviewer": "human",
            "user_notes": "Strong IB break, held longs all day",
            "signals_fired": 5,
            "signals_filtered": 2,
            "trades_taken": 3,
            "net_pnl": 1500.0,
            "day_type": "trend_up",
            "bias": "Bullish",
            "ib_range": 45.5,
        })
        assert review_id == "rev_test_001"
        rows = query(conn, "SELECT * FROM session_reviews WHERE review_id = ?", ["rev_test_001"])
        assert len(rows) == 1

    def test_auto_generated_id(self, conn):
        review_id = persist_session_review(conn, {
            "session_date": "2026-03-10",
            "reviewer": "system",
        })
        assert review_id.startswith("rev_")
        rows = query(conn, "SELECT * FROM session_reviews WHERE review_id = ?", [review_id])
        assert len(rows) == 1

    def test_upsert_replaces(self, conn):
        persist_session_review(conn, {
            "review_id": "rev_upsert",
            "session_date": "2026-03-10",
            "reviewer": "human",
            "net_pnl": 500.0,
        })
        persist_session_review(conn, {
            "review_id": "rev_upsert",
            "session_date": "2026-03-10",
            "reviewer": "human",
            "net_pnl": 1500.0,
        })
        rows = query(conn, "SELECT net_pnl FROM session_reviews WHERE review_id = ?", ["rev_upsert"])
        assert len(rows) == 1
        assert rows[0][0] == 1500.0

    def test_alignment_json(self, conn):
        alignment = {
            "aligned": ["IB break", "Bullish bias"],
            "system_gap": ["SMT divergence"],
            "user_gap": ["OR Acceptance signal"],
            "disagreement": [],
        }
        persist_session_review(conn, {
            "review_id": "rev_align",
            "session_date": "2026-03-10",
            "reviewer": "human",
            "alignment": alignment,
        })
        rows = query(conn, "SELECT alignment_json FROM session_reviews WHERE review_id = ?", ["rev_align"])
        parsed = json.loads(rows[0][0])
        assert parsed["aligned"] == ["IB break", "Bullish bias"]
        assert parsed["system_gap"] == ["SMT divergence"]

    def test_null_optional_fields(self, conn):
        persist_session_review(conn, {
            "review_id": "rev_minimal",
            "session_date": "2026-03-10",
            "reviewer": "system",
        })
        rows = query(conn, "SELECT user_notes, ib_range FROM session_reviews WHERE review_id = ?", ["rev_minimal"])
        assert rows[0][0] is None
        assert rows[0][1] is None

    def test_multiple_sessions(self, conn):
        for date in ("2026-03-10", "2026-03-11", "2026-03-12"):
            persist_session_review(conn, {
                "review_id": f"rev_{date}",
                "session_date": date,
                "reviewer": "system",
                "net_pnl": 100.0,
            })
        rows = query(conn, "SELECT COUNT(*) FROM session_reviews")
        assert rows[0][0] == 3


class TestObservationFromReview:
    """Test that review-generated observations persist correctly."""

    def test_human_review_observation(self, conn):
        persist_observation(conn, {
            "obs_id": "hr_20260310_abc123",
            "scope": "session",
            "strategy": "OR_Reversal",
            "session_date": "2026-03-10",
            "observation": "OR Rev set up perfectly but I missed it — was watching ES",
            "evidence": "User session review notes",
            "source": "human_review",
            "confidence": 0.7,
        })
        rows = query(conn, "SELECT * FROM observations WHERE source = 'human_review'")
        assert len(rows) == 1

    def test_system_review_observation(self, conn):
        persist_observation(conn, {
            "obs_id": "sr_20260310_xyz789",
            "scope": "session",
            "strategy": None,
            "session_date": "2026-03-10",
            "observation": "All 3 trades aligned with session bias — 100% WR when aligned",
            "evidence": "System session review analysis",
            "source": "system_review",
            "confidence": 0.6,
        })
        rows = query(conn, "SELECT * FROM observations WHERE source = 'system_review'")
        assert len(rows) == 1

    def test_meta_review_observation(self, conn):
        persist_observation(conn, {
            "obs_id": "meta_abc12345",
            "scope": "portfolio",
            "strategy": "80P_Rule",
            "observation": "80P LONG above POC consistently loses across 50+ sessions",
            "evidence": "Meta-review of accumulated observations and agent performance",
            "source": "meta_review",
            "confidence": 0.85,
        })
        rows = query(conn, "SELECT * FROM observations WHERE source = 'meta_review'")
        assert len(rows) == 1

    def test_observations_visible_to_historical_query(self, conn):
        """Observations from all sources should be queryable (feeds into _query_historical)."""
        for source in ("human_review", "system_review", "meta_review", "llm_trade_review"):
            persist_observation(conn, {
                "obs_id": f"test_{source}_{uuid.uuid4().hex[:6]}",
                "scope": "portfolio",
                "strategy": "OR_Reversal",
                "observation": f"Test observation from {source}",
                "source": source,
                "confidence": 0.5,
            })

        # This mirrors the query in _query_historical()
        rows = query(
            conn,
            """
            SELECT observation, evidence, confidence
            FROM observations
            WHERE strategy = ? OR scope = 'portfolio'
            ORDER BY created_at DESC LIMIT 5
            """,
            ["OR_Reversal"],
        )
        assert len(rows) == 4


# ---------------------------------------------------------------------------
# Phase B: TradeReviewer
# ---------------------------------------------------------------------------

class TestTradeReviewer:
    """Test TradeReviewer LLM-powered post-trade analysis."""

    def setup_method(self):
        self.mock_client = MagicMock()
        self.mock_client.is_available.return_value = True

        from rockit_core.agents.trade_reviewer import TradeReviewer
        self.reviewer = TradeReviewer(self.mock_client)

        self.sample_trade = {
            "trade_id": "t_0001",
            "strategy_name": "OR_Reversal",
            "direction": "LONG",
            "entry_price": 21050.0,
            "exit_price": 21100.0,
            "stop_price": 21000.0,
            "target_price": 21150.0,
            "net_pnl": 500.0,
            "exit_reason": "target",
            "bars_held": 15,
            "day_type": "trend_up",
            "session_date": "2026-03-10",
        }

        self.sample_session = {
            "day_type": "trend_up",
            "bias": "Bullish",
            "ib_range": 45.5,
            "ib_width_class": "normal",
            "trend_strength": "moderate",
            "dpoc_migration": "trending_on_the_move",
        }

    def _mock_response(self, **overrides):
        """Create a mock LLM response."""
        data = {
            "setup_quality": 4,
            "entry_timing": "good",
            "exit_assessment": "optimal",
            "what_worked": "Strong IB break with bias alignment",
            "what_failed": None,
            "lesson": "Bias-aligned OR Rev is the highest-edge setup",
            "observation": "OR Rev with IB break and DPOC trending confirms strong continuation",
            "confidence": 0.85,
        }
        data.update(overrides)
        return {"content": json.dumps(data), "reasoning": "Brief reasoning"}

    def test_review_trade_success(self):
        self.mock_client.chat.return_value = self._mock_response()
        result = self.reviewer.review_trade(self.sample_trade, self.sample_session)

        assert result["setup_quality"] == 4
        assert result["entry_timing"] == "good"
        assert result["exit_assessment"] == "optimal"
        assert result["what_worked"] is not None
        assert result["confidence"] == 0.85

    def test_review_trade_llm_error(self):
        self.mock_client.chat.return_value = {"content": "", "error": "Timeout after 180s"}
        result = self.reviewer.review_trade(self.sample_trade)

        assert "error" in result

    def test_review_trade_invalid_json(self):
        self.mock_client.chat.return_value = {"content": "not json at all"}
        result = self.reviewer.review_trade(self.sample_trade)

        assert "error" in result

    def test_setup_quality_clamped(self):
        self.mock_client.chat.return_value = self._mock_response(setup_quality=10)
        result = self.reviewer.review_trade(self.sample_trade)
        assert result["setup_quality"] == 5

    def test_setup_quality_clamped_low(self):
        self.mock_client.chat.return_value = self._mock_response(setup_quality=-1)
        result = self.reviewer.review_trade(self.sample_trade)
        assert result["setup_quality"] == 1

    def test_confidence_clamped(self):
        self.mock_client.chat.return_value = self._mock_response(confidence=1.5)
        result = self.reviewer.review_trade(self.sample_trade)
        assert result["confidence"] == 1.0

    def test_invalid_entry_timing_normalized(self):
        self.mock_client.chat.return_value = self._mock_response(entry_timing="invalid_value")
        result = self.reviewer.review_trade(self.sample_trade)
        assert result["entry_timing"] == "good"

    def test_invalid_exit_assessment_normalized(self):
        self.mock_client.chat.return_value = self._mock_response(exit_assessment="unknown")
        result = self.reviewer.review_trade(self.sample_trade)
        assert result["exit_assessment"] == "optimal"

    def test_prompt_includes_trade_details(self):
        self.mock_client.chat.return_value = self._mock_response()
        self.reviewer.review_trade(self.sample_trade, self.sample_session)

        # Verify the prompt sent to LLM contains trade info
        call_args = self.mock_client.chat.call_args
        user_prompt = call_args[0][1]  # Second positional arg
        prompt_data = json.loads(user_prompt)

        assert prompt_data["trade"]["strategy"] == "OR_Reversal"
        assert prompt_data["trade"]["direction"] == "LONG"
        assert prompt_data["trade"]["outcome"] == "WIN"
        assert prompt_data["session_context"]["bias"] == "Bullish"

    def test_markdown_code_fence_stripped(self):
        """LLM sometimes wraps JSON in ```json ... ``` — should still parse."""
        data = {
            "setup_quality": 3, "entry_timing": "late", "exit_assessment": "left_money",
            "what_worked": None, "what_failed": "Late entry", "lesson": "Enter earlier",
            "observation": "Late entries reduce edge", "confidence": 0.6,
        }
        self.mock_client.chat.return_value = {
            "content": f"```json\n{json.dumps(data)}\n```"
        }
        result = self.reviewer.review_trade(self.sample_trade)
        assert result["setup_quality"] == 3
        assert result["entry_timing"] == "late"


class TestTradeReviewerPersistence:
    """Test review_and_persist() writes to DuckDB."""

    def setup_method(self):
        self.mock_client = MagicMock()
        from rockit_core.agents.trade_reviewer import TradeReviewer
        self.reviewer = TradeReviewer(self.mock_client)

    def _mock_response(self):
        return {
            "content": json.dumps({
                "setup_quality": 4,
                "entry_timing": "good",
                "exit_assessment": "optimal",
                "what_worked": "Bias alignment",
                "what_failed": None,
                "lesson": "Aligned trades are the best",
                "observation": "OR Rev + Bullish bias = high edge",
                "confidence": 0.8,
            })
        }

    def test_persists_assessment(self):
        conn = connect(":memory:")
        self.mock_client.chat.return_value = self._mock_response()

        trade = {
            "trade_id": "t_persist_001",
            "strategy_name": "OR_Reversal",
            "direction": "LONG",
            "net_pnl": 500.0,
            "session_date": "2026-03-10",
        }

        result = self.reviewer.review_and_persist(trade, "run_001", conn=conn)
        assert "error" not in result

        rows = query(conn, "SELECT * FROM trade_assessments WHERE trade_id = ?", ["t_persist_001"])
        assert len(rows) == 1
        conn.close()

    def test_persists_observation(self):
        conn = connect(":memory:")
        self.mock_client.chat.return_value = self._mock_response()

        trade = {
            "trade_id": "t_obs_001",
            "strategy_name": "OR_Reversal",
            "direction": "LONG",
            "net_pnl": 500.0,
            "session_date": "2026-03-10",
        }

        self.reviewer.review_and_persist(trade, "run_001", conn=conn)

        rows = query(conn, "SELECT * FROM observations WHERE source = 'llm_trade_review'")
        assert len(rows) == 1
        conn.close()

    def test_no_persist_on_error(self):
        conn = connect(":memory:")
        self.mock_client.chat.return_value = {"content": "", "error": "Timeout"}

        trade = {
            "trade_id": "t_err_001",
            "strategy_name": "OR_Reversal",
            "net_pnl": -200.0,
            "session_date": "2026-03-10",
        }

        result = self.reviewer.review_and_persist(trade, "run_001", conn=conn)
        assert "error" in result

        rows = query(conn, "SELECT COUNT(*) FROM trade_assessments")
        assert rows[0][0] == 0
        conn.close()

    def test_no_persist_without_conn(self):
        self.mock_client.chat.return_value = self._mock_response()

        trade = {
            "trade_id": "t_noconn",
            "strategy_name": "OR_Reversal",
            "net_pnl": 500.0,
            "session_date": "2026-03-10",
        }

        # Should succeed without error (just skip persistence)
        result = self.reviewer.review_and_persist(trade, "run_001", conn=None)
        assert "error" not in result
