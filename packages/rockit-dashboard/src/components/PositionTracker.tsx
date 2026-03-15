import { ArrowUpRight, ArrowDownRight } from 'lucide-react'
import clsx from 'clsx'
import { useMarketStore } from '../store'
import { STRATEGY_DISPLAY } from '../types'

export function PositionTracker() {
  const strategies = useMarketStore(s => s.strategies)
  const sessionPnl = useMarketStore(s => s.sessionPnl)

  // Extract positions from FIRED and DONE strategies
  const openPositions = Object.values(strategies).filter(s => s.state === 'FIRED' && s.entry_price)
  const closedPositions = Object.values(strategies).filter(s => s.state === 'DONE' && s.current_pnl != null)

  return (
    <div className="bg-surface/50 border border-border rounded-2xl p-4 space-y-3">
      {/* Session summary */}
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-bold text-content-muted uppercase tracking-widest">Session</span>
        <span className={clsx(
          'text-sm font-mono font-black',
          sessionPnl > 0 && 'text-emerald-400',
          sessionPnl < 0 && 'text-rose-400',
          sessionPnl === 0 && 'text-content-muted',
        )}>
          {sessionPnl >= 0 ? '+' : ''}${sessionPnl.toFixed(0)}
        </span>
      </div>

      {/* Open positions */}
      {openPositions.length > 0 && (
        <div>
          <div className="text-[8px] font-bold text-emerald-400 uppercase tracking-widest mb-1.5">
            Open ({openPositions.length})
          </div>
          <div className="space-y-2">
            {openPositions.map(pos => {
              const display = STRATEGY_DISPLAY[pos.strategy_id]
              const isLong = pos.direction === 'LONG'
              const risk = Math.abs((pos.entry_price || 0) - (pos.stop_price || 0))
              const reward = Math.abs((pos.target_price || 0) - (pos.entry_price || 0))
              const progress = risk > 0 && pos.current_pnl != null
                ? Math.min(100, Math.max(0, ((pos.current_pnl / 20) / reward) * 100))
                : 0

              return (
                <div key={pos.strategy_id} className="bg-background/50 rounded-xl p-3 border border-border/50">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {isLong
                        ? <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400" />
                        : <ArrowDownRight className="w-3.5 h-3.5 text-rose-400" />
                      }
                      <span className="text-[10px] font-black text-content uppercase">
                        {display?.short || pos.strategy_id}
                      </span>
                      <span className={clsx('text-[9px] font-bold', isLong ? 'text-emerald-400' : 'text-rose-400')}>
                        {pos.direction}
                      </span>
                    </div>
                    <span className={clsx(
                      'text-xs font-mono font-black',
                      (pos.current_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400',
                    )}>
                      {(pos.current_pnl || 0) >= 0 ? '+' : ''}${(pos.current_pnl || 0).toFixed(0)}
                    </span>
                  </div>

                  {/* Entry / Stop / Target row */}
                  <div className="grid grid-cols-3 gap-2 text-[8px] mb-2">
                    <div>
                      <span className="text-content-muted block">Entry</span>
                      <span className="font-mono font-bold text-content">{pos.entry_price?.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-content-muted block">Stop</span>
                      <span className="font-mono font-bold text-rose-400">
                        {pos.trailing_stop ? pos.trailing_stop.toFixed(2) : pos.stop_price?.toFixed(2)}
                        {pos.trailing_stop && <span className="text-amber-400 ml-0.5">(T)</span>}
                      </span>
                    </div>
                    <div>
                      <span className="text-content-muted block">Target</span>
                      <span className="font-mono font-bold text-emerald-400">{pos.target_price?.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-slate-800 rounded-full h-1.5">
                    <div
                      className={clsx(
                        'h-1.5 rounded-full transition-all',
                        progress >= 0 ? 'bg-emerald-500' : 'bg-rose-500',
                      )}
                      style={{ width: `${Math.abs(progress)}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Closed positions */}
      {closedPositions.length > 0 && (
        <div>
          <div className="text-[8px] font-bold text-content-muted uppercase tracking-widest mb-1.5">
            Closed ({closedPositions.length})
          </div>
          <div className="space-y-1">
            {closedPositions.map(pos => {
              const display = STRATEGY_DISPLAY[pos.strategy_id]
              return (
                <div key={pos.strategy_id} className="flex items-center justify-between text-[9px] py-1.5 px-2 rounded-lg bg-background/30">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-content-muted">{display?.short || pos.strategy_id}</span>
                    <span className={clsx('font-bold', pos.direction === 'LONG' ? 'text-emerald-600' : 'text-rose-600')}>
                      {pos.direction}
                    </span>
                  </div>
                  <span className={clsx(
                    'font-mono font-bold',
                    (pos.current_pnl || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600',
                  )}>
                    {(pos.current_pnl || 0) >= 0 ? '+' : ''}${(pos.current_pnl || 0).toFixed(0)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {openPositions.length === 0 && closedPositions.length === 0 && (
        <div className="text-center py-4">
          <span className="text-[10px] text-content-muted uppercase tracking-widest">No positions today</span>
        </div>
      )}
    </div>
  )
}
