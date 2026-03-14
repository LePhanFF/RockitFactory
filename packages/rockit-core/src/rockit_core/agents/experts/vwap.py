"""
VWAP Expert — Volume-Weighted Average Price domain analysis.

Produces up to 3 cards:
  1. VWAP trend (slope + price position)
  2. VWAP mean reversion (distance from VWAP, band position)
  3. VWAP reclaim (price crossing back above/below VWAP)

Uses bar data + session context for VWAP, BB bands, and price information.
"""

from __future__ import annotations

import math

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class VwapExpert(DomainExpert):
    """VWAP domain expert — trend, mean reversion, and reclaim signals."""

    @property
    def domain(self) -> str:
        return "vwap"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        bar = context.get("bar") or {}
        session_ctx = context.get("session_context") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._vwap_trend_card,
            self._vwap_mean_revert_card,
            self._vwap_reclaim_card,
        ):
            c = fn(bar, session_ctx, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def historical_query(self, conn, signal: dict) -> dict:
        """Query DuckDB for VWAP-conditional win rates."""
        try:
            from rockit_core.research.db import query
            rows = query(conn, """
                SELECT
                    CASE WHEN d.close > d.vwap THEN 'above_vwap' ELSE 'below_vwap' END as vwap_pos,
                    t.outcome, COUNT(*) as cnt, AVG(t.net_pnl) as avg_pnl
                FROM trades t
                JOIN deterministic_tape d ON t.session_date = d.session_date
                WHERE t.strategy_name = ? AND t.direction = ?
                  AND d.vwap IS NOT NULL AND d.close IS NOT NULL
                GROUP BY 1, t.outcome
                ORDER BY cnt DESC
                LIMIT 10
            """, [signal.get("strategy_name", ""), signal.get("direction", "")])
            return {"vwap_stats": [dict(zip(["vwap_pos", "outcome", "count", "avg_pnl"], r)) for r in rows]}
        except Exception:
            return {}

    def _vwap_trend_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """VWAP trend: price position + slope direction."""
        vwap = self._get_vwap(bar, session_ctx)
        price = self._get_price(bar, session_ctx)

        if vwap is None or price is None or vwap <= 0:
            return None

        distance_pct = (price - vwap) / vwap * 100
        above_vwap = price > vwap

        # VWAP slope from session context (computed in features)
        vwap_slope = session_ctx.get("vwap_slope")

        if above_vwap:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.65
                obs = f"Price above VWAP ({distance_pct:+.2f}%) — bullish trend, aligned with LONG"
            else:
                direction, strength = "bullish", 0.35
                obs = f"Price above VWAP ({distance_pct:+.2f}%) — SHORT fading into VWAP uptrend"
        else:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.65
                obs = f"Price below VWAP ({distance_pct:+.2f}%) — bearish trend, aligned with SHORT"
            else:
                direction, strength = "bearish", 0.35
                obs = f"Price below VWAP ({distance_pct:+.2f}%) — LONG buying below VWAP"

        # Boost if slope aligns
        if vwap_slope is not None:
            try:
                slope = float(vwap_slope)
                if slope > 0 and signal_dir == "LONG":
                    strength = min(1.0, strength + 0.1)
                    obs += f" (VWAP slope positive: +{slope:.2f})"
                elif slope < 0 and signal_dir == "SHORT":
                    strength = min(1.0, strength + 0.1)
                    obs += f" (VWAP slope negative: {slope:.2f})"
            except (TypeError, ValueError):
                pass

        return EvidenceCard(
            card_id="vwap_trend",
            source="expert_vwap",
            layer="certainty",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=2,
            raw_data={
                "vwap": vwap, "price": price,
                "distance_pct": round(distance_pct, 3),
                "above_vwap": above_vwap,
            },
        )

    def _vwap_mean_revert_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Mean reversion signal when price is at BB extremes relative to VWAP."""
        vwap = self._get_vwap(bar, session_ctx)
        price = self._get_price(bar, session_ctx)
        bb_upper = self._get_float(bar, session_ctx, "bb_upper")
        bb_lower = self._get_float(bar, session_ctx, "bb_lower")

        if vwap is None or price is None:
            return None
        if bb_upper is None or bb_lower is None:
            return None
        if bb_upper <= bb_lower:
            return None

        # BB percentile: 0 = at lower band, 1 = at upper band
        bb_pct = (price - bb_lower) / (bb_upper - bb_lower)
        bb_pct = max(0.0, min(1.0, bb_pct))

        # Distance from VWAP in points
        vwap_dist = abs(price - vwap)

        if bb_pct >= 0.95:
            # At upper BB extreme — mean reversion SHORT favored
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.65
                obs = f"Price at upper BB extreme (BB%={bb_pct:.0%}) — overextended, supports SHORT reversion"
            else:
                direction, strength = "bearish", 0.4
                obs = f"Price at upper BB extreme (BB%={bb_pct:.0%}) — LONG entering at overextended level"
            return EvidenceCard(
                card_id="vwap_mean_revert",
                source="expert_vwap",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=3,
                raw_data={"bb_pct": round(bb_pct, 3), "vwap_dist": round(vwap_dist, 2)},
            )
        elif bb_pct <= 0.05:
            # At lower BB extreme — mean reversion LONG favored
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.65
                obs = f"Price at lower BB extreme (BB%={bb_pct:.0%}) — oversold, supports LONG reversion"
            else:
                direction, strength = "bullish", 0.4
                obs = f"Price at lower BB extreme (BB%={bb_pct:.0%}) — SHORT entering at oversold level"
            return EvidenceCard(
                card_id="vwap_mean_revert",
                source="expert_vwap",
                layer="probabilistic",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=3,
                raw_data={"bb_pct": round(bb_pct, 3), "vwap_dist": round(vwap_dist, 2)},
            )

        return None  # No extreme — no card

    def _vwap_reclaim_card(
        self, bar: dict, session_ctx: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Price reclaiming VWAP from below (bullish) or losing it from above (bearish)."""
        vwap = self._get_vwap(bar, session_ctx)
        price = self._get_price(bar, session_ctx)
        prev_close = self._get_float(bar, session_ctx, "prev_close")

        if vwap is None or price is None or prev_close is None:
            return None

        # Reclaim: was below VWAP, now above
        if prev_close < vwap and price > vwap:
            if signal_dir == "LONG":
                direction, strength = "bullish", 0.7
                obs = f"VWAP reclaim — price crossed above VWAP ({vwap:.0f}), strongly supports LONG"
            else:
                direction, strength = "bullish", 0.45
                obs = f"VWAP reclaim — price crossed above VWAP ({vwap:.0f}), warns against SHORT"
            return EvidenceCard(
                card_id="vwap_reclaim",
                source="expert_vwap",
                layer="certainty",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=2,
                raw_data={"vwap": vwap, "prev_close": prev_close, "price": price, "action": "reclaim"},
            )

        # Lost VWAP: was above, now below
        if prev_close > vwap and price < vwap:
            if signal_dir == "SHORT":
                direction, strength = "bearish", 0.7
                obs = f"VWAP lost — price fell below VWAP ({vwap:.0f}), strongly supports SHORT"
            else:
                direction, strength = "bearish", 0.45
                obs = f"VWAP lost — price fell below VWAP ({vwap:.0f}), warns against LONG"
            return EvidenceCard(
                card_id="vwap_reclaim",
                source="expert_vwap",
                layer="certainty",
                observation=obs,
                direction=direction,
                strength=strength,
                data_points=2,
                raw_data={"vwap": vwap, "prev_close": prev_close, "price": price, "action": "lost"},
            )

        return None

    # ── Helpers ──

    @staticmethod
    def _get_vwap(bar: dict, session_ctx: dict) -> float | None:
        for src in (bar, session_ctx):
            for key in ("vwap", "VWAP", "session_vwap"):
                v = src.get(key)
                if v is not None:
                    try:
                        val = float(v)
                        if not math.isnan(val) and val > 0:
                            return val
                    except (TypeError, ValueError):
                        pass
        return None

    @staticmethod
    def _get_price(bar: dict, session_ctx: dict) -> float | None:
        for src in (bar, session_ctx):
            for key in ("close", "Close", "current_price"):
                v = src.get(key)
                if v is not None:
                    try:
                        val = float(v)
                        if not math.isnan(val):
                            return val
                    except (TypeError, ValueError):
                        pass
        return None

    @staticmethod
    def _get_float(bar: dict, session_ctx: dict, key: str) -> float | None:
        for src in (bar, session_ctx):
            v = src.get(key)
            if v is not None:
                try:
                    val = float(v)
                    if not math.isnan(val):
                        return val
                except (TypeError, ValueError):
                    pass
        return None
