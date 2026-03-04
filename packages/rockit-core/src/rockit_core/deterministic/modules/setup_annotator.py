"""
Setup Annotator: Extracts all active trading setups from a snapshot
and selects ONE primary setup using a strict priority hierarchy.

Priority (highest to lowest):
  1. OR Reversal     — 9:30-10:00 sweep + reversal (66% WR, PF 3.34)
  2. 80P Rule        — gap open outside VA, acceptance close back inside (100% fill)
  3. VA Edge Fade    — poke beyond prior VA, rejection confirmed (70% WR)
  4. 20P Rule        — 3 consecutive IB extension closes (trend continuation)
  5. Edge Fade       — lower IB edge to midpoint, long-only (58% WR)
  6. Mean Reversion  — dual acceptance + range targets
  7. Balance P/b     — P-type / b-type fade playbook

Design rule: ONE primary_setup at a time — do not output conflicting setups
to the LLM. All setup data is present in setup_details for reference,
but only primary_setup drives the playbook output.
"""


def extract_all_setups(snapshot):
    """
    Extract all active setup signals from a snapshot.

    Returns:
        dict: {
            "primary_setup": str — name of highest-priority active setup, or "NONE"
            "primary_setup_detail": dict — entry/stop/target/confidence for primary
            "all_active_setups": list[str] — all firing setup names (for reference)
            "setup_details": dict — full detail dict for every setup
        }
    """
    intraday = snapshot.get('intraday', {})

    # --- Extract each module's data ---
    gva  = intraday.get('globex_va_analysis', {}) or {}
    t20p = intraday.get('twenty_percent_rule', {}) or {}
    vef  = intraday.get('va_edge_fade', {}) or {}
    orr  = snapshot.get('or_reversal', {}) or {}
    ef   = snapshot.get('edge_fade', {}) or {}
    mr   = snapshot.get('mean_reversion', {}) or {}
    bc   = snapshot.get('balance_classification', {}) or {}

    # --- Build detail dict for each setup ---
    setup_details = {
        'or_reversal': {
            'triggered': orr.get('signal') in ('LONG', 'SHORT'),
            'signal': orr.get('signal', 'NONE'),
            'entry': orr.get('entry'),
            'stop': orr.get('stop'),
            'target': orr.get('target'),
            'risk_pts': orr.get('risk'),
            'rr': orr.get('rr'),
            'opening_drive': orr.get('opening_drive'),
            'note': orr.get('note'),
        },
        '80p': {
            'triggered': bool(gva.get('80p_setup_ready')),
            'model': gva.get('active_model'),
            'type': gva.get('80p_setup_type'),
            'confidence': gva.get('80p_confidence', 0),
            'entry': gva.get('entry_price'),
            'stop': gva.get('stop_price'),
            'risk_pts': gva.get('risk_pts'),
            'target_4r': gva.get('target_4r'),
            'gap_status': gva.get('gap_status'),
        },
        'va_edge_fade': {
            'triggered': bool(vef.get('va_edge_fade_active')),
            'setup': vef.get('active_setup', 'none'),
            'poke_number': vef.get('poke_number', 0),
            'short_bias_bonus': bool(vef.get('short_bias_bonus')),
            'confidence': vef.get('confidence', 0),
            'entry': vef.get('entry_price'),
            'stop': vef.get('stop_price'),
            'risk_pts': vef.get('risk_pts'),
            'target_2r': vef.get('target_2r'),
        },
        '20p': {
            'triggered': bool(t20p.get('20p_triggered')),
            'direction': t20p.get('20p_direction', 'none'),
            'confidence': t20p.get('confidence', 0),
            'entry': t20p.get('entry_price'),
            'stop': t20p.get('stop_price'),
            'risk_pts': t20p.get('risk_pts'),
            'target_2r': t20p.get('target_2r'),
            'consec_closes': max(
                t20p.get('consecutive_closes_above_ibh', 0),
                t20p.get('consecutive_closes_below_ibl', 0)
            ),
        },
        'edge_fade': {
            'triggered': ef.get('signal') == 'LONG',
            'signal': ef.get('signal', 'NONE'),
            'entry': ef.get('entry'),
            'stop': ef.get('stop'),
            'target': ef.get('target'),
            'risk_pts': ef.get('risk'),
            'confidence': ef.get('confidence', 'low'),
            'of_quality': ef.get('of_quality', 0),
            'note': ef.get('note'),
        },
        'mean_reversion': {
            'triggered': mr.get('recommended_action') in ('DUAL_SIDED', 'SHORT_BIAS', 'LONG_BIAS'),
            'action': mr.get('recommended_action', 'STANDBY'),
            'ib_range_classification': mr.get('ib_range_classification'),
            'ib_range_pts': mr.get('ib_range_pts'),
            'combined_confidence': mr.get('combined_confidence', 0),
            'target_high': mr.get('mean_reversion_target_high'),
            'target_low': mr.get('mean_reversion_target_low'),
            'trade_setup_high': mr.get('trade_setup_high'),
            'trade_setup_low': mr.get('trade_setup_low'),
        },
        'balance_pb': {
            'triggered': bc.get('balance_type') in ('P', 'b'),
            'balance_type': bc.get('balance_type'),
            'playbook_action': bc.get('playbook_action'),
            'confidence': bc.get('confidence', 0),
            'dominant_bias': bc.get('dominant_bias'),
            'upper_probe_result': bc.get('upper_probe_result'),
            'lower_probe_result': bc.get('lower_probe_result'),
        },
    }

    # --- Collect all active setups (for reference) ---
    priority_order = ['or_reversal', '80p', 'va_edge_fade', '20p', 'edge_fade', 'mean_reversion', 'balance_pb']
    all_active = [name for name in priority_order if setup_details[name]['triggered']]

    # --- Select primary setup (highest priority active one) ---
    primary = all_active[0] if all_active else 'NONE'
    primary_detail = setup_details[primary] if primary != 'NONE' else {}

    return {
        'primary_setup': primary,
        'primary_setup_detail': primary_detail,
        'all_active_setups': all_active,
        'setup_details': setup_details,
    }


