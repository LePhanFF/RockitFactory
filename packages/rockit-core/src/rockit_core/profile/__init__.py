"""
Profile adapters wrapping rockit-framework modules.
Normalizes interfaces for use in the backtest engine session_context.
"""

from rockit_core.profile.volume_profile import VolumeProfileAdapter
from rockit_core.profile.tpo_profile import TPOProfileAdapter
from rockit_core.profile.ib_analysis import IBAnalysisAdapter
from rockit_core.profile.dpoc_migration import DPOCMigrationAdapter
from rockit_core.profile.confluences import ConfluenceAdapter
from rockit_core.profile.wick_parade import WickParadeAdapter

__all__ = [
    'VolumeProfileAdapter',
    'TPOProfileAdapter',
    'IBAnalysisAdapter',
    'DPOCMigrationAdapter',
    'ConfluenceAdapter',
    'WickParadeAdapter',
]
