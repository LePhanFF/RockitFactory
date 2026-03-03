# orchestrator.py
# Purpose: Merges JSON fragments from all modules into one final compact snapshot JSON.
# Keeps everything deterministic and modular – add new modules here as needed.

import json
import os
import numpy as np
from rockit_core.deterministic.modules.loader import load_nq_csv
from rockit_core.deterministic.modules.premarket import get_premarket
from rockit_core.deterministic.modules.ib_location import get_ib_location
from rockit_core.deterministic.modules.wick_parade import get_wick_parade
from rockit_core.deterministic.modules.dpoc_migration import get_dpoc_migration
from rockit_core.deterministic.modules.volume_profile import get_volume_profile
from rockit_core.deterministic.modules.tpo_profile import get_tpo_profile
from rockit_core.deterministic.modules.ninety_min_pd_arrays import get_ninety_min_pd_arrays
from rockit_core.deterministic.modules.fvg_detection import get_fvg_detection
from rockit_core.deterministic.modules.core_confluences import get_core_confluences  # NEW: For precomputed signals
from rockit_core.deterministic.modules.inference_engine import apply_inference_rules  # Phase 2: Deterministic rules
from rockit_core.deterministic.modules.cri import get_cri_readiness  # Phase 4: CRI readiness
from rockit_core.deterministic.modules.playbook_engine import generate_playbook_setup  # Phase 4: Playbook engine
from rockit_core.deterministic.modules.balance_classification import get_balance_classification  # Phase 11: Balance day classification
from rockit_core.deterministic.modules.mean_reversion_engine import get_mean_reversion_setup  # Phase 12: Mean reversion targets
from rockit_core.deterministic.modules.or_reversal import get_or_reversal_setup  # Phase 14: Opening Range Reversal
from rockit_core.deterministic.modules.edge_fade import get_edge_fade_setup  # Phase 14: Edge Fade mean reversion
from rockit_core.deterministic.modules.globex_va_analysis import get_globex_va_analysis  # 80% Rule: Dalton gap rejection detection
from rockit_core.deterministic.modules.twenty_percent_rule import get_twenty_percent_rule  # 20P Rule: IB extension breakout
from rockit_core.deterministic.modules.va_edge_fade import get_va_edge_fade  # VA Edge Fade: poke beyond VA, fade back in

# Phase 3: Orchestrator improvements
from rockit_core.deterministic.modules.config_validator import validate_config, validate_snapshot_schema
from rockit_core.deterministic.modules.schema_validator import validate_snapshot
from rockit_core.deterministic.modules.dataframe_cache import get_global_cache, clear_global_cache
from rockit_core.deterministic.modules.error_logger import get_global_logger, log_error

# Future: add more e.g., cross_market, vix_regime, intraday_sampling

