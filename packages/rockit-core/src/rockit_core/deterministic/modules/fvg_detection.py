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
    fivemin = available_df.resample('5min').agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna()

    # Detect FVGs with lifecycle tracking
    daily_fvg = detect_fvg(daily, "daily")
    fourh_fvg = detect_fvg(fourh, "4h")
    oneh_fvg = detect_fvg(oneh, "1h")
    ninetymin_fvg = detect_fvg(ninetymin, "90min")
    fifteenmin_fvg = detect_fvg(fifteenmin, "15min")
    fivemin_fvg = detect_fvg(fivemin, "5min")

    # Detect BPR (on active FVGs only)
    daily_bpr = detect_bpr(daily, daily_fvg, "daily")
    fourh_bpr = detect_bpr(fourh, fourh_fvg, "4h")
    oneh_bpr = detect_bpr(oneh, oneh_fvg, "1h")
    ninetymin_bpr = detect_bpr(ninetymin, ninetymin_fvg, "90min")
    fifteenmin_bpr = detect_bpr(fifteenmin, fifteenmin_fvg, "15min")
    fivemin_bpr = detect_bpr(fivemin, fivemin_fvg, "5min")

    # Check engulfed past FVGs on 5min and 15min
    fivemin_engulfed = check_engulfed_past_fvgs(fivemin_fvg, "5min")
    fifteenmin_engulfed = check_engulfed_past_fvgs(fifteenmin_fvg, "15min")

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
        "5min_fvg": fivemin_fvg,

        # Recently filled across all timeframes (quick access)
        "recently_filled": (
            [f for f in daily_fvg if f['status'] == 'filled'][-2:]
            + [f for f in fourh_fvg if f['status'] == 'filled'][-2:]
            + [f for f in oneh_fvg if f['status'] == 'filled'][-3:]
            + [f for f in fifteenmin_fvg if f['status'] == 'filled'][-3:]
            + [f for f in fivemin_fvg if f['status'] == 'filled'][-5:]
        ),

        # BPR events
        "daily_bpr": daily_bpr,
        "4h_bpr": fourh_bpr,
        "1h_bpr": oneh_bpr,
        "90min_bpr": ninetymin_bpr,
        "15min_bpr": fifteenmin_bpr,
        "5min_bpr": fivemin_bpr,

        # Engulfment
        "5min_engulfed": fivemin_engulfed,
        "15min_engulfed": fifteenmin_engulfed,

        "note": (
            "FVGs detected with lifecycle tracking. "
            "status: active (unfilled), partially_filled (price entered gap), filled (fully mitigated). "
            "Filled FVGs retained with fill_pct and filled_time. "
            "BPR = opposing engulfing inversion on active FVGs. "
            "Engulfed = current FVG fully covers past opposite-type FVG."
        ),
    }
