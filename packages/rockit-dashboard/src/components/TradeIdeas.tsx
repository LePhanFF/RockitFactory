import { ArrowUpRight, ArrowDownRight, Shield, ThumbsUp, ThumbsDown } from 'lucide-react'
import clsx from 'clsx'
import { useMarketStore, useUIStore } from '../store'
import { STRATEGY_DISPLAY } from '../types'
import type { TradeIdea } from '../types'

export function TradeIdeasPanel() {
  const ideas = useMarketStore(s => s.tradeIdeas)

  if (ideas.length === 0) {
    return (
      <div className="bg-surface/50 border border-border rounded-2xl p-6 text-center">
        <span className="text-[10px] text-content-muted uppercase tracking-widest">No active trade ideas</span>
      </div>
    )
  }

  // Sort: ready > developing > others
  const sorted = [...ideas].sort((a, b) => {
    const order = { ready: 0, developing: 1, fired: 2, expired: 3 }
    return (order[a.status] ?? 9) - (order[b.status] ?? 9)
  })

  return (
    <div className="space-y-2">
      {sorted.map(idea => <TradeIdeaCard key={idea.id} idea={idea} />)}
    </div>
  )
}

function TradeIdeaCard({ idea }: { idea: TradeIdea }) {
  const selectStrategy = useUIStore(s => s.selectStrategy)
  const display = STRATEGY_DISPLAY[idea.strategy_id] || { name: idea.strategy_id, short: idea.strategy_id }
  const isLong = idea.direction === 'LONG'

  const confidenceColor = {
    high: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    low: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  }[idea.confidence]

  return (
    <button
      onClick={() => selectStrategy(idea.strategy_id)}
      className={clsx(
        'w-full text-left rounded-2xl border p-4 transition-all hover:scale-[1.01] hover:shadow-lg',
        idea.status === 'ready' && 'bg-emerald-500/5 border-emerald-500/20',
        idea.status === 'developing' && 'bg-amber-500/5 border-amber-500/20',
        idea.status === 'fired' && 'bg-sky-500/5 border-sky-500/20',
        idea.status === 'expired' && 'bg-slate-500/5 border-slate-800/30 opacity-50',
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={clsx('text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded border', confidenceColor)}>
            {idea.confidence}
          </span>
          <span className="text-xs font-black text-content uppercase">{display.name}</span>
        </div>
        <div className="flex items-center gap-1">
          {isLong
            ? <ArrowUpRight className="w-4 h-4 text-emerald-400" />
            : <ArrowDownRight className="w-4 h-4 text-rose-400" />
          }
          <span className={clsx('text-xs font-black', isLong ? 'text-emerald-400' : 'text-rose-400')}>
            {idea.direction}
          </span>
        </div>
      </div>

      {/* Rationale */}
      <p className="text-[10px] text-content-muted mb-3 leading-relaxed">{idea.rationale}</p>

      {/* Entry / Stop / Target */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div>
          <span className="text-[8px] text-content-muted uppercase block">Entry</span>
          <span className="text-[10px] font-mono font-bold text-content">{idea.entry_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-[8px] text-content-muted uppercase block">Stop</span>
          <span className="text-[10px] font-mono font-bold text-rose-400">{idea.stop_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-[8px] text-content-muted uppercase block">Target</span>
          <span className="text-[10px] font-mono font-bold text-emerald-400">{idea.target_price.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-[8px] text-content-muted uppercase block">R:R</span>
          <span className="text-[10px] font-mono font-bold text-accent">{idea.r_reward.toFixed(1)}</span>
        </div>
      </div>

      {/* Evidence summary */}
      <div className="flex items-center gap-3 text-[9px]">
        <div className="flex items-center gap-1 text-emerald-400">
          <ThumbsUp className="w-3 h-3" />
          <span className="font-bold">{idea.evidence_for.length} for</span>
        </div>
        <div className="flex items-center gap-1 text-rose-400">
          <ThumbsDown className="w-3 h-3" />
          <span className="font-bold">{idea.evidence_against.length} against</span>
        </div>
        {idea.agent_verdict && (
          <div className={clsx(
            'flex items-center gap-1 ml-auto px-2 py-0.5 rounded border text-[8px] font-black uppercase',
            idea.agent_verdict === 'TAKE' && 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
            idea.agent_verdict === 'SKIP' && 'bg-rose-500/10 text-rose-400 border-rose-500/20',
            idea.agent_verdict === 'REDUCE_SIZE' && 'bg-amber-500/10 text-amber-400 border-amber-500/20',
          )}>
            <Shield className="w-2.5 h-2.5" />
            {idea.agent_verdict}
          </div>
        )}
      </div>

      {/* Evidence cards (collapsed) */}
      {(idea.evidence_for.length > 0 || idea.evidence_against.length > 0) && (
        <div className="mt-3 pt-3 border-t border-border/50 space-y-1">
          {idea.evidence_for.map((e, i) => (
            <div key={`for-${i}`} className="flex items-center gap-2 text-[8px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span className="text-content-muted font-bold">{e.source}:</span>
              <span className="text-content">{e.signal}</span>
              <span className="text-content-muted ml-auto">{(e.strength * 100).toFixed(0)}%</span>
            </div>
          ))}
          {idea.evidence_against.map((e, i) => (
            <div key={`against-${i}`} className="flex items-center gap-2 text-[8px]">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
              <span className="text-content-muted font-bold">{e.source}:</span>
              <span className="text-content">{e.signal}</span>
              <span className="text-content-muted ml-auto">{(e.strength * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Agent reasoning */}
      {idea.agent_reasoning && (
        <div className="mt-2 text-[9px] text-content-muted italic">
          "{idea.agent_reasoning}"
        </div>
      )}
    </button>
  )
}
