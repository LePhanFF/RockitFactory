# Integration Tests

> **Layer:** Component integration (middle of the testing pyramid)
> **Speed:** < 5 minutes total
> **CI gate:** Every PR, plus nightly full run
> **Principle:** Test component boundaries, not internal logic

---

## Overview

Integration tests verify that components work together correctly. Unlike unit
tests (which isolate a single function), integration tests exercise the seams
between components: strategy to filter chain, backtest engine to strategy
pipeline, orchestrator to deterministic modules, and API routes to backend logic.

```
Unit tests:          StrategyBase.on_bar() returns correct Signal
Integration tests:   Strategy → FilterChain → BacktestEngine produces correct trades
```

---

## Test Organization

```
packages/rockit-core/tests/integration/
├── test_strategy_pipeline.py      # Strategy + filter chain + signal output
├── test_backtest_regression.py    # Full 259-session backtest vs reference
└── test_deterministic_snapshot.py # Orchestrator output vs reference JSONs

packages/rockit-serve/tests/integration/
├── test_api_signals.py            # FastAPI test client → signal endpoints
├── test_api_snapshots.py          # FastAPI test client → snapshot endpoints
└── test_agent_pipeline.py         # LangGraph agent flow (mocked LLM)

packages/rockit-pipeline/tests/integration/
├── test_reflection_loop.py        # Outcome logging → scorecard → reflection
└── test_data_generation.py        # Deterministic snapshot → training JSONL
```

---

## Strategy Pipeline Integration

Tests the full path: bar data enters the strategy, signals come out, filters
accept or reject, and the result matches expectations for known sessions.

```python
# packages/rockit-core/tests/integration/test_strategy_pipeline.py

import pytest
import pandas as pd
from pathlib import Path

from rockit_core.strategies import ALL_STRATEGIES, CORE_STRATEGIES, load_strategies_from_config
from rockit_core.filters.composite import CompositeFilter
from rockit_core.backtest.engine import BacktestEngine


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sessions"


def load_session_csv(filename: str) -> pd.DataFrame:
    """Load a session CSV fixture into a DataFrame."""
    return pd.read_csv(FIXTURE_DIR / filename, parse_dates=["timestamp"])


class TestStrategyPipeline:
    """Integration: strategy evaluation through full filter chain."""

    @pytest.fixture
    def core_strategies(self) -> list:
        """Instantiate all core portfolio strategies."""
        return [ALL_STRATEGIES[name]() for name in CORE_STRATEGIES if name in ALL_STRATEGIES]

    @pytest.fixture
    def default_filters(self) -> CompositeFilter:
        """Default production filter chain."""
        return CompositeFilter.from_config("configs/filters.yaml")

    @pytest.fixture
    def trend_day_data(self) -> pd.DataFrame:
        """2026-01-15: Known clear trend-up day (NQ)."""
        return load_session_csv("2026-01-15_NQ.csv")

    @pytest.fixture
    def b_day_data(self) -> pd.DataFrame:
        """2026-01-22: Known clear B-Day (NQ)."""
        return load_session_csv("2026-01-22_NQ.csv")

    @pytest.fixture
    def p_day_data(self) -> pd.DataFrame:
        """2026-01-28: Known clear P-Day (NQ)."""
        return load_session_csv("2026-01-28_NQ.csv")

    def test_trend_day_produces_long_signal(
        self, core_strategies, default_filters, trend_day_data,
    ) -> None:
        """On a known trend day, at least one trend strategy fires LONG."""
        engine = BacktestEngine(
            strategies=core_strategies,
            filters=default_filters,
        )
        result = engine.run(trend_day_data)
        trend_signals = [
            s for s in result.signals
            if "trend" in s.strategy_name.lower()
        ]
        assert len(trend_signals) > 0, "Expected at least one trend signal on a trend day"
        assert all(s.direction == "LONG" for s in trend_signals)

    def test_b_day_does_not_produce_trend_signal(
        self, core_strategies, default_filters, b_day_data,
    ) -> None:
        """On a known B-Day, trend strategies must NOT fire."""
        engine = BacktestEngine(
            strategies=core_strategies,
            filters=default_filters,
        )
        result = engine.run(b_day_data)
        trend_signals = [
            s for s in result.signals
            if "trend" in s.strategy_name.lower()
        ]
        assert len(trend_signals) == 0, "Trend strategies should not fire on B-Day"

    def test_b_day_produces_b_day_signal(
        self, core_strategies, default_filters, b_day_data,
    ) -> None:
        """On a known B-Day, the B-Day strategy should fire."""
        engine = BacktestEngine(
            strategies=core_strategies,
            filters=default_filters,
        )
        result = engine.run(b_day_data)
        bday_signals = [
            s for s in result.signals
            if "b_day" in s.strategy_name.lower() or "edge_fade" in s.strategy_name.lower()
        ]
        assert len(bday_signals) > 0, "Expected B-Day or EdgeFade signal on a B-Day"

    def test_filter_chain_blocks_weak_order_flow(
        self, core_strategies, default_filters, trend_day_data,
    ) -> None:
        """Signals with weak order flow are blocked by the filter chain."""
        # Overwrite delta/CVD to be weak
        modified = trend_day_data.copy()
        modified["delta"] = 10.0
        modified["cvd"] = 50.0
        engine = BacktestEngine(
            strategies=core_strategies,
            filters=default_filters,
        )
        result = engine.run(modified)
        # With weak order flow, filters should block most or all signals
        assert len(result.signals) < 2, "Weak order flow should block most signals"

    def test_yaml_config_loading_produces_valid_pipeline(self) -> None:
        """load_strategies_from_config produces runnable strategy instances."""
        strategies = load_strategies_from_config("configs/strategies.yaml")
        assert len(strategies) > 0
        for s in strategies:
            assert hasattr(s, "name")
            assert hasattr(s, "on_bar")
            assert hasattr(s, "on_session_start")
```

