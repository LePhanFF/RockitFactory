# 10A — Domain Expert System: Architecture & Implementation Plan

> **Purpose**: Design a pluggable expert domain system that provides specialized market analysis, feeds into the agent pipeline, and supports ad-hoc user queries like "I want to short NQ at 21,500 — is this a good idea?"
>
> **Principle**: Experts provide facts. Analysts interpret. Lawyers argue. The judge decides. Each role is separate.
>
> **Status**: Planning — extracted from 10-Next-steps.md Expert Domain Refactoring section + expanded with ad-hoc query architecture
>
> **Date**: 2026-03-12

---

## The Problem Today

### Information Loss

The current agent pipeline reduces 38 deterministic modules (9,200 LOC, <10ms) down to **9 evidence cards** through just 2 observers:

```
38 deterministic modules
    ↓
ProfileObserver → 4 cards (TPO shape, VA position, POC position, poor extremes)
MomentumObserver → 5 cards (DPOC regime, trend strength, wick traps, IB extension, bias alignment)
    ↓
Orchestrator sees 9 cards → TAKE/SKIP/REDUCE_SIZE
```

**What gets lost**: Balance classification, acceptance tests, CRI sub-components, FVG lifecycle, prior VA models, edge fade zones, regime context, premarket levels, level confluence, trendline structure, cross-instrument divergence.

That is like asking lawyers to try a case where only 2 of 15 expert witnesses were allowed to testify.

### No Ad-Hoc Query Support

A user cannot currently ask: *"I want to short NQ at 21,500 — what do the experts say?"*

The pipeline only evaluates strategy signals. There is no way to consult experts on an arbitrary price level or trade idea.

---

## 1. Expert Domains

### Overview: 10 Domains

| # | Domain | Framework | Modules | Cards | Status | Priority |
|---|--------|-----------|---------|-------|--------|----------|
| 1 | **Profile** | Dalton Auction / Market Profile | 3 | 3-4 | Existing modules | HIGH |
| 2 | **Order Flow** | Volume/Delta/CVD analysis | 4 | 3-4 | Existing modules | HIGH |
| 3 | **Structure** | IB/Day Type/CRI/Acceptance | 5 | 3-5 | Existing modules | HIGH |
| 4 | **Level** | Key levels + confluence scoring | 5 | 3-5 | Partial — needs confluence algo | HIGH |
| 5 | **Momentum** | Trend/DPOC/EMA/Bias | 4 | 2-3 | Existing modules | HIGH |
| 6 | **Regime** | ATR/VIX/Weekly/Consecutive days | 2 | 2-3 | Existing modules | HIGH |
| 7 | **ICT / Liquidity** | Sweeps, FVG, NWOG/NDOG, Judas Swing | 3 | 3-4 | Partial — needs sweep detection | MEDIUM |
| 8 | **Multi-Timeframe** | 5m/15m/1H/4H swing + trend alignment | 2 (NEW) | 2-3 | NEW — needs swing detection | MEDIUM |
| 9 | **Swing / Trendline** | Swing points, trendlines, 3rd touch | 2 (NEW) | 2-3 | NEW — needs trendline module | MEDIUM |
| 10 | **Cross-Instrument** | SMT, ES/NQ/YM correlation | 2 | 1-2 | Existing basic modules | LOW |

**Total cards**: ~26-36 (vs current 9). Each expert runs independently, all in <10ms.

---

## 2. Per-Domain Implementation

### Domain 1: Profile Expert (Dalton Auction / Market Profile)

**Framework**: Dalton Market Profile — TPO distribution, Value Area dynamics, auction theory.

**Source modules**: `tpo_profile.py`, `volume_profile.py`, `balance_classification.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `profile_shape_alignment` | TPO shape + signal direction alignment | "b-shape (value building at bottom) aligned with LONG — bullish structural tell" |
| `profile_va_dynamics` | VA position, migration, width, acceptance | "Price above VAH, VA widening upward, 30-min acceptance outside — initiative, bullish" |
| `profile_balance_state` | Balance type, skew, morph detection | "Balance B-Day, 70% bearish skew, seam at 21,450 — fade upper probe" |
| `profile_structural_tells` | Poor highs/lows, single prints, excess | "Poor high + 3 single prints above POC — unfinished business, upside target" |

**Improvement**: Current ProfileObserver looks at shape, VA, POC, poor extremes in isolation. New expert cross-references them (shape + balance type + acceptance = richer signal). Balance classification output is currently **invisible** to agents.

**Ad-hoc query support**: "Is 21,500 inside or outside today's VA? What's the profile shape? Is there a poor high/low near that level?"

---

### Domain 2: Order Flow Expert

**Framework**: Volume Delta, CVD divergence, absorption, institutional footprint.

**Source modules**: `wick_parade.py`, `core_confluences.py`, `intraday_sampling.py`, `volume_profile.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `flow_delta_divergence` | Price vs CVD alignment/divergence | "Price making new high but CVD flat — sellers absorbing, bearish divergence" |
| `flow_wick_traps` | Wick parade pattern + context | "6 bear wicks in 45 min at VAH — sellers repeatedly trapped, support building" |
| `flow_volume_distribution` | Volume concentration pattern | "Volume concentrated at session lows (accumulation) — bullish" |
| `flow_absorption` | Delta absorption at key levels | "Large negative delta at VAH but price holding — absorption, buyers absorbing selling" |

