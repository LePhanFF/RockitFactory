# modules/schema_validator.py
"""
JSON schema validation for generated snapshots.
Catches serialization bugs and missing key errors before file write.
"""

import json
import os

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


def load_schema():
    """
    Loads JSON schema from config/schema.json.

    Returns:
        dict: Schema definition, or empty dict if file not found
    """
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'schema.json'
    )

    if not os.path.exists(schema_path):
        return {}

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load schema: {e}")
        return {}


def validate_snapshot(snapshot):
    """
    Validates snapshot against JSON schema.
    Falls back to basic validation if jsonschema not installed.

    Args:
        snapshot (dict): Generated snapshot

    Raises:
        ValueError: If validation fails

    Returns:
        dict: Same snapshot if valid
    """
    # Basic validation: check required top-level keys
    required_keys = ['session_date', 'current_et_time', 'premarket', 'intraday', 'core_confluences']
    missing = [key for key in required_keys if key not in snapshot]

    if missing:
        raise ValueError(f"Snapshot missing required keys: {missing}")

    # Basic validation: check intraday has required sub-keys
    intraday = snapshot.get('intraday', {})
    intraday_required = ['ib', 'volume_profile', 'tpo_profile', 'dpoc_migration']
    intraday_missing = [key for key in intraday_required if key not in intraday]

    if intraday_missing:
        raise ValueError(f"Snapshot.intraday missing required keys: {intraday_missing}")

    # Basic validation: check core_confluences has required sub-keys
    confluences = snapshot.get('core_confluences', {})
    confluences_required = ['ib_acceptance', 'dpoc_vs_ib', 'dpoc_compression', 'price_location', 'tpo_signals', 'migration']
    confluences_missing = [key for key in confluences_required if key not in confluences]

    if confluences_missing:
        raise ValueError(f"Snapshot.core_confluences missing required keys: {confluences_missing}")

    # Full JSON schema validation if available
    if JSONSCHEMA_AVAILABLE:
        try:
            schema = load_schema()
            if schema:
                jsonschema.validate(snapshot, schema)
        except jsonschema.ValidationError as e:
            raise ValueError(f"Schema validation failed: {e.message} at {'.'.join(str(p) for p in e.path)}")

    return snapshot