---

## Backtest Regression

The full 259-session backtest is the ultimate integration test. It must produce
results that match the reference baseline.

```python
# packages/rockit-core/tests/integration/test_backtest_regression.py

import json
import pytest
from pathlib import Path

from rockit_core.backtest.engine import BacktestEngine
from rockit_core.strategies import ALL_STRATEGIES, CORE_STRATEGIES
from rockit_core.filters.composite import CompositeFilter


BASELINE_PATH = Path("configs/baselines/current.json")
TOLERANCE = {
    "total_trades": 0,          # Must be exact
    "win_rate": 0.001,          # Allow 0.1% float rounding
    "profit_factor": 0.01,      # Allow 0.01 float rounding
    "net_pnl": 1.0,             # Allow $1 rounding
}


@pytest.mark.regression
@pytest.mark.slow
class TestBacktestRegression:
    """Full 259-session backtest must match reference baseline."""

    @pytest.fixture(scope="class")
    def backtest_result(self):
        """Run full backtest once for the entire class."""
        strategies = [ALL_STRATEGIES[n]() for n in CORE_STRATEGIES if n in ALL_STRATEGIES]
        filters = CompositeFilter.from_config("configs/filters.yaml")
        engine = BacktestEngine(strategies=strategies, filters=filters)
        sessions = load_all_sessions("data/sessions/")
        return engine.run(sessions)

    @pytest.fixture(scope="class")
    def baseline(self):
        """Load the frozen baseline."""
        return json.loads(BASELINE_PATH.read_text())

    def test_total_trades_matches(self, backtest_result, baseline) -> None:
        """Total trade count must match exactly."""
        assert backtest_result.total_trades == baseline["det_total_trades"]

    def test_win_rate_matches(self, backtest_result, baseline) -> None:
        """Win rate must match within tolerance."""
        assert abs(backtest_result.win_rate - baseline["det_win_rate"]) <= TOLERANCE["win_rate"]

    def test_profit_factor_matches(self, backtest_result, baseline) -> None:
        """Profit factor must match within tolerance."""
        assert abs(backtest_result.profit_factor - baseline["det_profit_factor"]) <= TOLERANCE["profit_factor"]

    def test_no_new_losing_streaks(self, backtest_result, baseline) -> None:
        """Max drawdown must not be worse than baseline."""
        assert backtest_result.max_drawdown >= baseline["det_max_drawdown"]

    def test_per_strategy_trade_counts(self, backtest_result, baseline) -> None:
        """Each strategy's trade count must match reference."""
        for strat_name, strat_baseline in baseline.get("strategy_baselines", {}).items():
            actual = backtest_result.strategy_stats.get(strat_name, {})
            expected_trades = strat_baseline["trades"]
            actual_trades = actual.get("trades", 0)
            assert actual_trades == expected_trades, (
                f"{strat_name}: expected {expected_trades} trades, got {actual_trades}"
            )

    def test_trade_list_identical(self, backtest_result, baseline) -> None:
        """Every trade in the backtest must match the reference trade list."""
        ref_trades = load_reference_trades("configs/baselines/reference_trades.json")
        assert len(backtest_result.trades) == len(ref_trades)
        for i, (actual, expected) in enumerate(zip(backtest_result.trades, ref_trades)):
            assert actual.session_date == expected["session_date"], f"Trade {i}: date mismatch"
            assert actual.direction == expected["direction"], f"Trade {i}: direction mismatch"
            assert actual.strategy_name == expected["strategy_name"], f"Trade {i}: strategy mismatch"
            assert abs(actual.entry_price - expected["entry_price"]) < 0.01, f"Trade {i}: entry mismatch"
```

