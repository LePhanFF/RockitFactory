import { useMarketStore, useAuthStore } from '../store'
import { StrategyCard } from './StrategyCard'
import { STRATEGY_DISPLAY } from '../types'

const STRATEGY_ORDER = [
  'or_reversal', 'or_acceptance', '80p_rule', '20p_ib_extension',
  'trend_bull', 'trend_bear', 'bday', 'ib_edge_fade',
  'pdh_pdl_reaction', 'va_edge_fade', 'ndog_gap_fill', 'nwog_gap_fill',
]

export function StrategyBoard() {
  const strategies = useMarketStore(s => s.strategies)
  const prefs = useAuthStore(s => s.strategyPrefs)
  const prefMap = Object.fromEntries(prefs.map(p => [p.strategy_id, p]))

  // Count by state
  const counts = Object.values(strategies).reduce((acc, s) => {
    acc[s.state] = (acc[s.state] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div>
      {/* Summary bar */}
      <div className="flex items-center gap-3 mb-3 text-[9px] font-bold uppercase tracking-widest">
        {counts.FIRED && <span className="text-emerald-400">{counts.FIRED} Fired</span>}
        {counts.ARMED && <span className="text-amber-400">{counts.ARMED} Armed</span>}
        {counts.WATCHING && <span className="text-sky-400">{counts.WATCHING} Watching</span>}
        {counts.BLOCKED && <span className="text-rose-400">{counts.BLOCKED} Blocked</span>}
        {counts.DONE && <span className="text-emerald-600">{counts.DONE} Done</span>}
      </div>

      {/* 4×3 grid */}
      <div className="grid grid-cols-4 gap-2">
        {STRATEGY_ORDER.map(sid => {
          const state = strategies[sid]
          if (!state) {
            return (
              <div key={sid} className="rounded-2xl border border-slate-800/30 bg-slate-900/20 p-3">
                <span className="text-[10px] font-bold text-slate-700 uppercase">
                  {STRATEGY_DISPLAY[sid]?.short || sid}
                </span>
                <div className="text-[9px] text-slate-700 mt-1">Waiting...</div>
              </div>
            )
          }
          return <StrategyCard key={sid} state={state} pref={prefMap[sid]} />
        })}
      </div>
    </div>
  )
}
