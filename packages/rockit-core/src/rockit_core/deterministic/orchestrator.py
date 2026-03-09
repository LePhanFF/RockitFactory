# orchestrator.py
# Purpose: Merges JSON fragments from all modules into one final compact snapshot JSON.
# Pure market reading — no strategy/trade signals. Add new modules via registry.

import json
import os
import numpy as np

# Core market data modules
from rockit_core.deterministic.modules.loader import load_nq_csv
from rockit_core.deterministic.modules.premarket import get_premarket
from rockit_core.deterministic.modules.ib_location import get_ib_location
from rockit_core.deterministic.modules.wick_parade import get_wick_parade
from rockit_core.deterministic.modules.dpoc_migration import get_dpoc_migration
from rockit_core.deterministic.modules.volume_profile import get_volume_profile
from rockit_core.deterministic.modules.tpo_profile import get_tpo_profile
from rockit_core.deterministic.modules.ninety_min_pd_arrays import get_ninety_min_pd_arrays
from rockit_core.deterministic.modules.fvg_detection import get_fvg_detection
from rockit_core.deterministic.modules.smt_detection import get_smt_detection
from rockit_core.deterministic.modules.core_confluences import get_core_confluences
from rockit_core.deterministic.modules.inference_engine import apply_inference_rules
# CRI + playbook (post-inference)
from rockit_core.deterministic.modules.cri import get_cri_readiness
from rockit_core.deterministic.modules.playbook_engine import generate_playbook_setup
# Strategy signal modules (top-level snapshot keys)
from rockit_core.deterministic.modules.balance_classification import get_balance_classification
from rockit_core.deterministic.modules.mean_reversion_engine import get_mean_reversion_setup
from rockit_core.deterministic.modules.or_reversal import get_or_reversal_setup
from rockit_core.deterministic.modules.edge_fade import get_edge_fade_setup
# Tape reading context (V1 additions for LLM tape reader)
from rockit_core.deterministic.modules.tape_context import get_tape_context
# Regime classification context (daily ATR, VIX, prior day type, weekly context)
from rockit_core.deterministic.modules.regime_context import get_regime_context
# Market structure modules (loaded dynamically via registry)
from rockit_core.deterministic.modules.market_structure_registry import (
    MARKET_MODULES, load_market_structure
)

