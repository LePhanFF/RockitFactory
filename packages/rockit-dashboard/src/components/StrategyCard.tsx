import { ArrowUpRight, ArrowDownRight, Lock, Eye, Crosshair, CheckCircle, XCircle, Clock } from 'lucide-react'
import clsx from 'clsx'
import type { StrategyState, StrategyPref } from '../types'
import { STRATEGY_DISPLAY } from '../types'
import { useUIStore } from '../store'

interface Props {
  state: StrategyState
  pref?: StrategyPref
}

const STATE_STYLES: Record<string, { bg: string; border: string; text: string; label: string }> = {
  INACTIVE: { bg: 'bg-slate-900/30', border: 'border-slate-800/50', text: 'text-slate-600', label: 'Inactive' },
  WATCHING: { bg: 'bg-sky-500/5', border: 'border-sky-500/20', text: 'text-sky-400', label: 'Watching' },
  ARMED:    { bg: 'bg-amber-500/5', border: 'border-amber-500/20', text: 'text-amber-400', label: 'Armed' },
  FIRED:    { bg: 'bg-emerald-500/5', border: 'border-emerald-500/20', text: 'text-emerald-400', label: 'Fired' },
  DONE:     { bg: 'bg-emerald-500/5', border: 'border-emerald-800/30', text: 'text-emerald-600', label: 'Done' },
  BLOCKED:  { bg: 'bg-rose-500/5', border: 'border-rose-500/20', text: 'text-rose-400', label: 'Blocked' },
}

const STATE_ICONS: Record<string, typeof Eye> = {
  INACTIVE: Clock,
  WATCHING: Eye,
  ARMED: Crosshair,
  FIRED: ArrowUpRight,
  DONE: CheckCircle,
  BLOCKED: XCircle,
}

export function StrategyCard({ state, pref }: Props) {
  const selectStrategy = useUIStore(s => s.selectStrategy)
  const display = STRATEGY_DISPLAY[state.strategy_id] || { name: state.strategy_id, short: state.strategy_id, color: 'slate' }
  const style = STATE_STYLES[state.state] || STATE_STYLES.INACTIVE
  const Icon = STATE_ICONS[state.state] || Clock

  const isUserActive = pref?.is_active !== false
  const masteryBadge = pref?.mastery_level === 'mastered' ? 'M' : pref?.mastery_level === 'practicing' ? 'P' : null

  return (
    <button
      onClick={() => selectStrategy(state.strategy_id)}
      className={clsx(
        'relative rounded-2xl border p-3 transition-all hover:scale-[1.02] hover:shadow-lg text-left w-full',
        style.bg, style.border,
        state.state === 'ARMED' && 'animate-pulse-glow',
        !isUserActive && 'opacity-40',
      )}
    >
      {/* Top row: name + state */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-black uppercase tracking-wider text-content truncate">
          {display.short}
        </span>
        <div className="flex items-center gap-1">
          {masteryBadge && (
            <span className="text-[8px] font-black bg-accent/20 text-accent px-1.5 py-0.5 rounded">
              {masteryBadge}
            </span>
          )}
          <Icon className={clsx('w-3 h-3', style.text)} />
        </div>
      </div>

      {/* State label */}
      <div className={clsx('text-[9px] font-bold uppercase tracking-widest mb-2', style.text)}>
        {state.state === 'BLOCKED' ? state.block_reason || 'Blocked' : style.label}
        {state.direction && state.state !== 'BLOCKED' && (
          <span className="ml-1">
            {state.direction === 'LONG'
              ? <ArrowUpRight className="w-3 h-3 inline text-emerald-400" />
              : <ArrowDownRight className="w-3 h-3 inline text-rose-400" />
            }
          </span>
        )}
      </div>

      {/* FIRED / ARMED details */}
      {(state.state === 'FIRED' || state.state === 'ARMED') && state.entry_price && (
        <div className="space-y-1 text-[9px] font-mono">
          <div className="flex justify-between">
            <span className="text-content-muted">Entry</span>
            <span className="text-content font-bold">{state.entry_price.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-content-muted">Stop</span>
            <span className="text-rose-400">{state.stop_price?.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-content-muted">Target</span>
            <span className="text-emerald-400">{state.target_price?.toFixed(2)}</span>
          </div>
          {state.trailing_stop && (
            <div className="flex justify-between">
              <span className="text-content-muted">Trail</span>
              <span className="text-amber-400">{state.trailing_stop.toFixed(2)}</span>
            </div>
          )}
        </div>
      )}

      {/* P&L for fired */}
      {state.state === 'FIRED' && state.current_pnl != null && (
        <div className={clsx(
          'mt-2 text-center py-1 rounded-lg text-xs font-mono font-black',
          state.current_pnl >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400',
        )}>
          {state.current_pnl >= 0 ? '+' : ''}{state.current_pnl.toFixed(0)}
        </div>
      )}

      {/* Done P&L */}
      {state.state === 'DONE' && state.current_pnl != null && (
        <div className={clsx(
          'mt-1 text-center text-[10px] font-mono font-bold',
          state.current_pnl >= 0 ? 'text-emerald-600' : 'text-rose-600',
        )}>
          {state.current_pnl >= 0 ? '+' : ''}${state.current_pnl.toFixed(0)}
        </div>
      )}

      {/* Condition progress for WATCHING/ARMED */}
      {(state.state === 'WATCHING' || state.state === 'ARMED') && Object.keys(state.condition_progress).length > 0 && (
        <div className="mt-2 space-y-0.5">
          {Object.entries(state.condition_progress).map(([key, val]) => (
            <div key={key} className="flex justify-between text-[8px]">
              <span className="text-content-muted">{key.replace(/_/g, ' ')}</span>
              <span className="text-content font-mono">{String(val)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Bottom: Historical stats */}
      <div className="mt-2 pt-2 border-t border-border/50 flex justify-between text-[8px] text-content-muted">
        <span>WR {state.historical_wr ? `${(state.historical_wr * 100).toFixed(0)}%` : '--'}</span>
        <span>PF {state.historical_pf?.toFixed(1) || '--'}</span>
      </div>
    </button>
  )
}
