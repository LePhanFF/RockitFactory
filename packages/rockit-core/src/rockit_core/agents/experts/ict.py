"""
ICT Expert — Inner Circle Trader concepts: FVGs, BPR, NDOG/NWOG gaps.

Produces up to 4 cards:
  1. FVG support/resistance (unfilled FVG near price)
  2. BPR zone (balanced price range — overlapping FVGs)
  3. NDOG/NWOG gap status (daily/weekly gap fill progress)
  4. Higher-TF FVG confluence (15-min FVG alignment)

Uses bar-level ICT columns (fvg_bull, fvg_bear, etc.) and snapshot_json.
"""

from __future__ import annotations

import json as _json
import math

from rockit_core.agents.evidence import EvidenceCard
from rockit_core.agents.experts.base import DomainExpert


class IctExpert(DomainExpert):
    """ICT domain expert — FVG, BPR, and gap analysis."""

    @property
    def domain(self) -> str:
        return "ict"

    def scorecard(self, context: dict) -> list[EvidenceCard]:
        cards: list[EvidenceCard] = []
        bar = context.get("bar") or {}
        session_ctx = context.get("session_context") or {}
        tape_row = context.get("tape_row") or {}
        signal = context.get("signal") or {}
        signal_dir = signal.get("direction", "").upper()

        for fn in (
            self._fvg_support_card,
            self._bpr_zone_card,
            self._gap_status_card,
            self._htf_fvg_card,
        ):
            c = fn(bar, session_ctx, tape_row, signal_dir)
            if c is not None:
                cards.append(c)

        return cards

    def _fvg_support_card(
        self, bar: dict, session_ctx: dict, tape_row: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Active FVG near price — support for LONG, resistance for SHORT."""
        fvg_bull = _get_bool(bar, "fvg_bull")
        fvg_bear = _get_bool(bar, "fvg_bear")

        if not fvg_bull and not fvg_bear:
            return None

        if fvg_bull and signal_dir == "LONG":
            direction, strength = "bullish", 0.65
            obs = "Price in bullish FVG zone — institutional support, aligned with LONG"
        elif fvg_bull and signal_dir == "SHORT":
            direction, strength = "bullish", 0.4
            obs = "Price in bullish FVG zone — SHORT entering support area, caution"
        elif fvg_bear and signal_dir == "SHORT":
            direction, strength = "bearish", 0.65
            obs = "Price in bearish FVG zone — institutional resistance, aligned with SHORT"
        elif fvg_bear and signal_dir == "LONG":
            direction, strength = "bearish", 0.4
            obs = "Price in bearish FVG zone — LONG entering resistance area, caution"
        else:
            return None

        return EvidenceCard(
            card_id="ict_fvg_support",
            source="expert_ict",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"fvg_bull": fvg_bull, "fvg_bear": fvg_bear},
        )

    def _bpr_zone_card(
        self, bar: dict, session_ctx: dict, tape_row: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """Balanced Price Range — overlapping bull+bear FVGs indicate consolidation."""
        in_bpr = _get_bool(bar, "in_bpr")
        if not in_bpr:
            return None

        return EvidenceCard(
            card_id="ict_bpr_zone",
            source="expert_ict",
            layer="instinct",
            observation="Price in BPR (Balanced Price Range) — overlapping FVGs, expect consolidation before resolution",
            direction="neutral",
            strength=0.5,
            data_points=1,
            raw_data={"in_bpr": True},
        )

    def _gap_status_card(
        self, bar: dict, session_ctx: dict, tape_row: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """NDOG/NWOG gap fill progress from snapshot data."""
        snapshot = tape_row.get("snapshot_json") or {}
        if isinstance(snapshot, str):
            try:
                snapshot = _json.loads(snapshot)
            except (_json.JSONDecodeError, TypeError):
                snapshot = {}

        fvg_data = snapshot.get("fvg_detection") or {}
        ndog = fvg_data.get("ndog") or {}
        nwog = fvg_data.get("nwog") or {}

        gap = ndog if ndog.get("status") else nwog
        if not gap or not gap.get("status"):
            return None

        status = gap.get("status", "")
        gap_dir = gap.get("direction", "")
        fill_pct = gap.get("fill_pct", 0)
        gap_type = gap.get("gap_type", "NDOG")

        if status == "filled":
            return None  # Already filled, no edge

        if status == "unfilled" and fill_pct < 0.3:
            # Gap mostly unfilled — magnet effect
            if gap_dir == "gap_up" and signal_dir == "SHORT":
                direction, strength = "bearish", 0.6
                obs = f"{gap_type} gap up {fill_pct:.0%} filled — gap fill magnet supports SHORT"
            elif gap_dir == "gap_down" and signal_dir == "LONG":
                direction, strength = "bullish", 0.6
                obs = f"{gap_type} gap down {fill_pct:.0%} filled — gap fill magnet supports LONG"
            elif gap_dir == "gap_up" and signal_dir == "LONG":
                direction, strength = "neutral", 0.45
                obs = f"{gap_type} gap up {fill_pct:.0%} filled — LONG running from gap fill target"
            else:
                direction, strength = "neutral", 0.45
                obs = f"{gap_type} gap down {fill_pct:.0%} filled — SHORT running from gap fill target"
        else:
            direction, strength = "neutral", 0.4
            obs = f"{gap_type} {status} ({fill_pct:.0%} filled)"

        return EvidenceCard(
            card_id="ict_gap_status",
            source="expert_ict",
            layer="probabilistic",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"gap_type": gap_type, "status": status, "fill_pct": fill_pct, "direction": gap_dir},
        )

    def _htf_fvg_card(
        self, bar: dict, session_ctx: dict, tape_row: dict, signal_dir: str
    ) -> EvidenceCard | None:
        """15-min FVG confluence — higher-timeframe support/resistance."""
        fvg_bull_15m = _get_bool(bar, "fvg_bull_15m")
        fvg_bear_15m = _get_bool(bar, "fvg_bear_15m")

        if not fvg_bull_15m and not fvg_bear_15m:
            return None

        if fvg_bull_15m and signal_dir == "LONG":
            direction, strength = "bullish", 0.7
            obs = "Price in 15-min bullish FVG — higher-TF support, strongly aligned with LONG"
        elif fvg_bull_15m and signal_dir == "SHORT":
            direction, strength = "bullish", 0.35
            obs = "Price in 15-min bullish FVG — SHORT entering HTF support zone"
        elif fvg_bear_15m and signal_dir == "SHORT":
            direction, strength = "bearish", 0.7
            obs = "Price in 15-min bearish FVG — higher-TF resistance, strongly aligned with SHORT"
        elif fvg_bear_15m and signal_dir == "LONG":
            direction, strength = "bearish", 0.35
            obs = "Price in 15-min bearish FVG — LONG entering HTF resistance zone"
        else:
            return None

        return EvidenceCard(
            card_id="ict_htf_fvg",
            source="expert_ict",
            layer="certainty",
            observation=obs,
            direction=direction,
            strength=strength,
            data_points=1,
            raw_data={"fvg_bull_15m": fvg_bull_15m, "fvg_bear_15m": fvg_bear_15m},
        )


def _get_bool(bar: dict, key: str) -> bool:
    v = bar.get(key)
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    try:
        return bool(v)
    except (TypeError, ValueError):
        return False
