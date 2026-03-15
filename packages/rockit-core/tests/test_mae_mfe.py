"""Tests for MAE/MFE tracking in Trade, OpenPosition, and extended metrics."""

from datetime import datetime

import numpy as np
import pytest

from rockit_core.engine.position import OpenPosition
from rockit_core.engine.trade import Trade
from rockit_core.reporting.metrics import (
    compute_metrics,
    _serial_correlation,
    _max_cluster_loss,
    _drawdown_duration_sessions,
    _wr_by_entry_hour,
)


# --- OpenPosition MAE/MFE Tracking ---


class TestOpenPositionExcursions:
    def _make_pos(self, direction='LONG', entry=100.0, stop=90.0, target=120.0):
        return OpenPosition(
            direction=direction, entry_price=entry, stop_price=stop,
            target_price=target, contracts=1, entry_time=datetime(2025, 1, 15, 10, 35),
            strategy_name='test', setup_type='test', day_type='neutral',
            trend_strength='moderate', session_date='2025-01-15',
        )

    def test_initial_mae_mfe_at_entry(self):
        pos = self._make_pos(entry=100.0)
        assert pos.mae_price == 100.0
        assert pos.mfe_price == 100.0

    def test_long_mae_updates_on_lower_low(self):
        pos = self._make_pos('LONG', entry=100.0)
        pos.bars_held = 1
        pos.update_excursions(95.0, 102.0)
        assert pos.mae_price == 95.0
        assert pos.mae_bar == 1

    def test_long_mfe_updates_on_higher_high(self):
        pos = self._make_pos('LONG', entry=100.0)
        pos.bars_held = 1
        pos.update_excursions(99.0, 110.0)
        assert pos.mfe_price == 110.0
        assert pos.mfe_bar == 1

    def test_long_mae_does_not_update_on_higher_low(self):
        pos = self._make_pos('LONG', entry=100.0)
        pos.bars_held = 1
        pos.update_excursions(95.0, 102.0)  # MAE = 95
        pos.bars_held = 2
        pos.update_excursions(97.0, 103.0)  # Low is higher, MAE stays 95
        assert pos.mae_price == 95.0
        assert pos.mae_bar == 1

    def test_short_mae_updates_on_higher_high(self):
        pos = self._make_pos('SHORT', entry=100.0, stop=110.0, target=80.0)
        pos.bars_held = 1
        pos.update_excursions(98.0, 105.0)
        assert pos.mae_price == 105.0  # Worst for SHORT = highest high

    def test_short_mfe_updates_on_lower_low(self):
        pos = self._make_pos('SHORT', entry=100.0, stop=110.0, target=80.0)
        pos.bars_held = 1
        pos.update_excursions(88.0, 99.0)
        assert pos.mfe_price == 88.0  # Best for SHORT = lowest low

    def test_multi_bar_tracking(self):
        pos = self._make_pos('LONG', entry=100.0)
        # Bar 1: slight pullback
        pos.bars_held = 1
        pos.update_excursions(98.0, 101.0)
        # Bar 2: big drop (MAE)
        pos.bars_held = 2
        pos.update_excursions(92.0, 99.0)
        # Bar 3: recovery and new high (MFE)
        pos.bars_held = 3
        pos.update_excursions(99.0, 115.0)
        # Bar 4: slight pullback again
        pos.bars_held = 4
        pos.update_excursions(105.0, 112.0)

        assert pos.mae_price == 92.0
        assert pos.mae_bar == 2
        assert pos.mfe_price == 115.0
        assert pos.mfe_bar == 3


# --- Trade MAE/MFE Computed Properties ---