---

## Deterministic Snapshot Regression

The orchestrator generates JSON snapshots from market data. These snapshots are
the input to the LLM training pipeline, so they must be deterministic.

```python
# packages/rockit-core/tests/integration/test_deterministic_snapshot.py

import json
import pytest
from pathlib import Path

from rockit_core.deterministic.orchestrator import Orchestrator


REFERENCE_DIR = Path(__file__).parent.parent / "fixtures" / "snapshots"
SESSION_DIR = Path(__file__).parent.parent / "fixtures" / "sessions"

# Test at multiple intraday timestamps to catch time-dependent bugs
SNAPSHOT_TIMES = ["10:30", "11:00", "11:45", "13:00", "14:30"]


class TestDeterministicSnapshot:
    """Orchestrator output must match reference JSONs exactly."""

    @pytest.fixture
    def orchestrator(self) -> Orchestrator:
        return Orchestrator()

    @pytest.mark.parametrize("time_str", SNAPSHOT_TIMES)
    def test_snapshot_matches_reference(self, orchestrator, time_str: str) -> None:
        """Snapshot at each time must match its reference."""
        input_data = pd.read_csv(
            SESSION_DIR / "2026-01-15_NQ.csv",
            parse_dates=["timestamp"],
        )
        snapshot = orchestrator.generate_snapshot(
            input_data, config={"time": time_str, "instrument": "NQ"},
        )
        ref_file = REFERENCE_DIR / f"2026-01-15_{time_str.replace(':', '')}_NQ.json"
        reference = json.loads(ref_file.read_text())

        # Numeric fields: compare with tolerance
        for section in ["ib", "volume_profile", "tpo_profile", "market_state"]:
            if section in reference:
                for key, ref_val in reference[section].items():
                    actual_val = snapshot[section][key]
                    if isinstance(ref_val, float):
                        assert abs(actual_val - ref_val) < 1e-6, (
                            f"{section}.{key}: {actual_val} != {ref_val}"
                        )
                    else:
                        assert actual_val == ref_val, (
                            f"{section}.{key}: {actual_val} != {ref_val}"
                        )

    def test_all_38_modules_present(self, orchestrator) -> None:
        """Snapshot must contain output from all 38 deterministic modules."""
        input_data = pd.read_csv(
            SESSION_DIR / "2026-01-15_NQ.csv",
            parse_dates=["timestamp"],
        )
        snapshot = orchestrator.generate_snapshot(
            input_data, config={"time": "11:45", "instrument": "NQ"},
        )
        # The orchestrator should have a known set of module keys
        expected_modules = orchestrator.module_names()
        for module_name in expected_modules:
            assert module_name in snapshot, f"Missing module output: {module_name}"

    def test_module_failure_does_not_crash_snapshot(self, orchestrator) -> None:
        """If one module fails, the snapshot still contains other modules."""
        # Provide incomplete data that will cause some modules to fail
        sparse_data = pd.DataFrame({
            "timestamp": pd.date_range("2026-01-15 09:30", periods=5, freq="5min"),
            "close": [21800.0, 21810.0, 21805.0, 21815.0, 21820.0],
        })
        snapshot = orchestrator.generate_snapshot(
            sparse_data, config={"time": "09:55", "instrument": "NQ"},
        )
        # Should still be a dict, not an exception
        assert isinstance(snapshot, dict)
        # Modules that failed should have error status, not crash
        for key, value in snapshot.items():
            if isinstance(value, dict) and "status" in value:
                assert value["status"] in ("ok", "failed", "partial")
```

