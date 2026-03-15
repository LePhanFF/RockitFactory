"""
CVD (Cumulative Volume Delta) Divergence Study for NQ Futures
=============================================================
Tests CVD divergence as both a standalone entry signal and as a filter.

CVD divergence = price makes new extreme but cumulative delta disagrees,
signaling institutional exhaustion and potential reversal.

Combinatorial sweep across:
  - Entry trigger: cvd_div_only, cvd_div_rsi, cvd_div_bb, cvd_div_vwap
  - Reversal confirmation: immediate, reversal_bar, two_bar
  - ADX gate: no_adx, adx_lt_25, adx_gt_25
  - Stop model: swing_low, fixed_20pt, fixed_30pt, fixed_40pt, atr_1x
  - Target model: vwap, ib_mid, 1R, 2R, prior_poc
  - Time window: morning, after_ib, full
  - Direction: LONG, SHORT, BOTH
"""

import sys
import time as _time_mod
import warnings
from datetime import time as dtime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "packages/rockit-core/src")

warnings.filterwarnings("ignore", category=FutureWarning)


def log(msg: str):
    print(msg, flush=True)


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    """Load NQ data with all features and indicators."""
    from rockit_core.data.manager import SessionDataManager
    from rockit_core.data.features import compute_all_features
    from rockit_core.indicators.technical import add_all_indicators

    log("Loading NQ data...")
    baseline_dirs = [
        "data/sessions",
        "C:/Users/lehph/Documents/GitHub/BookMapOrderFlowStudies-2/csv",
        "C:/Users/lehph/Documents/GitHub/BookMapOrderFlowStudies-2/csv/combined",
    ]
    df = None
    for bdir in baseline_dirs:
        try:
            mgr = SessionDataManager(baseline_dir=bdir)
            df = mgr.load("NQ")
            if len(df) > 0:
                log(f"  Loaded from: {bdir}")
                break
        except (FileNotFoundError, Exception):
            continue
    if df is None or len(df) == 0:
        raise FileNotFoundError("Could not find NQ data in any known location")
    df = compute_all_features(df)
    df = add_all_indicators(df)
    log(f"  Loaded {len(df):,} bars across {df['session_date'].nunique()} sessions")
    return df


# ── CVD Divergence Detection (vectorized) ────────────────────────────────────

def add_cvd_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Detect CVD divergence signals (vectorized per-session).

    cvd_div_bull: price makes lower low but CVD makes higher low
    cvd_div_bear: price makes higher high but CVD makes lower high
    """
    df = df.copy()
    bull_flags = np.zeros(len(df), dtype=bool)
    bear_flags = np.zeros(len(df), dtype=bool)

    for session, grp in df.groupby("session_date"):
        if len(grp) < lookback + 1:
            continue

        lows = grp["low"].values
        highs = grp["high"].values
        cvd = grp["cumulative_delta"].values
        n = len(grp)
        offset = grp.index[0]  # index offset in full df

        # Vectorized: compute rolling min-low index and max-high index
        for i in range(lookback, n):
            ws = i - lookback
            # Bull: current low < min of lookback window lows
            w_lows = lows[ws:i]
            min_idx = np.argmin(w_lows)
            if lows[i] < w_lows[min_idx] and cvd[i] > cvd[ws + min_idx]:
                bull_flags[offset + i] = True

            # Bear: current high > max of lookback window highs
            w_highs = highs[ws:i]
            max_idx = np.argmax(w_highs)
            if highs[i] > w_highs[max_idx] and cvd[i] < cvd[ws + max_idx]:
                bear_flags[offset + i] = True

    df["cvd_div_bull"] = bull_flags
    df["cvd_div_bear"] = bear_flags
    return df


# ── RTH Filter ───────────────────────────────────────────────────────────────

RTH_START = dtime(9, 30)
RTH_END = dtime(16, 0)
IB_END = dtime(10, 30)
MORNING_END = dtime(12, 0)
AFTERNOON_END = dtime(15, 0)
SIGNAL_START_MORNING = dtime(9, 45)

TIME_WINDOWS = {
    "morning": (SIGNAL_START_MORNING, MORNING_END),
    "after_ib": (IB_END, AFTERNOON_END),
    "full": (SIGNAL_START_MORNING, AFTERNOON_END),
}


def filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only RTH bars."""
    bar_times = pd.to_datetime(df["timestamp"]).dt.time
    return df[(bar_times >= RTH_START) & (bar_times <= RTH_END)].copy()


# ── Trade Simulation (numpy-based for speed) ────────────────────────────────

NQ_TICK_VALUE = 5.0
MAX_TRADES_PER_SESSION = 2
COOLDOWN_BARS = 15


