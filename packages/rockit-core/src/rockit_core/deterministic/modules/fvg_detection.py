# modules/fvg_detection.py
"""
Fair Value Gap detection with lifecycle tracking.

FVGs are detected using the standard ICT 3-candle rule across 6 timeframes.
Key difference from v1: filled FVGs are RETAINED with status='filled' and
fill metadata, not discarded. This preserves the signal "an FVG existed here
and was filled" for correlation analysis.

Lifecycle: active → partially_filled → filled
"""

import pandas as pd


def get_fvg_detection(df_extended, df_current, current_time_str="11:45"):
    """
    Detect Fair Value Gaps (FVG) on daily, 4H, 1H, 90min, 15min, and 5min
    timeframes from last 3-5 days.

    Returns FVGs with lifecycle tracking:
      - fvg_id: unique ID per timeframe (e.g., "1h_3")
      - status: 'active', 'partially_filled', or 'filled'
      - fill_pct: 0.0 to 1.0 (how much of the gap was filled)
      - filled_time: when mitigation occurred (None if active)
      - created_time: when the FVG was formed

    Also includes BPR detection and engulfment checks.
    """
    current_time = pd.to_datetime(current_time_str).time()
    available_df = df_current[df_current.index.time <= current_time].copy()

    def detect_fvg(df, timeframe):
        """Detect all FVGs with lifecycle tracking."""
        fvgs = []
        fvg_counter = 0

        for i in range(2, len(df)):
            prev = df.iloc[i - 2]
            next_bar = df.iloc[i]

            # Bullish FVG: gap between prev high and next low
            if prev['high'] < next_bar['low']:
                fvg_counter += 1
                fvgs.append({
                    'fvg_id': f'{timeframe}_{fvg_counter}',
                    'type': 'bullish',
                    'top': next_bar['low'],
                    'bottom': prev['high'],
                    'gap_size': next_bar['low'] - prev['high'],
                    'created_time': df.index[i].strftime('%Y-%m-%d %H:%M'),
                    'time': df.index[i].strftime('%Y-%m-%d %H:%M'),
                    'status': 'active',
                    'fill_pct': 0.0,
                    'filled_time': None,
                    'timeframe': timeframe,
                })

            # Bearish FVG: gap between prev low and next high
            if prev['low'] > next_bar['high']:
                fvg_counter += 1
                fvgs.append({
                    'fvg_id': f'{timeframe}_{fvg_counter}',
                    'type': 'bearish',
                    'top': prev['low'],
                    'bottom': next_bar['high'],
                    'gap_size': prev['low'] - next_bar['high'],
                    'created_time': df.index[i].strftime('%Y-%m-%d %H:%M'),
                    'time': df.index[i].strftime('%Y-%m-%d %H:%M'),
                    'status': 'active',
                    'fill_pct': 0.0,
                    'filled_time': None,
                    'timeframe': timeframe,
                })

        # Check fill status for each FVG
        for fvg in fvgs:
            fvg_time = pd.to_datetime(fvg['created_time'])
            fvg_idx = df.index.get_indexer([fvg_time], method='nearest')[0]
            gap_size = fvg['gap_size']
            deepest_fill = 0.0

            for j in range(fvg_idx + 1, len(df)):
                bar = df.iloc[j]

                if fvg['type'] == 'bullish':
                    # Bullish FVG fills when price drops into the gap
                    if bar['low'] <= fvg['top']:
                        penetration = fvg['top'] - max(bar['low'], fvg['bottom'])
                        fill = min(1.0, penetration / gap_size) if gap_size > 0 else 1.0
                        if fill > deepest_fill:
                            deepest_fill = fill
                        if bar['low'] <= fvg['bottom']:
                            # Fully filled
                            fvg['status'] = 'filled'
                            fvg['fill_pct'] = 1.0
                            fvg['filled_time'] = df.index[j].strftime('%Y-%m-%d %H:%M')
                            break
                else:
                    # Bearish FVG fills when price rises into the gap
                    if bar['high'] >= fvg['bottom']:
                        penetration = min(bar['high'], fvg['top']) - fvg['bottom']
                        fill = min(1.0, penetration / gap_size) if gap_size > 0 else 1.0
                        if fill > deepest_fill:
                            deepest_fill = fill
                        if bar['high'] >= fvg['top']:
                            # Fully filled
                            fvg['status'] = 'filled'
                            fvg['fill_pct'] = 1.0
                            fvg['filled_time'] = df.index[j].strftime('%Y-%m-%d %H:%M')
                            break

            # Partially filled (entered gap but didn't fully close it)
            if fvg['status'] == 'active' and deepest_fill > 0:
                fvg['status'] = 'partially_filled'
                fvg['fill_pct'] = round(deepest_fill, 3)

        return fvgs

    def _split_by_status(fvgs):
        """Split FVGs into active, recently_filled, and filled lists."""
        active = [f for f in fvgs if f['status'] in ('active', 'partially_filled')]
        filled = [f for f in fvgs if f['status'] == 'filled']
        # Recently filled = filled in last 5 bars of their timeframe
        # (approximate: last 5 entries in the filled list)
        recently_filled = filled[-5:] if filled else []
        return active, recently_filled, filled

    def detect_bpr(df, fvgs, timeframe):
        """Detect Balanced Price Range (BPR) events."""
        bpr_events = []
        active_fvgs = [f for f in fvgs if f['status'] in ('active', 'partially_filled')]
        for fvg in active_fvgs:
            fvg_time = pd.to_datetime(fvg['time'])
            fvg_idx = df.index.get_indexer([fvg_time], method='nearest')[0]
            for i in range(fvg_idx + 1, len(df)):
                bar = df.iloc[i]
                if (fvg['type'] == 'bearish'
                        and bar['low'] < fvg['bottom']
                        and bar['high'] > fvg['top']
                        and bar['close'] > bar['open']):
                    bpr_events.append({
                        'type': 'bullish_bpr',
                        'fvg_inverted': fvg,
                        'engulfing_time': df.index[i].strftime('%Y-%m-%d %H:%M'),
                    })
                elif (fvg['type'] == 'bullish'
                      and bar['high'] > fvg['top']
                      and bar['low'] < fvg['bottom']
                      and bar['close'] < bar['open']):
                    bpr_events.append({
                        'type': 'bearish_bpr',
                        'fvg_inverted': fvg,
                        'engulfing_time': df.index[i].strftime('%Y-%m-%d %H:%M'),
                    })
        return bpr_events

    def check_engulfed_past_fvgs(fvgs, timeframe):
        """Check if current FVG engulfs past FVGs."""
        engulfed = []
        active = [f for f in fvgs if f['status'] in ('active', 'partially_filled')]
        if len(active) < 2:
            return engulfed
        current_fvg = active[-1]
        for past_fvg in active[:-1]:
            if current_fvg['type'] != past_fvg['type']:
                if (current_fvg['bottom'] <= past_fvg['bottom']
                        and current_fvg['top'] >= past_fvg['top']):
                    engulfed.append({
                        'engulfing_fvg': current_fvg,
                        'engulfed_fvg': past_fvg,
                        'timeframe': timeframe,
                    })
        return engulfed

    # Resample to timeframes
    daily = available_df.resample('D').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()
    fourh = available_df.resample('4h').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()
    oneh = available_df.resample('1h').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()
    ninetymin = available_df.resample('90min').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()
    fifteenmin = available_df.resample('15min').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()
    # 5-min FVG disabled — too many gaps at this resolution, noise > signal.
    # Logic retained in detect_fvg() for on-demand use (e.g., signal-time deep dive).

    # Detect FVGs with lifecycle tracking
    daily_fvg = detect_fvg(daily, "daily")
    fourh_fvg = detect_fvg(fourh, "4h")
    oneh_fvg = detect_fvg(oneh, "1h")
    ninetymin_fvg = detect_fvg(ninetymin, "90min")
    fifteenmin_fvg = detect_fvg(fifteenmin, "15min")

    # Detect BPR (on active FVGs only)
    daily_bpr = detect_bpr(daily, daily_fvg, "daily")
    fourh_bpr = detect_bpr(fourh, fourh_fvg, "4h")
    oneh_bpr = detect_bpr(oneh, oneh_fvg, "1h")
    ninetymin_bpr = detect_bpr(ninetymin, ninetymin_fvg, "90min")
    fifteenmin_bpr = detect_bpr(fifteenmin, fifteenmin_fvg, "15min")

    # Check engulfed past FVGs on 15min only (5min disabled)
    fifteenmin_engulfed = check_engulfed_past_fvgs(fifteenmin_fvg, "15min")

    # --- NDOG (New Day Opening Gap) and NWOG (New Week Opening Gap) ---
    ndog = _detect_ndog(df_extended, df_current, available_df)
    nwog = _detect_nwog(df_extended, df_current, available_df)

    # Split each timeframe into active + recently_filled
    def _build_tf_result(all_fvgs):
        active, recently_filled, filled = _split_by_status(all_fvgs)
        return {
            'active': active,
            'recently_filled': recently_filled,
            'all': all_fvgs,
        }

    return {
        # FVGs with lifecycle (each has active, recently_filled, all)
        "daily_fvg": daily_fvg,
        "4h_fvg": fourh_fvg,
        "1h_fvg": oneh_fvg,
        "90min_fvg": ninetymin_fvg,
        "15min_fvg": fifteenmin_fvg,
        "5min_fvg": [],  # Disabled — too noisy at 5min resolution

        # Recently filled across all timeframes (quick access)
        "recently_filled": (
            [f for f in daily_fvg if f['status'] == 'filled'][-2:]
            + [f for f in fourh_fvg if f['status'] == 'filled'][-2:]
            + [f for f in oneh_fvg if f['status'] == 'filled'][-3:]
            + [f for f in fifteenmin_fvg if f['status'] == 'filled'][-3:]
        ),

        # BPR events
        "daily_bpr": daily_bpr,
        "4h_bpr": fourh_bpr,
        "1h_bpr": oneh_bpr,
        "90min_bpr": ninetymin_bpr,
        "15min_bpr": fifteenmin_bpr,
        "5min_bpr": [],  # Disabled

        # Engulfment
        "5min_engulfed": [],  # Disabled
        "15min_engulfed": fifteenmin_engulfed,

        # Opening gaps (ICT concepts)
        "ndog": ndog,
        "nwog": nwog,

        "note": (
            "FVGs detected with lifecycle tracking (5min disabled — too noisy). "
            "status: active (unfilled), partially_filled (price entered gap), filled (fully mitigated). "
            "Filled FVGs retained with fill_pct and filled_time. "
            "BPR = opposing engulfing inversion on active FVGs. "
            "Engulfed = current FVG fully covers past opposite-type FVG. "
            "NDOG = New Day Opening Gap (prior close → current open). "
            "NWOG = New Week Opening Gap (Friday close → Sunday/Monday open)."
        ),
    }


