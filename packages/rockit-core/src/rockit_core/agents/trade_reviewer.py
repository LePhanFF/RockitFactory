"""
Trade Reviewer — LLM-powered post-trade analysis.

Receives a completed trade + deterministic context at signal time.
Produces structured review: setup_quality, entry_timing, exit_assessment,
what_worked/failed, lesson, observation.

Persists results to trade_assessments + observations tables in DuckDB.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from rockit_core.agents.llm_client import OllamaClient

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[5] / "configs" / "prompts" / "trade_review_system.md"
)


def _load_system_prompt() -> str:
    """Load the trade review system prompt from configs/prompts/."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Trade review prompt not found at %s, using fallback", _PROMPT_PATH)
        return (
            "You are TRADE REVIEWER. Analyze the completed trade. "
            "Output valid JSON with: setup_quality, entry_timing, exit_assessment, "
            "what_worked, what_failed, lesson, observation, confidence."
        )


class TradeReviewer:
    """LLM-powered post-trade analysis agent."""

    def __init__(self, llm_client: OllamaClient, max_tokens: int = 4000):
        self._llm = llm_client
        self._max_tokens = max_tokens
        self._system_prompt = _load_system_prompt()

    def review_trade(
        self,
        trade: dict[str, Any],
        session_context: dict[str, Any] | None = None,
        deterministic_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Review a single trade with LLM analysis.

        Args:
            trade: Trade dict with strategy_name, direction, entry_price, net_pnl, etc.
            session_context: Session-level context (day_type, bias, IB range, etc.)
            deterministic_data: Deterministic snapshot at signal time.

        Returns:
            Dict with setup_quality, entry_timing, exit_assessment, what_worked,
            what_failed, lesson, observation, confidence. On error: {"error": str}.
        """
        user_prompt = self._build_prompt(trade, session_context, deterministic_data)
        response = self._llm.chat(self._system_prompt, user_prompt, self._max_tokens)

        if response.get("error"):
            logger.warning("Trade review LLM error: %s", response["error"])
            return {"error": response["error"]}

        return self._parse_response(response.get("content", ""))

    def review_and_persist(
        self,
        trade: dict[str, Any],
        run_id: str,
        session_context: dict[str, Any] | None = None,
        deterministic_data: dict[str, Any] | None = None,
        conn: Any = None,
    ) -> dict[str, Any]:
        """Review a trade and persist results to DuckDB.

        Persists to trade_assessments and observations tables.
        Returns the review dict.
        """
        review = self.review_trade(trade, session_context, deterministic_data)

        if review.get("error") or conn is None:
            return review

        trade_id = trade.get("trade_id", "")
        session_date = str(trade.get("session_date", "")).split(" ")[0].split("T")[0]
        strategy = trade.get("strategy_name") or trade.get("strategy", "")

        try:
            from rockit_core.research.db import persist_assessment, persist_observation

            # Persist to trade_assessments
            assessment = {
                "outcome_quality": str(review.get("setup_quality", "")),
                "why_worked": review.get("what_worked"),
                "why_failed": review.get("what_failed"),
                "deterministic_support": review.get("lesson"),
                "deterministic_warning": None,
                "improvement_suggestion": review.get("lesson"),
                "pre_signal_context": deterministic_data,
            }
            persist_assessment(conn, trade_id, run_id, assessment)

            # Persist observation if present
            obs_text = review.get("observation")
            if obs_text:
                persist_observation(conn, {
                    "obs_id": f"llm_tr_{session_date}_{uuid.uuid4().hex[:6]}",
                    "scope": "session",
                    "strategy": strategy,
                    "session_date": session_date,
                    "trade_id": trade_id,
                    "run_id": run_id,
                    "observation": obs_text,
                    "evidence": f"LLM trade review (setup_quality={review.get('setup_quality')})",
                    "source": "llm_trade_review",
                    "confidence": review.get("confidence", 0.5),
                })

            logger.info("Persisted trade review for %s", trade_id)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to persist trade review for %s", trade_id, exc_info=True)

        return review

    def _build_prompt(
        self,
        trade: dict[str, Any],
        session_context: dict[str, Any] | None = None,
        deterministic_data: dict[str, Any] | None = None,
    ) -> str:
        """Build the user prompt from trade + context."""
        outcome = "WIN" if trade.get("net_pnl", 0) > 0 else "LOSS"

        prompt_data: dict[str, Any] = {
            "trade": {
                "strategy": trade.get("strategy_name") or trade.get("strategy", ""),
                "direction": trade.get("direction", ""),
                "entry_price": trade.get("entry_price", 0),
                "exit_price": trade.get("exit_price", 0),
                "stop_price": trade.get("stop_price", 0),
                "target_price": trade.get("target_price", 0),
                "net_pnl": trade.get("net_pnl", 0),
                "outcome": outcome,
                "exit_reason": trade.get("exit_reason", ""),
                "bars_held": trade.get("bars_held", 0),
                "day_type": trade.get("day_type", ""),
            },
        }

        if session_context:
            prompt_data["session_context"] = {
                "day_type": session_context.get("day_type", "unknown"),
                "bias": session_context.get("bias") or session_context.get("session_bias", "unknown"),
                "ib_range": session_context.get("ib_range"),
                "ib_width_class": session_context.get("ib_width_class"),
                "trend_strength": session_context.get("trend_strength"),
                "composite_regime": session_context.get("composite_regime"),
                "dpoc_migration": session_context.get("dpoc_migration"),
                "tpo_shape": session_context.get("tpo_shape"),
            }

        if deterministic_data:
            prompt_data["deterministic_at_signal"] = deterministic_data

        return json.dumps(prompt_data, indent=2, default=str)

    @staticmethod
    def _parse_response(content: str) -> dict[str, Any]:
        """Parse LLM JSON response into review dict."""
        try:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [line for line in lines if not line.strip().startswith("```")]
                cleaned = "\n".join(lines)

            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Trade review response not valid JSON: %s", exc)
            return {"error": f"Parse error: {exc}", "raw_response": content}

        # Validate and clamp
        data["setup_quality"] = max(1, min(5, int(data.get("setup_quality", 3))))
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.5))))

        valid_timings = ("early", "good", "late", "chased")
        if data.get("entry_timing") not in valid_timings:
            data["entry_timing"] = "good"

        valid_exits = ("optimal", "left_money", "stopped_early", "held_too_long")
        if data.get("exit_assessment") not in valid_exits:
            data["exit_assessment"] = "optimal"

        return data