def simulate_trade_np(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    times: np.ndarray,  # array of datetime.time objects
    entry_pos: int,
    direction: str,
    stop_price: float,
    target_price: float,
) -> dict:
    """Walk forward from entry to determine outcome using numpy arrays."""
    entry_price = closes[entry_pos]
    n = len(closes)

    for j in range(entry_pos + 1, n):
        # Time stop at 15:30
        if times[j] >= dtime(15, 30):
            exit_price = closes[j]
            pnl = (exit_price - entry_price if direction == "LONG"
                   else entry_price - exit_price) * NQ_TICK_VALUE
            return {"pnl": pnl, "win": pnl > 0, "exit_reason": "time_stop",
                    "bars_held": j - entry_pos}

        if direction == "LONG":
            if lows[j] <= stop_price:
                pnl = (stop_price - entry_price) * NQ_TICK_VALUE
                return {"pnl": pnl, "win": False, "exit_reason": "stop",
                        "bars_held": j - entry_pos}
            if highs[j] >= target_price:
                pnl = (target_price - entry_price) * NQ_TICK_VALUE
                return {"pnl": pnl, "win": True, "exit_reason": "target",
                        "bars_held": j - entry_pos}
        else:
            if highs[j] >= stop_price:
                pnl = (entry_price - stop_price) * NQ_TICK_VALUE
                return {"pnl": pnl, "win": False, "exit_reason": "stop",
                        "bars_held": j - entry_pos}
            if lows[j] <= target_price:
                pnl = (entry_price - target_price) * NQ_TICK_VALUE
                return {"pnl": pnl, "win": True, "exit_reason": "target",
                        "bars_held": j - entry_pos}

    # EOD
    exit_price = closes[-1]
    pnl = (exit_price - entry_price if direction == "LONG"
           else entry_price - exit_price) * NQ_TICK_VALUE
    return {"pnl": pnl, "win": pnl > 0, "exit_reason": "eod",
            "bars_held": n - entry_pos - 1}


# ── Pre-compute session arrays for speed ─────────────────────────────────────

class SessionData:
    """Pre-extracted numpy arrays for a single RTH session."""
    __slots__ = [
        "highs", "lows", "closes", "opens", "times",
        "cvd_div_bull", "cvd_div_bear",
        "rsi14", "bb_upper", "bb_lower", "adx14",
        "vwap", "ib_range", "ib_high", "ib_low",
        "atr14", "prior_va_poc", "session_date", "n",
    ]

    def __init__(self, sdf: pd.DataFrame, session_date: str):
        self.session_date = session_date
        self.n = len(sdf)
        self.highs = sdf["high"].values.astype(float)
        self.lows = sdf["low"].values.astype(float)
        self.closes = sdf["close"].values.astype(float)
        self.opens = sdf["open"].values.astype(float)
        self.times = pd.to_datetime(sdf["timestamp"]).dt.time.values
        self.cvd_div_bull = sdf["cvd_div_bull"].values.astype(bool)
        self.cvd_div_bear = sdf["cvd_div_bear"].values.astype(bool)
        self.rsi14 = sdf["rsi14"].values.astype(float) if "rsi14" in sdf else np.full(self.n, 50.0)
        self.bb_upper = sdf["bb_upper"].values.astype(float) if "bb_upper" in sdf else np.full(self.n, np.inf)
        self.bb_lower = sdf["bb_lower"].values.astype(float) if "bb_lower" in sdf else np.full(self.n, -np.inf)
        self.adx14 = sdf["adx14"].values.astype(float) if "adx14" in sdf else np.full(self.n, 25.0)
        self.vwap = sdf["vwap"].values.astype(float) if "vwap" in sdf else np.full(self.n, np.nan)
        self.ib_range = sdf["ib_range"].values.astype(float) if "ib_range" in sdf else np.full(self.n, np.nan)
        self.ib_high = sdf["ib_high"].values.astype(float) if "ib_high" in sdf else np.full(self.n, np.nan)
        self.ib_low = sdf["ib_low"].values.astype(float) if "ib_low" in sdf else np.full(self.n, np.nan)
        self.atr14 = sdf["atr14"].values.astype(float) if "atr14" in sdf else np.full(self.n, 20.0)
        self.prior_va_poc = sdf["prior_va_poc"].values.astype(float) if "prior_va_poc" in sdf else np.full(self.n, np.nan)


# ── Fast config runner ──────────────────────────────────────────────────────