def _detect_ndog(df_extended, df_current, available_df):
    """Detect New Day Opening Gap (NDOG).

    NDOG = gap between prior session's last RTH close and current session's open.
    ndog_high = max(prior_close, current_open)
    ndog_low = min(prior_close, current_open)

    Tracks fill status: unfilled, partially_filled, filled.
    """
    try:
        # Get current session date and prior session
        if 'session_date' not in df_extended.columns:
            return {"status": "no_session_data"}

        current_date = df_current['session_date'].iloc[0] if 'session_date' in df_current.columns else None
        if current_date is None:
            return {"status": "no_session_date"}

        all_dates = sorted(df_extended['session_date'].unique())
        if current_date not in all_dates:
            return {"status": "no_session_date"}

        current_idx = all_dates.index(current_date)
        if current_idx == 0:
            return {"status": "no_prior_session"}

        prior_date = all_dates[current_idx - 1]

        # Prior session last RTH close
        prior_session = df_extended[df_extended['session_date'] == prior_date]
        prior_rth = prior_session.between_time('09:30', '16:00')
        if prior_rth.empty:
            return {"status": "no_prior_rth_data"}
        prior_close = float(prior_rth.iloc[-1]['close'])

        # Current session open (first RTH bar)
        current_rth = available_df[available_df.index.time >= pd.to_datetime('09:30').time()]
        if current_rth.empty:
            return {"status": "no_current_rth_data"}
        current_open = float(current_rth.iloc[0]['open'])

        # NDOG
        ndog_high = max(prior_close, current_open)
        ndog_low = min(prior_close, current_open)
        gap_size = ndog_high - ndog_low

        if gap_size < 0.5:  # No meaningful gap
            return {
                "status": "no_gap",
                "prior_close": round(prior_close, 2),
                "current_open": round(current_open, 2),
                "gap_size": round(gap_size, 2),
            }

        direction = "gap_up" if current_open > prior_close else "gap_down"

        # Check fill status
        fill_status = "unfilled"
        fill_pct = 0.0
        filled_time = None

        for i in range(len(current_rth)):
            bar = current_rth.iloc[i]
            if direction == "gap_up":
                # Gap up fills when price drops to prior close
                if bar['low'] <= ndog_low:
                    fill_status = "filled"
                    fill_pct = 1.0
                    filled_time = current_rth.index[i].strftime('%H:%M')
                    break
                elif bar['low'] < ndog_high:
                    penetration = ndog_high - bar['low']
                    pct = min(1.0, penetration / gap_size)
                    if pct > fill_pct:
                        fill_pct = pct
                        fill_status = "partially_filled"
            else:
                # Gap down fills when price rises to prior close
                if bar['high'] >= ndog_high:
                    fill_status = "filled"
                    fill_pct = 1.0
                    filled_time = current_rth.index[i].strftime('%H:%M')
                    break
                elif bar['high'] > ndog_low:
                    penetration = bar['high'] - ndog_low
                    pct = min(1.0, penetration / gap_size)
                    if pct > fill_pct:
                        fill_pct = pct
                        fill_status = "partially_filled"

        return {
            "gap_type": "NDOG",
            "direction": direction,
            "prior_close": round(prior_close, 2),
            "current_open": round(current_open, 2),
            "ndog_high": round(ndog_high, 2),
            "ndog_low": round(ndog_low, 2),
            "gap_size": round(gap_size, 2),
            "status": fill_status,
            "fill_pct": round(fill_pct, 3),
            "filled_time": filled_time,
        }
    except Exception:
        return {"status": "error"}


