import { CheckCircle, Circle, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useMarketStore } from '../store'
import { PHASE_NAMES } from '../types'

const PHASE_TIMES = ['< 9:30', '9:30-10:30', '10:30-12:00', '12:00-15:00']

const PHASE_STRATEGIES: Record<number, string[]> = {
  0: ['NDOG Gap Fill', 'NWOG Gap Fill'],
  1: ['PDH/PDL React', 'OR forming...'],
  2: ['OR Rev', 'OR Accept', '80P', 'Trend Bull/Bear', 'IB Edge', 'B-Day', 'VA Edge'],
  3: ['20P Extension', 'Manage open positions', 'EOD exits'],
}

export function TradePlan() {
  const { market, riskRules, sessionPnl } = useMarketStore()
  const currentPhase = market.phase

  return (
    <div className="bg-surface/50 border border-border rounded-2xl p-4 space-y-4">
      {/* Phase Timeline */}
      <div className="flex items-center gap-1">
        {PHASE_NAMES.map((name, i) => (
          <div key={i} className="flex-1 flex flex-col items-center">
            <div className={clsx(
              'w-full h-1.5 rounded-full transition-all',
              i < currentPhase && 'bg-emerald-500',
              i === currentPhase && 'bg-accent animate-pulse-glow',
              i > currentPhase && 'bg-slate-800',
            )} />
            <span className={clsx(
              'text-[8px] font-bold uppercase tracking-wider mt-1',
              i === currentPhase ? 'text-accent' : 'text-content-muted',
            )}>
              {name}
            </span>
            <span className="text-[7px] text-content-muted">{PHASE_TIMES[i]}</span>
          </div>
        ))}
      </div>

      {/* Current phase strategies */}
      <div className="bg-background/50 rounded-xl p-3">
        <div className="text-[9px] font-bold text-accent uppercase tracking-widest mb-2">
          Phase {currentPhase}: {PHASE_NAMES[currentPhase]} — Active Strategies
        </div>
        <div className="flex flex-wrap gap-1.5">
          {PHASE_STRATEGIES[currentPhase]?.map(s => (
            <span key={s} className="text-[9px] font-bold bg-accent/10 text-accent border border-accent/20 px-2 py-1 rounded-lg">
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* IB Decision Tree (Phase 2) */}
      {currentPhase >= 2 && market.ib_range && (
        <div className="bg-background/50 rounded-xl p-3">
          <div className="text-[9px] font-bold text-content-muted uppercase tracking-widest mb-2">
            Decision Tree
          </div>
          <div className="space-y-1 text-[10px]">
            <div className="flex items-center gap-2">
              <span className="text-content-muted">IB Range:</span>
              <span className={clsx(
                'font-mono font-bold',
                market.ib_range < 100 ? 'text-amber-400' : market.ib_range > 200 ? 'text-rose-400' : 'text-content',
              )}>
                {market.ib_range.toFixed(0)}pt
              </span>
              <span className="text-content-muted">
                {market.ib_range < 100 ? '(Narrow — watch for extension)' :
                 market.ib_range > 200 ? '(Wide — trend developing)' :
                 '(Normal)'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-content-muted">Day Type:</span>
              <span className="font-bold text-content">{market.day_type}</span>
              <span className="text-content-muted">({(market.day_type_confidence * 100).toFixed(0)}% conf)</span>
            </div>
          </div>
        </div>
      )}

      {/* Risk Rules */}
      <div className="space-y-1.5">
        <div className="text-[9px] font-bold text-content-muted uppercase tracking-widest">
          Risk Rules
        </div>
        <RiskRule
          label="Positions"
          current={riskRules.current_positions}
          max={riskRules.max_positions}
          ok={riskRules.current_positions < riskRules.max_positions}
        />
        <RiskRule
          label="Daily P&L"
          current={`$${sessionPnl.toFixed(0)}`}
          max={`$${riskRules.daily_loss_limit}`}
          ok={sessionPnl > riskRules.daily_loss_limit}
        />
        <RiskRule
          label="Consecutive losses"
          current={riskRules.consecutive_losses}
          max={riskRules.max_consecutive_losses}
          ok={riskRules.consecutive_losses < riskRules.max_consecutive_losses}
        />
      </div>
    </div>
  )
}

function RiskRule({ label, current, max, ok }: { label: string; current: any; max: any; ok: boolean }) {
  return (
    <div className="flex items-center justify-between text-[10px]">
      <div className="flex items-center gap-1.5">
        {ok
          ? <CheckCircle className="w-3 h-3 text-emerald-500" />
          : <AlertTriangle className="w-3 h-3 text-rose-400" />
        }
        <span className="text-content-muted">{label}</span>
      </div>
      <span className={clsx('font-mono font-bold', ok ? 'text-content' : 'text-rose-400')}>
        {String(current)} / {String(max)}
      </span>
    </div>
  )
}
