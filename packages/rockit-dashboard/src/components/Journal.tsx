import { useState, useEffect } from 'react'
import { X, Plus, Save, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../api/client'
import { useUIStore, useAuthStore } from '../store'
import { STRATEGY_DISPLAY } from '../types'
import type { UserTrade, JournalEntry } from '../types'

const TODAY = new Date().toISOString().slice(0, 10)

export function Journal() {
  const toggleJournal = useUIStore(s => s.toggleJournal)
  const strategyPrefs = useAuthStore(s => s.strategyPrefs)
  const [tab, setTab] = useState<'trades' | 'notes'>('trades')
  const [trades, setTrades] = useState<UserTrade[]>([])
  const [journal, setJournal] = useState<JournalEntry[]>([])
  const [sessionDate, setSessionDate] = useState(TODAY)

  // Load data
  useEffect(() => {
    api.getTrades({ session_date: sessionDate }).then(setTrades).catch(() => {})
    api.getJournal({ session_date: sessionDate }).then(setJournal).catch(() => {})
  }, [sessionDate])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-black text-content uppercase tracking-wider">Journal</h2>
          <input
            type="date"
            value={sessionDate}
            onChange={e => setSessionDate(e.target.value)}
            className="bg-background border border-border rounded-lg px-2 py-1 text-[10px] font-mono text-content"
          />
        </div>
        <button onClick={toggleJournal} className="p-1.5 rounded-lg hover:bg-panel text-content-muted hover:text-content transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tab switcher */}
      <div className="flex border-b border-border">
        <button
          onClick={() => setTab('trades')}
          className={clsx('flex-1 py-2 text-[10px] font-bold uppercase tracking-widest transition-colors',
            tab === 'trades' ? 'text-accent border-b-2 border-accent' : 'text-content-muted hover:text-content'
          )}
        >
          Trades ({trades.length})
        </button>
        <button
          onClick={() => setTab('notes')}
          className={clsx('flex-1 py-2 text-[10px] font-bold uppercase tracking-widest transition-colors',
            tab === 'notes' ? 'text-accent border-b-2 border-accent' : 'text-content-muted hover:text-content'
          )}
        >
          Notes ({journal.length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
        {tab === 'trades'
          ? <TradesTab trades={trades} setTrades={setTrades} sessionDate={sessionDate} strategyPrefs={strategyPrefs} />
          : <NotesTab journal={journal} setJournal={setJournal} sessionDate={sessionDate} />
        }
      </div>
    </div>
  )
}

// ─── Trades Tab ──────────────────────────────────────────────────────────────

function TradesTab({ trades, setTrades, sessionDate, strategyPrefs }: {
  trades: UserTrade[]; setTrades: (t: UserTrade[]) => void; sessionDate: string; strategyPrefs: any[]
}) {
  const [showForm, setShowForm] = useState(false)

  const handleCreate = async (data: any) => {
    const trade = await api.createTrade({ ...data, session_date: sessionDate })
    setTrades([trade, ...trades])
    setShowForm(false)
  }

  const handleClose = async (id: number, result: string, exitPrice: number) => {
    const updated = await api.updateTrade(id, { result, exit_price: exitPrice, exit_time: new Date().toTimeString().slice(0, 5) })
    setTrades(trades.map(t => t.id === id ? updated : t))
  }

  const handleDelete = async (id: number) => {
    await api.deleteTrade(id)
    setTrades(trades.filter(t => t.id !== id))
  }

  // Filter to user's active strategies
  const activeStrategyIds = strategyPrefs.filter((p: any) => p.is_active).map((p: any) => p.strategy_id)

  return (
    <div className="space-y-3">
      <button
        onClick={() => setShowForm(!showForm)}
        className="w-full flex items-center justify-center gap-2 py-2 rounded-xl border border-dashed border-border hover:border-accent text-content-muted hover:text-accent transition-colors text-[10px] font-bold uppercase"
      >
        <Plus className="w-3 h-3" /> Log Trade
      </button>

      {showForm && <TradeForm onSubmit={handleCreate} onCancel={() => setShowForm(false)} activeStrategies={activeStrategyIds} />}

      {trades.map(trade => (
        <TradeCard key={trade.id} trade={trade} onClose={handleClose} onDelete={handleDelete} />
      ))}
    </div>
  )
}

function TradeForm({ onSubmit, onCancel, activeStrategies }: {
  onSubmit: (data: any) => void; onCancel: () => void; activeStrategies: string[]
}) {
  const [form, setForm] = useState({
    strategy_id: activeStrategies[0] || 'or_reversal',
    direction: 'LONG',
    entry_price: '',
    stop_price: '',
    target_price: '',
    entry_time: new Date().toTimeString().slice(0, 5),
    notes: '',
  })

  return (
    <div className="bg-background/50 rounded-xl p-3 border border-accent/20 space-y-2 animate-fade-in">
      <div className="grid grid-cols-2 gap-2">
        <select
          value={form.strategy_id}
          onChange={e => setForm({ ...form, strategy_id: e.target.value })}
          className="bg-background border border-border rounded-lg px-2 py-1.5 text-[10px] text-content"
        >
          {activeStrategies.map(sid => (
            <option key={sid} value={sid}>{STRATEGY_DISPLAY[sid]?.name || sid}</option>
          ))}
        </select>
        <select
          value={form.direction}
          onChange={e => setForm({ ...form, direction: e.target.value })}
          className="bg-background border border-border rounded-lg px-2 py-1.5 text-[10px] text-content"
        >
          <option value="LONG">LONG</option>
          <option value="SHORT">SHORT</option>
        </select>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {['entry_price', 'stop_price', 'target_price'].map(field => (
          <input
            key={field}
            type="number"
            step="0.01"
            placeholder={field.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
            value={(form as any)[field]}
            onChange={e => setForm({ ...form, [field]: e.target.value })}
            className="bg-background border border-border rounded-lg px-2 py-1.5 text-[10px] font-mono text-content"
          />
        ))}
      </div>
      <textarea
        placeholder="Notes..."
        value={form.notes}
        onChange={e => setForm({ ...form, notes: e.target.value })}
        className="w-full bg-background border border-border rounded-lg px-2 py-1.5 text-[10px] text-content resize-none h-16"
      />
      <div className="flex gap-2">
        <button
          onClick={() => onSubmit({ ...form, entry_price: +form.entry_price, stop_price: +form.stop_price, target_price: +form.target_price })}
          className="flex-1 bg-accent text-white text-[10px] font-bold py-1.5 rounded-lg uppercase"
        >
          Save
        </button>
        <button onClick={onCancel} className="px-3 text-[10px] text-content-muted hover:text-content">Cancel</button>
      </div>
    </div>
  )
}

function TradeCard({ trade, onClose, onDelete }: {
  trade: UserTrade
  onClose: (id: number, result: string, exitPrice: number) => void
  onDelete: (id: number) => void
}) {
  const display = STRATEGY_DISPLAY[trade.strategy_id]

  return (
    <div className={clsx(
      'rounded-xl border p-3 text-[10px]',
      trade.result === 'WIN' && 'bg-emerald-500/5 border-emerald-500/20',
      trade.result === 'LOSS' && 'bg-rose-500/5 border-rose-500/20',
      trade.result === 'OPEN' && 'bg-surface border-border',
      trade.result === 'SCRATCH' && 'bg-slate-500/5 border-slate-500/20',
    )}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-black text-content uppercase">{display?.short || trade.strategy_id}</span>
          <span className={clsx('font-bold', trade.direction === 'LONG' ? 'text-emerald-400' : 'text-rose-400')}>
            {trade.direction}
          </span>
          <span className="text-content-muted">{trade.entry_time}</span>
        </div>
        <div className="flex items-center gap-1">
          {trade.result !== 'OPEN' && (
            <span className={clsx(
              'font-mono font-bold',
              trade.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400',
            )}>
              {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(0)}
            </span>
          )}
          <button onClick={() => onDelete(trade.id)} className="p-1 text-content-muted hover:text-rose-400">
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[9px] font-mono">
        <div><span className="text-content-muted">E:</span> {trade.entry_price.toFixed(2)}</div>
        <div><span className="text-content-muted">S:</span> {trade.stop_price.toFixed(2)}</div>
        <div><span className="text-content-muted">T:</span> {trade.target_price.toFixed(2)}</div>
      </div>

      {trade.notes && <p className="text-content-muted mt-1 italic">{trade.notes}</p>}

      {trade.result === 'OPEN' && (
        <div className="flex gap-1 mt-2">
          <button
            onClick={() => {
              const exit = prompt('Exit price?')
              if (exit) onClose(trade.id, 'WIN', +exit)
            }}
            className="flex-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-lg py-1 text-[9px] font-bold uppercase"
          >
            Win
          </button>
          <button
            onClick={() => {
              const exit = prompt('Exit price?')
              if (exit) onClose(trade.id, 'LOSS', +exit)
            }}
            className="flex-1 bg-rose-500/10 text-rose-400 border border-rose-500/20 rounded-lg py-1 text-[9px] font-bold uppercase"
          >
            Loss
          </button>
          <button
            onClick={() => onClose(trade.id, 'SCRATCH', trade.entry_price)}
            className="flex-1 bg-slate-500/10 text-slate-400 border border-slate-500/20 rounded-lg py-1 text-[9px] font-bold uppercase"
          >
            Scratch
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Notes Tab ───────────────────────────────────────────────────────────────

function NotesTab({ journal, setJournal, sessionDate }: {
  journal: JournalEntry[]; setJournal: (j: JournalEntry[]) => void; sessionDate: string
}) {
  const [newType, setNewType] = useState('premarket')
  const [newContent, setNewContent] = useState('')

  const handleCreate = async () => {
    if (!newContent.trim()) return
    const entry = await api.createJournalEntry({ session_date: sessionDate, entry_type: newType, content: newContent })
    setJournal([entry, ...journal])
    setNewContent('')
  }

  return (
    <div className="space-y-3">
      {/* New entry form */}
      <div className="bg-background/50 rounded-xl p-3 border border-border space-y-2">
        <div className="flex gap-2">
          <select
            value={newType}
            onChange={e => setNewType(e.target.value)}
            className="bg-background border border-border rounded-lg px-2 py-1 text-[10px] text-content"
          >
            <option value="premarket">Pre-Market</option>
            <option value="intraday">Intraday</option>
            <option value="postmarket">Post-Market</option>
            <option value="review">Review</option>
          </select>
        </div>
        <textarea
          placeholder="What's on your mind..."
          value={newContent}
          onChange={e => setNewContent(e.target.value)}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-[10px] text-content resize-none h-20"
        />
        <button
          onClick={handleCreate}
          disabled={!newContent.trim()}
          className="flex items-center gap-1 bg-accent text-white text-[10px] font-bold px-4 py-1.5 rounded-lg uppercase disabled:opacity-50"
        >
          <Save className="w-3 h-3" /> Save
        </button>
      </div>

      {/* Entries */}
      {journal.map(entry => (
        <div key={entry.id} className="bg-surface rounded-xl p-3 border border-border">
          <div className="flex items-center justify-between mb-2">
            <span className={clsx(
              'text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded border',
              entry.entry_type === 'premarket' && 'text-sky-400 bg-sky-500/10 border-sky-500/20',
              entry.entry_type === 'intraday' && 'text-amber-400 bg-amber-500/10 border-amber-500/20',
              entry.entry_type === 'postmarket' && 'text-violet-400 bg-violet-500/10 border-violet-500/20',
              entry.entry_type === 'review' && 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
            )}>
              {entry.entry_type}
            </span>
            <span className="text-[8px] text-content-muted font-mono">
              {new Date(entry.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <p className="text-[10px] text-content leading-relaxed whitespace-pre-wrap">{entry.content}</p>
        </div>
      ))}
    </div>
  )
}