**New computation needed**: CVD divergence detection (track cumulative delta vs price swing highs/lows). Simple function on existing delta data.

**Ad-hoc query support**: "Is there absorption at 21,500? What does delta say about sellers here? Any CVD divergence?"

---

### Domain 3: Structure Expert

**Framework**: IB classification, day type evolution, CRI terrain, acceptance tests.

**Source modules**: `cri.py`, `cri_psychology_voice.py`, `acceptance_test.py`, `ib_location.py`, `decision_engine.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `structure_cri_terrain` | CRI terrain + permission + sub-components | "TERRAIN: TRENDING (breath strong, reclaim confirmed). PERMISSION: FULL_SIZE. Trap risk: LOW" |
| `structure_day_evolution` | Day type + morph status + trend strength | "Morphing Balance → Trend Down. Confidence 75%. Strength: moderate bearish" |
| `structure_ib_extension` | IB extension magnitude + acceptance | "IB extended 1.8× below — 30-min acceptance confirmed. Initiative, not probe" |
| `structure_acceptance` | Pullback type + confidence | "Post-breakout: shallow pullback (didn't recross IBL). Acceptance confidence: 0.82" |
| `structure_time_context` | Time-of-day signal relevance | "Signal at 12:30 — late session. 84% of PnL comes from 10:00 hour" |

**Improvement**: CRI gate currently emits 1 binary card (pass/fail). New expert exposes sub-components so Advocate can argue "breath is strong even though trap is moderate" and Skeptic can counter "but reclaim is weak."

**Ad-hoc query support**: "Is IB extended? What day type are we in? Is CRI terrain favorable for a short? Has acceptance confirmed below IBL?"

---

### Domain 4: Level Expert (Highest Value New Domain)

**Framework**: Key level identification + confluence scoring. Covers prior VA, London/Asia, FVGs, naked levels.

**Source modules**: `globex_va_analysis.py`, `premarket.py`, `fvg_detection.py`, `ninety_min_pd_arrays.py`, `core_confluences.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `level_confluence_zone` | Cluster of levels near price/entry | "3 levels within 15 pts: London High (21,540), Prior VAH (21,535), unfilled bearish FVG (21,542). HIGH confluence resistance" |
| `level_prior_va_model` | Prior VA model + gap status | "Model A (failed auction above). 80P confidence: 72%" |
| `level_fvg_proximity` | Nearest unfilled FVG + respect rate | "Unfilled 15-min bearish FVG at 21,480. 3 of 4 prior FVGs in this zone respected (75%)" |
| `level_premarket_context` | London/Asia/overnight levels + gap | "London Low swept by 12 pts and rejected. ON range: 120 pts (wide). Gap: -45 pts (bearish)" |
| `level_naked_targets` | Untested significant levels | "PDH (21,620) untested — liquidity resting. Prior poor high at 21,615" |

**New computation needed**: Level confluence scoring algorithm:
```python
def score_level_confluence(entry_price: float, levels: list[dict], atr: float) -> dict:
    """Score how many significant levels cluster near the entry price.

    levels: [{"name": str, "price": float, "weight": float}]
        weight: 1.0 = major (PDH/PDL, London H/L, Prior VAH/VAL)
                0.7 = moderate (VWAP, unfilled FVG, 90-min array)
                0.5 = minor (EMA, ON range edge)
    """
    proximity = max(atr * 0.25, 10.0)
    nearby = [l for l in levels if abs(l["price"] - entry_price) <= proximity]
    weighted_score = sum(l["weight"] for l in nearby)
    confluence_score = min(weighted_score / 3.0, 1.0)
    # Determine support vs resistance
    support_levels = [l for l in nearby if l["price"] <= entry_price]
    resistance_levels = [l for l in nearby if l["price"] > entry_price]
    cluster_dir = "support" if len(support_levels) > len(resistance_levels) else "resistance"
    return {
        "confluence_score": confluence_score,
        "levels_within_proximity": len(nearby),
        "nearest_level": min(nearby, key=lambda l: abs(l["price"] - entry_price)) if nearby else None,
        "cluster_direction": cluster_dir,
        "level_names": [l["name"] for l in nearby],
    }
```

