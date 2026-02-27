# Platform Abstraction Layer

## The Problem

Today, strategy logic is duplicated:
- **Python** — research, backtesting, data generation
- **C# (NinjaTrader)** — indicators and execution strategies
- **Results don't match** — two implementations inevitably diverge

Every research tweak requires manual C# translation, which is the single biggest source of churn.

---

## The Solution: Annotation Protocol

Instead of reimplementing strategy logic on each platform, we define a **universal annotation protocol**. The Python server computes everything and returns platform-agnostic drawing instructions. Clients become thin renderers.

```
┌──────────────┐     HTTP/WebSocket      ┌──────────────────┐
│  rockit-serve │◀─────────────────────── │ NinjaTrader      │
│  (Python)     │ ─────────────────────▶  │ (thin C# client) │
│               │   Annotation JSON       │ Draws boxes/lines│
│  Computes:    │                         └──────────────────┘
│  - Signals    │
│  - Zones      │     HTTP/WebSocket      ┌──────────────────┐
│  - Levels     │◀─────────────────────── │ TradingView      │
│  - Setups     │ ─────────────────────▶  │ (Pine Script)    │
│               │   Annotation JSON       │ Draws boxes/lines│
│               │                         └──────────────────┘
│               │
│               │     HTTP                 ┌──────────────────┐
│               │◀─────────────────────── │ Dashboard UI     │
│               │ ─────────────────────▶  │ (React)          │
│               │   Annotation JSON       │ Renders charts   │
└──────────────┘                          └──────────────────┘
```

---

## Annotation Schema

All visual elements (zones, levels, signals) are expressed as annotations:

```json
{
  "instrument": "ES",
  "session": "2024-01-15_RTH",
  "timestamp": "2024-01-15T10:30:00-05:00",
  "annotations": [
    {
      "type": "zone",
      "id": "vah-2024-01-15",
      "label": "VAH",
      "category": "volume_profile",
      "top": 4825.50,
      "bottom": 4823.25,
      "time_start": "2024-01-15T09:30:00-05:00",
      "time_end": null,
      "style": {
        "color": "#4A90D9",
        "opacity": 0.3,
        "border": "solid"
      }
    },
    {
      "type": "level",
      "id": "poc-2024-01-15",
      "label": "POC",
      "category": "volume_profile",
      "price": 4824.00,
      "time_start": "2024-01-15T09:30:00-05:00",
      "time_end": null,
      "style": {
        "color": "#E74C3C",
        "width": 2,
        "dash": "solid"
      }
    },
    {
      "type": "signal",
      "id": "entry-long-001",
      "label": "Long Entry",
      "category": "trade_setup",
      "price": 4823.50,
      "time": "2024-01-15T10:30:00-05:00",
      "direction": "long",
      "metadata": {
        "strategy": "dalton_auction",
        "confidence": 0.82,
        "stop": 4820.00,
        "target_1": 4828.00,
        "target_2": 4832.00,
        "risk_reward": 2.5
      }
    },
    {
      "type": "zone",
      "id": "fvg-001",
      "label": "FVG",
      "category": "fvg",
      "top": 4826.00,
      "bottom": 4824.50,
      "time_start": "2024-01-15T10:15:00-05:00",
      "time_end": "2024-01-15T10:45:00-05:00",
      "style": {
        "color": "#2ECC71",
        "opacity": 0.2,
        "border": "dashed"
      }
    },
    {
      "type": "zone",
      "id": "bpr-001",
      "label": "BPR",
      "category": "bpr",
      "top": 4827.25,
      "bottom": 4825.75,
      "time_start": "2024-01-15T09:45:00-05:00",
      "time_end": null,
      "style": {
        "color": "#9B59B6",
        "opacity": 0.25,
        "border": "solid"
      }
    }
  ],
  "trade_setups": [
    {
      "id": "setup-001",
      "strategy": "dalton_auction",
      "direction": "long",
      "status": "active",
      "entry": {
        "price": 4823.50,
        "type": "limit",
        "time": "2024-01-15T10:30:00-05:00"
      },
      "stop": {
        "price": 4820.00,
        "type": "stop_market"
      },
      "targets": [
        {"price": 4828.00, "quantity_pct": 50, "label": "T1"},
        {"price": 4832.00, "quantity_pct": 50, "label": "T2"}
      ],
      "trail": {
        "type": "step",
        "trigger_price": 4828.00,
        "trail_offset": 2.00
      },
      "source": "deterministic",
      "llm_commentary": "Volume profile shows excess at VAH with..."
    }
  ]
}
```

---

## API Endpoints

```
GET  /api/v1/annotations/{instrument}?session={date}
     → Returns all annotations for a session

WSS  /api/v1/stream/{instrument}
     → WebSocket stream of real-time annotations as they're computed

GET  /api/v1/setups/{instrument}?status=active
     → Returns active trade setups

GET  /api/v1/setups/{instrument}/{setup_id}
     → Returns specific setup with full detail

POST /api/v1/setups/{setup_id}/execute
     → Acknowledge execution (for tracking)
```