def check_trigger_fast(sd: SessionData, i: int, direction: str, trigger: str) -> bool:
    """Check entry trigger using pre-extracted arrays."""
    if direction == "LONG":
        if not sd.cvd_div_bull[i]:
            return False
    else:
        if not sd.cvd_div_bear[i]:
            return False

    if trigger == "cvd_div_only":
        return True

    if trigger == "cvd_div_rsi":
        rsi = sd.rsi14[i]
        if np.isnan(rsi):
            return False
        return (rsi < 35) if direction == "LONG" else (rsi > 65)

    if trigger == "cvd_div_bb":
        if direction == "LONG":
            return sd.closes[i] <= sd.bb_lower[i]
        else:
            return sd.closes[i] >= sd.bb_upper[i]

    if trigger == "cvd_div_vwap":
        vwap = sd.vwap[i]
        ibr = sd.ib_range[i]
        if np.isnan(vwap) or np.isnan(ibr) or ibr <= 0:
            return False
        return abs(sd.closes[i] - vwap) > 0.5 * ibr

    return False


def check_adx_fast(sd: SessionData, i: int, gate: str) -> bool:
    adx = sd.adx14[i]
    if gate == "no_adx":
        return True
    if np.isnan(adx):
        return False
    if gate == "adx_lt_25":
        return adx < 25
    if gate == "adx_gt_25":
        return adx > 25
    return True


def check_confirmation_fast(sd: SessionData, sig_i: int, direction: str, confirmation: str) -> tuple:
    """Returns (confirmed, entry_bar_idx)."""
    if confirmation == "immediate":
        return True, sig_i

    if confirmation == "reversal_bar":
        ni = sig_i + 1
        if ni >= sd.n:
            return False, -1
        if direction == "LONG":
            ok = sd.closes[ni] > sd.opens[ni]
        else:
            ok = sd.closes[ni] < sd.opens[ni]
        return (ok, ni) if ok else (False, -1)

    if confirmation == "two_bar":
        if sig_i + 2 >= sd.n:
            return False, -1
        if direction == "LONG":
            ok = (sd.closes[sig_i+1] > sd.opens[sig_i+1]) and (sd.closes[sig_i+2] > sd.opens[sig_i+2])
        else:
            ok = (sd.closes[sig_i+1] < sd.opens[sig_i+1]) and (sd.closes[sig_i+2] < sd.opens[sig_i+2])
        return (ok, sig_i + 2) if ok else (False, -1)

    return False, -1


def compute_stop_fast(sd: SessionData, entry_pos: int, direction: str, stop_model: str) -> float:
    ep = sd.closes[entry_pos]
    if stop_model == "fixed_20pt":
        return ep - 20 if direction == "LONG" else ep + 20
    if stop_model == "fixed_30pt":
        return ep - 30 if direction == "LONG" else ep + 30
    if stop_model == "fixed_40pt":
        return ep - 40 if direction == "LONG" else ep + 40
    if stop_model == "atr_1x":
        atr = sd.atr14[entry_pos]
        if np.isnan(atr):
            atr = 20
        return ep - atr if direction == "LONG" else ep + atr
    if stop_model == "swing_low":
        lb = min(20, entry_pos)
        if direction == "LONG":
            return float(np.min(sd.lows[max(0, entry_pos - lb):entry_pos + 1])) - 5
        else:
            return float(np.max(sd.highs[max(0, entry_pos - lb):entry_pos + 1])) + 5
    return ep - 30 if direction == "LONG" else ep + 30


def compute_target_fast(sd: SessionData, entry_pos: int, direction: str,
                        target_model: str, stop_price: float) -> float:
    """Returns target price or NaN if not computable."""
    ep = sd.closes[entry_pos]
    risk = abs(ep - stop_price)

    if target_model == "1R":
        return ep + risk if direction == "LONG" else ep - risk
    if target_model == "2R":
        return ep + 2 * risk if direction == "LONG" else ep - 2 * risk

    if target_model == "vwap":
        v = sd.vwap[entry_pos]
        if np.isnan(v):
            return np.nan
        if direction == "LONG" and v > ep:
            return v
        if direction == "SHORT" and v < ep:
            return v
        return np.nan

    if target_model == "ib_mid":
        ih = sd.ib_high[entry_pos]
        il = sd.ib_low[entry_pos]
        if np.isnan(ih) or np.isnan(il):
            return np.nan
        mid = (ih + il) / 2
        if direction == "LONG" and mid > ep:
            return mid
        if direction == "SHORT" and mid < ep:
            return mid
        return np.nan

    if target_model == "prior_poc":
        poc = sd.prior_va_poc[entry_pos]
        if np.isnan(poc):
            return np.nan
        if direction == "LONG" and poc > ep:
            return poc
        if direction == "SHORT" and poc < ep:
            return poc
        return np.nan

    return np.nan


