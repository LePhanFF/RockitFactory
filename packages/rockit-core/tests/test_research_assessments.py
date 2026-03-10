"""
Tests for trade assessment and observation persistence in DuckDB.
"""

import pytest

from rockit_core.research.db import (
    connect,
    persist_assessment,
    persist_backtest_run,
    persist_observation,
    persist_trades,
    query,
)


@pytest.fixture
def conn():
    """In-memory DuckDB connection with schema created."""
    c = connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def run_with_trade(conn):
    """Create a backtest run with one trade for assessment tests."""
    run_id = "test_run_001"
    persist_backtest_run(conn, run_id, "NQ", {
        "sessions": 1, "trades": 1, "win_rate": 100.0,
        "profit_factor": 999.0, "net_pnl": 500.0,
        "max_drawdown": 0.0, "avg_win": 500.0, "avg_loss": 0.0,
        "expectancy": 500.0,
    }, ["OR Rev"])
    persist_trades(conn, run_id, [{
        "trade_id": "t001",
        "strategy_name": "Opening Range Rev",
        "direction": "LONG",
        "session_date": "2025-11-21",
        "entry_price": 21000.0,
        "exit_price": 21100.0,
        "stop_price": 20900.0,
        "target_price": 21100.0,
        "net_pnl": 500.0,
        "exit_reason": "TARGET",
    }])
    return run_id


class TestPersistAssessment:
    def test_insert_assessment(self, conn, run_with_trade):
        run_id = run_with_trade
        assessment = {
            "outcome_quality": "strong_win",
            "why_worked": "bias_aligned; favorable_tpo_B_shape",
            "why_failed": None,
            "deterministic_support": "session_bias_aligned",
            "deterministic_warning": None,
            "improvement_suggestion": None,
            "pre_signal_context": {"tape_bias": "Bullish", "tape_tpo_shape": "B_shape"},
        }
        persist_assessment(conn, "t001", run_id, assessment)

        rows = query(conn, "SELECT outcome_quality, why_worked FROM trade_assessments WHERE trade_id = ?", ["t001"])
        assert len(rows) == 1
        assert rows[0][0] == "strong_win"
        assert "bias_aligned" in rows[0][1]

    def test_upsert_assessment(self, conn, run_with_trade):
        run_id = run_with_trade
        # Insert first
        persist_assessment(conn, "t001", run_id, {"outcome_quality": "strong_win"})
        # Upsert with different quality
        persist_assessment(conn, "t001", run_id, {"outcome_quality": "lucky_win"})

        rows = query(conn, "SELECT outcome_quality FROM trade_assessments WHERE trade_id = ?", ["t001"])
        assert len(rows) == 1
        assert rows[0][0] == "lucky_win"

    def test_pre_signal_context_json(self, conn, run_with_trade):
        run_id = run_with_trade
        ctx = {"tape_bias": "Bearish", "tape_close": 21050.0}
        persist_assessment(conn, "t001", run_id, {
            "outcome_quality": "normal_loss",
            "pre_signal_context": ctx,
        })

        rows = query(conn, "SELECT pre_signal_context FROM trade_assessments WHERE trade_id = ?", ["t001"])
        assert rows[0][0] is not None

    def test_assessment_without_context(self, conn, run_with_trade):
        run_id = run_with_trade
        persist_assessment(conn, "t001", run_id, {
            "outcome_quality": "avoidable_loss",
            "why_failed": "counter-session-bias",
        })

        rows = query(conn, "SELECT outcome_quality, why_failed FROM trade_assessments WHERE trade_id = ?", ["t001"])
        assert rows[0][0] == "avoidable_loss"
        assert rows[0][1] == "counter-session-bias"


class TestPersistObservation:
    def test_insert_observation(self, conn):
        obs = {
            "obs_id": "test_obs_001",
            "scope": "portfolio",
            "observation": "Bias alignment is #1 predictor",
            "evidence": "251 aligned trades, 62.2% WR",
            "source": "phase4_analysis",
            "confidence": 0.95,
        }
        persist_observation(conn, obs)

        rows = query(conn, "SELECT observation, confidence FROM observations WHERE obs_id = ?", ["test_obs_001"])
        assert len(rows) == 1
        assert "Bias alignment" in rows[0][0]
        assert rows[0][1] == 0.95

    def test_upsert_observation(self, conn):
        obs = {
            "obs_id": "test_obs_002",
            "scope": "strategy",
            "strategy": "80P Rule",
            "observation": "80P contrarian original",
            "confidence": 0.80,
        }
        persist_observation(conn, obs)

        # Update
        obs["observation"] = "80P contrarian updated"
        obs["confidence"] = 0.90
        persist_observation(conn, obs)

        rows = query(conn, "SELECT observation, confidence FROM observations WHERE obs_id = ?", ["test_obs_002"])
        assert len(rows) == 1
        assert "updated" in rows[0][0]
        assert rows[0][1] == 0.90

    def test_observation_with_strategy(self, conn):
        obs = {
            "obs_id": "test_obs_003",
            "scope": "strategy",
            "strategy": "Opening Range Rev",
            "run_id": "test_run",
            "observation": "OR Rev + B_shape TPO = 76.8% WR",
            "evidence": "56 trades",
            "confidence": 0.90,
        }
        persist_observation(conn, obs)

        rows = query(conn, "SELECT strategy, observation FROM observations WHERE obs_id = ?", ["test_obs_003"])
        assert rows[0][0] == "Opening Range Rev"

    def test_observation_auto_id(self, conn):
        obs = {
            "observation": "Auto-generated ID test",
            "confidence": 0.50,
        }
        persist_observation(conn, obs)

        rows = query(conn, "SELECT COUNT(*) FROM observations")
        assert rows[0][0] >= 1
