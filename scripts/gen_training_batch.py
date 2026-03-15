"""
Batch training pair writer. Called by agents to write completed pairs.

Usage:
    uv run python scripts/gen_training_batch.py --day 2026-02-26 --times 09:35,09:40,09:45 --output data/training_pairs/batch_0226_0935.jsonl

This script reads snapshots for the given times and writes a JSONL file
where each line has: {"input": <snapshot>, "output": null, "metadata": {...}}

The agent then reads this file, fills in the "output" field with analysis,
and writes the completed file.
"""
import argparse
import json
import sys
from datetime import datetime


def extract_snapshots(day, times):
    """Read specific time snapshots from a day's JSONL file."""
    path = f"data/json_snapshots/deterministic_{day}.jsonl"
    snapshots = {}
    target_times = set(times)

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            snap = json.loads(line)
            if snap['current_et_time'] in target_times:
                snapshots[snap['current_et_time']] = snap

    return snapshots


def summarize_snapshot(snap):
    """Create a compact summary of key snapshot fields for agent context."""
    inf = snap.get('inference', {})
    ib = snap.get('intraday', {}).get('ib', {})
    cri = snap.get('cri_readiness', {})
    bal = snap.get('balance_classification', {})
    dpoc = snap.get('intraday', {}).get('dpoc_migration', {})
    wp = snap.get('intraday', {}).get('wick_parade', {})
    tpo = snap.get('intraday', {}).get('tpo_profile', {})
    pm = snap.get('premarket', {})
    ms_va = snap.get('market_structure', {}).get('prior_va_analysis', {})
    ef = snap.get('edge_fade', {})
    orr = snap.get('or_reversal', {})
    mr = snap.get('mean_reversion', {})
    cc = snap.get('core_confluences', {})

    dpoc_regime = dpoc.get('dpoc_regime', dpoc.get('migration_status', 'N/A'))

    return {
        "time": snap['current_et_time'],
        "day_type": inf.get('day_type', {}).get('type', 'N/A'),
        "bias": inf.get('bias', 'N/A'),
        "confidence": inf.get('confidence', 'N/A'),
        "trend_strength": inf.get('trend_strength', 'N/A'),
        "day_type_morph": inf.get('day_type_morph', 'N/A'),
        "day_type_reasoning": inf.get('day_type_reasoning', []),
        "one_liner": inf.get('one_liner', 'N/A'),
        "ib_status": ib.get('ib_status', 'N/A'),
        "ib_range": ib.get('ib_range', 0),
        "ib_width_class": ib.get('ib_width_class', 'N/A'),
        "ibh": ib.get('ib_high', 0),
        "ibl": ib.get('ib_low', 0),
        "ib_mid": ib.get('ib_mid', 0),
        "price": ib.get('current_close', 0),
        "vwap": ib.get('current_vwap', 0),
        "rsi": ib.get('rsi14', 0),
        "price_vs_ib": ib.get('price_vs_ib', 'N/A'),
        "price_vs_vwap": ib.get('price_vs_vwap', 'N/A'),
        "ext_pts": ib.get('extension_pts', 0),
        "ext_dir": ib.get('extension_direction', 'none'),
        "cri_status": cri.get('overall_status', 'N/A'),
        "terrain": cri.get('terrain', {}).get('classification', 'N/A'),
        "trap_type": cri.get('trap', {}).get('type', 'None'),
        "trap_detected": cri.get('trap', {}).get('detected', False),
        "reclaim": cri.get('reclaim', {}).get('state', 'N/A'),
        "perm_size": cri.get('permission', {}).get('size_cap', 'N/A'),
        "perm_aggr": cri.get('permission', {}).get('aggression', 'N/A'),
        "balance_type": bal.get('balance_type', 'N/A'),
        "skew": bal.get('skew', 'N/A'),
        "skew_strength": bal.get('skew_strength', 0),
        "seam": bal.get('seam_level', 0),
        "morph_status": bal.get('morph', {}).get('status', 'N/A'),
        "morph_type": bal.get('morph', {}).get('morph_type', 'N/A'),
        "playbook_action": bal.get('playbook_action', 'N/A'),
        "dpoc_regime": dpoc_regime,
        "dpoc_net": dpoc.get('net_migration_pts', 'N/A'),
        "wicks_bull": wp.get('bullish_wick_parade_count', 0),
        "wicks_bear": wp.get('bearish_wick_parade_count', 0),
        "tpo_shape": tpo.get('tpo_shape', 'N/A'),
        "fattening": tpo.get('fattening_zone', 'N/A'),
        "gap_status": ms_va.get('gap_status', 'N/A'),
        "p80_ready": ms_va.get('80p_setup_ready', False),
        "prior_vah": ms_va.get('previous_session_vah', 0),
        "prior_val": ms_va.get('previous_session_val', 0),
        "prior_poc": ms_va.get('previous_session_poc', 0),
        "onh": pm.get('overnight_high', 0),
        "onl": pm.get('overnight_low', 0),
        "on_range": pm.get('overnight_range', 0),
        "or_signal": orr.get('signal', orr.get('note', 'N/A')),
        "ef_signal": ef.get('signal', ef.get('note', 'N/A')),
        "mr_class": mr.get('ib_range_classification', 'N/A'),
        "ib_accept_high": cc.get('ib_acceptance', {}).get('close_above_ibh', False),
        "ib_accept_low": cc.get('ib_acceptance', {}).get('close_below_ibl', False),
        "dpoc_compression": cc.get('dpoc_compression', {}).get('compression_bias', 'none'),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--day', required=True)
    parser.add_argument('--times', required=True, help='Comma-separated times')
    parser.add_argument('--output', required=True)
    parser.add_argument('--summary-only', action='store_true', help='Print summaries for agent context')
    args = parser.parse_args()

    times = [t.strip() for t in args.times.split(',')]
    snapshots = extract_snapshots(args.day, times)

    if args.summary_only:
        for t in sorted(snapshots.keys()):
            s = summarize_snapshot(snapshots[t])
            print(json.dumps(s, indent=2))
            print("---")
        return

    # Write skeleton pairs (output=null) for agent to fill
    with open(args.output, 'w', encoding='utf-8') as f:
        for t in sorted(snapshots.keys()):
            pair = {
                "input": snapshots[t],
                "output": None,
                "metadata": {
                    "session_date": args.day,
                    "current_et_time": t,
                    "generated_at": datetime.now().isoformat(),
                    "generator": "claude-skill"
                }
            }
            f.write(json.dumps(pair, ensure_ascii=False) + '\n')

    print(f"Wrote {len(snapshots)} skeleton pairs to {args.output}")


if __name__ == '__main__':
    main()