**Ad-hoc query support**: "What levels are near 21,500? Is there confluence? What FVGs are nearby? Is prior VAH here?"

**This is the #1 priority new domain** — level confluence is the most impactful missing signal. The user draws levels and looks for clusters — the system sees none of this today.

---

### Domain 5: Momentum Expert

**Framework**: Trend direction, DPOC migration velocity, EMA alignment, bias composite.

**Source modules**: `dpoc_migration.py`, `dalton.py`, `decision_engine.py`, `core_confluences.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `momentum_trend_regime` | Trend direction + EMA alignment + ADX | "Strong bullish: EMA20 > EMA50, both rising, ADX 32. Aligned with LONG" |
| `momentum_dpoc_velocity` | DPOC migration + velocity + exhaustion | "DPOC up 25 pts in 60 min (fast). BUT decelerating — last 30 min only +5 pts. Exhaustion risk" |
| `momentum_bias_composite` | Multi-vote bias + alignment | "Bias: Bullish (4/5 votes). EMA20>50 [2x], prior session [1x], price>VWAP [1x]" |

**Improvement**: Current MomentumObserver misses DPOC velocity and exhaustion — the most actionable tape reading signals.

**Ad-hoc query support**: "Is the trend still strong or exhausting? What's DPOC doing? Is bias aligned with a short here?"

---

### Domain 6: Regime Expert

**Framework**: Macro context — volatility regime, VIX, weekly structure, consecutive balance days.

**Source modules**: `regime_context.py`, `vix_regime.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `regime_volatility` | ATR regime + VIX + implications | "ATR HIGH (280 pts, 90th pctl). VIX: 22.5 (elevated). Wide stops needed, reduce size" |
| `regime_pattern` | Consecutive balance + weekly + prior session | "3 consecutive balance days — breakout probability elevated. Prior: Trend Down" |
| `regime_sizing_guidance` | Regime-based sizing recommendation | "High vol + 3rd balance day = REDUCE_SIZE. 4th balance day breaks out 68% of the time" |

**Ad-hoc query support**: "What's the vol regime? Is this a good environment for mean reversion? How many balance days in a row?"

---

### Domain 7: ICT / Liquidity Expert (NEW)

**Framework**: Inner Circle Trader concepts — liquidity sweeps, Fair Value Gaps, Judas Swing, NWOG/NDOG, buy-side/sell-side liquidity.

**Source modules**: `fvg_detection.py`, `premarket.py`, `or_reversal.py` (sweep detection)

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `ict_liquidity_sweep` | Sweep of key level + reversal | "London High swept by 8 pts, rejected with bear engulfing. Sell-side liquidity taken — bearish" |
| `ict_fvg_imbalance` | Active FVGs + imbalance zones | "3 unfilled bearish FVGs above price (21,480, 21,520, 21,560). Price in discount zone relative to daily range" |
| `ict_gap_fill_thesis` | NWOG/NDOG fill probability | "NDOG: -35pt gap. VWAP supports fill. 30-min acceptance 40% on fill side. Fill probability: HIGH" |
| `ict_judas_swing` | False breakout + reversal pattern | "OR high swept, failed within 3 bars, reversing below OR low. Classic Judas Swing — SHORT bias confirmed" |

**New computation needed**:
- Liquidity sweep detection: price takes a key level (London H/L, PDH/PDL, session H/L) by N pts, then reverses within M bars
- Buy-side/sell-side liquidity mapping: cluster of equal highs/lows = resting liquidity
- NWOG/NDOG computation (partially exists)

**Ad-hoc query support**: "Was there a liquidity sweep today? Any Judas Swing? What FVGs are above/below 21,500?"

---

### Domain 8: Multi-Timeframe Analysis Expert (NEW)

**Framework**: Multi-timeframe trend alignment — is the 5m, 15m, 1H, 4H all agreeing?

**Source modules**: (NEW) `mtf_analysis.py` — compute from 1-min bars by resampling

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `mtf_trend_alignment` | Trend direction per timeframe + alignment | "5m: bearish, 15m: bearish, 1H: neutral, 4H: bullish. MIXED — 2 bearish, 1 neutral, 1 bullish. No clear alignment" |
| `mtf_ema_stack` | EMA20/50 position per timeframe | "15m: price < EMA20 < EMA50 (bearish stack). 1H: price > EMA20, EMA20 < EMA50 (transitional)" |
| `mtf_key_level_confluence` | Levels from different timeframes clustering | "1H resistance at 21,520 + 4H EMA50 at 21,530 + daily FVG at 21,540. Multi-TF resistance zone" |

