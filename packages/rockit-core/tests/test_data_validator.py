"""Tests for domain-specific data validation pipeline."""

import math
import pytest

from rockit_core.deterministic.modules.data_validator import (
    validate_snapshot_data,
    ValidationResult,
)


def _base_snapshot():
    """Create a valid base snapshot for testing."""
    return {
        "session_date": "2025-06-15",
        "current_et_time": "11:00",
        "premarket": {
            "asia_high": 21500.0,
            "asia_low": 21400.0,
            "london_high": 21550.0,
            "london_low": 21380.0,
            "overnight_high": 21560.0,
            "overnight_low": 21370.0,
            "previous_day_high": 21600.0,
            "previous_day_low": 21300.0,
        },
        "intraday": {
            "ib": {
                "ib_high": 21500.0,
                "ib_low": 21400.0,
                "ib_range": 100.0,
                "atr14": 150.0,
                "current_close": 21450.0,
            },
            "volume_profile": {
                "current_session": {
                    "poc": 21450.0,
                    "vah": 21480.0,
                    "val": 21420.0,
                    "high": 21500.0,
                    "low": 21400.0,
                    "hvn_zones": [],
                    "lvn_zones": [],
                },
                "previous_day": {
                    "poc": 21440.0,
                    "vah": 21500.0,
                    "val": 21350.0,
                    "high": 21600.0,
                    "low": 21300.0,
                    "hvn_zones": [],
                    "lvn_zones": [],
                },
            },
            "tpo_profile": {},
            "dpoc_migration": {},
            "smt_detection": {},
        },
        "core_confluences": {
            "ib_acceptance": {},
            "dpoc_vs_ib": {},
            "dpoc_compression": {},
            "price_location": {},
            "tpo_signals": {},
            "migration": {},
        },
        "market_structure": {},
    }


class TestValidationResult:
    def test_empty_result_is_valid(self):
        r = ValidationResult()
        assert r.is_valid
        assert r.to_dict()["valid"] is True

    def test_warning_does_not_invalidate(self):
        r = ValidationResult()
        r.warn("test", "minor issue")
        assert r.is_valid
        assert r.to_dict()["warning_count"] == 1

    def test_error_invalidates(self):
        r = ValidationResult()
        r.error("test", "critical issue")
        assert not r.is_valid
        assert r.to_dict()["error_count"] == 1


class TestIBValidation:
    def test_valid_ib(self):
        snap = _base_snapshot()
        result = validate_snapshot_data(snap)
        assert result.is_valid

    def test_ib_high_less_than_low(self):
        snap = _base_snapshot()
        snap["intraday"]["ib"]["ib_high"] = 21300.0
        snap["intraday"]["ib"]["ib_low"] = 21500.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid
        assert any("IB high" in e["message"] for e in result.errors)

    def test_ib_range_negative(self):
        snap = _base_snapshot()
        snap["intraday"]["ib"]["ib_range"] = -50.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_atr_zero_warns(self):
        snap = _base_snapshot()
        snap["intraday"]["ib"]["atr14"] = 0.0
        result = validate_snapshot_data(snap)
        assert len(result.warnings) > 0
        assert any("ATR14" in w["message"] for w in result.warnings)

    def test_atr_negative_warns(self):
        snap = _base_snapshot()
        snap["intraday"]["ib"]["atr14"] = -10.0
        result = validate_snapshot_data(snap)
        assert any("ATR14" in w["message"] for w in result.warnings)

    def test_missing_ib_warns(self):
        snap = _base_snapshot()
        del snap["intraday"]["ib"]
        result = validate_snapshot_data(snap)
        assert len(result.warnings) > 0


class TestVolumeProfileValidation:
    def test_valid_profile(self):
        snap = _base_snapshot()
        result = validate_snapshot_data(snap)
        assert result.is_valid

    def test_vah_less_than_val(self):
        snap = _base_snapshot()
        snap["intraday"]["volume_profile"]["current_session"]["vah"] = 21400.0
        snap["intraday"]["volume_profile"]["current_session"]["val"] = 21500.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_poc_outside_va_warns(self):
        snap = _base_snapshot()
        snap["intraday"]["volume_profile"]["current_session"]["poc"] = 21500.0  # Above VAH (21480)
        result = validate_snapshot_data(snap)
        assert any("POC" in w["message"] for w in result.warnings)

    def test_prior_vah_less_than_val(self):
        snap = _base_snapshot()
        snap["intraday"]["volume_profile"]["previous_day"]["vah"] = 21300.0
        snap["intraday"]["volume_profile"]["previous_day"]["val"] = 21500.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_not_available_post_ib_errors(self):
        """POC/VAH/VAL = 'not_available' after 10:30 should be an error."""
        snap = _base_snapshot()
        snap["current_et_time"] = "10:30"
        snap["intraday"]["volume_profile"]["current_session"] = {
            "poc": "not_available",
            "vah": "not_available",
            "val": "not_available",
            "high": "not_available",
            "low": "not_available",
            "hvn_zones": [],
            "lvn_zones": [],
        }
        result = validate_snapshot_data(snap)
        assert not result.is_valid
        assert any("not_available" in e["message"] for e in result.errors)

    def test_not_available_pre_ib_warns(self):
        """POC/VAH/VAL = 'not_available' before 10:30 is a warning, not error."""
        snap = _base_snapshot()
        snap["current_et_time"] = "09:35"
        snap["intraday"]["volume_profile"]["current_session"] = {
            "poc": "not_available",
            "vah": "not_available",
            "val": "not_available",
            "high": "not_available",
            "low": "not_available",
            "hvn_zones": [],
            "lvn_zones": [],
        }
        result = validate_snapshot_data(snap)
        assert result.is_valid  # warnings don't invalidate
        assert any("not_available" in w["message"] for w in result.warnings)


