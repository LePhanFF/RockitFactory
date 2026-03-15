import {
  LayoutDashboard, ArrowUpRight, ArrowDownRight, Activity,
  Palette, BookText, User, LogOut, Wifi, WifiOff, Clock
} from 'lucide-react'
import { useAuthStore, useMarketStore, useUIStore } from '../store'
import { PHASE_NAMES } from '../types'
import clsx from 'clsx'

export function Header() {
  const { user, logout } = useAuthStore()
  const { connected, market, sessionPnl, riskRules } = useMarketStore()
  const { theme, cycleTheme, toggleJournal } = useUIStore()

  const bias = market.bias
  const isLong = bias === 'LONG'
  const isShort = bias === 'SHORT'
  const phaseName = PHASE_NAMES[market.phase] || 'Pre-Market'

  return (
    <header className="shrink-0 bg-surface/95 border-b border-border px-4 py-2 flex items-center justify-between glass z-50 h-16">
      {/* Left: Brand */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-accent rounded-xl shadow-[0_0_20px_var(--accent-glow)] border border-white/10">
          <LayoutDashboard className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-black tracking-tighter text-content uppercase">
            ROCKIT <span className="text-accent">ENGINE</span>
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            {connected
              ? <Wifi className="w-2.5 h-2.5 text-emerald-400" />
              : <WifiOff className="w-2.5 h-2.5 text-rose-400" />
            }
            <span className="text-[9px] font-bold text-content-muted uppercase tracking-widest">
              {connected ? 'LIVE' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </div>

      {/* Center: Key metrics bar */}
      <div className={clsx(
        'flex-1 mx-4 h-full rounded-2xl border flex items-center justify-between px-4 gap-6 transition-all duration-500',
        isLong && 'bg-emerald-500/5 border-emerald-500/20',
        isShort && 'bg-rose-500/5 border-rose-500/20',
        !isLong && !isShort && 'bg-accent/5 border-accent/20',
      )}>
        {/* Instrument + Time */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-black text-content uppercase">{market.instrument}</span>
          <div className="flex items-center gap-1 bg-surface px-2 py-1 rounded-lg border border-border">
            <Clock className="w-3 h-3 text-accent" />
            <span className="text-xs font-mono font-black text-content">{market.current_time}</span>
          </div>
        </div>

        {/* Price */}
        <div className="text-center">
          <span className="text-[8px] font-bold text-content-muted uppercase tracking-widest block">Price</span>
          <span className="text-lg font-mono font-black text-content">{market.current_price.toFixed(2)}</span>
        </div>

        {/* Phase */}
        <div className="text-center">
          <span className="text-[8px] font-bold text-content-muted uppercase tracking-widest block">Phase</span>
          <span className="text-xs font-bold text-accent">{phaseName}</span>
        </div>

        {/* Day Type */}
        <div className="text-center">
          <span className="text-[8px] font-bold text-content-muted uppercase tracking-widest block">Day Type</span>
          <span className="text-xs font-bold text-content">{market.day_type}</span>
        </div>

        {/* Bias */}
        <div className={clsx(
          'px-3 py-1 rounded-lg border font-black text-xs tracking-wider',
          isLong && 'bg-emerald-500 text-emerald-950 border-emerald-400',
          isShort && 'bg-rose-500 text-rose-950 border-rose-400',
          !isLong && !isShort && 'bg-accent text-white border-accent',
        )}>
          <div className="flex items-center gap-1">
            {isLong ? <ArrowUpRight className="w-3 h-3" /> : isShort ? <ArrowDownRight className="w-3 h-3" /> : <Activity className="w-3 h-3" />}
            {bias}
          </div>
        </div>

        {/* Session P&L */}
        <div className="text-center">
          <span className="text-[8px] font-bold text-content-muted uppercase tracking-widest block">Session P&L</span>
          <span className={clsx(
            'text-sm font-mono font-black',
            sessionPnl > 0 && 'text-emerald-400',
            sessionPnl < 0 && 'text-rose-400',
            sessionPnl === 0 && 'text-content-muted',
          )}>
            {sessionPnl >= 0 ? '+' : ''}{sessionPnl.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 })}
          </span>
        </div>

        {/* Positions */}
        <div className="text-center">
          <span className="text-[8px] font-bold text-content-muted uppercase tracking-widest block">Positions</span>
          <span className="text-xs font-mono font-bold text-content">
            {riskRules.current_positions}/{riskRules.max_positions}
          </span>
        </div>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-2">
        <button onClick={toggleJournal} className="p-2 rounded-full bg-surface border border-border text-content-muted hover:text-accent transition-colors" title="Journal">
          <BookText className="w-4 h-4" />
        </button>
        <button onClick={cycleTheme} className="p-2 rounded-full bg-surface border border-border text-content-muted hover:text-accent transition-colors" title={`Theme: ${theme}`}>
          <Palette className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-2 pl-2 border-l border-border">
          <div className="w-7 h-7 rounded-full bg-panel flex items-center justify-center border border-border">
            <User className="w-3.5 h-3.5 text-content-muted" />
          </div>
          <span className="text-[10px] font-bold text-content-muted">{user?.display_name || user?.username}</span>
          <button onClick={logout} className="p-1.5 rounded-full hover:bg-rose-500/20 hover:text-rose-400 text-content-muted transition-colors" title="Logout">
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  )
}
