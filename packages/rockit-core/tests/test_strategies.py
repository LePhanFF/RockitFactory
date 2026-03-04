"""Tests for strategy foundation: day type classification, signals, and confidence scoring."""

import pandas as pd

from rockit_core.strategies.day_confidence import DayTypeConfidence, DayTypeConfidenceScorer
from rockit_core.strategies.day_type import (
    DayType,
    TrendStrength,
    classify_day_type,
    classify_session_day_type,
    classify_trend_strength,
)
from rockit_core.strategies.signal import Signal


# --- TrendStrength classification ---


def test_classify_trend_strength_weak():
    assert classify_trend_strength(0.3) == TrendStrength.WEAK


def test_classify_trend_strength_moderate():
    assert classify_trend_strength(0.7) == TrendStrength.MODERATE


def test_classify_trend_strength_strong():
    assert classify_trend_strength(1.5) == TrendStrength.STRONG


def test_classify_trend_strength_super():
    assert classify_trend_strength(2.5) == TrendStrength.SUPER


# --- DayType classification ---


def test_classify_day_type_neutral():
    # Small extension, not inside IB
    dt = classify_day_type(15000, 14900, 14960, 'BULL', TrendStrength.WEAK)
    # Extension = (14960 - 14950) / 100 = 0.1, weak strength -> NEUTRAL or B_DAY
    # 0.1 < 0.2 -> B_DAY
    assert dt == DayType.B_DAY


def test_classify_day_type_trend_up():
    # Strong extension above IB
    dt = classify_day_type(15000, 14900, 15200, 'BULL', TrendStrength.STRONG)
    # Extension = (15200 - 14950) / 100 = 2.5, but strength is STRONG not SUPER
    # extension > 1.0 -> TREND_UP
    assert dt == DayType.TREND_UP


def test_classify_day_type_super_trend():
    dt = classify_day_type(15000, 14900, 15300, 'BULL', TrendStrength.SUPER)
    assert dt == DayType.SUPER_TREND_UP


def test_classify_day_type_p_day():
    # Moderate extension
    dt = classify_day_type(15000, 14900, 15030, 'BULL', TrendStrength.MODERATE)
    # Extension = (15030 - 14950) / 100 = 0.8, moderate strength
    # 0.5 < 0.8 < 1.0 -> P_DAY
    assert dt == DayType.P_DAY


def test_classify_day_type_b_day_inside():
    dt = classify_day_type(15000, 14900, 14950, 'INSIDE', TrendStrength.WEAK)
    assert dt == DayType.B_DAY


# --- Session classification ---


def test_classify_session_day_type():
    # Extension = (15250 - 14950) / 100 = 3.0 → SUPER strength → SUPER_TREND_UP
    dt, strength = classify_session_day_type(15000, 14900, 15250)
    assert dt == DayType.SUPER_TREND_UP
    assert strength == TrendStrength.SUPER


# --- Signal ---


def test_signal_risk_points():
    from datetime import datetime
    sig = Signal(
        timestamp=datetime.now(),
        direction='LONG',
        entry_price=15100.0,
        stop_price=15080.0,
        target_price=15150.0,
        strategy_name='test',
        setup_type='test',
        day_type='trend_up',
    )
    assert sig.risk_points == 20.0
    assert sig.reward_points == 50.0
    assert sig.risk_reward_ratio == 2.5


def test_signal_risk_reward_zero_risk():
    from datetime import datetime
    sig = Signal(
        timestamp=datetime.now(),
        direction='LONG',
        entry_price=15100.0,
        stop_price=15100.0,
        target_price=15150.0,
        strategy_name='test',
        setup_type='test',
        day_type='neutral',
    )
    assert sig.risk_reward_ratio == 0.0


# --- DayTypeConfidenceScorer ---


def test_confidence_scorer_initial():
    scorer = DayTypeConfidenceScorer()
    scorer.on_session_start(15000, 14900, 100, 50)

    # Not enough bars yet -> neutral
    bar = pd.Series({'close': 15010, 'high': 15020, 'low': 14990})
    conf = scorer.update(bar, 0)
    assert conf.neutral == 0.5  # default when < 5 bars


def test_confidence_scorer_trend_bull():
    scorer = DayTypeConfidenceScorer()
    scorer.on_session_start(15000, 14900, 100, 50)

    # Simulate trending bars above IB
    for i in range(20):
        price = 15050 + i * 10  # Steadily climbing
        bar = pd.Series({'close': price, 'high': price + 5, 'low': price - 5})
        conf = scorer.update(bar, i)

    # After 20 trending bars above IB, trend_bull confidence should be high
    assert conf.trend_bull > 0.5


def test_confidence_scorer_b_day():
    scorer = DayTypeConfidenceScorer()
    scorer.on_session_start(15000, 14900, 100, 50)

    # Simulate bars inside IB
    for i in range(20):
        price = 14950 + (i % 5) * 5 - 10  # Oscillating inside IB
        price = max(14905, min(14995, price))  # Keep inside
        bar = pd.Series({'close': price, 'high': price + 3, 'low': price - 3})
        conf = scorer.update(bar, i)

    # After 20 inside bars, b_day confidence should be high
    assert conf.b_day > 0.3