def generate_setup_narrative(primary_setup, primary_detail, snapshot, inference):
    """
    Generate a plain-English narrative explaining WHY the primary setup is being played.
    References specific field values so the LLM learns the reasoning chain.

    Returns: str — 2-4 sentence explanation
    """
    if primary_setup == 'NONE':
        day_type = inference.get('day_type', 'unknown')
        bias = inference.get('bias', 'Flat')
        return (
            f"No high-conviction setup active. Day context: {day_type}, bias {bias}. "
            f"No sweep+reversal, gap, VA poke, IB extension, or balance extreme detected. "
            f"Observe and wait for structure to develop."
        )

    intraday = snapshot.get('intraday', {})
    ib = intraday.get('ib', {})
    ib_high = ib.get('ib_high', 0)
    ib_low = ib.get('ib_low', 0)
    atr14 = ib.get('atr14', 0)
    day_type = inference.get('day_type', 'unknown')
    bias = inference.get('bias', 'unknown')

    if primary_setup == 'or_reversal':
        signal = primary_detail.get('signal', 'NONE')
        drive = primary_detail.get('opening_drive', 'ROTATION')
        entry = primary_detail.get('entry')
        stop = primary_detail.get('stop')
        target = primary_detail.get('target')
        risk = primary_detail.get('risk_pts')
        rr = primary_detail.get('rr')
        direction = 'SHORT' if signal == 'SHORT' else 'LONG'
        swept_side = 'high swept overnight/PDH level' if signal == 'SHORT' else 'low swept overnight/PDL level'
        reversal_side = 'reversed below OR midpoint' if signal == 'SHORT' else 'reversed above OR midpoint'
        return (
            f"OR Reversal (Judas Swing) active: EOR {swept_side}, then price {reversal_side}. "
            f"Opening drive: {drive}. Entry {direction} at {entry}, stop at {stop} "
            f"({risk:.1f}pts risk), target {target} ({rr:.1f}R). "
            f"Day context developing as {day_type}. "
            f"Playbook: fade the false open sweep, ride the reversal to target within RTH session."
        )

    if primary_setup == '80p':
        model = primary_detail.get('model', 'A')
        setup_type = primary_detail.get('type', '')
        gap_status = primary_detail.get('gap_status', '')
        entry = primary_detail.get('entry')
        stop = primary_detail.get('stop')
        risk = primary_detail.get('risk_pts')
        target = primary_detail.get('target_4r')
        confidence = primary_detail.get('confidence', 0)
        gva = intraday.get('globex_va_analysis', {})
        prev_vah = gva.get('previous_session_vah', 0)
        prev_val = gva.get('previous_session_val', 0)
        direction = 'LONG' if 'long' in str(setup_type).lower() else 'SHORT'
        return (
            f"80P Rule (Dalton Mean Reversion) active — Model {model}: "
            f"RTH open {gap_status} prior session VA ({prev_val:.2f}–{prev_vah:.2f}). "
            f"Acceptance close confirmed back inside VA. 100% historical gap fill probability. "
            f"Entry {direction} at {entry}, stop at VA edge +10pts ({stop}), "
            f"risk {risk:.1f}pts, target opposite VA ({target}). "
            f"Confidence {confidence}%. Playbook: mean reversion to fill the gap."
        )

    if primary_setup == 'va_edge_fade':
        setup = primary_detail.get('setup', 'none')
        poke_num = primary_detail.get('poke_number', 1)
        entry = primary_detail.get('entry')
        stop = primary_detail.get('stop')
        risk = primary_detail.get('risk_pts')
        target = primary_detail.get('target_2r')
        short_bonus = primary_detail.get('short_bias_bonus', False)
        confidence = primary_detail.get('confidence', 0)
        gva = intraday.get('globex_va_analysis', {})
        prev_vah = gva.get('previous_session_vah', 0)
        prev_val = gva.get('previous_session_val', 0)
        direction = 'SHORT' if 'vah' in setup else 'LONG'
        level = f"VAH {prev_vah:.2f}" if 'vah' in setup else f"VAL {prev_val:.2f}"
        bonus_note = " Short bias bonus applies (VAH fades historically 70% WR)." if short_bonus else ""
        return (
            f"VA Edge Fade active: price poked beyond prior session {level} "
            f"(poke #{poke_num}) then closed back inside — rejection confirmed by 2x consecutive closes inside VA. "
            f"Entry {direction} at {entry}, stop 2xATR ({stop}), "
            f"risk {risk:.1f}pts, target 2R ({target}).{bonus_note} "
            f"Confidence {confidence}%. Playbook: fade the failed breakout, ride back to VA interior."
        )

    if primary_setup == '20p':
        direction = primary_detail.get('direction', 'none').upper()
        consec = primary_detail.get('consec_closes', 0)
        entry = primary_detail.get('entry')
        stop = primary_detail.get('stop')
        risk = primary_detail.get('risk_pts')
        target = primary_detail.get('target_2r')
        confidence = primary_detail.get('confidence', 0)
        boundary = 'IBH' if direction == 'LONG' else 'IBL'
        boundary_level = ib_high if direction == 'LONG' else ib_low
        return (
            f"20P Rule active: {consec} consecutive 5-min closes {'above IBH' if direction == 'LONG' else 'below IBL'} "
            f"post-10:30 — trend continuation confirmed. "
            f"IB boundary {boundary} ({boundary_level:.2f}) broken with acceptance. "
            f"Entry {direction} at {entry}, stop 2xATR ({stop}), "
            f"risk {risk:.1f}pts, target 2R ({target}). "
            f"Confidence {confidence}%. Playbook: enter trend continuation, ride to 2R minimum."
        )

    if primary_setup == 'edge_fade':
        signal = primary_detail.get('signal', 'NONE')
        entry = primary_detail.get('entry')
        stop = primary_detail.get('stop')
        target = primary_detail.get('target')
        risk = primary_detail.get('risk_pts')
        of_quality = primary_detail.get('of_quality', 0)
        confidence = primary_detail.get('confidence', 'low')
        return (
            f"Edge Fade (LONG only) active: price extended to lower IB edge, "
            f"order flow quality score {of_quality}/3. "
            f"Entry LONG at {entry}, stop at {stop}, "
            f"risk {risk:.1f}pts, target IB midpoint ({target}). "
            f"Confidence {confidence}. Playbook: mean reversion long from lower IB boundary to midpoint. "
            f"Day context: {day_type}, bias {bias}."
        )

    if primary_setup == 'mean_reversion':
        action = primary_detail.get('action', 'STANDBY')
        ib_class = primary_detail.get('ib_range_classification', 'normal')
        ib_pts = primary_detail.get('ib_range_pts', 0)
        combined_conf = primary_detail.get('combined_confidence', 0)
        target_high = primary_detail.get('target_high')
        target_low = primary_detail.get('target_low')
        return (
            f"Mean Reversion Engine active ({action}): {ib_class} IB range ({ib_pts:.0f}pts). "
            f"Dual acceptance confirmed at both VA extremes. "
            f"SHORT target from high: {target_high}, LONG target from low: {target_low}. "
            f"Combined confidence {combined_conf:.0%}. "
            f"Playbook: fade both extremes with defined risk — {'VWAP' if ib_class == 'tight' else 'opposite VA'} as target."
        )

    if primary_setup == 'balance_pb':
        balance_type = primary_detail.get('balance_type', 'neutral')
        action = primary_detail.get('playbook_action', 'WAIT_DUAL_SIDED')
        confidence = primary_detail.get('confidence', 0)
        upper_result = primary_detail.get('upper_probe_result', 'none')
        lower_result = primary_detail.get('lower_probe_result', 'none')
        bc = snapshot.get('balance_classification', {}) or {}
        note = bc.get('note', '')
        return (
            f"Balance Day {balance_type}-type classification: "
            f"upper probe {upper_result}, lower probe {lower_result}. "
            f"Playbook: {action.replace('_', ' ')}. "
            f"Confidence {confidence:.0%}. "
            f"{'P-type = upper rejected, lower accepted → SHORT VAH fade.' if balance_type == 'P' else 'b-type = lower rejected, upper accepted → LONG VAL fade.'} "
            f"{note}"
        )

    return f"Setup {primary_setup} active. See setup_details for entry/stop/target."


def build_output_dict(snapshot, inference):
    """
    Build the full training output dict from a snapshot + inference.
    Includes base inference fields + single unambiguous primary_setup + narrative.
    """
    setup_annotation = extract_all_setups(snapshot)
    primary = setup_annotation['primary_setup']
    primary_detail = setup_annotation['primary_setup_detail']

    narrative = generate_setup_narrative(primary, primary_detail, snapshot, inference)

    return {
        # Base inference fields
        'day_type': inference.get('day_type'),
        'bias': inference.get('bias'),
        'confidence': inference.get('confidence'),
        'trend_strength': inference.get('trend_strength'),
        'one_liner': inference.get('one_liner'),
        'value_acceptance': inference.get('value_acceptance'),
        # Setup fields — one clear primary, narrative explains WHY, all details available
        'primary_setup': primary,
        'setup_reasoning': narrative,
        'primary_setup_detail': primary_detail,
        'all_active_setups': setup_annotation['all_active_setups'],
        'setup_details': setup_annotation['setup_details'],
    }