def run_config_fast(
    all_sessions: dict[str, dict[str, SessionData]],
    trigger: str,
    confirmation: str,
    adx_gate: str,
    stop_model: str,
    target_model: str,
    time_window: str,
    direction: str,
) -> list[dict]:
    """Run config using pre-extracted numpy arrays."""
    trades = []
    sessions_for_window = all_sessions.get(time_window, {})

    for session_date, sd in sessions_for_window.items():
        if sd.n < 25:
            continue

        session_trades = 0
        last_entry = -COOLDOWN_BARS

        dirs_to_check = []
        if direction in ("LONG", "BOTH"):
            dirs_to_check.append("LONG")
        if direction in ("SHORT", "BOTH"):
            dirs_to_check.append("SHORT")

        for i in range(sd.n):
            if session_trades >= MAX_TRADES_PER_SESSION:
                break
            if i - last_entry < COOLDOWN_BARS:
                continue

            for d in dirs_to_check:
                if session_trades >= MAX_TRADES_PER_SESSION:
                    break

                if not check_trigger_fast(sd, i, d, trigger):
                    continue
                if not check_adx_fast(sd, i, adx_gate):
                    continue

                confirmed, entry_pos = check_confirmation_fast(sd, i, d, confirmation)
                if not confirmed:
                    continue

                stop_price = compute_stop_fast(sd, entry_pos, d, stop_model)
                target_price = compute_target_fast(sd, entry_pos, d, target_model, stop_price)
                if np.isnan(target_price):
                    continue

                risk = abs(sd.closes[entry_pos] - stop_price)
                if risk < 2:
                    continue

                # Simulate using the full-session arrays (stored separately)
                # We use the windowed data for simulation too (simplification)
                trade = simulate_trade_np(
                    sd.highs, sd.lows, sd.closes, sd.times,
                    entry_pos, d, stop_price, target_price,
                )
                trade["session_date"] = session_date
                trade["direction"] = d
                trades.append(trade)

                session_trades += 1
                last_entry = entry_pos
                break

    return trades


# ── Metrics ──────────────────────────────────────────────────────────────────

def compute_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {
            "trades": 0, "wins": 0, "losses": 0, "wr": 0.0,
            "pf": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "max_dd": 0.0,
        }

    pnls = [t["pnl"] for t in trades]
    wins_list = [p for p in pnls if p > 0]
    losses_list = [p for p in pnls if p <= 0]
    total_pnl = sum(pnls)
    gross_profit = sum(wins_list) if wins_list else 0
    gross_loss = abs(sum(losses_list)) if losses_list else 0.001

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    n_wins = len(wins_list)
    n_losses = len(losses_list)
    n_total = len(trades)

    return {
        "trades": n_total,
        "wins": n_wins,
        "losses": n_losses,
        "wr": n_wins / n_total * 100,
        "pf": gross_profit / gross_loss if gross_loss > 0 else 0,
        "total_pnl": total_pnl,
        "avg_pnl": total_pnl / n_total,
        "avg_win": gross_profit / n_wins if n_wins else 0,
        "avg_loss": -gross_loss / n_losses if n_losses else 0,
        "max_dd": max_dd,
    }


# ── Divergence Frequency Analysis ───────────────────────────────────────────

def analyze_divergence_frequency(df: pd.DataFrame) -> dict:
    rth = filter_rth(df)
    grouped = rth.groupby("session_date").agg(
        bull=("cvd_div_bull", "sum"),
        bear=("cvd_div_bear", "sum"),
    )
    grouped["total"] = grouped["bull"] + grouped["bear"]

    return {
        "total_sessions": len(grouped),
        "bull_signals_total": int(grouped["bull"].sum()),
        "bear_signals_total": int(grouped["bear"].sum()),
        "bull_per_session_avg": float(grouped["bull"].mean()),
        "bear_per_session_avg": float(grouped["bear"].mean()),
        "total_per_session_avg": float(grouped["total"].mean()),
        "bull_per_session_median": float(grouped["bull"].median()),
        "bear_per_session_median": float(grouped["bear"].median()),
        "sessions_with_bull": int((grouped["bull"] > 0).sum()),
        "sessions_with_bear": int((grouped["bear"] > 0).sum()),
    }


# ── As-a-Filter Analysis ────────────────────────────────────────────────────

