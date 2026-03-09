# modules/data_validator.py
"""
Domain-specific data validation for deterministic snapshots.

Validates numeric sanity, structural relationships, and prior session levels.
Returns warnings and errors without raising (non-fatal by default).
Integrate into orchestrator for per-snapshot quality checks.
"""

import math


class ValidationResult:
    """Result of a validation check."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    @property
    def is_valid(self):
        return len(self.errors) == 0

    def error(self, field, message):
        self.errors.append({"field": field, "message": message, "level": "error"})

    def warn(self, field, message):
        self.warnings.append({"field": field, "message": message, "level": "warning"})

    def to_dict(self):
        return {
            "valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_snapshot_data(snapshot):
    """
    Domain-specific validation of snapshot data values.

    Checks:
    - POC within VA (VAL <= POC <= VAH)
    - VAH > VAL
    - IB high >= IB low
    - ATR > 0
    - No NaN/Inf in critical numeric fields
    - Valid day_type enum
    - Prior session levels present
    - Holiday/half-day handling

    Args:
        snapshot: dict — generated snapshot

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()

    _validate_ib(snapshot, result)
    _validate_volume_profile(snapshot, result)
    _validate_premarket(snapshot, result)
    _validate_inference(snapshot, result)
    _validate_numeric_sanity(snapshot, result)

    return result


def _validate_ib(snapshot, result):
    """Validate Initial Balance data."""
    ib = _get_nested(snapshot, 'intraday', 'ib')
    if ib is None:
        result.warn("intraday.ib", "IB data missing")
        return

    ib_high = ib.get('ib_high')
    ib_low = ib.get('ib_low')

    if ib_high is not None and ib_low is not None:
        if not _is_valid_number(ib_high) or not _is_valid_number(ib_low):
            result.error("intraday.ib", f"IB high/low not valid numbers: {ib_high}/{ib_low}")
        elif ib_high < ib_low:
            result.error("intraday.ib", f"IB high ({ib_high}) < IB low ({ib_low})")

    ib_range = ib.get('ib_range')
    if ib_range is not None:
        if not _is_valid_number(ib_range):
            result.error("intraday.ib.ib_range", f"IB range not valid: {ib_range}")
        elif ib_range < 0:
            result.error("intraday.ib.ib_range", f"IB range negative: {ib_range}")

    atr = ib.get('atr14')
    if atr is not None:
        if not _is_valid_number(atr):
            result.error("intraday.ib.atr14", f"ATR14 not valid: {atr}")
        elif atr <= 0:
            result.warn("intraday.ib.atr14", f"ATR14 non-positive: {atr}")


def _validate_volume_profile(snapshot, result):
    """Validate volume profile / value area data."""
    vp = _get_nested(snapshot, 'intraday', 'volume_profile')
    if vp is None:
        result.warn("intraday.volume_profile", "Volume profile data missing")
        return

    current_time = snapshot.get('current_et_time', '09:30')
    is_post_ib = current_time >= '10:30'

    # Current session VA (nested under current_session)
    cs = vp.get('current_session', vp)  # fallback to vp itself for flat structure
    vah = cs.get('vah')
    val = cs.get('val')
    poc = cs.get('poc')

    # Check for "not_available" string values — error post-IB, warning pre-IB
    if vah == "not_available" or val == "not_available" or poc == "not_available":
        if is_post_ib:
            result.error("intraday.volume_profile.current_session",
                         f"POC/VAH/VAL not_available at {current_time} — no RTH data?")
        else:
            result.warn("intraday.volume_profile.current_session",
                        f"POC/VAH/VAL not_available at {current_time} — session may be pre-open")
        return

    if vah is not None and val is not None:
        if _is_valid_number(vah) and _is_valid_number(val):
            if vah < val:
                result.error("intraday.volume_profile", f"VAH ({vah}) < VAL ({val})")
        else:
            result.error("intraday.volume_profile", "VAH/VAL not valid numbers")

    if poc is not None and vah is not None and val is not None:
        if _is_valid_number(poc) and _is_valid_number(vah) and _is_valid_number(val):
            if poc > vah or poc < val:
                result.warn("intraday.volume_profile",
                            f"POC ({poc}) outside VA range ({val}-{vah})")

    # Prior day VA
    prev = vp.get('previous_day', {})
    if prev:
        prev_vah = prev.get('vah') or prev.get('prev_vah')
        prev_val = prev.get('val') or prev.get('prev_val')
        prev_poc = prev.get('poc') or prev.get('prev_poc')

        if prev_vah is not None and prev_val is not None:
            if _is_valid_number(prev_vah) and _is_valid_number(prev_val):
                if prev_vah < prev_val:
                    result.error("volume_profile.previous_day",
                                 f"Prior VAH ({prev_vah}) < Prior VAL ({prev_val})")

        if prev_poc is not None and prev_vah is not None and prev_val is not None:
            if (_is_valid_number(prev_poc) and _is_valid_number(prev_vah)
                    and _is_valid_number(prev_val)):
                if prev_poc > prev_vah or prev_poc < prev_val:
                    result.warn("volume_profile.previous_day",
                                f"Prior POC ({prev_poc}) outside prior VA ({prev_val}-{prev_vah})")