---

## API Integration

Tests the FastAPI application using the built-in `TestClient`. No running server
needed. These tests verify routing, request validation, response schemas, and
error handling.

```python
# packages/rockit-serve/tests/integration/test_api_signals.py

import pytest
from fastapi.testclient import TestClient

from rockit_serve.app import create_app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client with mocked dependencies."""
    app = create_app(
        snapshot_provider=MockSnapshotProvider(),
        agent_graph=MockAgentGraph(),
    )
    return TestClient(app)


class TestSignalsAPI:
    """Integration tests for the /signals endpoint."""

    def test_get_signals_returns_200(self, client) -> None:
        """GET /api/v1/signals returns 200 with valid query params."""
        resp = client.get("/api/v1/signals", params={
            "instrument": "NQ",
            "date": "2026-01-15",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_signal_response_schema(self, client) -> None:
        """Each signal in the response has required fields."""
        resp = client.get("/api/v1/signals", params={
            "instrument": "NQ",
            "date": "2026-01-15",
        })
        for signal in resp.json()["signals"]:
            assert "direction" in signal
            assert signal["direction"] in ("LONG", "SHORT")
            assert "entry_price" in signal
            assert "stop_price" in signal
            assert "target_price" in signal
            assert "strategy_name" in signal
            assert "confidence" in signal

    def test_invalid_instrument_returns_422(self, client) -> None:
        """Invalid instrument returns validation error."""
        resp = client.get("/api/v1/signals", params={
            "instrument": "INVALID",
            "date": "2026-01-15",
        })
        assert resp.status_code == 422

    def test_missing_date_returns_422(self, client) -> None:
        """Missing required date parameter returns 422."""
        resp = client.get("/api/v1/signals", params={"instrument": "NQ"})
        assert resp.status_code == 422


class TestSnapshotAPI:
    """Integration tests for the /snapshot endpoint."""

    def test_get_snapshot_returns_200(self, client) -> None:
        """GET /api/v1/snapshot returns full deterministic snapshot."""
        resp = client.get("/api/v1/snapshot", params={
            "instrument": "NQ",
            "date": "2026-01-15",
            "time": "11:45",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "ib" in data
        assert "volume_profile" in data

    def test_health_check(self, client) -> None:
        """GET /health returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200
```

---

## Agent Pipeline Integration (Mocked LLM)

Tests the LangGraph agent pipeline with a mock LLM. Validates graph routing,
state transitions, and output structure without depending on LLM quality.