---

## NinjaTrader Client (Thin C# Indicator)

The NinjaTrader indicator becomes a simple HTTP client that draws annotations:

```csharp
// packages/rockit-clients/ninjatrader/RockitIndicator.cs
public class RockitIndicator : NinjaTrader.NinjaScript.Indicators.Indicator
{
    private string apiUrl = "https://rockit-api.run.app";
    private HttpClient client = new HttpClient();
    private List<Annotation> annotations = new List<Annotation>();

    protected override void OnBarUpdate()
    {
        if (CurrentBar < 1) return;
        if (IsFirstTickOfBar)
        {
            // Fetch annotations from API
            RefreshAnnotations();
        }

        // Draw all annotations
        foreach (var ann in annotations)
        {
            switch (ann.Type)
            {
                case "zone":
                    DrawZone(ann);
                    break;
                case "level":
                    DrawLevel(ann);
                    break;
                case "signal":
                    DrawSignal(ann);
                    break;
            }
        }
    }

    private void DrawZone(Annotation ann)
    {
        Draw.Rectangle(this, ann.Id, false,
            TimeFromString(ann.TimeStart), ann.Top,
            TimeFromString(ann.TimeEnd ?? DateTime.Now.ToString()),
            ann.Bottom,
            ColorFromHex(ann.Style.Color),
            ColorFromHex(ann.Style.Color),
            (int)(ann.Style.Opacity * 100));
    }

    private void DrawLevel(Annotation ann)
    {
        Draw.HorizontalLine(this, ann.Id,
            ann.Price,
            ColorFromHex(ann.Style.Color),
            DashStyleFromString(ann.Style.Dash),
            ann.Style.Width);
    }

    private void DrawSignal(Annotation ann)
    {
        Draw.ArrowUp(this, ann.Id,
            false,
            TimeFromString(ann.Time),
            ann.Price,
            ColorFromHex(ann.Direction == "long" ? "#2ECC71" : "#E74C3C"));
    }
}
```

```csharp
// packages/rockit-clients/ninjatrader/RockitStrategy.cs
public class RockitStrategy : NinjaTrader.NinjaScript.Strategies.Strategy
{
    private HttpClient client = new HttpClient();

    protected override void OnBarUpdate()
    {
        if (Position.MarketPosition == MarketPosition.Flat)
        {
            // Poll for active trade setups
            var setup = GetActiveSetup();
            if (setup != null)
            {
                ExecuteSetup(setup);
            }
        }
        else
        {
            // Manage open position (trail stops, targets)
            ManagePosition();
        }
    }

    private void ExecuteSetup(TradeSetup setup)
    {
        if (setup.Direction == "long")
        {
            EnterLongLimit(setup.Entry.Price, setup.Label);
            SetStopLoss(CalculationMode.Price, setup.Stop.Price);
            foreach (var target in setup.Targets)
            {
                SetProfitTarget(CalculationMode.Price, target.Price);
            }
        }
        // ... similar for short
    }
}
```

**Key insight:** The C# code is ~200 lines total. It draws boxes, lines, and arrows. It places orders at prices the API tells it. No strategy logic whatsoever. This client rarely needs to change.

---

## TradingView Client (Pine Script)

```pine
// packages/rockit-clients/tradingview/rockit_indicator.pine
//@version=5
indicator("Rockit Signals", overlay=true)

// TradingView webhook integration
// Annotations fetched via TradingView's external data feature
// or displayed via alert-driven webhook updates

// Zone drawing
drawZone(top, bottom, startTime, color, opacity) =>
    box.new(startTime, top, time, bottom,
            border_color=color, bgcolor=color.new(color, 100-opacity))

// Level drawing
drawLevel(price, color, style) =>
    line.new(bar_index[50], price, bar_index, price,
             color=color, style=style, width=2)
```

---

## What This Eliminates

| Before | After |
|--------|-------|
| Maintain strategy logic in Python AND C# | Strategy logic only in Python |
| NinjaTrader performance != backtest | Same computation, NinjaTrader just renders |
| Days to translate new strategy to C# | Zero translation — API delivers results |
| Platform-specific bugs | One implementation, tested once |
| Adding TradingView means new implementation | Add thin Pine Script client (< 100 lines) |

---

## Latency Considerations

For live trading, latency matters. The annotation protocol supports two modes:

1. **Polling** (simple, ~1s latency): Client polls `GET /annotations` every second
2. **WebSocket** (real-time, ~50ms latency): Client connects to `WSS /stream` for push updates

For NinjaTrader execution strategies where milliseconds matter, the WebSocket mode ensures signals arrive with minimal delay. The computation happens server-side and is pushed immediately.

For most indicator/visualization use cases, 1-second polling is more than adequate.