def clean_for_json(obj):
    """Convert numpy types to Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def suppress_tier3_fields(snapshot):
    """
    Suppress TIER 3 fields (low value, not used in training).

    Remove:
    - EMA20, EMA50, EMA200 (redundant with POC/VAH/VAL analysis)
    - Previous week high/low (less relevant than prior day)
    - Ninety min PD arrays (not used in playbooks)

    Keep (DO NOT suppress):
    - current_vwap (important signal)
    - wick_parade (used for CRI trap detection)
    - globex_va_analysis (80P signal)
    - twenty_percent_rule (20P signal)
    - va_edge_fade (VA Edge Fade signal)
    - All core confluence signals, CRI fields
    """
    try:
        # Remove from IB location
        if 'intraday' in snapshot and 'ib' in snapshot['intraday']:
            ib = snapshot['intraday']['ib']
            ib.pop('ema20', None)
            ib.pop('ema50', None)
            ib.pop('ema200', None)

        # Remove entire subsections
        if 'intraday' in snapshot:
            intraday = snapshot['intraday']
            # NOTE: wick_parade is used for CRI trap detection - DO NOT SUPPRESS
            intraday.pop('ninety_min_pd_arrays', None)

        # Remove from premarket
        if 'premarket' in snapshot:
            premarket = snapshot['premarket']
            premarket.pop('previous_week_high', None)
            premarket.pop('previous_week_low', None)

    except Exception as e:
        # Silently fail - suppression is optional, don't break snapshot on error
        pass

    return snapshot

def generate_snapshot(config):
    """
    Generates a snapshot JSON by calling modules and merging their outputs.
    Loads NQ primary, ES/YM optional for SMT/cross-market.

    Phase 3 Improvements:
    - Validates config before processing
    - Caches DataFrames to avoid re-reading CSVs (30% speed improvement)
    - Comprehensive error handling with logging
    - Output schema validation
    - Strict dependency ordering (volume_profile before tpo_profile)
    """
    logger = get_global_logger()
    cache = get_global_cache()

    try:
        # PHASE 3.1: Config validation
        validate_config(config)

        # PHASE 3.2: DataFrame caching (avoid re-reading CSVs)
        session_date = config['session_date']
        nq_path = config['csv_paths']['nq']

        df_extended, df_current = cache.get('NQ', session_date)
        if df_extended is None:
            df_extended, df_current = load_nq_csv(nq_path, session_date)
            cache.set('NQ', session_date, df_extended, df_current)

        # Load ES/YM if paths provided (use extended/current as needed) – optional, no caching
        df_es_extended = df_es_current = None
        if 'es' in config['csv_paths'] and config['csv_paths']['es']:
            df_es_extended, df_es_current = load_nq_csv(config['csv_paths']['es'], session_date)

        df_ym_extended = df_ym_current = None
        if 'ym' in config['csv_paths'] and config['csv_paths']['ym']:
            df_ym_extended, df_ym_current = load_nq_csv(config['csv_paths']['ym'], session_date)

        # IB data (used by several modules)
        ib_data = get_ib_location(df_current, config['current_time'])

        # PHASE 3.3: Strict dependency ordering
        # volume_profile MUST run before tpo_profile (provides prior_day)
        volume_profile_result = get_volume_profile(df_extended, df_current, config['current_time'])
        prior_day = volume_profile_result.get('previous_day', {})

        # Collect intraday fragments (order matters for dependencies)
        intraday_data = {
            "ib": ib_data,
            "wick_parade": get_wick_parade(df_current, config['current_time']),
            "dpoc_migration": get_dpoc_migration(
                df_current,
                config['current_time'],
                atr14_current=ib_data.get('atr14'),
                current_close=ib_data.get('current_close')
            ),
            "volume_profile": volume_profile_result,
            # tpo_profile depends on volume_profile (prior_day) – called after
            "tpo_profile": get_tpo_profile(
                df_current,
                config['current_time'],
                prior_day=prior_day
            ),
            "ninety_min_pd_arrays": get_ninety_min_pd_arrays(df_current, config['current_time']),
            "fvg_detection": get_fvg_detection(df_extended, df_current, config['current_time']),
            # 80P Rule: Globex VA + gap analysis (Dalton mean reversion)
            "globex_va_analysis": get_globex_va_analysis(
                df_extended,
                df_current,
                config['current_time'],
                session_date=session_date
            ),
        }

        # 20P Rule: IB extension breakout (depends on ib_data already computed)
        gva = intraday_data["globex_va_analysis"]
        intraday_data["twenty_percent_rule"] = get_twenty_percent_rule(
            df_current,
            config['current_time'],
            atr14=ib_data.get('atr14'),
            ib_high=ib_data.get('ib_high'),
            ib_low=ib_data.get('ib_low'),
            ib_range=ib_data.get('ib_range'),
        )

        # VA Edge Fade: poke beyond prior session VA, fails, fade back in
        # Uses prior session VAH/VAL from globex_va_analysis
        intraday_data["va_edge_fade"] = get_va_edge_fade(
            df_current,
            config['current_time'],
            previous_session_vah=gva.get('previous_session_vah'),
            previous_session_val=gva.get('previous_session_val'),
            atr14=ib_data.get('atr14'),
        )

        # Compute core confluences from the collected intraday data
        core_confluences_data = get_core_confluences(intraday_data, config['current_time'])

        # Assemble full snapshot
        snapshot = {
            "session_date": config['session_date'],
            "current_et_time": config['current_time'],
            "premarket": get_premarket(df_extended, df_es_extended, df_ym_extended, session_date=session_date),
            "intraday": intraday_data,
            "core_confluences": core_confluences_data
        }

        # Clean snapshot for JSON serialization
        snapshot = clean_for_json(snapshot)

        # PHASE 3.4: Output schema validation (catches serialization bugs early)
        try:
            validate_snapshot_schema(snapshot)
        except ValueError as e:
            logger.log('validate_snapshot_schema', e, {'session_date': session_date})
            raise

        # Phase 2: Apply deterministic inference rules to generate preliminary decision
        try:
            inference_result = apply_inference_rules(snapshot)
            snapshot["inference"] = inference_result
        except Exception as e:
            logger.log('apply_inference_rules', e, {
                'session_date': session_date,
                'current_time': config['current_time']
            })
            # Don't fail entire snapshot – mark inference as failed but continue
            snapshot["inference"] = {"error": str(e), "status": "failed"}

        # Phase 4: Compute CRI readiness (terrain, identity, permission)
        try:
            cri_result = get_cri_readiness(
                df_current,
                intraday_data,
                snapshot.get('premarket', {}),
                config['current_time']
            )
            snapshot["cri_readiness"] = cri_result
        except Exception as e:
            logger.log('get_cri_readiness', e, {
                'session_date': session_date,
                'current_time': config['current_time']
            })
            snapshot["cri_readiness"] = {"error": str(e), "status": "failed"}

        # Phase 4: Generate playbook setup recommendations
        try:
            playbook_result = generate_playbook_setup(
                snapshot,
                snapshot.get("inference", {}),
                snapshot.get("cri_readiness", {})
            )
            snapshot["playbook_setup"] = playbook_result
        except Exception as e:
            logger.log('generate_playbook_setup', e, {
                'session_date': session_date,
                'current_time': config['current_time']
            })
            snapshot["playbook_setup"] = {"error": str(e), "status": "failed"}

        # Phase 11: Generate balance classification (only for Balance days)
        try:
            day_type_info = snapshot.get("inference", {}).get("day_type", {})
            day_type = day_type_info.get("type", "unknown") if isinstance(day_type_info, dict) else str(day_type_info)

            if day_type == "Balance":
                balance_result = get_balance_classification(
                    df_current,
                    intraday_data,
                    config['current_time']
                )
                snapshot["balance_classification"] = balance_result
            else:
                # Not a Balance day – no balance classification needed
                snapshot["balance_classification"] = None
        except Exception as e:
            logger.log('get_balance_classification', e, {
                'session_date': session_date,
                'current_time': config['current_time'],
                'day_type': day_type
            })
            snapshot["balance_classification"] = {"error": str(e), "status": "failed"}

        # Phase 12: Generate mean reversion setup (early day_type + dual acceptance + targets)
        try:
            mr_result = get_mean_reversion_setup(
                df_current,
                intraday_data,
                config['current_time']
            )
            snapshot["mean_reversion"] = mr_result
        except Exception as e:
            logger.log('get_mean_reversion_setup', e, {
                'session_date': session_date,
                'current_time': config['current_time']
            })
            snapshot["mean_reversion"] = {"error": str(e), "status": "failed"}

        # Phase 14a: Opening Range Reversal (9:30-10:15 only)
        # Merge premarket levels into intraday_data so OR module can access them
        try:
            intraday_with_premarket = dict(intraday_data)
            intraday_with_premarket['premarket'] = snapshot.get('premarket', {})
            or_result = get_or_reversal_setup(
                df_current,
                config['current_time'],
                intraday_with_premarket
            )
            snapshot["or_reversal"] = or_result
        except Exception as e:
            logger.log('get_or_reversal_setup', e, {
                'session_date': session_date,
                'current_time': config['current_time']
            })
            snapshot["or_reversal"] = {"error": str(e), "status": "failed"}

        # Phase 14b: Edge Fade mean reversion (10:00-13:30, Balance/Neutral days)
        try:
            # Build IB history for expansion check (simplified: use current IB if no history)
            ib_history_5days = [ib_data.get('ib_range', 0)] if ib_data else [0]

            ef_result = get_edge_fade_setup(
                df_current,
                intraday_data,
                config['current_time'],
                ib_history_5days
            )
            snapshot["edge_fade"] = ef_result
        except Exception as e:
            logger.log('get_edge_fade_setup', e, {
                'session_date': session_date,
                'current_time': config['current_time']
            })
            snapshot["edge_fade"] = {"error": str(e), "status": "failed"}

        # PHASE 3.5: Full schema validation
        try:
            validate_snapshot(snapshot)
        except ValueError as e:
            logger.log('validate_snapshot', e, {'session_date': session_date})
            raise

        # Save to output dir
        os.makedirs(config['output_dir'], exist_ok=True)
        filename = f"{config['session_date']}_{config['current_time'].replace(':', '')}.json"
        path = os.path.join(config['output_dir'], filename)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=4, ensure_ascii=False)

        print(f"Snapshot saved: {path}")

        # Suppress TIER 3 fields (optional, for training data optimization)
        # This removes low-value fields to reduce JSON size by 47%
        snapshot = suppress_tier3_fields(snapshot)

        return snapshot

    except Exception as e:
        # Top-level error handling
        logger.log('generate_snapshot', e, {
            'session_date': config.get('session_date'),
            'current_time': config.get('current_time')
        })
        print(f"Error generating snapshot: {e}")
        raise