**New computation needed**:
- Resample 1-min bars to 5m, 15m, 1H, 4H
- Compute EMA20/EMA50 per timeframe
- Classify trend per timeframe (bullish/bearish/neutral based on EMA alignment)
- Score alignment (all agree = strong, mixed = weak)

**Ad-hoc query support**: "Are higher timeframes aligned with a short? What's the 1H trend? Is 4H EMA50 near my level?"

---

### Domain 9: Swing / Trendline Expert (NEW)

**Framework**: Price structure — swing highs/lows, trendline detection, 3rd touch signals.

**Source modules**: (NEW) `swing_detection.py`, (NEW) `trendline_detection.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `swing_structure` | Current HH/HL/LH/LL sequence | "15m: HH, HL, HH, HL — confirmed uptrend. Last swing low: 21,380. Break level: 21,380" |
| `trendline_3rd_touch` | Trendline approaching/confirmed | "3rd touch of 15m descending trendline at 21,490. Rejection score: 0.7. Historical: 64% bounce rate" |
| `trendline_confluence` | Trendline + level intersection | "Descending trendline 3rd touch AT London Low (21,350) — double confluence. HIGH conviction" |

**New computation needed**:
- Swing detection: causal rolling window (left=5, right=2 for 5-min, left=3, right=1 for 15-min). No lookahead.
- Trendline fitting: iterative swing-to-swing connection (wick-based, not close-based). Track touch count.
- 3rd touch detection: alert when price approaches a trendline with 2+ prior touches

**Ad-hoc query support**: "Is there a trendline near 21,500? How many touches? Is the swing structure bullish or bearish?"

---

### Domain 10: Cross-Instrument Expert

**Framework**: SMT divergence, ES/NQ/YM relative strength, cross-instrument confirmation.

**Source modules**: `cross_market.py`, `smt_detection.py`

**Evidence cards**:

| Card ID | What It Captures | Example |
|---------|-----------------|---------|
| `cross_smt_divergence` | SMT divergence across instruments | "NQ new high but ES did not confirm (15m). Bearish SMT divergence" |
| `cross_relative_strength` | Which instrument leads/lags | "NQ leading ES by 0.3%. YM lagging both. NQ leadership = trend continuation likely" |

**Requires**: Multi-instrument data loader (ES + YM alongside NQ). Lowest priority.

**Ad-hoc query support**: "Is ES confirming NQ's move? Any SMT divergence?"

---

## 3. Plugging Experts Into the Framework

### Current Architecture

```
Signal fires
    → CRIGateAgent (pass/fail)
    → ProfileObserver (4 cards)
    → MomentumObserver (5 cards)
    → [Optional] LLM Debate (Advocate/Skeptic)
    → DeterministicOrchestrator (TAKE/SKIP/REDUCE_SIZE)
```

### New Architecture

```
Signal fires (or ad-hoc query)
    → CRIGateAgent (pass/fail)
    → Expert Domain Observers (8-10 experts, ~26-36 cards)
        ├── ProfileExpert (3-4 cards)
        ├── OrderFlowExpert (3-4 cards)
        ├── StructureExpert (3-5 cards)
        ├── LevelExpert (3-5 cards)
        ├── MomentumExpert (2-3 cards)
        ├── RegimeExpert (2-3 cards)
        ├── ICTLiquidityExpert (3-4 cards)
        ├── MTFExpert (2-3 cards)
        ├── SwingTrendlineExpert (2-3 cards)
        └── CrossInstrumentExpert (1-2 cards)
    → [Optional] LLM Debate (Advocate/Skeptic argue from richer evidence)
    → DeterministicOrchestrator (deterministic decision)
```

### Implementation: Expert Base Class

Each expert extends the existing `AgentBase` and produces `EvidenceCard` instances:

```python
# packages/rockit-core/src/rockit_core/agents/observers/base_expert.py

from abc import ABC, abstractmethod
from rockit_core.agents.evidence import EvidenceCard