class TestTradeMAEMFE:
    def _make_trade(self, direction='LONG', entry=100.0, exit=110.0,
                    stop=90.0, target=120.0, mae=95.0, mfe=115.0,
                    net_pnl=200.0, entry_time=None):
        return Trade(
            direction=direction, entry_price=entry, exit_price=exit,
            stop_price=stop, target_price=target,
            mae_price=mae, mfe_price=mfe,
            mae_bar=2, mfe_bar=5,
            net_pnl=net_pnl, gross_pnl=net_pnl + 10,
            contracts=1, bars_held=10, exit_reason='TARGET',
            strategy_name='test', session_date='2025-01-15',
            entry_time=entry_time or datetime(2025, 1, 15, 10, 35),
        )

    def test_long_mae_points(self):
        t = self._make_trade('LONG', entry=100.0, mae=95.0)
        assert t.mae_points == 5.0

    def test_long_mfe_points(self):
        t = self._make_trade('LONG', entry=100.0, mfe=115.0)
        assert t.mfe_points == 15.0

    def test_short_mae_points(self):
        t = self._make_trade('SHORT', entry=100.0, exit=90.0,
                             stop=110.0, target=80.0, mae=105.0, mfe=88.0)
        assert t.mae_points == 5.0  # 105 - 100

    def test_short_mfe_points(self):
        t = self._make_trade('SHORT', entry=100.0, exit=90.0,
                             stop=110.0, target=80.0, mae=105.0, mfe=88.0)
        assert t.mfe_points == 12.0  # 100 - 88

    def test_mae_pct_of_stop(self):
        t = self._make_trade('LONG', entry=100.0, stop=90.0, mae=95.0)
        # risk = 10, mae = 5pts, pct = 0.5
        assert t.mae_pct_of_stop == pytest.approx(0.5)

    def test_mfe_pct_of_target(self):
        t = self._make_trade('LONG', entry=100.0, target=120.0, mfe=115.0)
        # reward = 20, mfe = 15pts, pct = 0.75
        assert t.mfe_pct_of_target == pytest.approx(0.75)

    def test_entry_efficiency_good_entry(self):
        # MFE=15, MAE=2 → (15-2)/(15+2) = 0.765
        t = self._make_trade('LONG', entry=100.0, mae=98.0, mfe=115.0)
        assert t.entry_efficiency == pytest.approx(13.0 / 17.0, abs=0.01)

    def test_entry_efficiency_bad_entry(self):
        # MFE=2, MAE=15 → (2-15)/(2+15) = -0.765
        t = self._make_trade('LONG', entry=100.0, mae=85.0, mfe=102.0)
        assert t.entry_efficiency < 0

    def test_heat(self):
        # risk=10, mae=5 → heat = 0.5
        t = self._make_trade('LONG', entry=100.0, stop=90.0, mae=95.0)
        assert t.heat == pytest.approx(0.5)

    def test_heat_exceeded_stop(self):
        # risk=10, mae=12 → heat = 1.2 (went past stop without fill)
        t = self._make_trade('LONG', entry=100.0, stop=90.0, mae=88.0)
        assert t.heat == pytest.approx(1.2)

    def test_entry_hour(self):
        t = self._make_trade(entry_time=datetime(2025, 1, 15, 11, 22))
        assert t.entry_hour == 11

    def test_entry_hour_none(self):
        t = self._make_trade()
        t.entry_time = None
        assert t.entry_hour is None


# --- Extended Metrics ---


def _make_trades_for_metrics():
    """Create a small list of trades with known MAE/MFE for testing."""
    trades = [
        Trade(direction='LONG', entry_price=100, exit_price=110, stop_price=90, target_price=120,
              mae_price=95, mfe_price=115, mae_bar=2, mfe_bar=5,
              net_pnl=200, gross_pnl=210, contracts=1, bars_held=10,
              exit_reason='TARGET', strategy_name='test', session_date='2025-01-15',
              entry_time=datetime(2025, 1, 15, 10, 35)),
        Trade(direction='LONG', entry_price=100, exit_price=95, stop_price=90, target_price=120,
              mae_price=88, mfe_price=103, mae_bar=4, mfe_bar=1,
              net_pnl=-100, gross_pnl=-90, contracts=1, bars_held=8,
              exit_reason='STOP', strategy_name='test', session_date='2025-01-15',
              entry_time=datetime(2025, 1, 15, 11, 10)),
        Trade(direction='SHORT', entry_price=200, exit_price=190, stop_price=210, target_price=180,
              mae_price=205, mfe_price=185, mae_bar=1, mfe_bar=6,
              net_pnl=150, gross_pnl=160, contracts=1, bars_held=12,
              exit_reason='TARGET', strategy_name='test', session_date='2025-01-16',
              entry_time=datetime(2025, 1, 16, 10, 45)),
        Trade(direction='LONG', entry_price=100, exit_price=98, stop_price=90, target_price=120,
              mae_price=93, mfe_price=108, mae_bar=3, mfe_bar=2,
              net_pnl=-40, gross_pnl=-30, contracts=1, bars_held=6,
              exit_reason='EOD', strategy_name='test', session_date='2025-01-16',
              entry_time=datetime(2025, 1, 16, 14, 0)),
    ]
    return trades


