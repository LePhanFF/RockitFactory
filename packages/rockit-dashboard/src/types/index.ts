/* ─── API response types — mirrors rockit-serve schemas.py ─── */

export interface User {
  id: number
  username: string
  email: string
  display_name: string
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface StrategyPref {
  id: number
  strategy_id: string
  is_active: boolean
  mastery_level: 'learning' | 'practicing' | 'mastered'
  notes: string
}

export interface StrategyState {
  strategy_id: string
  state: 'INACTIVE' | 'WATCHING' | 'ARMED' | 'FIRED' | 'DONE' | 'BLOCKED'
  direction: string | null
  entry_price: number | null
  stop_price: number | null
  target_price: number | null
  current_pnl: number | null
  trailing_stop: number | null
  block_reason: string | null
  condition_progress: Record<string, unknown>
  historical_wr: number | null
  historical_pf: number | null
}

export interface MarketContext {
  instrument: string
  current_price: number
  current_time: string
  phase: number
  day_type: string
  day_type_confidence: number
  bias: string
  ib_high: number | null
  ib_low: number | null
  ib_range: number | null
  vwap: number | null
  poc: number | null
  vah: number | null
  val: number | null
  pdh: number | null
  pdl: number | null
  prior_poc: number | null
  ema20: number | null
  ema50: number | null
  ema200: number | null
  rsi14: number | null
  atr14: number | null
  adx14: number | null
  cvd: number | null
  tpo_shape: string | null
  dpoc: number | null
  dpoc_direction: string | null
  regime: string | null
}

export interface EvidenceCard {
  source: string
  direction: string
  strength: number
  signal: string
}

export interface TradeIdea {
  id: string
  strategy_id: string
  confidence: 'high' | 'medium' | 'low'
  direction: string
  entry_price: number
  stop_price: number
  target_price: number
  r_reward: number
  rationale: string
  evidence_for: EvidenceCard[]
  evidence_against: EvidenceCard[]
  agent_verdict: string | null
  agent_reasoning: string | null
  status: 'developing' | 'ready' | 'fired' | 'expired'
}

export interface LiveSnapshot {
  timestamp: string
  market: MarketContext
  strategies: StrategyState[]
  trade_ideas: TradeIdea[]
  positions: Position[]
  session_pnl: number
  risk_rules: RiskRules
}

export interface Position {
  strategy_id: string
  direction: string
  entry_price: number
  stop_price: number
  target_price: number
  current_pnl: number
  trailing_stop: number | null
  status: 'OPEN' | 'CLOSED'
}

export interface RiskRules {
  max_positions: number
  current_positions: number
  daily_loss_limit: number
  current_daily_pnl: number
  consecutive_losses: number
  max_consecutive_losses: number
}

export interface UserTrade {
  id: number
  session_date: string
  strategy_id: string
  instrument: string
  direction: string
  entry_price: number
  stop_price: number
  target_price: number
  exit_price: number | null
  result: 'OPEN' | 'WIN' | 'LOSS' | 'SCRATCH'
  pnl: number
  r_multiple: number
  notes: string
  entry_time: string
  exit_time: string
}

export interface JournalEntry {
  id: number
  session_date: string
  entry_type: 'premarket' | 'intraday' | 'postmarket' | 'review'
  content: string
  created_at: string
  updated_at: string
}

// ─── Strategy display metadata ───

export const STRATEGY_DISPLAY: Record<string, { name: string; short: string; color: string }> = {
  or_reversal:      { name: 'OR Reversal',      short: 'OR Rev',   color: 'emerald' },
  or_acceptance:    { name: 'OR Acceptance',     short: 'OR Acc',   color: 'emerald' },
  '80p_rule':       { name: '80% Rule',          short: '80P',      color: 'violet' },
  '20p_ib_extension': { name: '20% IB Extension', short: '20P',    color: 'violet' },
  trend_bull:       { name: 'Trend Bull',        short: 'T Bull',   color: 'sky' },
  trend_bear:       { name: 'Trend Bear',        short: 'T Bear',   color: 'rose' },
  bday:             { name: 'B-Day',             short: 'B-Day',    color: 'amber' },
  ib_edge_fade:     { name: 'IB Edge Fade',      short: 'IB Edge',  color: 'amber' },
  pdh_pdl_reaction: { name: 'PDH/PDL React',     short: 'PDH/PDL',  color: 'cyan' },
  va_edge_fade:     { name: 'VA Edge Fade',      short: 'VA Edge',  color: 'cyan' },
  ndog_gap_fill:    { name: 'NDOG Gap Fill',     short: 'NDOG',     color: 'orange' },
  nwog_gap_fill:    { name: 'NWOG Gap Fill',     short: 'NWOG',     color: 'orange' },
}

export const PHASE_NAMES = ['Pre-Market', 'First Hour', 'Mid-Session', 'Afternoon'] as const