class BaseExpert(ABC):
    """Base class for all domain expert observers."""

    domain: str = ""  # e.g., "profile", "order_flow", "level"

    @abstractmethod
    def observe(
        self,
        signal: dict,
        bar: dict,
        session_context: dict,
        snapshot: dict | None = None,  # raw deterministic snapshot
    ) -> list[EvidenceCard]:
        """Produce evidence cards from domain-specific analysis."""
        ...

    @abstractmethod
    def consult(
        self,
        query: dict,
        session_context: dict,
        snapshot: dict | None = None,
    ) -> list[EvidenceCard]:
        """Answer an ad-hoc query about a price level or trade idea.

        query: {
            "price": 21500.0,
            "direction": "SHORT",
            "question": "Is this a good short level?",
        }
        """
        ...

    def _make_card(self, card_id: str, observation: str, direction: str,
                   strength: float, **kwargs) -> EvidenceCard:
        """Helper to create a card with domain metadata."""
        return EvidenceCard(
            card_id=f"{self.domain}_{card_id}",
            source=f"expert_{self.domain}",
            layer="certainty",  # experts produce facts, not opinions
            observation=observation,
            direction=direction,
            strength=strength,
            raw_data=kwargs.get("raw_data", {}),
            data_points=kwargs.get("data_points", 1),
        )
```

### Pipeline Integration

The `AgentPipeline` accepts a list of observers. Swap old for new:

```python
# Old (current)
pipeline = AgentPipeline(
    observers=[ProfileObserver(), MomentumObserver()],
)

# New (expert domains)
from rockit_core.agents.observers.profile_expert import ProfileExpert
from rockit_core.agents.observers.order_flow_expert import OrderFlowExpert
from rockit_core.agents.observers.structure_expert import StructureExpert
from rockit_core.agents.observers.level_expert import LevelExpert
from rockit_core.agents.observers.momentum_expert import MomentumExpert
from rockit_core.agents.observers.regime_expert import RegimeExpert
from rockit_core.agents.observers.ict_expert import ICTLiquidityExpert
from rockit_core.agents.observers.mtf_expert import MTFExpert
from rockit_core.agents.observers.swing_expert import SwingTrendlineExpert
from rockit_core.agents.observers.cross_instrument_expert import CrossInstrumentExpert

pipeline = AgentPipeline(
    observers=[
        ProfileExpert(),
        OrderFlowExpert(),
        StructureExpert(),
        LevelExpert(),
        MomentumExpert(),
        RegimeExpert(),
        ICTLiquidityExpert(),
        MTFExpert(),
        SwingTrendlineExpert(),
        CrossInstrumentExpert(),
    ],
)
```

**Backward compatible**: Old `ProfileObserver` + `MomentumObserver` still work. New experts are additive. A/B test old vs new.

**Parallelizable**: All experts run independently — pure functions of the snapshot. Can run concurrently.

---

## 4. Ad-Hoc Query System: "I Want to Short at 21,500"

### The Vision

```
User: "I want to short NQ at 21,500. What do the experts say?"

System:
1. Loads current session snapshot (or latest deterministic data)
2. Constructs query: {price: 21500, direction: "SHORT", instrument: "NQ"}
3. Calls each expert's `consult()` method
4. Aggregates evidence cards
5. Runs through Orchestrator (or LLM debate if enabled)
6. Returns structured response
```

### Query Interface

```python
class ExpertConsultation:
    """Ad-hoc query system — consult all experts about a trade idea."""

    def __init__(self, experts: list[BaseExpert], orchestrator=None, llm_client=None):
        self.experts = experts
        self.orchestrator = orchestrator or DeterministicOrchestrator()
        self.llm_client = llm_client

    def consult(
        self,
        price: float,
        direction: str,  # "LONG" or "SHORT"
        instrument: str = "NQ",
        question: str | None = None,
    ) -> ConsultationResult:
        """Consult all experts about a proposed trade.

        Returns:
            ConsultationResult with:
            - expert_cards: all evidence cards from all experts
            - matching_strategies: strategies that would fire near this level
            - confluence_score: how many levels cluster here
            - overall_assessment: FAVORABLE / NEUTRAL / UNFAVORABLE
            - risk_factors: list of warnings
            - reasoning: structured explanation
        """
        # 1. Load current session state
        snapshot = self._load_current_snapshot(instrument)
        session_ctx = self._build_session_context(snapshot)

        query = {
            "price": price,
            "direction": direction,
            "instrument": instrument,
            "question": question or f"Is {direction} at {price} a good trade?",
        }

        # 2. Consult each expert
        all_cards = []
        for expert in self.experts:
            try:
                cards = expert.consult(query, session_ctx, snapshot)
                all_cards.extend(cards)
            except Exception as e:
                logger.warning(f"Expert {expert.domain} failed: {e}")

        # 3. Check for matching strategies
        matching = self._find_matching_strategies(price, direction, session_ctx)

        # 4. Score confluence
        confluence = self._score_level_confluence(price, session_ctx)

        # 5. Aggregate assessment
        bull_score = sum(c.strength for c in all_cards if c.direction == "bullish")
        bear_score = sum(c.strength for c in all_cards if c.direction == "bearish")

        if direction == "SHORT":
            aligned = bear_score
            opposing = bull_score
        else:
            aligned = bull_score
            opposing = bear_score

        if aligned > opposing * 1.5:
            assessment = "FAVORABLE"
        elif opposing > aligned * 1.5:
            assessment = "UNFAVORABLE"
        else:
            assessment = "NEUTRAL"

        # 6. Optional LLM synthesis
        if self.llm_client:
            reasoning = self._llm_synthesize(query, all_cards, matching, confluence)
        else:
            reasoning = self._deterministic_summary(all_cards, matching, confluence)

        return ConsultationResult(
            expert_cards=all_cards,
            matching_strategies=matching,
            confluence=confluence,
            assessment=assessment,
            risk_factors=[c.observation for c in all_cards if c.direction != direction_to_bias(direction)],
            reasoning=reasoning,
        )

    def _find_matching_strategies(self, price, direction, ctx):
        """Check which strategies would fire near this price level."""
        matches = []
        # Check each active strategy's trigger conditions
        # e.g., if price near PDH and direction SHORT → PDH/PDL Failed Auction match
        # if price near IB midpoint and direction LONG → IB Retracement match
        # if price near prior VAL and direction LONG → 80P Rule match
        return matches
