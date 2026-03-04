# modules/config_validator.py
"""
Configuration validation module.
Ensures required keys are present and have valid values before orchestrator runs.
Prevents malformed config crashes.
"""

import os
from datetime import datetime


def validate_config(config):
    """
    Validates config dict for required keys and valid values.

    Args:
        config (dict): Configuration dict (typically from config.yaml)

    Raises:
        ValueError: If required key is missing or invalid

    Returns:
        dict: Same config if valid
    """
    errors = []

    # Check required keys
    required_keys = ['session_date', 'current_time', 'csv_paths']
    for key in required_keys:
        if key not in config:
            errors.append(f"Missing required key: {key}")

    if errors:
        raise ValueError(f"Config validation failed:\n" + "\n".join(errors))

    # Validate session_date format (YYYY-MM-DD)
    try:
        datetime.strptime(config['session_date'], '%Y-%m-%d')
    except ValueError:
        errors.append(f"Invalid session_date format: {config['session_date']} (expected YYYY-MM-DD)")

    # Validate current_time format (HH:MM)
    if not isinstance(config['current_time'], str):
        errors.append(f"current_time must be string, got {type(config['current_time'])}")
    elif ':' not in config['current_time']:
        errors.append(f"current_time format invalid: {config['current_time']} (expected HH:MM)")
    else:
        try:
            parts = config['current_time'].split(':')
            if len(parts) != 2:
                raise ValueError
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
        except (ValueError, IndexError):
            errors.append(f"current_time out of range: {config['current_time']}")

    # Validate csv_paths
    if not isinstance(config['csv_paths'], dict):
        errors.append(f"csv_paths must be dict, got {type(config['csv_paths'])}")
    elif 'nq' not in config['csv_paths']:
        errors.append("csv_paths must contain 'nq' (NQ is required)")
    else:
        nq_path = config['csv_paths']['nq']
        if not nq_path or not os.path.exists(nq_path):
            errors.append(f"NQ CSV not found: {nq_path}")

    # Validate optional output_dir
    if 'output_dir' in config:
        output_dir = config['output_dir']
        parent = os.path.dirname(output_dir)
        if parent and not os.path.exists(parent):
            errors.append(f"output_dir parent does not exist: {parent}")

    if errors:
        raise ValueError(f"Config validation failed:\n" + "\n".join(errors))

    return config


def validate_snapshot_schema(snapshot):
    """
    Validates snapshot has required top-level keys.

    Args:
        snapshot (dict): Generated snapshot

    Raises:
        ValueError: If required key missing

    Returns:
        dict: Same snapshot if valid
    """
    required_keys = [
        'session_date',
        'current_et_time',
        'premarket',
        'intraday',
        'core_confluences'
    ]

    missing = [key for key in required_keys if key not in snapshot]

    if missing:
        raise ValueError(f"Snapshot schema validation failed - missing keys: {missing}")

    return snapshot
