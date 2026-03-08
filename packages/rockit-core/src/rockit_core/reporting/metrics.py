"""
Performance metrics for backtest results.
Sharpe, Sortino, Calmar, max DD, profit factor, expectancy, and more.
"""

import numpy as np
from typing import List, Dict, Any
from rockit_core.engine.trade import Trade


def compute_metrics(trades: List[Trade], initial_equity: float = 150_000) -> Dict[str, Any]:
    """
    Compute comprehensive performance metrics from a list of trades.

    All P&L values are in dollars (already computed by ExecutionModel).

    Args:
        trades: List of completed Trade objects.
        initial_equity: Starting account balance.

    Returns:
        Dict of named metrics.
    """
    if not trades:
        return _empty_metrics()

    pnl_list = [t.net_pnl for t in trades]
    gross_list = [t.gross_pnl for t in trades]
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]

    total_pnl = sum(pnl_list)
    total_gross = sum(gross_list)
    total_commission = sum(t.commission for t in trades)
    total_slippage = sum(t.slippage_cost for t in trades)

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / len(trades) * 100

    avg_win = np.mean([t.net_pnl for t in wins]) if wins else 0.0
    avg_loss = np.mean([t.net_pnl for t in losses]) if losses else 0.0
    largest_win = max((t.net_pnl for t in wins), default=0.0)
    largest_loss = min((t.net_pnl for t in losses), default=0.0)

    gross_profit = sum(t.net_pnl for t in wins)
    gross_loss = abs(sum(t.net_pnl for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    expectancy = total_pnl / len(trades)

    # Payoff ratio (avg win / avg loss)
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Equity curve for drawdown and ratio calculations
    equity_curve = _build_equity_curve(trades, initial_equity)
    max_dd = _max_drawdown(equity_curve)
    max_dd_pct = (max_dd / max(equity_curve)) * 100 if max(equity_curve) > 0 else 0.0

    # Daily P&L for Sharpe/Sortino
    daily_pnl = _daily_pnl(trades)
    sharpe = _sharpe_ratio(daily_pnl) if len(daily_pnl) > 1 else 0.0
    sortino = _sortino_ratio(daily_pnl) if len(daily_pnl) > 1 else 0.0

    # Calmar = annualized return / max drawdown
    total_days = len(daily_pnl)
    annualized_return = (total_pnl / initial_equity) * (252 / max(total_days, 1))
    calmar = annualized_return / (max_dd_pct / 100) if max_dd_pct > 0 else float('inf')

    # Consecutive stats
    max_consec_wins, max_consec_losses = _consecutive_streaks(trades)

    # Average bars held
    avg_bars = np.mean([t.bars_held for t in trades])
    avg_bars_win = np.mean([t.bars_held for t in wins]) if wins else 0
    avg_bars_loss = np.mean([t.bars_held for t in losses]) if losses else 0

    # R-multiple stats
    r_multiples = [t.r_multiple for t in trades if t.risk_points > 0]
    avg_r = np.mean(r_multiples) if r_multiples else 0.0
    expectancy_r = avg_r

    # Exit reason breakdown
    exit_reasons = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    # --- Extended metrics (Phase 1.1) ---

    # MAE/MFE trade quality metrics
    mae_pcts = [t.mae_pct_of_stop for t in trades if t.risk_points > 0]
    mfe_pcts = [t.mfe_pct_of_target for t in trades if t.reward_points > 0]
    mae_pts = [t.mae_points for t in trades]
    mfe_pts = [t.mfe_points for t in trades]

    avg_mae_pct_of_stop = float(np.mean(mae_pcts)) if mae_pcts else 0.0
    avg_mfe_pct_of_target = float(np.mean(mfe_pcts)) if mfe_pcts else 0.0
    edge_ratio = float(np.mean(mfe_pts)) / float(np.mean(mae_pts)) if mae_pts and np.mean(mae_pts) > 0 else 0.0

    # Stop/target hit rates
    stop_count = exit_reasons.get('STOP', 0)
    target_count = exit_reasons.get('TARGET', 0)
    stop_out_rate = stop_count / len(trades) * 100 if trades else 0.0
    target_hit_rate = target_count / len(trades) * 100 if trades else 0.0

    # R-multiple distribution
    r_multiple_median = float(np.median(r_multiples)) if r_multiples else 0.0
    r_multiple_stddev = float(np.std(r_multiples, ddof=1)) if len(r_multiples) > 1 else 0.0
    pct_above_2r = sum(1 for r in r_multiples if r > 2.0) / len(r_multiples) * 100 if r_multiples else 0.0
    pct_below_neg1r = sum(1 for r in r_multiples if r < -1.0) / len(r_multiples) * 100 if r_multiples else 0.0

    # Risk-adjusted ratios
    recovery_factor = total_pnl / max_dd if max_dd > 0 else 0.0
    neg_pnl_sum = abs(sum(p for p in pnl_list if p < 0))
    gain_to_pain = sum(pnl_list) / neg_pnl_sum if neg_pnl_sum > 0 else 0.0
    kelly_fraction = (win_rate / 100) - ((1 - win_rate / 100) / payoff_ratio) if payoff_ratio > 0 and payoff_ratio != float('inf') else 0.0

    # Ulcer index (sqrt of mean squared drawdown)
    eq_arr = np.array(_build_equity_curve(trades, initial_equity))
    running_peak = np.maximum.accumulate(eq_arr)
    dd_pct_arr = (running_peak - eq_arr) / running_peak * 100
    ulcer_index = float(np.sqrt(np.mean(dd_pct_arr ** 2)))

    # Cluster & sequence metrics
    serial_corr = _serial_correlation(pnl_list)
    max_cluster_loss, max_cluster_loss_count = _max_cluster_loss(trades)
    dd_duration = _drawdown_duration_sessions(trades)
    daily_pnl_vol = float(np.std(daily_pnl, ddof=1)) if len(daily_pnl) > 1 else 0.0

    # Session-level metrics
    session_wr, pct_flat, intraday_max_dd_val = _session_level_metrics(trades)

    # Win rate by entry hour
    wr_by_hour = _wr_by_entry_hour(trades)

    return {
        # Counts
        'total_trades': len(trades),
        'winning_trades': win_count,
        'losing_trades': loss_count,
        'win_rate': round(win_rate, 2),

        # P&L
        'total_net_pnl': round(total_pnl, 2),
        'total_gross_pnl': round(total_gross, 2),
        'total_commission': round(total_commission, 2),
        'total_slippage': round(total_slippage, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'largest_win': round(largest_win, 2),
        'largest_loss': round(largest_loss, 2),
        'expectancy_per_trade': round(expectancy, 2),

        # Ratios
        'profit_factor': round(profit_factor, 2),
        'payoff_ratio': round(payoff_ratio, 2),
        'sharpe_ratio': round(sharpe, 2),
        'sortino_ratio': round(sortino, 2),
        'calmar_ratio': round(calmar, 2),

        # Drawdown
        'max_drawdown': round(max_dd, 2),
        'max_drawdown_pct': round(max_dd_pct, 2),

        # R-multiples
        'avg_r_multiple': round(avg_r, 2),
        'expectancy_r': round(expectancy_r, 2),

        # Streaks
        'max_consecutive_wins': max_consec_wins,
        'max_consecutive_losses': max_consec_losses,

        # Duration
        'avg_bars_held': round(avg_bars, 1),
        'avg_bars_win': round(avg_bars_win, 1),
        'avg_bars_loss': round(avg_bars_loss, 1),

        # Equity
        'initial_equity': initial_equity,
        'final_equity': round(initial_equity + total_pnl, 2),
        'total_return_pct': round(total_pnl / initial_equity * 100, 2),
        'annualized_return_pct': round(annualized_return * 100, 2),

        # Breakdown
        'exit_reasons': exit_reasons,

        # --- Extended metrics (Phase 1.1) ---

        # MAE/MFE trade quality
        'avg_mae_pct_of_stop': round(avg_mae_pct_of_stop, 3),
        'avg_mfe_pct_of_target': round(avg_mfe_pct_of_target, 3),
        'edge_ratio': round(edge_ratio, 2),
        'stop_out_rate': round(stop_out_rate, 1),
        'target_hit_rate': round(target_hit_rate, 1),

        # R-multiple distribution
        'r_multiple_median': round(r_multiple_median, 2),
        'r_multiple_stddev': round(r_multiple_stddev, 2),
        'pct_trades_above_2r': round(pct_above_2r, 1),
        'pct_trades_below_neg1r': round(pct_below_neg1r, 1),

        # Risk-adjusted ratios
        'recovery_factor': round(recovery_factor, 2),
        'gain_to_pain_ratio': round(gain_to_pain, 2),
        'kelly_fraction': round(kelly_fraction, 3),
        'ulcer_index': round(ulcer_index, 2),

        # Cluster & sequence
        'serial_correlation': round(serial_corr, 3),
        'max_cluster_loss': round(max_cluster_loss, 2),
        'max_cluster_loss_count': max_cluster_loss_count,
        'drawdown_duration_sessions': dd_duration,
        'daily_pnl_volatility': round(daily_pnl_vol, 2),

        # Session-level
        'session_win_rate': round(session_wr, 1),
        'pct_flat_sessions': round(pct_flat, 1),
        'intraday_max_dd': round(intraday_max_dd_val, 2),
        'wr_by_entry_hour': wr_by_hour,
    }


def _empty_metrics() -> Dict[str, Any]:
    return {
        'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
        'win_rate': 0.0, 'total_net_pnl': 0.0, 'total_gross_pnl': 0.0,
        'total_commission': 0.0, 'total_slippage': 0.0,
        'avg_win': 0.0, 'avg_loss': 0.0, 'largest_win': 0.0, 'largest_loss': 0.0,
        'expectancy_per_trade': 0.0, 'profit_factor': 0.0, 'payoff_ratio': 0.0,
        'sharpe_ratio': 0.0, 'sortino_ratio': 0.0, 'calmar_ratio': 0.0,
        'max_drawdown': 0.0, 'max_drawdown_pct': 0.0,
        'avg_r_multiple': 0.0, 'expectancy_r': 0.0,
        'max_consecutive_wins': 0, 'max_consecutive_losses': 0,
        'avg_bars_held': 0.0, 'avg_bars_win': 0.0, 'avg_bars_loss': 0.0,
        'initial_equity': 0, 'final_equity': 0, 'total_return_pct': 0.0,
        'annualized_return_pct': 0.0, 'exit_reasons': {},
        # Extended metrics
        'avg_mae_pct_of_stop': 0.0, 'avg_mfe_pct_of_target': 0.0,
        'edge_ratio': 0.0, 'stop_out_rate': 0.0, 'target_hit_rate': 0.0,
        'r_multiple_median': 0.0, 'r_multiple_stddev': 0.0,
        'pct_trades_above_2r': 0.0, 'pct_trades_below_neg1r': 0.0,
        'recovery_factor': 0.0, 'gain_to_pain_ratio': 0.0,
        'kelly_fraction': 0.0, 'ulcer_index': 0.0,
        'serial_correlation': 0.0, 'max_cluster_loss': 0.0,
        'max_cluster_loss_count': 0, 'drawdown_duration_sessions': 0,
        'daily_pnl_volatility': 0.0, 'session_win_rate': 0.0,
        'pct_flat_sessions': 0.0, 'intraday_max_dd': 0.0,
        'wr_by_entry_hour': {},
    }


def _build_equity_curve(trades: List[Trade], initial: float) -> List[float]:
    curve = [initial]
    for t in trades:
        curve.append(curve[-1] + t.net_pnl)
    return curve


def _max_drawdown(equity_curve: List[float]) -> float:
    peak = equity_curve[0]
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _daily_pnl(trades: List[Trade]) -> List[float]:
    """Group trades by session_date, sum daily P&L."""
    daily = {}
    for t in trades:
        key = t.session_date
        daily[key] = daily.get(key, 0.0) + t.net_pnl
    return list(daily.values())


def _sharpe_ratio(daily_pnl: List[float], risk_free_rate: float = 0.0) -> float:
    """Annualized Sharpe ratio from daily P&L."""
    if len(daily_pnl) < 2:
        return 0.0
    arr = np.array(daily_pnl)
    mean_ret = arr.mean() - risk_free_rate / 252
    std_ret = arr.std(ddof=1)
    if std_ret == 0:
        return 0.0
    return (mean_ret / std_ret) * np.sqrt(252)


def _sortino_ratio(daily_pnl: List[float], risk_free_rate: float = 0.0) -> float:
    """Annualized Sortino ratio (downside deviation only)."""
    if len(daily_pnl) < 2:
        return 0.0
    arr = np.array(daily_pnl)
    mean_ret = arr.mean() - risk_free_rate / 252
    downside = arr[arr < 0]
    if len(downside) == 0:
        return float('inf')
    downside_std = downside.std(ddof=1)
    if downside_std == 0:
        return 0.0
    return (mean_ret / downside_std) * np.sqrt(252)


def _serial_correlation(pnl_list: List[float]) -> float:
    """Autocorrelation of returns at lag 1. >0 = clustered, <0 = mean-reverting."""
    if len(pnl_list) < 3:
        return 0.0
    arr = np.array(pnl_list)
    mean = arr.mean()
    var = np.var(arr, ddof=0)
    if var == 0:
        return 0.0
    n = len(arr)
    cov = np.sum((arr[:-1] - mean) * (arr[1:] - mean)) / n
    return float(cov / var)


def _max_cluster_loss(trades: List[Trade]) -> tuple:
    """Return (worst sum of consecutive losses in $, count of trades in that cluster)."""
    max_loss = 0.0
    max_count = 0
    cur_loss = 0.0
    cur_count = 0
    for t in trades:
        if t.net_pnl <= 0:
            cur_loss += t.net_pnl
            cur_count += 1
            if cur_loss < max_loss:
                max_loss = cur_loss
                max_count = cur_count
        else:
            cur_loss = 0.0
            cur_count = 0
    return max_loss, max_count


def _drawdown_duration_sessions(trades: List[Trade]) -> int:
    """Sessions from peak equity to recovery (longest drawdown duration)."""
    if not trades:
        return 0
    # Build session-level equity
    session_pnl = {}
    for t in trades:
        session_pnl[t.session_date] = session_pnl.get(t.session_date, 0.0) + t.net_pnl
    sessions = sorted(session_pnl.keys())
    equity = 0.0
    peak = 0.0
    max_duration = 0
    dd_start = 0
    for i, s in enumerate(sessions):
        equity += session_pnl[s]
        if equity >= peak:
            peak = equity
            dd_start = i + 1
        else:
            max_duration = max(max_duration, i + 1 - dd_start)
    return max_duration


def _session_level_metrics(trades: List[Trade]) -> tuple:
    """Return (session_win_rate, pct_flat_sessions, intraday_max_dd)."""
    if not trades:
        return 0.0, 0.0, 0.0
    # Session win rate
    session_pnl = {}
    for t in trades:
        session_pnl[t.session_date] = session_pnl.get(t.session_date, 0.0) + t.net_pnl
    winning_sessions = sum(1 for v in session_pnl.values() if v > 0)
    session_wr = winning_sessions / len(session_pnl) * 100 if session_pnl else 0.0

    # Pct flat = sessions with no trades / total sessions
    # We only know about sessions WITH trades, so we can't compute this here.
    # Set to 0 — will be computed when we have full session data in Phase 3.
    pct_flat = 0.0

    # Intraday max DD = worst per-session PnL
    intraday_max_dd = abs(min(session_pnl.values())) if session_pnl else 0.0

    return session_wr, pct_flat, intraday_max_dd


def _wr_by_entry_hour(trades: List[Trade]) -> dict:
    """Win rate per entry hour bucket."""
    hour_wins = {}
    hour_total = {}
    for t in trades:
        h = t.entry_hour
        if h is None:
            continue
        hour_total[h] = hour_total.get(h, 0) + 1
        if t.net_pnl > 0:
            hour_wins[h] = hour_wins.get(h, 0) + 1
    return {h: round(hour_wins.get(h, 0) / hour_total[h] * 100, 1) for h in sorted(hour_total.keys())}


def _consecutive_streaks(trades: List[Trade]) -> tuple:
    """Return (max consecutive wins, max consecutive losses)."""
    max_wins = max_losses = 0
    cur_wins = cur_losses = 0
    for t in trades:
        if t.net_pnl > 0:
            cur_wins += 1
            cur_losses = 0
            max_wins = max(max_wins, cur_wins)
        else:
            cur_losses += 1
            cur_wins = 0
            max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses


def print_metrics(metrics: Dict[str, Any]) -> None:
    """Pretty-print a metrics dict."""
    print(f"\n{'='*70}")
    print(f"  PERFORMANCE REPORT")
    print(f"{'='*70}")

    print(f"\n--- Trade Summary ---")
    print(f"  Total Trades:        {metrics['total_trades']}")
    print(f"  Win Rate:            {metrics['win_rate']:.1f}%"
          f"  ({metrics['winning_trades']}W / {metrics['losing_trades']}L)")
    print(f"  Profit Factor:       {metrics['profit_factor']:.2f}")
    print(f"  Payoff Ratio:        {metrics['payoff_ratio']:.2f}")
    print(f"  Expectancy:          ${metrics['expectancy_per_trade']:,.2f} / trade")

    print(f"\n--- P&L ---")
    print(f"  Gross P&L:           ${metrics['total_gross_pnl']:>12,.2f}")
    print(f"  Commissions:         ${metrics['total_commission']:>12,.2f}")
    print(f"  Slippage:            ${metrics['total_slippage']:>12,.2f}")
    print(f"  Net P&L:             ${metrics['total_net_pnl']:>12,.2f}")

    print(f"\n--- Win/Loss ---")
    print(f"  Avg Win:             ${metrics['avg_win']:>10,.2f}")
    print(f"  Avg Loss:            ${metrics['avg_loss']:>10,.2f}")
    print(f"  Largest Win:         ${metrics['largest_win']:>10,.2f}")
    print(f"  Largest Loss:        ${metrics['largest_loss']:>10,.2f}")

    print(f"\n--- Risk Ratios ---")
    print(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio:       {metrics['sortino_ratio']:.2f}")
    print(f"  Calmar Ratio:        {metrics['calmar_ratio']:.2f}")
    print(f"  Avg R-Multiple:      {metrics['avg_r_multiple']:.2f}")

    print(f"\n--- Drawdown ---")
    print(f"  Max Drawdown:        ${metrics['max_drawdown']:>10,.2f}")
    print(f"  Max Drawdown %:      {metrics['max_drawdown_pct']:.2f}%")

    print(f"\n--- Equity ---")
    print(f"  Initial:             ${metrics['initial_equity']:>12,.2f}")
    print(f"  Final:               ${metrics['final_equity']:>12,.2f}")
    print(f"  Total Return:        {metrics['total_return_pct']:.2f}%")
    print(f"  Annualized Return:   {metrics['annualized_return_pct']:.2f}%")

    print(f"\n--- Duration ---")
    print(f"  Avg Bars Held:       {metrics['avg_bars_held']:.1f}")
    print(f"  Avg Bars (Win):      {metrics['avg_bars_win']:.1f}")
    print(f"  Avg Bars (Loss):     {metrics['avg_bars_loss']:.1f}")

    print(f"\n--- Streaks ---")
    print(f"  Max Consec Wins:     {metrics['max_consecutive_wins']}")
    print(f"  Max Consec Losses:   {metrics['max_consecutive_losses']}")

    if metrics.get('exit_reasons'):
        print(f"\n--- Exit Reasons ---")
        for reason, count in sorted(metrics['exit_reasons'].items(),
                                     key=lambda x: -x[1]):
            pct = count / metrics['total_trades'] * 100
            print(f"  {reason:20s}: {count:4d}  ({pct:5.1f}%)")

    # Extended metrics (Phase 1.1)
    if metrics.get('edge_ratio', 0) > 0:
        print(f"\n--- Trade Quality (MAE/MFE) ---")
        print(f"  Edge Ratio:          {metrics['edge_ratio']:.2f}  (>1.0 = favorable)")
        print(f"  Avg MAE % of Stop:   {metrics['avg_mae_pct_of_stop']:.1%}")
        print(f"  Avg MFE % of Target: {metrics['avg_mfe_pct_of_target']:.1%}")
        print(f"  Stop-Out Rate:       {metrics['stop_out_rate']:.1f}%")
        print(f"  Target Hit Rate:     {metrics['target_hit_rate']:.1f}%")

        print(f"\n--- R-Multiple Distribution ---")
        print(f"  Median R:            {metrics['r_multiple_median']:.2f}")
        print(f"  R Std Dev:           {metrics['r_multiple_stddev']:.2f}")
        print(f"  % Trades > 2R:       {metrics['pct_trades_above_2r']:.1f}%")
        print(f"  % Trades < -1R:      {metrics['pct_trades_below_neg1r']:.1f}%")

        print(f"\n--- Advanced Risk ---")
        print(f"  Recovery Factor:     {metrics['recovery_factor']:.2f}")
        print(f"  Gain-to-Pain:        {metrics['gain_to_pain_ratio']:.2f}")
        print(f"  Kelly Fraction:      {metrics['kelly_fraction']:.3f}")
        print(f"  Ulcer Index:         {metrics['ulcer_index']:.2f}")

        print(f"\n--- Cluster & Sequence ---")
        print(f"  Serial Correlation:  {metrics['serial_correlation']:.3f}")
        print(f"  Max Cluster Loss:    ${metrics['max_cluster_loss']:,.2f}  ({metrics['max_cluster_loss_count']} trades)")
        print(f"  DD Duration:         {metrics['drawdown_duration_sessions']} sessions")
        print(f"  Daily P&L Vol:       ${metrics['daily_pnl_volatility']:,.2f}")

        print(f"\n--- Session Level ---")
        print(f"  Session Win Rate:    {metrics['session_win_rate']:.1f}%")
        print(f"  Intraday Max DD:     ${metrics['intraday_max_dd']:,.2f}")

    if metrics.get('wr_by_entry_hour'):
        print(f"\n--- Win Rate by Hour ---")
        for hour, wr in sorted(metrics['wr_by_entry_hour'].items()):
            print(f"  {hour:02d}:00              {wr:.1f}%")

    print(f"{'='*70}\n")
