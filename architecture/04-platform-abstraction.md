# Platform Abstraction Layer

> **Revision 2** — Updated after inspecting actual C# code and confirming no Pine Script exists.
> Key corrections:
> - Current NinjaTrader C# (923 LOC) is 100% standalone order flow — zero overlap with Python strategies
> - This is a **full rewrite**, not a port. The old C# gets discarded entirely
> - No Pine Script exists in any repo — TradingView client is net-new development
> - Annotation schema now based on actual deterministic snapshot structure from rockit-framework

## The Problem (Confirmed by Code Inspection)

The current NinjaTrader C# code (`DualOrderFlow_Evaluation.cs` and `DualOrderFlow_Funded.cs`) implements its own:
- Delta/CVD computation from raw order flow
- Imbalance percentile calculation
- Volume spike detection (1.5x multiplier)
- Signal generation (delta threshold 85, imbalance threshold 85)
- Position management (31 contracts, $1,500 daily loss limit)
- ATR-based exits (0.4x stop, 2.0x reward)

**None of this overlaps with the Python strategies.** The Python side has 16 strategies based on Dalton day types (TrendBull, PDay, BDay, etc.), while the C# does pure order flow signal detection. They are completely different trading approaches that happen to live in the same project.

This means:
- Backtest results (Python) literally cannot match NinjaTrader results (C#) — they're different strategies
- Any Python strategy tweak has no effect on NinjaTrader — and vice versa
- The C# code is essentially a separate trading system

---

## The Solution: API-Driven Thin Clients

Replace all client-side strategy logic with thin clients that consume the Rockit API. The API provides two things:

1. **Annotations** — What to draw on the chart (zones, levels, signals)
2. **Trade Setups** — What trades to take (entry, stop, targets, trail rules)

The client's job: draw the annotations, fill the trades, manage execution locally.

```
┌──────────────┐     HTTP/WebSocket      ┌──────────────────┐
│  rockit-serve │◀─────────────────────── │ NinjaTrader      │
│  (Python API) │ ─────────────────────▶  │ (thin C# client) │
│               │   Annotations +         │                  │
│  Computes:    │   Trade Setups          │ Draws zones/lines│
│  - 38 det.   │                         │ Fills entries     │
│    modules    │                         │ Manages stops     │
│  - LLM infer │                         │ Trails targets    │
│  - Signals   │                         └──────────────────┘
│  - Setups    │
│               │     HTTP/WebSocket      ┌──────────────────┐
│               │◀─────────────────────── │ TradingView      │
│               │ ─────────────────────▶  │ (Pine Script)    │
│               │   Annotations           │ Draws zones/lines│
│               │                         └──────────────────┘
│               │
│               │     HTTP                 ┌──────────────────┐
│               │◀─────────────────────── │ Dashboard UI     │
│               │ ─────────────────────▶  │ (React)          │
│               │   Annotations +         │ Renders charts   │
│               │   Trade Setups +        │ Shows analysis   │
│               │   LLM Commentary        │                  │
└──────────────┘                          └──────────────────┘
```

---

## Annotation Schema

Based on the actual deterministic snapshot structure from rockit-framework (38 modules), the annotation protocol encodes what the snapshot produces into drawing instructions:

```json
{
  "instrument": "NQ",
  "session": "2025-01-02",
  "timestamp": "2025-01-02T11:45:00-05:00",
  "deterministic_summary": {
    "day_type": "P-Day (Bullish)",
    "bias": "Long",
    "confidence": 72,
    "trend_strength": "Moderate",
    "cri_status": "GREEN_LIGHT",
    "matched_playbook": "IB_Extension_Long"
  },
  "annotations": [
    {
      "type": "zone",
      "id": "ib-range",
      "label": "IB Range",
      "category": "initial_balance",
      "top": 22275.0,
      "bottom": 22257.25,
      "time_start": "2025-01-02T09:30:00-05:00",
      "time_end": "2025-01-02T10:30:00-05:00",
      "style": { "color": "#4A90D9", "opacity": 0.15, "border": "solid" }
    },
    {
      "type": "level",
      "id": "poc-current",
      "label": "POC",
      "category": "volume_profile",
      "price": 22723.0,
      "time_start": "2025-01-02T09:30:00-05:00",
      "style": { "color": "#E74C3C", "width": 2, "dash": "solid" }
    },
    {
      "type": "level",
      "id": "vah-current",
      "label": "VAH",
      "category": "volume_profile",
      "price": 22750.0,
      "time_start": "2025-01-02T09:30:00-05:00",
      "style": { "color": "#3498DB", "width": 1, "dash": "dashed" }
    },
    {
      "type": "level",
      "id": "val-current",
      "label": "VAL",
      "category": "volume_profile",
      "price": 22700.0,
      "time_start": "2025-01-02T09:30:00-05:00",
      "style": { "color": "#3498DB", "width": 1, "dash": "dashed" }
    },
    {
      "type": "level",
      "id": "dpoc-current",
      "label": "DPOC",
      "category": "dpoc_migration",
      "price": 22262.5,
      "time_start": "2025-01-02T09:30:00-05:00",
      "style": { "color": "#F39C12", "width": 2, "dash": "solid" },
      "metadata": { "migration_direction": "down", "steps_since_1030": 137.75 }
    },
    {
      "type": "zone",
      "id": "fvg-1h-001",
      "label": "1H FVG (Bull)",
      "category": "fvg",
      "top": 22702.75,
      "bottom": 22638.0,
      "time_start": "2025-01-02T09:00:00-05:00",
      "style": { "color": "#2ECC71", "opacity": 0.2, "border": "dashed" }
    },
    {
      "type": "level",
      "id": "asia-high",
      "label": "Asia High",
      "category": "premarket",
      "price": 22310.75,
      "time_start": "2025-01-02T09:30:00-05:00",
      "style": { "color": "#9B59B6", "width": 1, "dash": "dotted" }
    },
    {
      "type": "level",
      "id": "london-high",
      "label": "London High",
      "category": "premarket",
      "price": 22336.5,
      "time_start": "2025-01-02T09:30:00-05:00",
      "style": { "color": "#9B59B6", "width": 1, "dash": "dotted" }
    },
    {
      "type": "signal",
      "id": "entry-long-001",
      "label": "Long Entry (TrendBull)",
      "category": "trade_setup",
      "price": 22265.0,
      "time": "2025-01-02T11:45:00-05:00",
      "direction": "long",
      "metadata": {
        "strategy": "TrendBull",
        "confidence": 0.82,
        "day_type": "P-Day",
        "playbook": "IB_Extension_Long"
      }
    }
  ],
  "trade_setups": [
    {
      "id": "setup-001",
      "strategy": "TrendBull",
      "direction": "long",
      "status": "active",
      "entry": {
        "price": 22265.0,
        "type": "limit",
        "time": "2025-01-02T11:45:00-05:00"
      },
      "stop": {
        "price": 22250.0,
        "type": "stop_market"
      },
      "targets": [
        { "price": 22290.0, "quantity_pct": 50, "label": "T1" },
        { "price": 22320.0, "quantity_pct": 50, "label": "T2" }
      ],
      "trail": {
        "type": "step",
        "trigger_price": 22290.0,
        "trail_offset": 5.0
      },
      "source": "deterministic",
      "llm_commentary": "Bullish P-Day developing. DPOC migrating up, IB accepted above prior VAH..."
    }
  ]
}
```

**Key: the API provides instructions.** Entry price, stop price, targets, trail rules. The client fills the order, sets the stop, manages the trail. The API does not manage the position — the client does.

---

## API Endpoints

```
GET  /api/v1/annotations/{instrument}?session={date}
     → All annotations for a session (historical or current)

WSS  /api/v1/stream/{instrument}
     → Real-time annotation stream (push on each new computation)

GET  /api/v1/setups/{instrument}?status=active
     → Active trade setups with entry/stop/target/trail

GET  /api/v1/setups/{instrument}/{setup_id}
     → Specific setup detail

GET  /api/v1/analysis/{instrument}?session={date}
     → Full deterministic + LLM analysis for a session

POST /api/v1/ingest
     → Receive new market data (from rockit-ingest)
```

---

## NinjaTrader Client (Full Rewrite — ~300 lines total)

The current `DualOrderFlow_Evaluation.cs` (397 LOC) and `DualOrderFlow_Funded.cs` (526 LOC) are **discarded entirely**. They implement standalone order flow logic that has nothing to do with the Python strategies.

The new client is two simple files:

### RockitIndicator.cs — Draws annotations from API

```csharp
// packages/rockit-clients/ninjatrader/RockitIndicator.cs
public class RockitIndicator : NinjaTrader.NinjaScript.Indicators.Indicator
{
    [NinjaScriptProperty]
    public string ApiUrl { get; set; } = "https://rockit-api.run.app";

    private HttpClient client;
    private List<Annotation> annotations = new List<Annotation>();
    private DateTime lastRefresh = DateTime.MinValue;

    protected override void OnStateChange()
    {
        if (State == State.SetDefaults)
        {
            Name = "Rockit Signals";
            IsOverlay = true;
        }
        else if (State == State.Configure)
        {
            client = new HttpClient();
            client.DefaultRequestHeaders.Add("Authorization", "Bearer " + ApiKey);
        }
    }

    protected override void OnBarUpdate()
    {
        if (CurrentBar < 1) return;

        // Refresh annotations every N seconds
        if ((DateTime.Now - lastRefresh).TotalSeconds > RefreshIntervalSeconds)
        {
            RefreshAnnotations();
            lastRefresh = DateTime.Now;
        }

        foreach (var ann in annotations)
        {
            switch (ann.Type)
            {
                case "zone":
                    Draw.Rectangle(this, ann.Id, false,
                        ann.TimeStart, ann.Top,
                        ann.TimeEnd ?? DateTime.Now, ann.Bottom,
                        Brushes.Transparent,
                        ColorFromHex(ann.Style.Color),
                        (int)(ann.Style.Opacity * 100));
                    break;

                case "level":
                    Draw.HorizontalLine(this, ann.Id,
                        ann.Price,
                        ColorFromHex(ann.Style.Color),
                        DashStyleFromString(ann.Style.Dash),
                        ann.Style.Width);
                    break;

                case "signal":
                    if (ann.Direction == "long")
                        Draw.ArrowUp(this, ann.Id, false, ann.Time, ann.Price, Brushes.Green);
                    else
                        Draw.ArrowDown(this, ann.Id, false, ann.Time, ann.Price, Brushes.Red);
                    break;
            }
        }
    }
}
```

### RockitStrategy.cs — Fills trades from API setups

```csharp
// packages/rockit-clients/ninjatrader/RockitStrategy.cs
public class RockitStrategy : NinjaTrader.NinjaScript.Strategies.Strategy
{
    [NinjaScriptProperty]
    public string ApiUrl { get; set; } = "https://rockit-api.run.app";

    private HttpClient client;

    protected override void OnBarUpdate()
    {
        // Only act when flat — API manages setup lifecycle
        if (Position.MarketPosition == MarketPosition.Flat)
        {
            var setup = GetActiveSetup();
            if (setup != null && setup.Status == "active")
            {
                ExecuteSetup(setup);
            }
        }
    }

    private void ExecuteSetup(TradeSetup setup)
    {
        // Place entry at the price API specifies
        if (setup.Direction == "long")
        {
            EnterLongLimit(0, true, setup.Contracts, setup.Entry.Price, "RockitEntry");
        }
        else
        {
            EnterShortLimit(0, true, setup.Contracts, setup.Entry.Price, "RockitEntry");
        }

        // Set stop at the price API specifies
        SetStopLoss("RockitEntry", CalculationMode.Price, setup.Stop.Price, false);

        // Set targets at the prices API specifies
        foreach (var target in setup.Targets)
        {
            SetProfitTarget("RockitEntry", CalculationMode.Price, target.Price);
        }
    }

    // Client manages trail locally using rules from API
    protected override void OnPositionUpdate(...)
    {
        if (currentSetup?.Trail != null)
        {
            // Trail stop per API instructions
            if (Close[0] >= currentSetup.Trail.TriggerPrice)
            {
                SetStopLoss("RockitEntry", CalculationMode.Price,
                    Close[0] - currentSetup.Trail.TrailOffset, false);
            }
        }
    }
}
```

**Key insight:** ~300 lines total replaces 923 lines. No strategy logic, no order flow computation, no signal detection. The client draws what the API says and fills trades at the prices the API provides. The client handles local execution mechanics (order placement, stop management, trailing) because those need to be responsive to local market data.

---

## TradingView Client (New — Nothing Exists Today)

No Pine Script exists in any current repo. This is built from scratch:

```pine
// packages/rockit-clients/tradingview/rockit_indicator.pine
//@version=5
indicator("Rockit Signals", overlay=true, max_lines_count=500, max_boxes_count=500)

// TradingView cannot make HTTP calls directly.
// Two integration options:
//
// Option A: Webhook alerts from rockit-serve push to TradingView
//   - Server sends alerts via TradingView webhook API
//   - Pine Script displays alert-driven annotations
//
// Option B: External data bridge
//   - Lightweight bridge service fetches from rockit-serve
//   - Publishes to TradingView data feed
//   - Pine Script reads from custom data feed
//
// For MVP, use Option A (webhook-driven alerts displayed as labels/lines)
```

TradingView's API limitations mean this client will be simpler than NinjaTrader — primarily visual annotations via webhook alerts, without trade execution capability.

---

## What Gets Eliminated

| Before (Actual Code Today) | After |
|---------------------------|-------|
| 923 LOC of standalone C# order flow strategy logic | ~300 LOC thin API client |
| C# implements its own delta/CVD/imbalance (zero Python overlap) | All computation in Python API |
| NinjaTrader results have nothing to do with backtest results | Same computation, NinjaTrader just renders + executes |
| No TradingView indicators at all | Thin Pine Script client via webhooks |
| No dashboard (only a spec document) | React dashboard consuming same API |
| Adding a new platform = rewrite strategies | Adding a new platform = write a thin HTTP client |

---

## Latency Considerations

For the annotation/visualization use case, 1-5 second polling is fine.

For trade execution, latency matters more:

| Mode | Latency | Use Case |
|------|---------|----------|
| Polling (GET /setups) | 1-5s | Adequate for most setups (entries aren't time-critical to the millisecond) |
| WebSocket (WSS /stream) | 50-200ms | Better for fast-moving markets |
| Local cache + periodic refresh | <10ms locally, 1-5s stale | Best for NinjaTrader execution |

**Cloud Run cold start risk:** First request after idle can take 1-3 seconds. Mitigate with:
- Minimum instances = 1 (keeps one instance warm)
- Client-side caching of last-known annotations
- Fallback: if API unreachable, NinjaTrader continues with cached annotations (no new trades, existing positions managed locally)

**Important:** The API provides trade *instructions* (entry at price X, stop at Y). The client decides when and how to fill. If the market moves past the entry price, the client can choose not to fill — that's local execution logic, not API logic.