```

### Example Output

```
=== EXPERT CONSULTATION: SHORT NQ at 21,500 ===

ASSESSMENT: FAVORABLE (bear evidence 3.2 vs bull evidence 1.4)

MATCHING STRATEGIES:
  ✓ PDH/PDL Failed Auction SHORT — PDH at 21,505, spike stop at 21,515
  ✓ OR Reversal SHORT — OR high at 21,510, within tolerance
  ✗ 80P Rule — price inside VA, not at edge

LEVEL CONFLUENCE (score: 0.83 — HIGH):
  • PDH: 21,505 (5 pts away) — weight 1.0
  • London High: 21,498 (2 pts away) — weight 1.0
  • Unfilled bearish FVG: 21,490-21,510 — weight 0.7
  Total: 3 levels within 15 pts = strong resistance zone

EXPERT EVIDENCE:
  Profile: b-shape forming, VA building below 21,480 — bearish structural tell (0.7)
  Order Flow: CVD divergence — price at highs but delta declining (0.6)
  Structure: IB extended 1.3× above, but acceptance NOT confirmed — could be probe (0.5)
  Level: HIGH confluence resistance at 21,500 — PDH + London High + FVG (0.9)
  Momentum: DPOC migrating up but decelerating — exhaustion risk (0.5)
  Regime: VIX 18.5 (moderate). Normal vol environment (0.3 neutral)
  ICT: London High swept by 12 pts at 9:42, rejected. Sell-side liquidity taken (0.8)
  MTF: 5m bearish, 15m neutral, 1H bullish — mixed alignment (0.4 neutral)
  Swing: 15m HH, HL pattern intact — structure still bullish until 21,380 break (0.6 BULL)
  Cross: ES confirming NQ highs — no SMT divergence (0.3 neutral)

RISK FACTORS:
  ⚠ 15m swing structure still bullish — shorting into uptrend
  ⚠ 1H timeframe bullish — higher TF not aligned
  ⚠ ES confirming — no cross-instrument divergence to support short

RECOMMENDATION:
  The level confluence is strong (PDH + London High + FVG). ICT liquidity sweep
  confirms sell-side taken. However, 15m swing structure is still bullish (HH/HL)
  and 1H is bullish. This is a counter-trend short at a key level — use tight stop
  (spike at 21,515 + 5pt = 21,520) and reduced size. Wait for swing structure break
  at 21,380 for full-size short.
```

### API Integration

```python
# FastAPI endpoint for ad-hoc queries
@router.post("/experts/consult")
async def consult_experts(request: ConsultRequest):
    """Consult all domain experts about a trade idea."""
    result = consultation.consult(
        price=request.price,
        direction=request.direction,
        instrument=request.instrument,
        question=request.question,
    )
    return result.to_dict()