```python
# packages/rockit-serve/tests/integration/test_agent_pipeline.py

import pytest
from rockit_serve.agents.graph import build_agent_graph
from tests.conftest import MockChatModel, make_high_confidence_context, make_moderate_confidence_context


@pytest.fixture
def mock_llm() -> MockChatModel:
    """Deterministic mock LLM with canned responses."""
    return MockChatModel(responses={
        "ADVOCATE": '{"argument": "Strong trend continuation setup", "conviction": "high"}',
        "SKEPTIC": '{"argument": "Delta is weakening", "conviction": "medium"}',
        "JUDGE": '{"decision": "TAKE", "reasoning": "Advocate case stronger"}',
    })


@pytest.mark.agent
class TestAgentPipeline:
    """Integration tests for the LangGraph debate pipeline."""

    def test_high_confidence_skips_debate(self, mock_llm) -> None:
        """When deterministic confidence > 0.90, skip LLM debate."""
        graph = build_agent_graph(llm=mock_llm)
        result = graph.invoke({
            "time_slice": make_high_confidence_context(),
            "session_date": "2026-01-15",
        })
        assert result.get("advocate_argument") is None
        assert result["consensus_decision"] == "TAKE"

    def test_debate_produces_structured_output(self, mock_llm) -> None:
        """Moderate confidence triggers debate with structured output."""
        graph = build_agent_graph(llm=mock_llm)
        result = graph.invoke({
            "time_slice": make_moderate_confidence_context(),
            "session_date": "2026-01-15",
        })
        assert result["advocate_argument"] is not None
        assert result["skeptic_argument"] is not None
        assert result["consensus_decision"] in ("TAKE", "SKIP", "REDUCE_SIZE")

    def test_risk_check_blocks_overlimit(self, mock_llm) -> None:
        """Risk gate blocks signals when exposure exceeds daily limit."""
        graph = build_agent_graph(llm=mock_llm)
        result = graph.invoke({
            "time_slice": make_moderate_confidence_context(),
            "session_date": "2026-01-15",
            "current_exposure": 4000.0,  # At max daily drawdown
        })
        assert result["final_signals"] == []

    def test_graph_state_keys_present(self, mock_llm) -> None:
        """All expected state keys exist in the final graph output."""
        graph = build_agent_graph(llm=mock_llm)
        result = graph.invoke({
            "time_slice": make_moderate_confidence_context(),
            "session_date": "2026-01-15",
        })
        required_keys = [
            "deterministic_snapshot",
            "consensus_decision",
            "final_signals",
        ]
        for key in required_keys:
            assert key in result, f"Missing state key: {key}"
```

---

## Reflection Loop Integration

```python
# packages/rockit-pipeline/tests/integration/test_reflection_loop.py

import pytest
from rockit_pipeline.reflection.outcome_logger import OutcomeLogger
from rockit_pipeline.reflection.scorecard import ScorecardBuilder


class TestReflectionLoop:
    """Integration: outcome logging through scorecard generation."""

    def test_outcome_logger_records_win(self) -> None:
        """OutcomeLogger correctly classifies a winning trade."""
        logger = OutcomeLogger()
        outcome = logger.record(
            signal=make_signal(direction="LONG", entry_price=21850.0, target_price=21930.0),
            exit_price=21925.0,
            exit_reason="target_hit",
        )
        assert outcome.outcome == "WIN"
        assert outcome.pnl > 0

    def test_scorecard_aggregates_outcomes(self) -> None:
        """ScorecardBuilder produces correct aggregates from outcomes."""
        outcomes = [
            make_outcome(pnl=200.0, outcome="WIN"),
            make_outcome(pnl=-100.0, outcome="LOSS"),
            make_outcome(pnl=150.0, outcome="WIN"),
        ]
        builder = ScorecardBuilder()
        scorecard = builder.build(outcomes, period="2026-01-15 to 2026-01-17")
        assert scorecard.total_trades == 3
        assert scorecard.win_rate == pytest.approx(2 / 3)
        assert scorecard.net_pnl == pytest.approx(250.0)
```
