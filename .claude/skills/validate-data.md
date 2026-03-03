---
name: validate-data
description: Validate session data integrity — row counts, columns, date ranges, gaps
allowed-tools: ["Bash", "Read"]
---

Validate that session data is complete and well-formed.

## Usage
- `/validate-data` — Validate all instruments
- `/validate-data NQ` — Validate single instrument

## Steps

1. **Load and inspect data**:
   ```bash
   uv run python -c "
   from rockit_core.data.manager import SessionDataManager
   mgr = SessionDataManager()
   for inst in ['NQ', 'ES', 'YM']:
       info = mgr.info(inst)
       df = mgr.load(inst)
       # Check for required columns
       required = ['timestamp','instrument','open','high','low','close','volume',
                    'ema20','ema50','ema200','rsi14','atr14','vwap',
                    'vol_ask','vol_bid','vol_delta','session_date']
       missing = [c for c in required if c not in df.columns]
       print(f'  Missing columns: {missing or \"none\"}')
       # Check for NaN in critical columns
       for col in ['open','high','low','close','volume']:
           nan_pct = df[col].isna().mean() * 100
           if nan_pct > 0:
               print(f'  WARNING: {col} has {nan_pct:.1f}% NaN')
       # Check for session gaps (weekdays without data)
       import pandas as pd
       dates = pd.to_datetime(df['session_date'].unique())
       all_weekdays = pd.bdate_range(dates.min(), dates.max())
       # Exclude known holidays roughly
       missing_days = set(all_weekdays.date) - set(dates.date)
       if len(missing_days) > 10:
           print(f'  INFO: {len(missing_days)} weekdays without data (holidays + gaps)')
       print()
   "
   ```

2. **Report**:
   - Per instrument: rows, sessions, date range
   - Missing columns (if any)
   - NaN percentage in critical columns
   - Session gaps (missing weekdays beyond holidays)
   - Data quality verdict: PASS / WARN / FAIL