def _validate_premarket(snapshot, result):
    """Validate premarket / prior session levels."""
    premarket = snapshot.get('premarket')
    if premarket is None:
        result.warn("premarket", "Premarket data missing")
        return

    # Prior day high/low must be present
    pdh = premarket.get('previous_day_high')
    pdl = premarket.get('previous_day_low')

    if pdh is None or not _is_valid_number(pdh):
        result.warn("premarket.previous_day_high",
                     "Prior day high missing or invalid — may be holiday/first session")
    if pdl is None or not _is_valid_number(pdl):
        result.warn("premarket.previous_day_low",
                     "Prior day low missing or invalid — may be holiday/first session")

    if (_is_valid_number(pdh) and _is_valid_number(pdl)
            and pdh is not None and pdl is not None and pdh < pdl):
        result.error("premarket", f"Prior day high ({pdh}) < prior day low ({pdl})")

    # Asia session levels
    asia_high = premarket.get('asia_high')
    asia_low = premarket.get('asia_low')
    if asia_high is not None and asia_low is not None:
        if _is_valid_number(asia_high) and _is_valid_number(asia_low) and asia_high < asia_low:
            result.error("premarket.asia", f"Asia high ({asia_high}) < Asia low ({asia_low})")

    # London session levels
    london_high = premarket.get('london_high')
    london_low = premarket.get('london_low')
    if london_high is not None and london_low is not None:
        if _is_valid_number(london_high) and _is_valid_number(london_low):
            if london_high < london_low:
                result.error("premarket.london",
                             f"London high ({london_high}) < London low ({london_low})")

    # Overnight levels
    on_high = premarket.get('overnight_high')
    on_low = premarket.get('overnight_low')
    if on_high is not None and on_low is not None:
        if _is_valid_number(on_high) and _is_valid_number(on_low) and on_high < on_low:
            result.error("premarket.overnight",
                         f"Overnight high ({on_high}) < Overnight low ({on_low})")


def _validate_inference(snapshot, result):
    """Validate inference engine output."""
    inference = snapshot.get('inference')
    if inference is None:
        return  # inference might not run at early times

    if 'error' in inference:
        result.warn("inference", f"Inference failed: {inference.get('error')}")
        return

    day_type = inference.get('day_type')
    valid_day_types = {
        'trend_day_bull', 'trend_day_bear', 'trend_day',
        'p_day_up', 'p_day_down', 'p_day',
        'b_day', 'balance_day', 'balance',
        'neutral', 'neutral_day',
        'normal_day', 'normal_up', 'normal_down',
        'rotational',
        None,  # May not be classified yet
    }
    if day_type is not None and day_type not in valid_day_types:
        result.warn("inference.day_type", f"Unexpected day_type: '{day_type}'")


def _validate_numeric_sanity(snapshot, result):
    """Scan for NaN/Inf in critical numeric fields."""
    critical_paths = [
        ('intraday', 'ib', 'ib_high'),
        ('intraday', 'ib', 'ib_low'),
        ('intraday', 'ib', 'ib_range'),
        ('intraday', 'ib', 'atr14'),
        ('intraday', 'ib', 'current_close'),
        ('intraday', 'volume_profile', 'current_session', 'poc'),
        ('intraday', 'volume_profile', 'current_session', 'vah'),
        ('intraday', 'volume_profile', 'current_session', 'val'),
        ('intraday', 'tpo_profile', 'current_poc'),
        ('intraday', 'tpo_profile', 'current_vah'),
        ('intraday', 'tpo_profile', 'current_val'),
    ]

    for path in critical_paths:
        val = snapshot
        key_str = '.'.join(path)
        for key in path:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                val = None
                break

        if val is not None and isinstance(val, (int, float)):
            if math.isnan(val) or math.isinf(val):
                result.error(key_str, f"NaN/Inf detected: {val}")


def _get_nested(d, *keys):
    """Safely get nested dict value."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key)
        else:
            return None
    return d


def _is_valid_number(val):
    """Check if value is a valid finite number."""
    if val is None:
        return False
    if not isinstance(val, (int, float)):
        return False
    if math.isnan(val) or math.isinf(val):
        return False
    return True