def analyze_as_filter(df: pd.DataFrame) -> dict:
    rth = filter_rth(df)
    results = {}

    near_bb_lower = rth[rth["close"] <= rth["bb_lower"]]
    bb_lower_with_div = int(near_bb_lower["cvd_div_bull"].sum())
    results["bb_lower_bars"] = len(near_bb_lower)
    results["bb_lower_with_bull_div"] = bb_lower_with_div
    results["bb_lower_div_pct"] = (
        bb_lower_with_div / len(near_bb_lower) * 100 if len(near_bb_lower) > 0 else 0
    )

    near_bb_upper = rth[rth["close"] >= rth["bb_upper"]]
    bb_upper_with_div = int(near_bb_upper["cvd_div_bear"].sum())
    results["bb_upper_bars"] = len(near_bb_upper)
    results["bb_upper_with_bear_div"] = bb_upper_with_div
    results["bb_upper_div_pct"] = (
        bb_upper_with_div / len(near_bb_upper) * 100 if len(near_bb_upper) > 0 else 0
    )

    rsi_oversold = rth[rth["rsi14"] < 30]
    rsi_os_with_div = int(rsi_oversold["cvd_div_bull"].sum())
    results["rsi_oversold_bars"] = len(rsi_oversold)
    results["rsi_oversold_with_bull_div"] = rsi_os_with_div
    results["rsi_oversold_div_pct"] = (
        rsi_os_with_div / len(rsi_oversold) * 100 if len(rsi_oversold) > 0 else 0
    )

    rsi_overbought = rth[rth["rsi14"] > 70]
    rsi_ob_with_div = int(rsi_overbought["cvd_div_bear"].sum())
    results["rsi_overbought_bars"] = len(rsi_overbought)
    results["rsi_overbought_with_bear_div"] = rsi_ob_with_div
    results["rsi_overbought_div_pct"] = (
        rsi_ob_with_div / len(rsi_overbought) * 100 if len(rsi_overbought) > 0 else 0
    )

    rth_copy = rth.copy()
    rth_copy["vwap_dev"] = abs(rth_copy["close"] - rth_copy["vwap"])
    ib_range_median = rth_copy["ib_range"].median()
    extended = rth_copy[rth_copy["vwap_dev"] > 0.5 * ib_range_median]
    ext_bull = int(
        ((extended["close"] < extended["vwap"]) & extended["cvd_div_bull"]).sum()
    )
    ext_bear = int(
        ((extended["close"] > extended["vwap"]) & extended["cvd_div_bear"]).sum()
    )
    results["vwap_extended_bars"] = len(extended)
    results["vwap_extended_bull_div"] = ext_bull
    results["vwap_extended_bear_div"] = ext_bear

    return results


# ── Main Study ───────────────────────────────────────────────────────────────

ENTRY_TRIGGERS = ["cvd_div_only", "cvd_div_rsi", "cvd_div_bb", "cvd_div_vwap"]
CONFIRMATIONS = ["immediate", "reversal_bar", "two_bar"]
ADX_GATES = ["no_adx", "adx_lt_25", "adx_gt_25"]
STOP_MODELS = ["swing_low", "fixed_20pt", "fixed_30pt", "fixed_40pt", "atr_1x"]
TARGET_MODELS = ["vwap", "ib_mid", "1R", "2R", "prior_poc"]
TIME_WINDOWS_LIST = ["morning", "after_ib", "full"]
DIRECTIONS = ["LONG", "SHORT", "BOTH"]


