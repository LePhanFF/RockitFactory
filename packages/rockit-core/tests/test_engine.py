"""Tests for the backtest engine components."""

from datetime import datetime

import pandas as pd

from rockit_core.config.instruments import NQ, get_instrument
from rockit_core.engine.equity import EquityCurve
from rockit_core.engine.execution import ExecutionModel
from rockit_core.engine.position import OpenPosition, PositionManager
from rockit_core.engine.trade import Trade


# --- Trade tests ---


def test_trade_is_winner():
    trade = Trade(net_pnl=100.0)
    assert trade.is_winner is True
    trade2 = Trade(net_pnl=-50.0)
    assert trade2.is_winner is False


def test_trade_risk_points_long():
    trade = Trade(direction='LONG', entry_price=15100.0, stop_price=15080.0)
    assert trade.risk_points == 20.0


def test_trade_risk_points_short():
    trade = Trade(direction='SHORT', entry_price=15100.0, stop_price=15120.0)
    assert trade.risk_points == 20.0


def test_trade_r_multiple():
    trade = Trade(
        direction='LONG',
        entry_price=15100.0,
        exit_price=15140.0,
        stop_price=15080.0,
    )
    assert trade.r_multiple == 2.0


# --- ExecutionModel tests ---


def test_execution_fill_entry_long():
    model = ExecutionModel(NQ)
    # NQ: tick_size=0.25, slippage=1 tick
    fill = model.fill_entry('LONG', 15100.0)
    assert fill == 15100.25  # Long fills higher


def test_execution_fill_entry_short():
    model = ExecutionModel(NQ)
    fill = model.fill_entry('SHORT', 15100.0)
    assert fill == 15099.75  # Short fills lower


def test_execution_fill_exit_long():
    model = ExecutionModel(NQ)
    fill = model.fill_exit('LONG', 15150.0)
    assert fill == 15149.75  # Selling to close fills lower


def test_execution_gross_pnl():
    model = ExecutionModel(NQ)
    # NQ: point_value=20.0
    pnl = model.calculate_gross_pnl('LONG', 15100.0, 15120.0, 1)
    assert pnl == 400.0  # 20 points * $20/pt


def test_execution_commission_round_trip():
    model = ExecutionModel(NQ)
    # NQ: commission=2.05/side
    comm = model.calculate_commission(1)
    assert comm == 4.10  # 2 sides


def test_execution_net_pnl():
    model = ExecutionModel(NQ)
    gross, comm, slip, net = model.calculate_net_pnl('LONG', 15100.0, 15120.0, 1)
    assert gross == 400.0
    assert comm == 4.10
    assert slip == 10.0  # 1 tick * $5/tick * 2 sides
    assert net == 400.0 - 4.10 - 10.0


def test_execution_calculate_contracts():
    model = ExecutionModel(NQ)
    # Risk $400, stop 20 points, NQ $20/pt = $400/contract = 1 contract
    contracts = model.calculate_contracts(400.0, 20.0)
    assert contracts == 1

    # Risk $400, stop 10 points = $200/contract = 2 contracts
    contracts = model.calculate_contracts(400.0, 10.0)
    assert contracts == 2

    # Risk $400, stop 0 = 0 contracts
    contracts = model.calculate_contracts(400.0, 0.0)
    assert contracts == 0


# --- PositionManager tests ---


def test_position_manager_initial_state():
    mgr = PositionManager(account_size=100_000)
    assert mgr.equity == 100_000
    assert mgr.has_open_positions() is False
    assert mgr.get_open_contracts() == 0


def test_position_manager_add_and_remove():
    mgr = PositionManager()
    pos = OpenPosition(
        direction='LONG', entry_price=15100.0, stop_price=15080.0,
        target_price=15150.0, contracts=1, entry_time=datetime.now(),
        strategy_name='test', setup_type='test', day_type='neutral',
        trend_strength='weak', session_date='2025-10-15',
    )
    mgr.add_position(pos)
    assert mgr.has_open_positions() is True
    assert mgr.get_open_contracts() == 1
    mgr.remove_position(pos)
    assert mgr.has_open_positions() is False