# CLI usage
# uv run python -c "
# from rockit_core.agents.consultation import ExpertConsultation
# ec = ExpertConsultation.default()
# result = ec.consult(price=21500, direction='SHORT')
# print(result.summary())
# "
```

### Dashboard Integration

The RockitUI dashboard can call the `/experts/consult` endpoint:
- User clicks a price level on the chart
- Selects direction (LONG/SHORT)
- Dashboard calls API, renders expert cards as a panel
- Color-coded: green = supporting, red = opposing, gray = neutral
- Shows matching strategies that would fire at this level

---

## 5. Deterministic Module → Expert Domain Mapping

| Module | Expert Domain | Notes |
|--------|--------------|-------|
| `tpo_profile.py` | Profile | TPO shape, distribution |
| `volume_profile.py` | Profile + Level | VA/POC → Profile; HVN/LVN → Level |
| `balance_classification.py` | Profile | Balance type, skew, morph |
| `wick_parade.py` | Order Flow | Wick traps, absorption patterns |
| `core_confluences.py` | Order Flow + Momentum | Delta → Flow; EMA/VWAP → Momentum |
| `intraday_sampling.py` | Order Flow | Volume distribution |
| `cri.py` | Structure | CRI terrain, permission, sub-components |
| `cri_psychology_voice.py` | Structure | Sizing guidance, terrain conflicts |
| `acceptance_test.py` | Structure | Breakout acceptance, pullback type |
| `ib_location.py` | Structure | IB position, ADX, BBands |
| `decision_engine.py` | Structure + Momentum | Day type → Structure; Trend → Momentum |
| `globex_va_analysis.py` | Level | Prior VA model, gap classification |
| `premarket.py` | Level + ICT | London/Asia → Level; Sweep detection → ICT |
| `fvg_detection.py` | Level + ICT | FVG proximity → Level; Imbalance zones → ICT |
| `ninety_min_pd_arrays.py` | Level | 90-min displacement/rebalance zones |
| `dpoc_migration.py` | Momentum | DPOC direction, velocity, exhaustion |
| `dalton.py` | Momentum | Trend analysis, EMA crossover |
| `regime_context.py` | Regime | ATR, consecutive balance, weekly, VIX |
| `vix_regime.py` | Regime | VIX level, regime classification |
| `cross_market.py` | Cross-Instrument | Cross-market correlation |
| `smt_detection.py` | Cross-Instrument | SMT divergence |
| `or_reversal.py` | ICT | OR sweep detection (Judas Swing) |
| `edge_fade.py` | Level | Edge fade zones |
| `va_edge_fade.py` | Level | VA edge proximity |
| `mean_reversion_engine.py` | Momentum | Mean reversion signals |
| `twenty_percent_rule.py` | Structure | IB extension acceptance |
| `tape_context.py` | (meta — feeds all experts) | General tape context |
| `enhanced_reasoning.py` | (meta — feeds LLM) | LLM reasoning prompts |
| `trader_voice.py` | (meta — feeds LLM) | Trader voice for analysis |
| `setup_annotator.py` | (meta — feeds UI) | Setup annotations |
| `playbook_engine.py` | (meta — feeds LLM) | Playbook matching |
| `playbook_engine_v2.py` | (meta — feeds LLM) | Playbook v2 |
| `data_validator.py` | (infra) | Data validation |
| `error_logger.py` | (infra) | Error logging |
| `loader.py` | (infra) | Module loading |
| `config_validator.py` | (infra) | Config validation |
| `schema_validator.py` | (infra) | Schema validation |
| `dataframe_cache.py` | (infra) | Caching |

**Summary**:
- 6 core expert domains consume 26+ modules
- 2 new expert domains (MTF, Swing/Trendline) need new modules
- 1 expert domain (Cross-Instrument) needs enhanced modules
- 6 meta/infra modules are NOT consumed by experts

---

## 6. Implementation Phases

### Phase 1: Core 6 Experts (No New Modules)

**Scope**: Create 6 expert observer classes that consume EXISTING module outputs. Pure reorganization.

**Files**:
1. `agents/observers/base_expert.py` — BaseExpert with `observe()` + `consult()`
2. `agents/observers/profile_expert.py` — Profile Expert
3. `agents/observers/order_flow_expert.py` — Order Flow Expert
4. `agents/observers/structure_expert.py` — Structure Expert
5. `agents/observers/level_expert.py` — Level Expert (with confluence scoring)
6. `agents/observers/momentum_expert.py` — Momentum Expert
7. `agents/observers/regime_expert.py` — Regime Expert
8. Unit tests: 8-12 tests per expert (48-72 new tests)

**Estimated effort**: 2-3 sessions. Each expert ~150-250 lines.

**Validation**: A/B test — old observers (9 cards) vs new experts (~24 cards). Run E baseline (66.5% WR, PF 3.58) must be met or exceeded.

### Phase 2: Ad-Hoc Query System

**Scope**: Build `ExpertConsultation` class + API endpoint + CLI interface.

**Files**:
1. `agents/consultation.py` — ExpertConsultation class
2. `serve/routers/experts.py` — FastAPI endpoints
3. Strategy matching logic (which strategies fire near a given price)
4. Tests

**Estimated effort**: 1-2 sessions.

### Phase 3: ICT Liquidity Expert

**Scope**: Build liquidity sweep detection, Judas Swing identification, NWOG/NDOG tracking.

**New modules needed**:
- `deterministic/modules/liquidity_sweep.py` — sweep detection at key levels
- `deterministic/modules/ndog_computation.py` — daily gap computation

**Estimated effort**: 2 sessions.

### Phase 4: MTF + Swing/Trendline Experts

**Scope**: Build multi-timeframe resampling, swing detection, trendline fitting.

**New modules needed**:
- `deterministic/modules/mtf_analysis.py` — resample + EMA per timeframe
- `deterministic/modules/swing_detection.py` — causal swing high/low detection
- `deterministic/modules/trendline_detection.py` — iterative swing-to-swing trendlines

**Estimated effort**: 3-4 sessions. Trendline detection is the hardest part.

### Phase 5: Cross-Instrument Expert

**Scope**: Enhanced SMT detection, multi-instrument data loading.

**Requires**: ES + YM data loaded alongside NQ.

**Estimated effort**: 2 sessions.

### Phase 6: Benchmark

- **Run G**: Expert Domain observers + LLM debate
- **Run H**: Expert Domain observers + ad-hoc query validation
- Compare Run G vs Run E (expert domains vs old observers)
- False positive rate: do expert domains help SKIP more losing trades?

---

## 7. Key Design Principles

1. **Experts produce FACTS, not opinions**. Every card is backed by deterministic data. The `layer` field is always `"certainty"`. Opinions come from the LLM debate layer.

2. **Each expert runs independently**. No cross-domain dependencies at the observer level. Cross-domain synthesis happens in the Orchestrator (or LLM debate).

3. **Backward compatible**. Old observers still work. New experts are additive. A/B test before switching.

4. **Ad-hoc queries use the SAME experts**. The `consult()` method produces the same card types as `observe()`. Only the trigger changes (user query vs strategy signal).

5. **Card budget**: Each expert produces 2-5 cards. With 10 domains, worst case is 50 cards, typical ~30. The Orchestrator scorecard handles this — it sums bull/bear scores regardless of count. LLM debate benefits from richer evidence.

6. **Parallelizable**: All experts are pure functions of the snapshot. Can run concurrently (<10ms total).

7. **Every expert supports `consult()`**: This is what enables the ad-hoc query system. An expert that can't answer "what do you think about price X?" is incomplete.

---

## 8. Answering the User's Core Question

> "I want to short market at X level, consult experts and agents — is it good or bad?"

**Yes, this is absolutely possible.** Here's how it works:

```
User: "Short NQ at 21,500"
    ↓