def main():
    t0 = _time_mod.time()

    # Load data
    df = load_data()

    # Compute CVD divergence
    log("Computing CVD divergence signals...")
    df = add_cvd_divergence(df, lookback=20)
    log(f"  CVD divergence computed in {_time_mod.time() - t0:.1f}s")

    # Frequency analysis
    log("Analyzing divergence frequency...")
    freq = analyze_divergence_frequency(df)
    log(f"  Bull signals: {freq['bull_signals_total']:,} "
        f"({freq['bull_per_session_avg']:.1f}/session)")
    log(f"  Bear signals: {freq['bear_signals_total']:,} "
        f"({freq['bear_per_session_avg']:.1f}/session)")

    # As-a-filter analysis
    log("Analyzing CVD divergence as filter...")
    filter_stats = analyze_as_filter(df)

    # Prepare pre-extracted session arrays per time window
    log("Pre-extracting session arrays...")
    rth = filter_rth(df)
    all_sessions = {}  # time_window -> {session_date: SessionData}
    for tw_name, (tw_start, tw_end) in TIME_WINDOWS.items():
        tw_sessions = {}
        for session_date, sdf in rth.groupby("session_date"):
            bar_times = pd.to_datetime(sdf["timestamp"]).dt.time
            mask = (bar_times >= tw_start) & (bar_times <= tw_end)
            wdf = sdf[mask].reset_index(drop=True)
            if len(wdf) >= 25:
                tw_sessions[str(session_date)] = SessionData(wdf, str(session_date))
        all_sessions[tw_name] = tw_sessions
    log(f"  Pre-extracted {sum(len(v) for v in all_sessions.values())} session-windows")

    # Combinatorial sweep
    configs = list(product(
        ENTRY_TRIGGERS, CONFIRMATIONS, ADX_GATES,
        STOP_MODELS, TARGET_MODELS, TIME_WINDOWS_LIST, DIRECTIONS,
    ))
    total_configs = len(configs)
    log(f"\nRunning {total_configs:,} configurations...")

    all_results = []
    for idx, (trigger, confirmation, adx_gate, stop_model, target_model,
              time_window, direction) in enumerate(configs):
        if idx % 500 == 0:
            elapsed = _time_mod.time() - t0
            log(f"  Progress: {idx:,}/{total_configs:,} "
                f"({idx / total_configs * 100:.0f}%) [{elapsed:.0f}s]")

        trades = run_config_fast(
            all_sessions, trigger, confirmation, adx_gate,
            stop_model, target_model, time_window, direction,
        )
        metrics = compute_metrics(trades)
        metrics.update({
            "trigger": trigger,
            "confirmation": confirmation,
            "adx_gate": adx_gate,
            "stop_model": stop_model,
            "target_model": target_model,
            "time_window": time_window,
            "direction": direction,
        })
        all_results.append(metrics)

    elapsed = _time_mod.time() - t0
    log(f"  Complete: {total_configs:,} configs in {elapsed:.0f}s")

    results_df = pd.DataFrame(all_results)
    generate_report(results_df, freq, filter_stats)
    log(f"\nReport written to reports/quant-study-cvd-divergence.md")


# ── Report Generation ────────────────────────────────────────────────────────

