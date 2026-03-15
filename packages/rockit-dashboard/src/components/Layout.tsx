import { useEffect } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useAuthStore } from '../store'
import { api } from '../api/client'
import { Header } from './Header'
import { StrategyBoard } from './StrategyBoard'
import { TradePlan } from './TradePlan'
import { MarketContextPanel } from './MarketContext'
import { TradeIdeasPanel } from './TradeIdeas'
import { PositionTracker } from './PositionTracker'
import { Journal } from './Journal'
import { useUIStore } from '../store'

export function Layout() {
  useWebSocket()

  const setStrategyPrefs = useAuthStore(s => s.setStrategyPrefs)
  const journalOpen = useUIStore(s => s.journalOpen)

  // Load strategy preferences on mount
  useEffect(() => {
    api.getStrategyPrefs()
      .then(prefs => setStrategyPrefs(prefs))
      .catch(() => {}) // Ignore if not yet set up
  }, [setStrategyPrefs])

  return (
    <div className="h-screen flex flex-col bg-background">
      <Header />

      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left column — 60% */}
        <div className="flex-[3] flex flex-col gap-3 p-3 overflow-y-auto custom-scrollbar">
          {/* Strategy Board */}
          <section>
            <SectionLabel>Strategy Board</SectionLabel>
            <StrategyBoard />
          </section>

          {/* Market Context */}
          <section>
            <SectionLabel>Market Context</SectionLabel>
            <MarketContextPanel />
          </section>
        </div>

        {/* Right column — 40% */}
        <div className="flex-[2] flex flex-col gap-3 p-3 pl-0 overflow-y-auto custom-scrollbar border-l border-border">
          {/* Trade Plan */}
          <section>
            <SectionLabel>Trade Plan</SectionLabel>
            <TradePlan />
          </section>

          {/* Trade Ideas */}
          <section>
            <SectionLabel>Trade Ideas</SectionLabel>
            <TradeIdeasPanel />
          </section>

          {/* Positions */}
          <section>
            <SectionLabel>Positions & P&L</SectionLabel>
            <PositionTracker />
          </section>
        </div>

        {/* Journal slide-out */}
        {journalOpen && (
          <div className="w-[420px] border-l border-border bg-surface overflow-y-auto custom-scrollbar animate-fade-in">
            <Journal />
          </div>
        )}
      </div>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[9px] font-black uppercase tracking-[0.25em] text-content-muted mb-2 px-1">
      {children}
    </h2>
  )
}