def _detect_nwog(df_extended, df_current, available_df):
    """Detect New Week Opening Gap (NWOG).

    NWOG = gap between Friday's last RTH close and Sunday/Monday's open.
    nwog_high = max(friday_close, monday_open)
    nwog_low = min(friday_close, monday_open)

    Only computed on Monday sessions. Tracks fill status across the week.
    """
    try:
        if 'session_date' not in df_extended.columns:
            return {"status": "no_session_data"}

        current_date = df_current['session_date'].iloc[0] if 'session_date' in df_current.columns else None
        if current_date is None:
            return {"status": "no_session_date"}

        current_dt = pd.to_datetime(current_date)

        # NWOG is defined from the start of the week
        # Find the Friday before current session
        day_of_week = current_dt.dayofweek  # Monday=0, Friday=4
        if day_of_week == 0:
            # Monday — look back to Friday (3 calendar days)
            friday_date = (current_dt - pd.Timedelta(days=3)).strftime('%Y-%m-%d')
        elif day_of_week <= 4:
            # Tue-Fri — find the most recent Monday's open
            days_since_monday = day_of_week
            monday_date = (current_dt - pd.Timedelta(days=days_since_monday)).strftime('%Y-%m-%d')
            friday_date = (current_dt - pd.Timedelta(days=days_since_monday + 3)).strftime('%Y-%m-%d')
        else:
            return {"status": "weekend"}

        # Find Friday session in extended data
        all_dates = sorted(df_extended['session_date'].unique())

        # Find the closest Friday session (might be Thursday if Friday was holiday)
        friday_session = None
        for d in reversed(all_dates):
            dt = pd.to_datetime(d)
            if dt < current_dt and dt.dayofweek == 4:  # Friday
                friday_session = d
                break
            elif dt < current_dt and dt.dayofweek == 3 and friday_date not in all_dates:
                # Thursday if Friday was holiday
                friday_session = d
                break

        if friday_session is None:
            return {"status": "no_prior_friday"}

        # Friday last RTH close
        friday_data = df_extended[df_extended['session_date'] == friday_session]
        friday_rth = friday_data.between_time('09:30', '16:00')
        if friday_rth.empty:
            return {"status": "no_friday_rth_data"}
        friday_close = float(friday_rth.iloc[-1]['close'])

        # Monday (or current week start) first RTH open
        # Find the first session of this week
        monday_session = None
        for d in all_dates:
            dt = pd.to_datetime(d)
            if dt.isocalendar()[1] == current_dt.isocalendar()[1] and dt.year == current_dt.year:
                monday_session = d
                break

        if monday_session is None:
            monday_session = current_date

        monday_data = df_extended[df_extended['session_date'] == monday_session]
        monday_rth = monday_data.between_time('09:30', '16:00')
        if monday_rth.empty:
            # If Monday has no RTH data, use current session
            current_rth = available_df[available_df.index.time >= pd.to_datetime('09:30').time()]
            if current_rth.empty:
                return {"status": "no_monday_rth_data"}
            monday_open = float(current_rth.iloc[0]['open'])
        else:
            monday_open = float(monday_rth.iloc[0]['open'])

        # NWOG
        nwog_high = max(friday_close, monday_open)
        nwog_low = min(friday_close, monday_open)
        gap_size = nwog_high - nwog_low

        if gap_size < 1.0:
            return {
                "status": "no_gap",
                "friday_close": round(friday_close, 2),
                "monday_open": round(monday_open, 2),
                "gap_size": round(gap_size, 2),
            }

        direction = "gap_up" if monday_open > friday_close else "gap_down"

        # Check fill status using current session data
        current_rth = available_df[available_df.index.time >= pd.to_datetime('09:30').time()]
        fill_status = "unfilled"
        fill_pct = 0.0
        filled_time = None

        for i in range(len(current_rth)):
            bar = current_rth.iloc[i]
            if direction == "gap_up":
                if bar['low'] <= nwog_low:
                    fill_status = "filled"
                    fill_pct = 1.0
                    filled_time = current_rth.index[i].strftime('%H:%M')
                    break
                elif bar['low'] < nwog_high:
                    penetration = nwog_high - bar['low']
                    pct = min(1.0, penetration / gap_size)
                    if pct > fill_pct:
                        fill_pct = pct
                        fill_status = "partially_filled"
            else:
                if bar['high'] >= nwog_high:
                    fill_status = "filled"
                    fill_pct = 1.0
                    filled_time = current_rth.index[i].strftime('%H:%M')
                    break
                elif bar['high'] > nwog_low:
                    penetration = bar['high'] - nwog_low
                    pct = min(1.0, penetration / gap_size)
                    if pct > fill_pct:
                        fill_pct = pct
                        fill_status = "partially_filled"

        return {
            "gap_type": "NWOG",
            "direction": direction,
            "friday_close": round(friday_close, 2),
            "monday_open": round(monday_open, 2),
            "nwog_high": round(nwog_high, 2),
            "nwog_low": round(nwog_low, 2),
            "gap_size": round(gap_size, 2),
            "status": fill_status,
            "fill_pct": round(fill_pct, 3),
            "filled_time": filled_time,
            "friday_session": friday_session,
        }
    except Exception:
        return {"status": "error"}