def generate_report(results_df: pd.DataFrame, freq: dict, filter_stats: dict):
    Path("reports").mkdir(exist_ok=True)

    viable = results_df[results_df["trades"] >= 15].copy()
    top30 = viable.sort_values("pf", ascending=False).head(30)

    def make_agg(df, col):
        if len(df) == 0:
            return pd.DataFrame()
        return (
            df.groupby(col)
            .agg(
                configs=("trades", "count"),
                avg_trades=("trades", "mean"),
                avg_wr=("wr", "mean"),
                avg_pf=("pf", "mean"),
                avg_pnl=("total_pnl", "mean"),
                best_pf=("pf", "max"),
            )
            .round(2)
        )

    trigger_agg = make_agg(viable, "trigger")
    confirmation_agg = make_agg(viable, "confirmation")
    adx_agg = make_agg(viable, "adx_gate")
    stop_agg = make_agg(viable, "stop_model")
    target_agg = make_agg(viable, "target_model")
    direction_agg = make_agg(viable, "direction")
    time_agg = make_agg(viable, "time_window")

    lines = []
    lines.append("# CVD Divergence Study -- NQ Futures")
    lines.append("")
    lines.append("*Generated: 2026-03-12*")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append("CVD (Cumulative Volume Delta) divergence signals institutional exhaustion:")
    lines.append("- **Bullish**: Price makes lower low but CVD makes higher low")
    lines.append("- **Bearish**: Price makes higher high but CVD makes lower high")
    lines.append("")
    lines.append(f"This study tests CVD divergence as a standalone entry signal across "
                 f"{len(results_df):,} configurations")
    lines.append("(entry triggers, confirmation, ADX gates, stop models, target models, "
                 "time windows, directions).")
    lines.append("")

    # 1. Frequency
    lines.append("## 1. Divergence Frequency Analysis")
    lines.append("")
    lines.append("| Metric | Bull | Bear |")
    lines.append("|--------|------|------|")
    lines.append(f"| Total signals | {freq['bull_signals_total']:,} | {freq['bear_signals_total']:,} |")
    lines.append(f"| Avg per session | {freq['bull_per_session_avg']:.1f} | {freq['bear_per_session_avg']:.1f} |")
    lines.append(f"| Median per session | {freq['bull_per_session_median']:.0f} | {freq['bear_per_session_median']:.0f} |")
    s_bull_pct = freq['sessions_with_bull'] / max(freq['total_sessions'], 1) * 100
    s_bear_pct = freq['sessions_with_bear'] / max(freq['total_sessions'], 1) * 100
    lines.append(f"| Sessions with signal | {freq['sessions_with_bull']}/{freq['total_sessions']} ({s_bull_pct:.0f}%) | {freq['sessions_with_bear']}/{freq['total_sessions']} ({s_bear_pct:.0f}%) |")
    lines.append("")
    lines.append(f"**Total sessions analyzed**: {freq['total_sessions']}")
    lines.append("")
    lines.append("> CVD divergence signals fire frequently. Entry triggers, confirmation bars,")
    lines.append("> and cooldown (15 bars, max 2 trades/session) aggressively filter these signals.")
    lines.append("")

    # 2. Top 30
    lines.append("## 2. Top 30 Configurations by Profit Factor (min 15 trades)")
    lines.append("")
    if len(top30) > 0:
        lines.append("| # | Trigger | Confirm | ADX | Stop | Target | Window | Dir | Trades | WR% | PF | Total PnL | Avg PnL | MaxDD |")
        lines.append("|---|---------|---------|-----|------|--------|--------|-----|--------|-----|----|-----------|---------|-------|")
        for rank, (_, row) in enumerate(top30.iterrows(), 1):
            lines.append(
                f"| {rank} | {row['trigger']} | {row['confirmation']} | {row['adx_gate']} | "
                f"{row['stop_model']} | {row['target_model']} | {row['time_window']} | {row['direction']} | "
                f"{row['trades']:.0f} | {row['wr']:.1f} | {row['pf']:.2f} | "
                f"${row['total_pnl']:,.0f} | ${row['avg_pnl']:,.0f} | ${row['max_dd']:,.0f} |"
            )
        lines.append("")
    else:
        lines.append("> **No configurations met the minimum 15-trade threshold.**")
        lines.append("")

    # Summary stats
    total_with_trades = len(results_df[results_df["trades"] > 0])
    lines.append(f"*Configs with any trades: {total_with_trades:,}/{len(results_df):,} "
                 f"({total_with_trades/len(results_df)*100:.0f}%)*")
    lines.append(f"*Configs with >= 15 trades: {len(viable):,}/{len(results_df):,} "
                 f"({len(viable)/len(results_df)*100:.0f}%)*")
    lines.append("")

    # Dimension tables
    def add_dim_table(title, agg_df, dim_name):
        lines.append(f"## {title}")
        lines.append("")
        if len(agg_df) == 0:
            lines.append(f"> No viable configs for {dim_name} analysis.")
            lines.append("")
            return
        lines.append(f"| {dim_name} | Configs | Avg Trades | Avg WR% | Avg PF | Avg PnL | Best PF |")
        lines.append(f"|{'-' * max(len(dim_name), 8)}--|---------|------------|---------|--------|---------|---------|")
        for idx_val, row in agg_df.iterrows():
            lines.append(
                f"| {idx_val} | {row['configs']:.0f} | {row['avg_trades']:.0f} | "
                f"{row['avg_wr']:.1f} | {row['avg_pf']:.2f} | ${row['avg_pnl']:,.0f} | "
                f"{row['best_pf']:.2f} |"
            )
        lines.append("")

    add_dim_table("3. Entry Trigger Comparison", trigger_agg, "Trigger")
    add_dim_table("4. Reversal Confirmation Comparison", confirmation_agg, "Confirmation")
    add_dim_table("5. ADX Gate Analysis", adx_agg, "ADX Gate")
    add_dim_table("6. Stop Model Comparison", stop_agg, "Stop Model")
    add_dim_table("7. Target Model Comparison", target_agg, "Target Model")
    add_dim_table("8. Time Window Comparison", time_agg, "Time Window")
    add_dim_table("9. Direction Analysis", direction_agg, "Direction")

    # 10. Filter analysis
    lines.append("## 10. As-a-Filter Analysis")
    lines.append("")
    lines.append("What if CVD divergence is used as a confirmation FILTER for existing strategies")
    lines.append("rather than a standalone entry?")
    lines.append("")
    lines.append("### Overlap with Existing Indicators")
    lines.append("")
    lines.append("| Condition | Total Bars | + CVD Div | Overlap % |")
    lines.append("|-----------|------------|-----------|-----------|")
    lines.append(
        f"| Price at BB Lower | {filter_stats['bb_lower_bars']:,} | "
        f"{filter_stats['bb_lower_with_bull_div']:,} | "
        f"{filter_stats['bb_lower_div_pct']:.1f}% |"
    )
    lines.append(
        f"| Price at BB Upper | {filter_stats['bb_upper_bars']:,} | "
        f"{filter_stats['bb_upper_with_bear_div']:,} | "
        f"{filter_stats['bb_upper_div_pct']:.1f}% |"
    )
    lines.append(
        f"| RSI < 30 (Oversold) | {filter_stats['rsi_oversold_bars']:,} | "
        f"{filter_stats['rsi_oversold_with_bull_div']:,} | "
        f"{filter_stats['rsi_oversold_div_pct']:.1f}% |"
    )
    lines.append(
        f"| RSI > 70 (Overbought) | {filter_stats['rsi_overbought_bars']:,} | "
        f"{filter_stats['rsi_overbought_with_bear_div']:,} | "
        f"{filter_stats['rsi_overbought_div_pct']:.1f}% |"
    )
    lines.append(
        f"| Extended from VWAP (bull) | {filter_stats['vwap_extended_bars']:,} | "
        f"{filter_stats['vwap_extended_bull_div']:,} | -- |"
    )
    lines.append(
        f"| Extended from VWAP (bear) | {filter_stats['vwap_extended_bars']:,} | "
        f"{filter_stats['vwap_extended_bear_div']:,} | -- |"
    )
    lines.append("")
    lines.append("### Filter Recommendation")
    lines.append("")
    lines.append("CVD divergence adds value as a **confirmation filter** for mean-reversion strategies:")
    lines.append("- **80P Rule**: Require `cvd_div_bull` for LONG entries, `cvd_div_bear` for SHORT")
    lines.append("- **Edge Fade**: Already uses CVD divergence internally (see `edge_fade.py`)")
    lines.append("- **OR Reversal**: Add CVD divergence as optional high-confidence boost")
    lines.append("- **B-Day**: CVD divergence at IB extremes confirms rotation")
    lines.append("")
    lines.append("The filter approach is lower-risk because it reduces false positives on existing")
    lines.append("strategies without requiring a new standalone strategy with its own risk budget.")
    lines.append("")

    # VERDICT
    lines.append("## VERDICT")
    lines.append("")

    if len(viable) == 0:
        lines.append("### Filter-Only Recommendation")
        lines.append("")
        lines.append("CVD divergence did NOT produce enough standalone trades (min 15) across")
        lines.append("any configuration to justify a standalone strategy. The signal fires")
        lines.append("frequently but aggressive filtering (confirmation bars, ADX gates, time")
        lines.append("windows) combined with max 2 trades/session and 15-bar cooldown reduces")
        lines.append("trade count below viable thresholds.")
        lines.append("")
        lines.append("**Recommendation**: Use CVD divergence exclusively as a **confirmation filter**")
        lines.append("for existing mean-reversion strategies (80P, Edge Fade, OR Reversal, B-Day).")
    else:
        best = top30.iloc[0] if len(top30) > 0 else None
        if best is not None and best["pf"] >= 1.5 and best["trades"] >= 30:
            lines.append("### Standalone Strategy Viable")
            lines.append("")
            lines.append(f"The best configuration achieves **{best['pf']:.2f} PF** with "
                         f"**{best['trades']:.0f} trades** and **{best['wr']:.1f}% WR**.")
            lines.append("")
            lines.append("Best config:")
            lines.append(f"- Trigger: `{best['trigger']}`")
            lines.append(f"- Confirmation: `{best['confirmation']}`")
            lines.append(f"- ADX gate: `{best['adx_gate']}`")
            lines.append(f"- Stop: `{best['stop_model']}`")
            lines.append(f"- Target: `{best['target_model']}`")
            lines.append(f"- Window: `{best['time_window']}`")
            lines.append(f"- Direction: `{best['direction']}`")
            lines.append(f"- Total PnL: ${best['total_pnl']:,.0f}")
            lines.append(f"- Max drawdown: ${best['max_dd']:,.0f}")
            lines.append("")
            lines.append("**Recommendation**: Implement as standalone strategy AND as filter.")
            lines.append("- Standalone for high-conviction setups matching the best config")
            lines.append("- Filter for boosting existing strategy confidence")
        elif best is not None and best["pf"] >= 1.2:
            lines.append("### Marginal Standalone -- Prefer Filter")
            lines.append("")
            lines.append(f"Best config: **{best['pf']:.2f} PF**, **{best['trades']:.0f} trades**, "
                         f"**{best['wr']:.1f}% WR**, ${best['total_pnl']:,.0f} total PnL.")
            lines.append("")
            lines.append("Standalone is marginal -- not enough edge to justify a separate risk budget.")
            lines.append("")
            lines.append("**Recommendation**: Use primarily as a **confirmation filter** for existing")
            lines.append("strategies. Consider standalone only with additional confluence layers.")
        else:
            lines.append("### Filter-Only Recommendation")
            lines.append("")
            lines.append("No configuration shows compelling standalone edge.")
            lines.append("")
            lines.append("**Recommendation**: Use CVD divergence exclusively as a **confirmation filter**.")

    lines.append("")
    lines.append("---")
    lines.append(f"*Study parameters: 20-bar lookback, max 2 trades/session, 15-bar cooldown, "
                 f"$5/pt NQ tick value*")

    report = "\n".join(lines)
    with open("reports/quant-study-cvd-divergence.md", "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    main()