class TestExtendedMetrics:
    def test_metrics_include_mae_mfe_fields(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert 'avg_mae_pct_of_stop' in m
        assert 'avg_mfe_pct_of_target' in m
        assert 'edge_ratio' in m

    def test_edge_ratio_positive(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert m['edge_ratio'] > 0

    def test_stop_out_rate(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        # 1 out of 4 trades = STOP
        assert m['stop_out_rate'] == 25.0

    def test_target_hit_rate(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        # 2 out of 4 trades = TARGET
        assert m['target_hit_rate'] == 50.0

    def test_r_multiple_median(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert isinstance(m['r_multiple_median'], float)

    def test_recovery_factor(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert 'recovery_factor' in m

    def test_kelly_fraction(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert 'kelly_fraction' in m
        # 50% WR with positive payoff → Kelly should be positive
        assert m['kelly_fraction'] > 0

    def test_ulcer_index(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert m['ulcer_index'] >= 0

    def test_serial_correlation_range(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert -1.0 <= m['serial_correlation'] <= 1.0

    def test_session_win_rate(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        # Session 1: +200 -100 = +100 (win). Session 2: +150 -40 = +110 (win)
        assert m['session_win_rate'] == 100.0

    def test_wr_by_entry_hour(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert isinstance(m['wr_by_entry_hour'], dict)
        assert 10 in m['wr_by_entry_hour']  # Two trades at hour 10

    def test_daily_pnl_volatility(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert m['daily_pnl_volatility'] >= 0

    def test_empty_trades_has_extended_metrics(self):
        m = compute_metrics([])
        assert m['edge_ratio'] == 0.0
        assert m['kelly_fraction'] == 0.0
        assert m['serial_correlation'] == 0.0
        assert m['wr_by_entry_hour'] == {}

    def test_gain_to_pain_ratio(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert m['gain_to_pain_ratio'] > 0

    def test_max_cluster_loss(self):
        trades = _make_trades_for_metrics()
        m = compute_metrics(trades)
        assert m['max_cluster_loss'] <= 0  # Loss is negative
        assert m['max_cluster_loss_count'] >= 0


# --- Helper Function Unit Tests ---


class TestSerialCorrelation:
    def test_random_returns(self):
        np.random.seed(42)
        returns = list(np.random.randn(100))
        sc = _serial_correlation(returns)
        assert -0.3 < sc < 0.3  # Random → near zero

    def test_alternating_returns(self):
        returns = [100, -100] * 20
        sc = _serial_correlation(returns)
        assert sc < -0.5  # Alternating → negative

    def test_clustered_returns(self):
        returns = [100] * 10 + [-100] * 10
        sc = _serial_correlation(returns)
        assert sc > 0.3  # Clustered → positive

    def test_too_few_returns(self):
        assert _serial_correlation([100]) == 0.0
        assert _serial_correlation([100, -100]) == 0.0


class TestMaxClusterLoss:
    def test_single_cluster(self):
        trades = [
            Trade(net_pnl=100, session_date='d1'),
            Trade(net_pnl=-50, session_date='d1'),
            Trade(net_pnl=-30, session_date='d1'),
            Trade(net_pnl=-20, session_date='d1'),
            Trade(net_pnl=200, session_date='d2'),
        ]
        loss, count = _max_cluster_loss(trades)
        assert loss == -100  # -50 + -30 + -20
        assert count == 3

    def test_no_losses(self):
        trades = [Trade(net_pnl=100), Trade(net_pnl=200)]
        loss, count = _max_cluster_loss(trades)
        assert loss == 0.0
        assert count == 0


class TestWRByEntryHour:
    def test_basic(self):
        trades = [
            Trade(net_pnl=100, entry_time=datetime(2025, 1, 1, 10, 30)),
            Trade(net_pnl=-50, entry_time=datetime(2025, 1, 1, 10, 45)),
            Trade(net_pnl=200, entry_time=datetime(2025, 1, 1, 11, 15)),
        ]
        wr = _wr_by_entry_hour(trades)
        assert wr[10] == 50.0  # 1/2
        assert wr[11] == 100.0  # 1/1