class TestPremarketValidation:
    def test_valid_premarket(self):
        snap = _base_snapshot()
        result = validate_snapshot_data(snap)
        assert result.is_valid

    def test_pdh_less_than_pdl(self):
        snap = _base_snapshot()
        snap["premarket"]["previous_day_high"] = 21200.0
        snap["premarket"]["previous_day_low"] = 21400.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_missing_pdh_warns(self):
        snap = _base_snapshot()
        snap["premarket"]["previous_day_high"] = None
        result = validate_snapshot_data(snap)
        assert any("Prior day high" in w["message"] for w in result.warnings)

    def test_asia_high_less_than_low(self):
        snap = _base_snapshot()
        snap["premarket"]["asia_high"] = 21300.0
        snap["premarket"]["asia_low"] = 21500.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_london_high_less_than_low(self):
        snap = _base_snapshot()
        snap["premarket"]["london_high"] = 21300.0
        snap["premarket"]["london_low"] = 21500.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_overnight_high_less_than_low(self):
        snap = _base_snapshot()
        snap["premarket"]["overnight_high"] = 21300.0
        snap["premarket"]["overnight_low"] = 21500.0
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_missing_premarket_warns(self):
        snap = _base_snapshot()
        del snap["premarket"]
        result = validate_snapshot_data(snap)
        assert len(result.warnings) > 0


class TestInferenceValidation:
    def test_valid_day_type(self):
        snap = _base_snapshot()
        snap["inference"] = {"day_type": "trend_day_bull", "bias": "bullish"}
        result = validate_snapshot_data(snap)
        assert result.is_valid

    def test_unknown_day_type_warns(self):
        snap = _base_snapshot()
        snap["inference"] = {"day_type": "super_extreme_day"}
        result = validate_snapshot_data(snap)
        assert any("day_type" in w["message"] for w in result.warnings)

    def test_inference_error_warns(self):
        snap = _base_snapshot()
        snap["inference"] = {"error": "something broke", "status": "failed"}
        result = validate_snapshot_data(snap)
        assert any("Inference failed" in w["message"] for w in result.warnings)

    def test_no_inference_is_ok(self):
        snap = _base_snapshot()
        result = validate_snapshot_data(snap)
        assert result.is_valid


class TestNumericSanity:
    def test_nan_in_ib_high_errors(self):
        snap = _base_snapshot()
        snap["intraday"]["ib"]["ib_high"] = float('nan')
        result = validate_snapshot_data(snap)
        assert not result.is_valid
        assert any("NaN" in e["message"] for e in result.errors)

    def test_inf_in_poc_errors(self):
        snap = _base_snapshot()
        snap["intraday"]["volume_profile"]["current_session"]["poc"] = float('inf')
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_negative_inf_errors(self):
        snap = _base_snapshot()
        snap["intraday"]["ib"]["atr14"] = float('-inf')
        result = validate_snapshot_data(snap)
        assert not result.is_valid

    def test_valid_numbers_pass(self):
        snap = _base_snapshot()
        result = validate_snapshot_data(snap)
        # No NaN/Inf errors
        nan_errors = [e for e in result.errors if "NaN" in e["message"] or "Inf" in e["message"]]
        assert len(nan_errors) == 0


class TestEdgeCases:
    def test_empty_snapshot(self):
        result = validate_snapshot_data({})
        # Should warn but not crash
        assert len(result.warnings) > 0

    def test_partial_snapshot(self):
        snap = {"intraday": {"ib": {"ib_high": 100}}}
        result = validate_snapshot_data(snap)
        # Should not crash
        assert isinstance(result, ValidationResult)

    def test_to_dict_format(self):
        snap = _base_snapshot()
        result = validate_snapshot_data(snap)
        d = result.to_dict()
        assert "valid" in d
        assert "error_count" in d
        assert "warning_count" in d
        assert "errors" in d
        assert "warnings" in d