# Orchestrator infrastructure
from rockit_core.deterministic.modules.config_validator import validate_config, validate_snapshot_schema
from rockit_core.deterministic.modules.schema_validator import validate_snapshot
from rockit_core.deterministic.modules.data_validator import validate_snapshot_data
from rockit_core.deterministic.modules.dataframe_cache import get_global_cache, clear_global_cache
from rockit_core.deterministic.modules.error_logger import get_global_logger, log_error


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
    - Ninety min PD arrays (not used)
    """
    try:
        if 'intraday' in snapshot and 'ib' in snapshot['intraday']:
            ib = snapshot['intraday']['ib']
            ib.pop('ema20', None)
            ib.pop('ema50', None)
            ib.pop('ema200', None)

        if 'intraday' in snapshot:
            snapshot['intraday'].pop('ninety_min_pd_arrays', None)

        if 'premarket' in snapshot:
            snapshot['premarket'].pop('previous_week_high', None)
            snapshot['premarket'].pop('previous_week_low', None)

    except Exception:
        pass

    return snapshot

def generate_snapshot(config):
    """
    Generates a snapshot JSON by calling modules and merging their outputs.
    Loads NQ primary, ES/YM optional for SMT/cross-market.

    Snapshot structure:
    - premarket: overnight, asia, london, prior day levels
    - intraday: ib, volume_profile, tpo_profile, dpoc_migration, wick_parade, fvg_detection
    - market_structure: OR analysis, prior VA, IB extension, balance, range, edge zone, VA poke
    - core_confluences: precomputed signals
    - inference: day type, bias, trend strength
    - cri_readiness: terrain, identity, permission
    """
    logger = get_global_logger()
    cache = get_global_cache()

    try:
        validate_config(config)

        session_date = config['session_date']
        nq_path = config['csv_paths']['nq']

        df_extended, df_current = cache.get('NQ', session_date)
        if df_extended is None:
            df_extended, df_current = load_nq_csv(nq_path, session_date)
            cache.set('NQ', session_date, df_extended, df_current)

        # Load ES/YM if paths provided – optional
        df_es_extended = df_es_current = None
        if 'es' in config['csv_paths'] and config['csv_paths']['es']:
            df_es_extended, df_es_current = load_nq_csv(config['csv_paths']['es'], session_date)

        df_ym_extended = df_ym_current = None
        if 'ym' in config['csv_paths'] and config['csv_paths']['ym']:
            df_ym_extended, df_ym_current = load_nq_csv(config['csv_paths']['ym'], session_date)

        # IB data (used by several modules)
        ib_data = get_ib_location(df_current, config['current_time'])

        # Strict dependency ordering: volume_profile MUST run before tpo_profile
        volume_profile_result = get_volume_profile(df_extended, df_current, config['current_time'])
        prior_day = volume_profile_result.get('previous_day', {})

        # Collect core intraday data (pure market data, no strategy logic)
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
            "tpo_profile": get_tpo_profile(
                df_current,
                config['current_time'],
                prior_day=prior_day
            ),
            "ninety_min_pd_arrays": get_ninety_min_pd_arrays(df_current, config['current_time']),
            "fvg_detection": get_fvg_detection(df_extended, df_current, config['current_time']),
            "smt_detection": {},  # populated after premarket runs (needs overnight levels)
        }

        # Premarket data
        premarket_data = get_premarket(df_extended, df_es_extended, df_ym_extended, session_date=session_date)

        # Update SMT detection with premarket data (overnight levels)
        intraday_data["smt_detection"] = get_smt_detection(
            df_current, df_es_current, df_ym_current,
            current_time_str=config['current_time'],
            ib_data=ib_data,
            premarket_data=premarket_data,
            prior_va_data=prior_day,
        )

        # Core confluences (computed from intraday data)
        core_confluences_data = get_core_confluences(intraday_data, config['current_time'])

        # Market structure modules (loaded dynamically via registry)
        market_structure = load_market_structure(
            MARKET_MODULES, df_extended, df_current, intraday_data,
            config, ib_data, premarket_data
        )

        # Assemble snapshot
        snapshot = {
            "session_date": config['session_date'],
            "current_et_time": config['current_time'],
            "premarket": premarket_data,
            "intraday": intraday_data,
            "market_structure": market_structure,
            "core_confluences": core_confluences_data,
        }

        # Clean for JSON serialization
        snapshot = clean_for_json(snapshot)

        # Schema validation (early check)
        try:
            validate_snapshot_schema(snapshot)
        except ValueError as e:
            logger.log('validate_snapshot_schema', e, {'session_date': session_date})
            raise

        # Deterministic inference rules
        try:
            inference_result = apply_inference_rules(snapshot)
            snapshot["inference"] = inference_result
        except Exception as e:
            logger.log('apply_inference_rules', e, {
                'session_date': session_date,
                'current_time': config['current_time']
            })
            snapshot["inference"] = {"error": str(e), "status": "failed"}

        # CRI readiness (terrain, identity, permission)
        try:
            cri_result = get_cri_readiness(
                df_current, intraday_data,
                snapshot.get('premarket', {}),
                config['current_time']
            )
            snapshot["cri_readiness"] = cri_result
        except Exception as e:
            logger.log('get_cri_readiness', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["cri_readiness"] = {"error": str(e), "status": "failed"}

        # Playbook setup recommendations
        try:
            playbook_result = generate_playbook_setup(
                snapshot,
                snapshot.get("inference", {}),
                snapshot.get("cri_readiness", {})
            )
            snapshot["playbook_setup"] = playbook_result
        except Exception as e:
            logger.log('generate_playbook_setup', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["playbook_setup"] = {"error": str(e), "status": "failed"}

        # Balance classification (skew, seam, morph — runs for all day types post-10:30)
        try:
            balance_result = get_balance_classification(
                df_current, intraday_data, config['current_time']
            )
            snapshot["balance_classification"] = balance_result
        except Exception as e:
            logger.log('get_balance_classification', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["balance_classification"] = {"error": str(e), "status": "failed"}

        # Mean reversion setup (IB range classification + rejection targets)
        try:
            mr_result = get_mean_reversion_setup(
                df_current, intraday_data, config['current_time']
            )
            snapshot["mean_reversion"] = mr_result
        except Exception as e:
            logger.log('get_mean_reversion_setup', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["mean_reversion"] = {"error": str(e), "status": "failed"}

        # Opening Range Reversal (9:30-10:15)
        try:
            intraday_with_premarket = dict(intraday_data)
            intraday_with_premarket['premarket'] = snapshot.get('premarket', {})
            or_result = get_or_reversal_setup(
                df_current, config['current_time'], intraday_with_premarket
            )
            snapshot["or_reversal"] = or_result
        except Exception as e:
            logger.log('get_or_reversal_setup', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["or_reversal"] = {"error": str(e), "status": "failed"}

        # Edge Fade mean reversion (10:00-13:30)
        try:
            ib_history_5days = [ib_data.get('ib_range', 0)] if ib_data else [0]
            ef_result = get_edge_fade_setup(
                df_current, intraday_data, config['current_time'], ib_history_5days
            )
            snapshot["edge_fade"] = ef_result
        except Exception as e:
            logger.log('get_edge_fade_setup', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["edge_fade"] = {"error": str(e), "status": "failed"}

        # Tape reading context (IB touches, C-period, open type, VA depth, DPOC retention)
        try:
            tape_ctx = get_tape_context(
                df_current, intraday_data,
                snapshot.get('premarket', {}),
                config['current_time']
            )
            snapshot["tape_context"] = tape_ctx
        except Exception as e:
            logger.log('get_tape_context', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["tape_context"] = {"error": str(e), "status": "failed"}

        # Regime classification context (daily ATR, VIX, prior day, weekly, composite)
        try:
            regime_ctx = get_regime_context(
                df_extended, df_current, intraday_data,
                session_date, config['current_time']
            )
            snapshot["regime_context"] = regime_ctx
        except Exception as e:
            logger.log('get_regime_context', e, {
                'session_date': session_date, 'current_time': config['current_time']
            })
            snapshot["regime_context"] = {"error": str(e), "status": "failed"}

        # Clean again after adding inference/CRI/playbook/strategy modules
        snapshot = clean_for_json(snapshot)

        # Full schema validation
        try:
            validate_snapshot(snapshot)
        except ValueError as e:
            logger.log('validate_snapshot', e, {'session_date': session_date})
            raise

        # Domain-specific data validation (non-fatal: logs warnings)
        try:
            validation = validate_snapshot_data(snapshot)
            snapshot["_validation"] = validation.to_dict()
            if validation.errors:
                for err in validation.errors:
                    logger.log('data_validation', ValueError(err['message']), {
                        'session_date': session_date, 'field': err['field']
                    })
        except Exception as e:
            logger.log('validate_snapshot_data', e, {'session_date': session_date})

        # Save to output dir
        os.makedirs(config['output_dir'], exist_ok=True)
        filename = f"{config['session_date']}_{config['current_time'].replace(':', '')}.json"
        path = os.path.join(config['output_dir'], filename)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=4, ensure_ascii=False)

        print(f"Snapshot saved: {path}")

        # Suppress TIER 3 fields (optional, for training data optimization)
        snapshot = suppress_tier3_fields(snapshot)

        return snapshot

    except Exception as e:
        logger.log('generate_snapshot', e, {
            'session_date': config.get('session_date'),
            'current_time': config.get('current_time')
        })
        print(f"Error generating snapshot: {e}")
        raise