ExpertConsultation.consult(price=21500, direction="SHORT")
    ↓
    ├── ProfileExpert.consult() → "b-shape forming, bearish" (0.7 bear)
    ├── OrderFlowExpert.consult() → "CVD diverging bearish" (0.6 bear)
    ├── StructureExpert.consult() → "IB extended but no acceptance" (0.5 neutral)
    ├── LevelExpert.consult() → "HIGH confluence: PDH + London High + FVG" (0.9 bear)
    ├── MomentumExpert.consult() → "DPOC exhausting" (0.5 bear)
    ├── RegimeExpert.consult() → "Normal vol" (0.3 neutral)
    ├── ICTExpert.consult() → "London High swept and rejected" (0.8 bear)
    ├── MTFExpert.consult() → "Mixed — 5m bear, 1H bull" (0.4 neutral)
    ├── SwingExpert.consult() → "15m still HH/HL — counter-trend" (0.6 BULL warning)
    └── CrossExpert.consult() → "ES confirming — no divergence" (0.3 neutral)
    ↓
Strategy Matcher:
    ✓ PDH/PDL Failed Auction SHORT matches (PDH at 21,505)
    ✓ OR Reversal SHORT possible (OR high at 21,510)
    ↓
Orchestrator or LLM Synthesis:
    ASSESSMENT: FAVORABLE with caveats
    • Strong level confluence (PDH + London + FVG)
    • ICT liquidity sweep confirms bearish thesis
    • BUT: 15m swing structure still bullish — reduce size
    • Matching strategy: PDH/PDL Failed Auction with spike stop
```

**Three access paths**:
1. **CLI**: `uv run python -m rockit_core.agents.consultation --price 21500 --dir SHORT`
2. **API**: `POST /experts/consult {price: 21500, direction: "SHORT"}`
3. **Dashboard**: Click price level on chart → select direction → see expert panel

All three use the exact same expert pipeline. Same evidence cards. Same logic. Different UIs.
