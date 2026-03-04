"""
Cross-platform CSV data loader for NinjaTrader volumetric exports.
Replaces the old data_loader.py with proper path handling and bug fixes.

Supports:
  - Direct CSV path via csv_dir parameter
  - data/sessions/ directory with zip extraction fallback
  - Legacy csv/ directory auto-discovery
"""

import zipfile

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


def find_project_root() -> Path:
    """Walk up from this file to find the repo root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / 'pyproject.toml').is_file():
            return current
        # Also check for csv/ directory (legacy)
        if (current / 'csv').is_dir():
            return current
        current = current.parent
    raise FileNotFoundError("Could not locate project root")


def _extract_zip_if_needed(data_dir: Path, instrument: str) -> Path:
    """Extract zip to CSV if CSV doesn't exist yet."""
    csv_path = data_dir / f'{instrument}_Volumetric_1.csv'
    if csv_path.exists():
        return csv_path

    zip_path = data_dir / f'{instrument}_Volumetric_1.zip'
    if not zip_path.exists():
        raise FileNotFoundError(
            f"Neither CSV nor zip found for {instrument} in {data_dir}"
        )

    with zipfile.ZipFile(zip_path, 'r') as zf:
        csv_members = [m for m in zf.namelist() if m.endswith('.csv')]
        if not csv_members:
            raise FileNotFoundError(f"No CSV inside {zip_path}")
        with zf.open(csv_members[0]) as src, open(csv_path, 'wb') as dst:
            dst.write(src.read())

    print(f"Extracted: {zip_path.name} -> {csv_path.name}")
    return csv_path


def load_csv(instrument: str = 'NQ', csv_dir: Optional[Path] = None) -> pd.DataFrame:
    """
    Load NinjaTrader volumetric CSV data.

    Args:
        instrument: 'NQ', 'ES', or 'YM'
        csv_dir: Optional path to csv directory. Searches in order:
                 1. Provided csv_dir
                 2. {project_root}/data/sessions/ (with zip extraction)
                 3. {project_root}/csv/ (legacy)

    Returns:
        DataFrame with parsed timestamps and numeric columns.
    """
    instrument = instrument.upper()
    filename = f'{instrument}_Volumetric_1.csv'

    if csv_dir is not None:
        csv_dir = Path(csv_dir)
        filepath = csv_dir / filename
        # Try zip extraction if CSV missing
        if not filepath.exists():
            filepath = _extract_zip_if_needed(csv_dir, instrument)
    else:
        root = find_project_root()

        # Try data/sessions/ first (new convention)
        sessions_dir = root / 'data' / 'sessions'
        if sessions_dir.is_dir():
            sessions_csv = sessions_dir / filename
            sessions_zip = sessions_dir / f'{instrument}_Volumetric_1.zip'
            if sessions_csv.exists() or sessions_zip.exists():
                filepath = _extract_zip_if_needed(sessions_dir, instrument)
            elif (root / 'csv').is_dir():
                filepath = root / 'csv' / filename
            else:
                raise FileNotFoundError(
                    f"CSV not found in data/sessions/ or csv/ for {instrument}"
                )
        elif (root / 'csv').is_dir():
            filepath = root / 'csv' / filename
        else:
            raise FileNotFoundError(
                f"No data directory found (tried data/sessions/, csv/)"
            )

    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    # Read CSV, skip schema line (first line starts with #)
    df = pd.read_csv(filepath, low_memory=False, comment='#')

    # Convert numeric columns
    numeric_cols = [
        'open', 'high', 'low', 'close', 'volume',
        'ema20', 'ema50', 'ema200', 'rsi14', 'atr14',
        'vwap', 'vwap_upper1', 'vwap_upper2', 'vwap_upper3',
        'vwap_lower1', 'vwap_lower2', 'vwap_lower3',
        'vol_ask', 'vol_bid', 'vol_delta',
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Parse timestamps
    df = df[df['timestamp'].astype(str).str.len() >= 19].copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
    df = df.dropna(subset=['timestamp'])

    # Parse session date
    df['session_date'] = pd.to_datetime(df['session_date'], errors='coerce')

    # Derived time columns
    df['time'] = df['timestamp'].dt.time

    print(f"Loaded {instrument}: {len(df):,} rows")
    print(f"  Date range: {df['session_date'].min().date()} to {df['session_date'].max().date()}")
    print(f"  Sessions: {df['session_date'].nunique()}")

    return df
