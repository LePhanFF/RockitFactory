import clsx from 'clsx'
import { useMarketStore } from '../store'

export function MarketContextPanel() {
  const market = useMarketStore(s => s.market)
  const fmt = (v: number | null) => v != null ? v.toFixed(2) : '--'

  // Sort levels by proximity to current price
  const levels = [
    { label: 'PDH', value: market.pdh, type: 'resistance' },
    { label: 'VAH', value: market.vah, type: 'resistance' },
    { label: 'POC', value: market.poc, type: 'neutral' },
    { label: 'VWAP', value: market.vwap, type: 'neutral' },
    { label: 'Prior POC', value: market.prior_poc, type: 'neutral' },
    { label: 'VAL', value: market.val, type: 'support' },
    { label: 'PDL', value: market.pdl, type: 'support' },
  ].filter(l => l.value != null)
   .map(l => ({ ...l, distance: Math.abs((l.value || 0) - market.current_price) }))
   .sort((a, b) => a.distance - b.distance)

  return (
    <div className="bg-surface/50 border border-border rounded-2xl p-4">
      <div className="grid grid-cols-2 gap-4">
        {/* Structure */}
        <div className="space-y-3">
          <div className="text-[9px] font-bold text-content-muted uppercase tracking-widest">Structure</div>

          {market.ib_high && market.ib_low && (
            <div className="bg-background/50 rounded-xl p-3 space-y-1.5">
              <div className="text-[9px] font-bold text-orange-400 uppercase tracking-wider">Initial Balance</div>
              <Row label="IB High" value={fmt(market.ib_high)} />
              <Row label="IB Low" value={fmt(market.ib_low)} />
              <Row label="Range" value={`${market.ib_range?.toFixed(0) || '--'}pt`}
                className={clsx(
                  market.ib_range && market.ib_range < 100 && 'text-amber-400',
                  market.ib_range && market.ib_range > 200 && 'text-rose-400',
                )} />
            </div>
          )}

          <div className="bg-background/50 rounded-xl p-3 space-y-1.5">
            <div className="text-[9px] font-bold text-violet-400 uppercase tracking-wider">Profile</div>
            <Row label="POC" value={fmt(market.poc)} />
            <Row label="DPOC" value={fmt(market.dpoc)}
              extra={market.dpoc_direction ? `(${market.dpoc_direction})` : undefined} />
            <Row label="VAH" value={fmt(market.vah)} />
            <Row label="VAL" value={fmt(market.val)} />
            {market.tpo_shape && <Row label="TPO Shape" value={market.tpo_shape} />}
          </div>

          <div className="bg-background/50 rounded-xl p-3 space-y-1.5">
            <div className="text-[9px] font-bold text-sky-400 uppercase tracking-wider">Indicators</div>
            <Row label="EMA(20)" value={fmt(market.ema20)} />
            <Row label="EMA(50)" value={fmt(market.ema50)} />
            <Row label="EMA(200)" value={fmt(market.ema200)} />
            <Row label="RSI(14)" value={market.rsi14?.toFixed(1) || '--'}
              className={clsx(
                market.rsi14 && market.rsi14 > 70 && 'text-rose-400',
                market.rsi14 && market.rsi14 < 30 && 'text-emerald-400',
              )} />
            <Row label="ADX(14)" value={market.adx14?.toFixed(1) || '--'}
              className={clsx(market.adx14 && market.adx14 >= 28 && 'text-accent')} />
            <Row label="ATR(14)" value={`${market.atr14?.toFixed(0) || '--'}pt`} />
          </div>
        </div>

        {/* Levels + Order Flow */}
        <div className="space-y-3">
          <div className="text-[9px] font-bold text-content-muted uppercase tracking-widest">
            Key Levels (by proximity)
          </div>

          <div className="bg-background/50 rounded-xl p-3 space-y-1">
            {levels.map(l => (
              <div key={l.label} className="flex items-center justify-between text-[10px]">
                <div className="flex items-center gap-2">
                  <div className={clsx(
                    'w-1.5 h-1.5 rounded-full',
                    l.type === 'resistance' && 'bg-rose-400',
                    l.type === 'support' && 'bg-emerald-400',
                    l.type === 'neutral' && 'bg-accent',
                  )} />
                  <span className="text-content-muted">{l.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-content">{fmt(l.value)}</span>
                  <span className="text-[8px] text-content-muted font-mono">
                    {l.distance.toFixed(0)}pt
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-background/50 rounded-xl p-3 space-y-1.5">
            <div className="text-[9px] font-bold text-amber-400 uppercase tracking-wider">Order Flow</div>
            <Row label="CVD" value={market.cvd?.toFixed(0) || '--'}
              className={clsx(
                market.cvd && market.cvd > 0 && 'text-emerald-400',
                market.cvd && market.cvd < 0 && 'text-rose-400',
              )} />
            <Row label="VWAP" value={fmt(market.vwap)} />
            {market.regime && <Row label="Regime" value={market.regime.replace(/_/g, ' ')} />}
          </div>

          <div className="bg-background/50 rounded-xl p-3 space-y-1.5">
            <div className="text-[9px] font-bold text-cyan-400 uppercase tracking-wider">Context</div>
            <Row label="Day Type" value={market.day_type} />
            <Row label="Confidence" value={`${(market.day_type_confidence * 100).toFixed(0)}%`} />
            <Row label="Bias" value={market.bias}
              className={clsx(
                market.bias === 'LONG' && 'text-emerald-400',
                market.bias === 'SHORT' && 'text-rose-400',
              )} />
          </div>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value, className, extra }: {
  label: string; value: string; className?: string; extra?: string
}) {
  return (
    <div className="flex items-center justify-between text-[10px]">
      <span className="text-content-muted">{label}</span>
      <span className={clsx('font-mono font-bold text-content', className)}>
        {value} {extra && <span className="text-content-muted text-[8px]">{extra}</span>}
      </span>
    </div>
  )
}
