"""Tests for VIX regime classification module."""

import os
import tempfile
from pathlib import Path

import pytest

from rockit_core.deterministic.modules.vix_regime import (
    classify_vix,
    get_vix_regime,
    clear_cache,
)


# --- Classification ---

class TestClassifyVix:
    def test_low_regime(self):
        assert classify_vix(12.0) == 'low'
        assert classify_vix(14.9) == 'low'

    def test_moderate_regime(self):
        assert classify_vix(15.0) == 'moderate'
        assert classify_vix(19.9) == 'moderate'

    def test_elevated_regime(self):
        assert classify_vix(20.0) == 'elevated'
        assert classify_vix(24.9) == 'elevated'

    def test_high_regime(self):
        assert classify_vix(25.0) == 'high'
        assert classify_vix(34.9) == 'high'

    def test_extreme_regime(self):
        assert classify_vix(35.0) == 'extreme'
        assert classify_vix(80.0) == 'extreme'


# --- VIX Data Loading ---

@pytest.fixture
def vix_csv(tmp_path):
    """Create a small test VIX CSV."""
    csv_path = tmp_path / "test_vix.csv"
    csv_path.write_text(
        "DATE,OPEN,HIGH,LOW,CLOSE\n"
        "01/02/2025,14.50,15.20,14.10,14.80\n"
        "01/03/2025,15.00,16.00,14.80,15.50\n"
        "01/06/2025,16.00,17.50,15.80,17.00\n"
        "01/07/2025,17.20,18.00,16.50,16.80\n"
        "01/08/2025,16.50,17.00,16.00,16.20\n"
        "01/09/2025,21.00,22.50,20.00,22.00\n"
        "01/10/2025,22.50,23.00,21.00,21.50\n",
        encoding='utf-8',
    )
    clear_cache()
    yield str(csv_path)
    clear_cache()


class TestGetVixRegime:
    def test_exact_date_match(self, vix_csv):
        result = get_vix_regime('2025-01-03', csv_path=vix_csv)
        assert result['vix_open'] == 15.00
        assert result['vix_close'] == 15.50
        assert result['vix_regime'] == 'moderate'

    def test_low_regime_date(self, vix_csv):
        result = get_vix_regime('2025-01-02', csv_path=vix_csv)
        assert result['vix_close'] == 14.80
        assert result['vix_regime'] == 'low'

    def test_elevated_regime_date(self, vix_csv):
        result = get_vix_regime('2025-01-09', csv_path=vix_csv)
        assert result['vix_close'] == 22.00
        assert result['vix_regime'] == 'elevated'

    def test_weekend_falls_back_to_friday(self, vix_csv):
        """Saturday 01/04 should fall back to Friday 01/03."""
        result = get_vix_regime('2025-01-04', csv_path=vix_csv)
        assert result['vix_close'] == 15.50  # Friday's close

    def test_prior_close(self, vix_csv):
        result = get_vix_regime('2025-01-03', csv_path=vix_csv)
        assert result['vix_prior_close'] == 14.80  # 01/02 close

    def test_change_pct(self, vix_csv):
        result = get_vix_regime('2025-01-03', csv_path=vix_csv)
        expected = round((15.50 - 14.80) / 14.80 * 100, 2)
        assert result['vix_change_pct'] == expected

    def test_5d_avg(self, vix_csv):
        # 01/10 has 7 prior dates, so 5d avg is from 01/03-01/09
        result = get_vix_regime('2025-01-10', csv_path=vix_csv)
        assert result['vix_5d_avg'] is not None
        assert result['vix_5d_avg'] > 0

    def test_missing_csv_returns_unknown(self):
        clear_cache()
        result = get_vix_regime('2025-01-03', csv_path='/nonexistent/path.csv')
        assert result['vix_regime'] == 'unknown'
        assert result['vix_close'] is None

    def test_date_before_data_returns_unknown(self, vix_csv):
        result = get_vix_regime('1989-01-01', csv_path=vix_csv)
        assert result['vix_regime'] == 'unknown'


# --- Integration with real CBOE data ---

class TestRealData:
    """Tests using the actual CBOE CSV if available."""

    @pytest.fixture(autouse=True)
    def check_real_csv(self):
        clear_cache()
        self.csv_path = str(
            Path(__file__).resolve().parents[3] / "data" / "vix" / "VIX_History.csv"
        )
        if not os.path.exists(self.csv_path):
            pytest.skip("Real VIX CSV not found")
        yield
        clear_cache()

    def test_real_data_loads(self):
        result = get_vix_regime('2025-01-02', csv_path=self.csv_path)
        assert result['vix_close'] is not None
        assert result['vix_regime'] != 'unknown'

    def test_real_data_recent_date(self):
        result = get_vix_regime('2026-03-06', csv_path=self.csv_path)
        assert result['vix_close'] is not None
        assert result['vix_regime'] in ('low', 'moderate', 'elevated', 'high', 'extreme')

    def test_real_data_covid_crash(self):
        """VIX should have been extreme during COVID crash (March 2020)."""
        result = get_vix_regime('2020-03-16', csv_path=self.csv_path)
        assert result['vix_close'] is not None
        assert result['vix_close'] > 50  # VIX hit 82 on 3/16/2020
        assert result['vix_regime'] == 'extreme'