def test_position_manager_daily_loss_limit():
    mgr = PositionManager(max_day_loss=500)
    mgr.record_trade_pnl('2025-10-15', -600.0)
    assert mgr.daily_loss_exceeded('2025-10-15') is True
    assert mgr.can_open_trade('2025-10-15') is False


def test_position_manager_trade_count_limit():
    mgr = PositionManager(max_trades_per_day=2)
    mgr.record_trade_pnl('2025-10-15', 100.0)
    mgr.record_trade_pnl('2025-10-15', 50.0)
    assert mgr.can_open_trade('2025-10-15') is False


def test_position_manager_equity_tracking():
    mgr = PositionManager(account_size=100_000)
    mgr.record_trade_pnl('2025-10-15', 500.0)
    assert mgr.equity == 100_500
    assert mgr.peak_equity == 100_500
    mgr.record_trade_pnl('2025-10-15', -200.0)
    assert mgr.equity == 100_300
    assert mgr.max_drawdown_seen == 200.0


# --- OpenPosition tests ---


def test_open_position_unrealized_pnl():
    pos = OpenPosition(
        direction='LONG', entry_price=15100.0, stop_price=15080.0,
        target_price=15150.0, contracts=1, entry_time=datetime.now(),
        strategy_name='test', setup_type='test', day_type='neutral',
        trend_strength='weak', session_date='2025-10-15',
    )
    assert pos.unrealized_pnl_points(15120.0) == 20.0
    assert pos.unrealized_pnl_points(15080.0) == -20.0


def test_open_position_stop_hit():
    pos = OpenPosition(
        direction='LONG', entry_price=15100.0, stop_price=15080.0,
        target_price=15150.0, contracts=1, entry_time=datetime.now(),
        strategy_name='test', setup_type='test', day_type='neutral',
        trend_strength='weak', session_date='2025-10-15',
    )
    assert pos.check_stop_hit(15079.0, 15120.0) is True
    assert pos.check_stop_hit(15081.0, 15120.0) is False


def test_open_position_target_hit():
    pos = OpenPosition(
        direction='LONG', entry_price=15100.0, stop_price=15080.0,
        target_price=15150.0, contracts=1, entry_time=datetime.now(),
        strategy_name='test', setup_type='test', day_type='neutral',
        trend_strength='weak', session_date='2025-10-15',
    )
    assert pos.check_target_hit(15100.0, 15151.0) is True
    assert pos.check_target_hit(15100.0, 15149.0) is False


def test_open_position_trail_to_breakeven():
    pos = OpenPosition(
        direction='LONG', entry_price=15100.0, stop_price=15080.0,
        target_price=15150.0, contracts=1, entry_time=datetime.now(),
        strategy_name='test', setup_type='test', day_type='neutral',
        trend_strength='weak', session_date='2025-10-15',
    )
    pos.trail_to_breakeven()
    assert pos.trailing_stop == 15100.0
    assert pos.breakeven_activated is True


# --- EquityCurve tests ---


def test_equity_curve_basics():
    curve = EquityCurve(100_000)
    curve.record(datetime(2025, 10, 15), 100_500, 500, 2, '2025-10-15')
    curve.record(datetime(2025, 10, 16), 100_200, -300, 1, '2025-10-16')
    assert curve.final_equity == 100_200
    assert curve.max_drawdown == 300.0
    assert curve.total_return == 200.0
    assert len(curve.snapshots) == 2


# --- Instrument tests ---


def test_get_instrument():
    nq = get_instrument('NQ')
    assert nq.symbol == 'NQ'
    assert nq.point_value == 20.0
    assert nq.tick_size == 0.25


def test_get_instrument_case_insensitive():
    nq = get_instrument('nq')
    assert nq.symbol == 'NQ'
