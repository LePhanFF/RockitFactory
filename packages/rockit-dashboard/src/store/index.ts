import { create } from 'zustand'
import type { LiveSnapshot, MarketContext, StrategyState, TradeIdea, StrategyPref, User, RiskRules } from '../types'

// ─── Auth Store ──────────────────────────────────────────────────────────────

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  strategyPrefs: StrategyPref[]
  login: (token: string, user: User) => void
  logout: () => void
  setStrategyPrefs: (prefs: StrategyPref[]) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('rockit_token'),
  isAuthenticated: !!localStorage.getItem('rockit_token'),
  strategyPrefs: [],
  login: (token, user) => {
    localStorage.setItem('rockit_token', token)
    set({ token, user, isAuthenticated: true })
  },
  logout: () => {
    localStorage.removeItem('rockit_token')
    set({ token: null, user: null, isAuthenticated: false, strategyPrefs: [] })
  },
  setStrategyPrefs: (prefs) => set({ strategyPrefs: prefs }),
}))

// ─── Market Store ────────────────────────────────────────────────────────────

interface MarketState {
  connected: boolean
  market: MarketContext
  strategies: Record<string, StrategyState>
  tradeIdeas: TradeIdea[]
  positions: any[]
  sessionPnl: number
  riskRules: RiskRules
  setConnected: (v: boolean) => void
  applySnapshot: (snap: LiveSnapshot) => void
}

const defaultMarket: MarketContext = {
  instrument: 'NQ', current_price: 0, current_time: '--:--', phase: 0,
  day_type: 'UNKNOWN', day_type_confidence: 0, bias: 'NEUTRAL',
  ib_high: null, ib_low: null, ib_range: null, vwap: null,
  poc: null, vah: null, val: null, pdh: null, pdl: null, prior_poc: null,
  ema20: null, ema50: null, ema200: null, rsi14: null, atr14: null, adx14: null,
  cvd: null, tpo_shape: null, dpoc: null, dpoc_direction: null, regime: null,
}

const defaultRiskRules: RiskRules = {
  max_positions: 2, current_positions: 0,
  daily_loss_limit: -4000, current_daily_pnl: 0,
  consecutive_losses: 0, max_consecutive_losses: 2,
}

export const useMarketStore = create<MarketState>((set) => ({
  connected: false,
  market: defaultMarket,
  strategies: {},
  tradeIdeas: [],
  positions: [],
  sessionPnl: 0,
  riskRules: defaultRiskRules,
  setConnected: (v) => set({ connected: v }),
  applySnapshot: (snap) => set({
    market: snap.market,
    strategies: Object.fromEntries(snap.strategies.map(s => [s.strategy_id, s])),
    tradeIdeas: snap.trade_ideas,
    positions: snap.positions,
    sessionPnl: snap.session_pnl,
    riskRules: snap.risk_rules as RiskRules,
  }),
}))

// ─── UI Store ────────────────────────────────────────────────────────────────

type Theme = 'dark' | 'light' | 'metal'

interface UIState {
  theme: Theme
  journalOpen: boolean
  selectedStrategy: string | null
  cycleTheme: () => void
  toggleJournal: () => void
  selectStrategy: (id: string | null) => void
}

const THEMES: Theme[] = ['dark', 'light', 'metal']

export const useUIStore = create<UIState>((set, get) => ({
  theme: (localStorage.getItem('rockit_theme') as Theme) || 'dark',
  journalOpen: false,
  selectedStrategy: null,
  cycleTheme: () => {
    const next = THEMES[(THEMES.indexOf(get().theme) + 1) % THEMES.length]
    localStorage.setItem('rockit_theme', next)
    document.documentElement.setAttribute('data-theme', next === 'dark' ? '' : next)
    set({ theme: next })
  },
  toggleJournal: () => set(s => ({ journalOpen: !s.journalOpen })),
  selectStrategy: (id) => set({ selectedStrategy: id }),
}))
