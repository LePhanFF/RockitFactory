"""
TPO Expert — Market Profile / TPO domain analysis.

Refactored from ProfileObserver with the same 4 evidence cards,
now following the DomainExpert pattern for plug-in architecture.

Produces up to 4 cards:
  1. TPO shape alignment (b/p/D shape bias)
  2. VA position (price vs VAH/VAL)
  3. POC position (entry vs POC — value play detection)
  4. Poor extremes (weak resistance/support)
"""

from __future__ import annotations

import json as _json

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class TpoExpert(DomainExpert):
    """Market Profile / TPO domain expert.

    Reads TPO shape, Value Area, POC, and poor extremes from
    deterministic snapshots and session context.
    """

    @property
    def domain(self) -> str:
        return "tpo"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        tape_row = context.get("tape_row") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._tpo_shape_card,
            self._va_position_card,
            self._poc_position_card,
            self._poor_extremes_card,
        ):
            c = fn(tape_row, session_ctx, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def historical_query(self, conn, signal: dict) -> dict:
        """Query DuckDB for TPO-conditional win rates."""
        try:
            from rockit_core.research.db import query
            rows = query(conn, """
                SELECT d.tpo_shape, t.outcome, COUNT(*) as cnt, AVG(t.net_pnl) as avg_pnl
                FROM trades t
                JOIN deterministic_tape d ON t.session_date = d.session_date
                WHERE t.strategy_name = ? AND t.direction = ?
                  AND d.tpo_shape IS NOT NULL
                GROUP BY d.tpo_shape, t.outcome
                ORDER BY cnt DESC
                LIMIT 20
            """, [signal.get("strategy_name", ""), signal.get("direction", "")])
            return {"tpo_shape_stats": [dict(zip(["shape", "outcome", "count", "avg_pnl"], r)) for r in rows]}
        except Exception:
            return {}

    def _tpo_shape_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        shape = (
            tape_row.get("tpo_shape")
            or session_ctx.get("tpo_shape")
            or ""
        ).lower()

        if not shape:
            return None

        if shape in ("b", "b_shape"):
            direction = "bullish"
            strength = 0.7 if signal_dir == "LONG" else 0.3
            obs = f"TPO b-shape (value at bottom) — {'aligned' if signal_dir == 'LONG' else 'opposed'} with {signal_dir}"
        elif shape in ("p", "p_shape"):
            direction = "bearish"
            strength = 0.7 if signal_dir == "SHORT" else 0.3
            obs = f"TPO p-shape (value at top) — {'aligned' if signal_dir == 'SHORT' else 'opposed'} with {signal_dir}"
        elif shape in ("d", "d_shape"):
            direction = "neutral"
            strength = 0.5
            obs = f"TPO D-shape (balanced) — neutral for {signal_dir}"
        else:
            direction = "neutral"
            strength = 0.4
            obs = f"TPO shape '{shape}' — no strong directional bias"

        return EvidenceCard(
            card_id="tpo_shape",
            source="expert_tpo",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"tpo_shape": shape, "signal_direction": signal_dir},
        )

    def _va_position_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        vah = tape_row.get("current_vah") or session_ctx.get("current_vah")
        val = tape_row.get("current_val") or session_ctx.get("current_val")
        price = tape_row.get("close") or session_ctx.get("current_price")

        if not all((vah, val, price)):
            return None

        try:
            vah, val, price = float(vah), float(val), float(price)
        except (TypeError, ValueError):
            return None

        if price > vah:
            position = "above_vah"
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.6
                obs = f"Price above VAH ({price:.0f} > {vah:.0f}) — LONG has momentum"
            else:
                direction, strength = "bullish", 0.4
                obs = f"Price above VAH ({price:.0f} > {vah:.0f}) — SHORT fading into strength"
        elif price < val:
            position = "below_val"
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.6
                obs = f"Price below VAL ({price:.0f} < {val:.0f}) — SHORT has momentum"
            else:
                direction, strength = "bearish", 0.4
                obs = f"Price below VAL ({price:.0f} < {val:.0f}) — LONG buying into weakness"
        else:
            position = "inside_va"
            direction, strength = "neutral", 0.5
            obs = f"Price inside VA ({val:.0f}-{vah:.0f}) — balanced, no edge"

        return EvidenceCard(
            card_id="tpo_va_position",
            source="expert_tpo",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=3,
            raw_data={"vah": vah, "val": val, "price": price, "position": position},
        )

    def _poc_position_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        poc = tape_row.get("current_poc") or session_ctx.get("current_poc")
        price = tape_row.get("close") or session_ctx.get("current_price")

        if not all((poc, price)):
            return None

        try:
            poc, price = float(poc), float(price)
        except (TypeError, ValueError):
            return None

        if signal_dir == "LONG" and price <= poc:
            direction, strength = "bullish", 0.65
            obs = f"Entry below POC ({price:.0f} <= {poc:.0f}) — LONG is a value play"
        elif signal_dir == "SHORT" and price >= poc:
            direction, strength = "bearish", 0.65
            obs = f"Entry above POC ({price:.0f} >= {poc:.0f}) — SHORT is a value play"
        elif signal_dir == "LONG" and price > poc:
            direction, strength = "neutral", 0.35
            obs = f"Entry above POC ({price:.0f} > {poc:.0f}) — LONG chasing away from value"
        else:
            direction, strength = "neutral", 0.35
            obs = f"Entry below POC ({price:.0f} < {poc:.0f}) — SHORT reaching into value"

        return EvidenceCard(
            card_id="tpo_poc_position",
            source="expert_tpo",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=2,
            raw_data={"poc": poc, "price": price, "signal_direction": signal_dir},
        )

    def _poor_extremes_card(
        self, tape_row: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        snapshot = tape_row.get("snapshot_json") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = _json.loads(snapshot)
            except (_json.JSONDecodeError, TypeError):
                snapshot = {}

        tpo_data = snapshot.get("tpo_profile") or {}
        poor_high = tpo_data.get("poor_high", False)
        poor_low = tpo_data.get("poor_low", False)

        if not poor_high and not poor_low:
            return None

        if poor_high and signal_dir == "SHORT":
            direction, strength = "bearish", 0.6
            obs = "Poor high detected — weak resistance, SHORT has easier path"
        elif poor_low and signal_dir == "LONG":
            direction, strength = "bullish", 0.6
            obs = "Poor low detected — weak support likely to be revisited, LONG has easier path"
        elif poor_high and signal_dir == "LONG":
            direction, strength = "neutral", 0.4
            obs = "Poor high detected — LONG may face revisit of high before continuation"
        elif poor_low and signal_dir == "SHORT":
            direction, strength = "neutral", 0.4
            obs = "Poor low detected — SHORT may face revisit of low before continuation"
        else:
            direction, strength = "neutral", 0.5
            obs = f"Poor extremes: high={poor_high}, low={poor_low}"

        return EvidenceCard(
            card_id="tpo_poor_extremes",
            source="expert_tpo",
            layer="instinct",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"poor_high": poor_high, "poor_low": poor_low},
        )
