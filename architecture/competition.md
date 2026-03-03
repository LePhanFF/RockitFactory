# Competitive Landscape: Agentic AI Trading Systems (2024-2026)

> Research compiled March 2026. Covers commercial platforms, open-source frameworks, academic papers, and lessons learned.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Academic Research — Multi-Agent Trading Frameworks](#academic-research)
3. [Open-Source Frameworks](#open-source-frameworks)
4. [Commercial Platforms and Startups](#commercial-platforms-and-startups)
5. [Institutional Players](#institutional-players)
6. [Architecture Patterns Across the Field](#architecture-patterns)
7. [Benchmarks and Real-World Performance](#benchmarks-and-real-world-performance)
8. [Failures, Vulnerabilities, and Lessons Learned](#failures-and-lessons-learned)
9. [Model Selection Across the Landscape](#model-selection)
10. [How Rockit Compares](#how-rockit-compares)

---

## Executive Summary

The agentic AI trading space has exploded since late 2024. The dominant pattern is **multi-agent LLM systems** where specialized agents (analysts, researchers, traders, risk managers) debate and collaborate to produce trading decisions. Y Combinator's Spring 2026 RFS explicitly calls for "AI-native hedge funds" as a priority investment area, signaling that the industry considers this a greenfield opportunity.

Key findings relevant to Rockit:

- **Nobody is doing what Rockit does.** No system we found combines deterministic Market Profile / Auction Market Theory analysis with LLM-powered agent debate. The entire field operates on standard technical indicators (RSI, MACD, Bollinger Bands), fundamental data (earnings, filings), and news sentiment. Rockit's 38-module deterministic layer analyzing TPO profiles, value areas, DPOC migration, and day-type classification is architecturally unique.
- **The bull/bear debate pattern is now standard.** TradingAgents (the most cited framework) uses bullish vs. bearish researchers with a facilitator — very close to Rockit's Advocate/Skeptic/Orchestrator design.
- **Self-reflection is emerging but immature.** TradingGroup (2025) and OpenAI's Self-Evolving Agents cookbook show the direction, but no production system has demonstrated sustained self-improvement in live markets.
- **Pure LLM trading consistently underperforms.** Every benchmark (StockBench, AI-Trader, Agent Trading Arena) shows most LLM agents fail to beat buy-and-hold. The winners combine deterministic signals with LLM reasoning — exactly Rockit's three-tier architecture.
- **Security is an unsolved problem.** TradeTrap (2025) demonstrated that small perturbations to any component (data, prompts, memory, state) can cascade into catastrophic portfolio failures.

---

## Academic Research

### TradingAgents (Tauric Research, Dec 2024 — ICML 2025)

**Paper:** [arXiv 2412.20138](https://arxiv.org/abs/2412.20138) | **Code:** [GitHub](https://github.com/TauricResearch/TradingAgents)

The most influential multi-agent trading paper of this period. Simulates a realistic trading firm with seven agent roles.

**Architecture:**
- **Analyst Team** (concurrent): Fundamental Analyst, Sentiment Analyst, News Analyst, Technical Analyst
- **Researcher Team** (debate): Bullish Researcher vs. Bearish Researcher + Facilitator Agent
- **Trader Agent**: Integrates analyst reports and debate conclusions
- **Risk Management Team**: Risk-seeking, Neutral, and Risk-conservative agents + Facilitator
- **Fund Manager**: Final approval and execution

**Key design decisions:**
- **Hybrid communication**: Structured documents for analyst reports (avoiding "telephone effect" information degradation), natural language for debates
- **Dual-model strategy**: Deep-thinking models (o1-preview) for analysis, quick-thinking models (gpt-4o-mini) for data retrieval and summarization
- **Multi-round debate**: Facilitator determines number of rounds, reviews history, selects prevailing perspective
- **Multi-source data**: Stock prices, news (Bloomberg, Yahoo, FinnHub), Reddit/Twitter sentiment, insider transactions, financial statements, 60 technical indicators

**Results (Jan-Mar 2024, AAPL/GOOGL/AMZN):**
- 23-27% cumulative returns, 5.6-8.2 Sharpe ratios, <2.1% max drawdown
- Outperformed all rule-based baselines by 6%+ in returns and 2+ Sharpe points

**Limitations:**
- Only 3 stocks tested over 3 months — very limited scope
- Backtesting only, no live deployment
- Data gaps (missing Reddit data during test period)
- Baselines were simple rule-based strategies, not ML approaches
- v0.2.0 (Feb 2026) added multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x)

**Relevance to Rockit:** Direct architectural parallel to Advocate/Skeptic/Orchestrator. However, TradingAgents uses no deterministic analysis layer — everything flows through LLMs, making it far more expensive and slower than Rockit's Tier 0 deterministic approach.

---

### TradingGroup (ACM ICAIF, Nov 2025)

**Paper:** [arXiv 2508.17565](https://arxiv.org/abs/2508.17565)

Introduces self-reflection and automated data synthesis for continuous improvement.

**Architecture — Five specialized agents:**
1. **News-Sentiment Agent**: Retrieval + re-ranking + scoring of financial news
2. **Financial-Report Agent**: Hybrid RAG over quarterly/annual reports
3. **Stock-Forecasting Agent**: Technical indicators (RSI, ATR, MAs) + upstream agent outputs
4. **Style-Preference Agent**: Determines trading style (aggressive/balanced/conservative) based on account performance
5. **Trading-Decision Agent**: Final buy/hold/sell synthesis

**Self-Reflection Mechanism:**
- Extracts recent successful and failed prediction cases
- Summarizes patterns and root causes
- Injects conclusions into LLM context for future decisions
- Trading-Decision Agent reviews past 20 days' decisions with actual outcomes
- Ablation studies confirmed self-reflection is a critical performance driver

**Data-Synthesis Pipeline:**
- Collects agent inputs, outputs, account states, and chain-of-thought trajectories
- Assigns reward labels (directional accuracy for forecasting, returns vs. benchmark for decisions)
- High-quality samples support supervised fine-tuning
- **Qwen3-Trader-8B-PEFT** (LoRA fine-tuned on synthetic data) surpassed GPT-4o-mini on 2 of 5 stocks

**Dynamic Risk Management:**
- 10-day historical volatility with style-dependent multipliers
- Adaptive take-profit and stop-loss thresholds
- Continuous monitoring with forced sells at loss thresholds

**Models used:** GPT-4o-mini (inference), Qwen3-8B with LoRA (fine-tuning, 0.53% trainable params), DeepSeek-R1 and Qwen3 (training data generation)

**Results (TSLA/NFLX/AMZN/MSFT/COIN, Oct 2022-Apr 2023):**
- 40.46% cumulative return on AMZN (best)
- Fine-tuned 8B model beat GPT-4o-mini on TSLA (28.67% vs 25.66%) and NFLX (29.11% vs 20.46%)
- Lowest max drawdown and favorable volatility across datasets

**Relevance to Rockit:** Most architecturally similar to Rockit's self-learning loop. The data-synthesis pipeline (collecting trajectories, labeling with outcomes, fine-tuning) is essentially what Rockit plans with daily Qwen3.5 reflection + multi-day Opus review. The LoRA fine-tuning of Qwen on synthetic data validates Rockit's "one model, one LoRA" approach.

---

### QuantAgent (Y-Research, Stony Brook, Sep 2025)

**Paper:** [arXiv 2509.09995](https://arxiv.org/abs/2509.09995) | **Code:** [GitHub](https://github.com/Y-Research-SBU/QuantAgent)

Price-driven multi-agent system built on LangGraph. Notable for operating purely on price data — no news, no sentiment.

**Architecture — Four agents on LangGraph:**
1. **IndicatorAgent**: RSI, MACD, ROC, Stochastic, Williams %R from OHLC
2. **PatternAgent**: Chart pattern recognition (double bottoms, triangles) from candlestick visualizations
3. **TrendAgent**: Support/resistance detection via slope analysis
4. **RiskAgent + DecisionAgent**: Risk boundaries (0.05% stop-loss) + final LONG/SHORT decisions requiring confirmed alignment across all three upstream agents

**Key innovation — Price-only approach:**
- Justification: "Prices adjust rapidly to public information" (efficient market hypothesis)
- Eliminates dependency on news/sentiment data feeds
- Reduces latency and data pipeline complexity
- Tested on 9 instruments including **Bitcoin and Nasdaq futures**

**Results:**
- 26.5% accuracy improvement over random baseline on NQ futures (4-hour)
- Highest close-to-close returns across 8 tested assets
- Consistent outperformance on 1-hour timeframes

**Relevance to Rockit:** Closest to Rockit's futures focus. Uses LangGraph (same as Rockit's planned framework). However, QuantAgent uses basic technical indicators while Rockit uses Market Profile — a far more sophisticated analysis framework. QuantAgent's "alignment across all agents" requirement is similar to Rockit's consensus-building approach.

---

### FinMem (AAAI/ICLR Workshop, 2023-2024)

**Paper:** [arXiv 2311.13743](https://arxiv.org/abs/2311.13743) | **Code:** [GitHub](https://github.com/pipiku915/FinMem-LLM-StockTrading)

Introduced layered memory architecture for trading agents.

**Architecture — Three modules:**
1. **Profiling Module**: Customizes agent characteristics (risk tolerance, trading style)
2. **Memory Module**: Working memory (short-term processing) + stratified long-term memory ranked by novelty, relevance, and importance
3. **Decision Module**: Converts memory-derived insights into investment actions

**Key insight:** Memory architecture aligned with human cognitive structure provides interpretability and real-time tuning. Adjustable "cognitive span" retains critical information beyond human perceptual limits.

**Relevance to Rockit:** Validates Rockit's DuckDB-based structured retrieval approach (Historian agent). FinMem's layered memory is functionally similar to Rockit's plan for DuckDB queries providing historical context — structured retrieval over vector RAG.

---

### Expert Investment Teams (Feb 2026)

**Paper:** [arXiv 2602.23330](https://arxiv.org/abs/2602.23330)

Very recent paper arguing that **fine-grained task decomposition** is the critical driver of multi-agent trading performance.

**Key finding:** Explicitly decomposing investment analysis into fine-grained tasks significantly improves risk-adjusted returns vs. coarse-grained designs. Alignment between analytical outputs and downstream decision preferences is the critical performance driver.

**Tested on:** Japanese stock data with strict leakage-controlled backtesting.

**Relevance to Rockit:** Validates Rockit's 38-module deterministic decomposition. Each module (session_context, profile_analysis, delta_analysis, etc.) performs a fine-grained analytical task — exactly what this paper argues produces better results.

---

### Agent Trading Arena (EMNLP 2025)

**Paper:** [arXiv 2502.17967](https://arxiv.org/abs/2502.17967)

Studies LLM numerical understanding limitations in trading.

**Key findings:**
- LLMs fixate on absolute values, overlook percentage changes, overemphasize recent entries
- Chart-based visualizations dramatically outperform text-only: GPT-4o returns of 47.69% (charts+text) vs 33.65% (text-only) — a 42% improvement
- Reflection module boosted returns by 41.7% (from 35.76% to 47.69%)
- Traditional backtesting cannot replicate real market dynamics where agent actions influence prices

**Relevance to Rockit:** Argues strongly for Rockit's approach of keeping numerical analysis in deterministic Python (Tier 0) rather than feeding raw numbers to LLMs. The LLM layer should receive pre-processed insights, not raw price data.

---

### FinAgent (KDD 2024)

**Paper:** [NTU Singapore](https://personal.ntu.edu.sg/boan/papers/KDD24_FinAgent.pdf)

Multimodal foundation agent for financial trading. Processes numerical, textual, and visual market data.

**Relevance to Rockit:** Demonstrates the value of multimodal input processing, though Rockit's deterministic pre-processing achieves the same goal more efficiently (sub-10ms vs. LLM inference latency).

---

### Hybrid Bayesian Network Architecture (Dec 2025)

**Paper:** [arXiv 2512.01123](https://arxiv.org/html/2512.01123)

Uses LLMs to construct Bayesian Networks, then inference is fully deterministic.

**Key insight:** "Separation of model construction from inference guarantees deterministic outputs — identical conditions consistently yield the same decisions, eliminating stochastic variability common in direct LLM applications."

**Validated on:** 8,919 options wheel strategy trades from 2007-2025 with strict out-of-sample testing.

**Relevance to Rockit:** Strongest validation of Rockit's core architecture principle — deterministic analysis (Tier 0) handles the heavy lifting, LLMs provide context and reasoning (Tier 1/2). This paper proves that eliminating LLM stochasticity from the decision path improves reliability.

---

## Open-Source Frameworks

### TradingAgents (TauricResearch)

**Repository:** [GitHub](https://github.com/TauricResearch/TradingAgents) | 8.5k+ stars

Built on LangGraph. Most mature open-source multi-agent trading framework. See academic section above for architecture details. v0.2.0 (Feb 2026) supports multiple LLM providers.

---

### AgenticTrading (Open-Finance-Lab / SecureFinAI)

**Repository:** [GitHub](https://github.com/Open-Finance-Lab/AgenticTrading) | **Paper:** [arXiv 2512.02227](https://arxiv.org/abs/2512.02227)

Protocol-oriented multi-agent architecture from the FinRL ecosystem.

**Key innovations:**
- First application of **MCP (Model Context Protocol)** and **A2A (Agent-to-Agent) protocols** to quantitative finance
- **Neo4j-based contextual memory** for long-term strategy learning
- **DAG-based strategy orchestration** via dynamic composition of trading workflows
- LLM-driven alpha discovery through automated factor mining
- Auditable decision chains for interpretability

**Agent mapping:** Planner, Orchestrator, Alpha Agents, Risk Agents, Portfolio Agents, Backtest Agents, Execution Agents, Audit Agents, Memory Agent

**Results:**
- Stock trading (hourly, Apr-Dec 2024): 20.42% return, 2.63 Sharpe, -3.59% max DD (vs S&P 500 at 15.97%)
- BTC trading (minute data, Jul-Aug 2025): 8.39% return, 0.38 Sharpe, -2.80% max DD (vs BTC +3.80%)

**Relevance to Rockit:** The MCP/A2A protocol approach is more enterprise-oriented than Rockit needs. However, the Neo4j memory agent validates Rockit's structured retrieval approach (DuckDB). The DAG-based orchestration is analogous to Rockit's LangGraph graph design.

---

### AI Hedge Fund (virattt)

**Repository:** [GitHub](https://github.com/virattt/ai-hedge-fund) | 20k+ stars

Most popular open-source AI hedge fund simulator. Uses "persona" agents modeled after famous investors.

**Architecture:**
- **Strategy Agents**: Warren Buffett (intrinsic value), Charlie Munger (moat quality), Michael Burry (contrarian), Mohnish Pabrai (cloning), Peter Lynch (growth at reasonable price), Phil Fisher (qualitative growth)
- **Analysis Agents**: Valuation, Sentiment, Fundamentals, Technicals
- **Management**: Risk Manager, Portfolio Manager

**Key design:** Multiple agents with conflicting investment philosophies debate the same data and reach consensus. Educational/research only — not for live trading.

**Relevance to Rockit:** The "persona" approach (each agent embodies a different investment philosophy) is an alternative to Rockit's role-based approach (Advocate/Skeptic). Rockit's design is more focused — debate between bull and bear views on the same strategy, vs. debate between entirely different investment philosophies.

---

### AutoHedge (The Swarm Corporation)

**Repository:** [GitHub](https://github.com/The-Swarm-Corporation/AutoHedge) | **PyPI:** [autohedge](https://pypi.org/project/autohedge/)

Swarm intelligence approach with four agents.

**Architecture:**
- **Director Agent**: Macro theses and strategic direction
- **Quant Agent**: Technical and statistical analysis
- **Risk Manager Agent**: Position sizing and risk parameters
- **Execution Agent**: Entry/exit orders

**Key features:** Continuous analysis, structured outputs, risk-first architecture. Currently supports autonomous trading on Solana (crypto). Claims 12-18% returns, <4% max DD, 60-65% win rate (backtested).

**Relevance to Rockit:** Simpler than Rockit's architecture. No debate mechanism, no self-reflection. The Director/Quant/Risk/Execution decomposition is a common pattern but less sophisticated than Rockit's deterministic + agent hybrid.

---

### AITradingCrew (CrewAI-based)

**Repository:** [GitHub](https://github.com/philippe-ostiguy/AITradingCrew)

Multi-agent trading analysis using CrewAI framework.

**Agent roles:**
- News Summarizer Agent
- Sentiment Summarizer Agent (StockTwits)
- Technical Indicator Agent (20+ indicators)
- TimeGPT Analyst Agent (ML forecasts)
- Fundamental Analysis Agent
- Day Trader Advisor Agent (synthesis)

**Relevance to Rockit:** Uses CrewAI instead of LangGraph. Demonstrates that the multi-agent trading pattern is framework-agnostic. Rockit chose LangGraph for its lower-level control and graph-based state management — a deliberate architectural advantage for complex workflows.

---

### TradingAgents IntraDay (fork)

**Repository:** [GitHub](https://github.com/random-alex/TradingAgentsIntraDay)

Fork of TradingAgents specifically adapted for intraday trading. Specialized agents collaboratively evaluate intraday market conditions.

**Relevance to Rockit:** Directly relevant — Rockit also targets intraday futures trading. However, this fork appears to be a thin adaptation, not a ground-up intraday design like Rockit's session-based analysis.

---

### FinRL (AI4Finance Foundation)

**Repository:** [GitHub](https://github.com/AI4Finance-Foundation/FinRL) | 14k+ stars

Reinforcement learning framework for trading. Not LLM-based, but important context.

**2025 Updates:**
- **FinRL-DeepSeek**: Integrates RL with DeepSeek LLMs for risk assessment signals from financial news
- **FinRL-AlphaSeek**: Ensemble RL agents with Alpha101 features for crypto trading
- Annual contest (FinRL Contest 2025) driving community innovation

**Relevance to Rockit:** FinRL represents the "pre-LLM" generation of AI trading. Rockit's approach is architecturally distinct — deterministic analysis + LLM reasoning rather than learned reward functions. However, FinRL's ensemble approach (combining multiple RL agents to reduce individual failures) parallels Rockit's multi-agent consensus pattern.

---

## Commercial Platforms and Startups

### GPTrader

**Website:** [gptrader.app](https://gptrader.app/)

All-in-one AI trading platform. Natural language strategy generation, backtesting, and deployment of autonomous trading bots.

**Models:** GPT-4, DeepSeek | **Markets:** Crypto, stocks, forex | **Claims:** 88% returns using agentic AI (marketing, unverified)

---

### Composer

**Website:** [composer.trade](https://www.composer.trade/)

AI-native, no-code investing platform. $200M+ daily trading volume.

**Key feature:** Proprietary trading language that enables LLMs to build, deploy, and backtest strategies in under 60 seconds. Supports stocks, crypto, and options.

---

### Tickeron

**Website:** [tickeron.com](https://tickeron.com/bot-trading/)

Established AI trading bot platform with pattern recognition and automated execution.

---

### AlgosOne

**Website:** [algosone.ai](https://algosone.ai/ai-trading/)

AI trading and investment platform with autonomous decision-making capabilities.

---

### NexusTrade

**Website:** [nexustrade.io](https://nexustrade.io/)

Tested every major LLM for algorithmic trading. Concluded there is "one clear winner" (based on their benchmarking, the top model varied by task type).

---

## Institutional Players

### Bridgewater Associates — AIA Labs

Bridgewater's Artificial Investment Associate Labs, led by Co-CIO Greg Jensen and Chief Scientist Jasjeet Sekhon, is the most significant institutional effort in agentic AI trading.

**Key details:**
- Goal: Replicate Ray Dalio's macro process end-to-end by machine
- Technology: Combines LLMs, ML data models, and reasoning tools for causal market understanding
- AIA's technology is the **primary decision-maker** in Bridgewater's newest strategy
- Engineers describe it as "millions of 80th-percentile associates working in parallel"
- Now managing a $2B+ fund run primarily by machine learning
- Ray Dalio himself has stepped back from the board (sold remaining stake 2025)

**Relevance to Rockit:** Validates the agent-based approach at institutional scale. However, Bridgewater has hundreds of engineers and decades of data — the architecture isn't published.

---

### Y Combinator — Spring 2026 RFS: AI-Native Hedge Funds

YC's Spring 2026 Request for Startups explicitly calls for AI-native hedge funds as a priority category.

**YC's vision:**
- "The next Renaissance, Bridgewater, and D.E. Shaw's are going to be built on AI"
- Swarms of agents replacing human traders: fundamental analysis, macro, event-driven, stat arb, sentiment, risk anomaly detection
- Existing large funds are slow to adapt due to compliance friction, legacy workflows, cultural inertia
- Founder insight from YC-backed Charlie Holtz (ex-Point72 quant researcher): institutional inertia is real

**Relevance to Rockit:** Strong market validation. YC considers this a greenfield opportunity precisely because incumbents are slow. Rockit's architecture (deterministic + agentic + self-learning) aligns with YC's vision but adds domain specificity (Market Profile / AMT) that generic platforms lack.

---

## Architecture Patterns

### Pattern 1: Multi-Agent Role Decomposition

**Used by:** TradingAgents, TradingGroup, AgenticTrading, AI Hedge Fund, AutoHedge, AITradingCrew, QuantAgent

Every system decomposes trading into specialized agents. Common roles:
- Data gathering / analysis agents (concurrent)
- Debate / research agents (sequential, multi-round)
- Decision / trader agents (synthesis)
- Risk management agents (validation / veto)

**Rockit's approach:** Similar decomposition but with a unique twist — the deterministic layer (38 modules) replaces the data-gathering agents. LLM agents receive pre-processed insights rather than raw data.

---

### Pattern 2: Bull/Bear Debate (Advocate/Skeptic)

**Used by:** TradingAgents (explicit), AI Hedge Fund (implicit via conflicting philosophies)

TradingAgents has dedicated Bullish and Bearish Researchers with a Facilitator who determines debate rounds and selects the prevailing view.

**Rockit's approach:** Advocate/Skeptic/Orchestrator pattern is architecturally equivalent but simpler — two opposing views + adjudicator rather than multi-round debate. This is likely more efficient for the intraday timeframes Rockit targets.

---

### Pattern 3: Deterministic + LLM Hybrid

**Used by:** Bayesian Network paper (LLM constructs model, inference is deterministic), QuantAgent (technical indicators + LLM reasoning), intraday paper on SSRN (deterministic signals + LLM news filter)

**Key insight from the field:** Separation of deterministic computation from LLM reasoning produces more reliable, reproducible results. The Bayesian Network paper states: "Identical conditions consistently yield the same decisions, eliminating stochastic variability."

**Rockit's approach:** This is Rockit's core architecture — the three-tier model (Tier 0 deterministic, Tier 1 Qwen local, Tier 2 Opus API). Rockit is the most aggressive implementation of this pattern, with 80% of work handled deterministically in sub-10ms. No other system we found has this ratio.

---

### Pattern 4: Self-Reflection and Continuous Improvement

**Used by:** TradingGroup (self-reflection + data synthesis), OpenAI Self-Evolving Agents cookbook, Agent Trading Arena (reflection module)

TradingGroup's approach:
1. Extract recent successful and failed cases
2. Summarize patterns and root causes
3. Inject conclusions into future prompts
4. Generate training data from trajectories
5. Fine-tune with LoRA

**Rockit's approach:** More structured — daily Qwen3.5 post-market reflection + multi-day Opus meta-review + A/B testing for prompt/parameter changes + auto-rollback on performance regression. Rockit's self-learning loop is more comprehensive than any published system.

---

### Pattern 5: Dual-Model Strategy (Fast + Deep)

**Used by:** TradingAgents (o1-preview for analysis + gpt-4o-mini for data), TradingGroup (GPT-4o-mini for inference + Qwen3-8B for fine-tuning)

Assigning different model tiers to different task complexities is now standard practice.

**Rockit's approach:** Three-tier model (Tier 0 Python, Tier 1 Qwen3.5 local, Tier 2 Opus API) is more granular than the typical two-tier approach, and uniquely includes a non-LLM deterministic tier.

---

### Pattern 6: Structured Retrieval over Vector RAG

**Used by:** AgenticTrading (Neo4j), FinMem (layered memory with novelty/relevance/importance ranking)

The trend is moving away from pure vector embeddings toward structured storage with explicit retrieval logic.

**Rockit's approach:** DuckDB for structured historical queries (Historian agent). This is simpler and more appropriate for the domain than graph databases — trading data is inherently tabular/temporal, not graph-shaped.

---

## Benchmarks and Real-World Performance

### StockBench (Mar-Jul 2025)

**Paper:** [arXiv 2510.02209](https://arxiv.org/abs/2510.02209) | [Website](https://stockbench.github.io/)

Contamination-free benchmark using recent market data, continuously updated.

**Key findings:**
- **Most LLM agents fail to beat buy-and-hold**
- Top models: Kimi-K2 (1.9% return), Qwen3-235B (2.4% return) — modest but with significantly lower max DD than baseline's -15.2%
- Tested GPT-5, Claude-4, Qwen3, Kimi-K2, GLM-4.5
- Agents receive daily prices, fundamentals, and news; must make sequential buy/sell/hold decisions

### AI-Trader (Dec 2025)

**Paper:** [arXiv 2512.10971](https://arxiv.org/abs/2512.10971) | [Live Bench](https://ai4trade.ai)

First fully-automated, live, data-uncontaminated benchmark across US stocks, A-shares, and crypto.

**Key finding:** "Most agents exhibit poor returns and weak risk management, with risk control capability determining cross-market robustness."

### LLM Agents Do Not Replicate Human Traders (Feb 2025)

**Paper:** [arXiv 2502.15800](https://arxiv.org/html/2502.15800v3)

Markets of 20 identical LLM agents showed fundamentally different behavior from human traders. LLMs demonstrate consistent strategy adherence but lack adaptive market-making behavior.

### Can LLMs Outperform in the Long Run? (May 2025)

**Paper:** [arXiv 2505.07078](https://arxiv.org/html/2505.07078v3)

Long-term evaluation showing mixed results — LLM strategies can work in certain market conditions but struggle with regime changes.

### Aggregate Assessment

The benchmarks paint a sobering picture: **standalone LLM trading agents are not reliably profitable**. The successful systems are those that combine LLMs with deterministic analysis, structured data pipelines, and risk management guardrails — precisely Rockit's architecture.

---

## Failures and Lessons Learned

### TradeTrap: LLM Trading Agent Vulnerabilities (Dec 2025)

**Paper:** [arXiv 2512.02261](https://arxiv.org/abs/2512.02261) | **Code:** [GitHub](https://github.com/Yanlewen/TradeTrap)

Systematic stress-testing of LLM trading agents revealed critical vulnerabilities:

**Four attack surfaces:**
1. **Market Intelligence** — Fake news injection and MCP tool hijacking caused agents to make decisions on corrupted data. High position concentration, increased trading frequency, severe drawdowns.
2. **Strategy Formulation** — Prompt injection inverted directional signals. Adaptive agent's returns collapsed from 7.81% to 0.89%.
3. **Portfolio/Ledger** — Memory poisoning (fabricated transaction records) and state tampering (corrupted position feedback). State tampering caused 61% portfolio loss (-100% annualized return, 91.97% max drawdown).
4. **Trade Execution** — Identified as vulnerable but not deeply explored.

**Critical finding:** "Small, localized perturbations propagate through entire decision pipelines without triggering safeguards." A corrupted state perception alone was sufficient to steer agents into catastrophic failure.

**Implications for Rockit:** Rockit's deterministic layer provides inherent protection against several of these attack vectors. The 38 deterministic modules produce verifiable, reproducible outputs that can serve as ground truth for detecting anomalies in LLM reasoning. However, Rockit should implement explicit state verification and cross-module consistency checking.

---

### Numerical Understanding Failures

**Paper:** [Agent Trading Arena, arXiv 2502.17967](https://arxiv.org/abs/2502.17967)

LLMs systematically fail at numerical reasoning in trading contexts:
- Fixate on absolute values, miss percentage changes
- Overemphasize recent data points, ignore long-horizon patterns
- Chart-based input improves performance by 42% over text-only
- Reflection modules help but do not fully compensate

**Implication for Rockit:** Validates the design decision to keep all numerical analysis in deterministic Python. LLMs should never receive raw price data — they should receive pre-computed insights like "Value Area is rotating higher, DPOC migrated +15 points from prior session."

---

### Overtrading and Loss of Discipline

Multiple sources report LLM agents that:
- Accumulated 83 positions with a 30:1 BUY:SELL ratio (one practitioner's report)
- Failed to close positions for 7 days (stop-loss monitoring failure)
- Overtrade in volatile conditions, generating excessive transaction costs
- Struggle to find balance between adaptation and overfitting

**Implication for Rockit:** Rockit's "strategies emit signals, they do NOT manage positions" principle is a critical guardrail. The deterministic layer controls signal generation; agents provide context, not execution. This separation prevents the overtrading problem.

---

### ESMA Regulatory Warning (March 2025)

The European Securities and Markets Authority warned that AI-powered trading tools "can generate incorrect information based on outdated, incorrect or incomplete information, with accuracy varying significantly."

---

### Operational Failures

Common operational issues reported across practitioners:
- Managing LLM context windows across multi-agent conversations
- Verifying that deployed agents actually work as expected
- Building operational discipline around automated trading
- Preventing recurring failures in data pipelines

---

## Model Selection

| System | Primary Model | Secondary / Fine-tuning | Notes |
|--------|--------------|------------------------|-------|
| TradingAgents | o1-preview, gpt-4o | gpt-4o-mini | Now supports GPT-5.x, Claude 4.x, Gemini 3.x, Grok 4.x |
| TradingGroup | GPT-4o-mini | Qwen3-8B (LoRA) | Fine-tuned 8B model beat GPT-4o-mini on 2/5 stocks |
| QuantAgent | GPT-4o, Claude 3.5 | — | Price-only, no sentiment |
| AI Hedge Fund | GPT-4o, Llama 3 | — | Educational only |
| AutoHedge | GPT-4, Claude | — | Also supports local models |
| GPTrader | GPT-4, DeepSeek | — | Commercial platform |
| FinRL-DeepSeek | DeepSeek (signals) | RL agents (execution) | Hybrid RL+LLM |
| StockBench top | Kimi-K2, Qwen3-235B | — | Benchmark results |
| **Rockit (planned)** | **Qwen3.5 (local)** | **Qwen3.5 + LoRA** | **Opus 4.6 for meta-review only** |

**Trend:** GPT-4o/4o-mini remains the most commonly used model, but open-source models (Qwen, DeepSeek) are closing the gap rapidly. TradingGroup demonstrated that a LoRA-fine-tuned Qwen3-8B can beat GPT-4o-mini — validating Rockit's planned approach.

**Rockit's edge:** Local inference via Ollama/vLLM eliminates API costs and latency for real-time trading. No other system we found runs locally-hosted open-source models for live intraday trading.

---

## How Rockit Compares

### Unique Architectural Advantages

| Feature | Rockit | TradingAgents | TradingGroup | QuantAgent | AgenticTrading |
|---------|--------|---------------|--------------|------------|----------------|
| **Deterministic analysis layer** | 38 modules, <10ms | None | None | Basic indicators | None |
| **Domain framework** | Market Profile / AMT | Generic TA | Generic TA | Basic TA | Generic |
| **Asset class** | Futures (NQ, ES, YM) | Stocks | Stocks | Futures + crypto | Stocks + crypto |
| **Intraday focus** | Yes (session-based) | Daily | Daily | 1h/4h | Hourly/minute |
| **Bull/bear debate** | Advocate/Skeptic | Bull/Bear Researchers | No | No | No |
| **Self-reflection** | Daily + multi-day meta | No | Yes (20-day window) | No | Memory agent |
| **Self-improvement (fine-tuning)** | LoRA on Qwen3.5 | No | LoRA on Qwen3-8B | No | No |
| **Local inference** | Ollama/vLLM | API only | API + fine-tuned | API + Flask | API only |
| **Day type classification** | 7 types (Trend, P, B, Neutral, etc.) | None | None | None | None |
| **Proven backtest** | 548 trades, 51.5% WR, 1.91 PF | 3 stocks, 3 months | 5 stocks, 6 months | 9 instruments | Stocks + BTC |

### Where Rockit Leads

1. **Deterministic-first architecture**: No other system has 80% of analysis handled by deterministic Python modules. This produces faster, cheaper, more reproducible results.
2. **Domain specificity**: Market Profile / Auction Market Theory is a sophisticated framework used by professional futures traders. No competing system uses it.
3. **Intraday futures trading**: The field is overwhelmingly focused on daily stock trading. Rockit targets a higher-frequency, higher-volatility niche.
4. **Local-first deployment**: Running Qwen3.5 locally via Ollama eliminates API costs, reduces latency to sub-second, and enables true real-time trading.
5. **Three-tier model strategy**: The Tier 0 / Tier 1 / Tier 2 separation is more granular and cost-effective than any published system.

### Where Rockit Should Learn from Others

1. **Structured communication protocols**: TradingAgents' hybrid approach (structured documents for reports, natural language for debates) reduces information degradation. Rockit should adopt this for agent-to-agent communication.
2. **Data synthesis pipeline**: TradingGroup's automated pipeline for generating training data from agent trajectories is directly applicable to Rockit's self-learning loop.
3. **State verification**: TradeTrap's findings on state tampering vulnerabilities demand that Rockit implement explicit position verification and cross-module consistency checking.
4. **Visual data for LLM reasoning**: Agent Trading Arena's 42% improvement from chart-based input suggests Rockit should consider generating chart visualizations as input to LLM agents, not just text summaries.
5. **Fine-grained task decomposition**: The Expert Investment Teams paper validates Rockit's approach but suggests explicit documentation of how each module's output aligns with downstream decision preferences.
6. **Benchmark participation**: Rockit should track performance against StockBench/AI-Trader style benchmarks to maintain credibility, even though those benchmarks target different asset classes.

### Gaps in the Field That Rockit Fills

1. **No Market Profile AI systems exist.** The entire competitive landscape uses RSI/MACD/Bollinger Bands. Rockit's Dalton-based analysis (TPO profiles, value areas, DPOC migration, initial balance, day type classification) is architecturally differentiated.
2. **No hybrid deterministic+agent futures trading systems exist.** Everything is either pure RL (FinRL), pure LLM (TradingAgents), or basic indicators + LLM (QuantAgent). Rockit's deep deterministic layer is unique.
3. **No self-learning loop with meta-review exists in production.** TradingGroup's self-reflection is the closest, but it lacks the multi-day meta-review (Opus) and auto-rollback guardrails that Rockit plans.
4. **No system targets session-based futures trading with day type classification.** This is a niche that professional futures traders understand but the AI/ML community has not addressed.

---

## Key Sources

### Academic Papers
- [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138) (ICML 2025)
- [TradingGroup: Multi-Agent Trading with Self-Reflection and Data-Synthesis](https://arxiv.org/abs/2508.17565) (ACM ICAIF 2025)
- [QuantAgent: Price-Driven Multi-Agent LLMs for High-Frequency Trading](https://arxiv.org/abs/2509.09995)
- [FinMem: LLM Trading Agent with Layered Memory](https://arxiv.org/abs/2311.13743) (AAAI/ICLR)
- [Expert Investment Teams: Fine-Grained Trading Tasks](https://arxiv.org/abs/2602.23330) (Feb 2026)
- [Agent Trading Arena: Numerical Understanding in LLM Agents](https://arxiv.org/abs/2502.17967) (EMNLP 2025)
- [TradeTrap: Are LLM Trading Agents Reliable?](https://arxiv.org/abs/2512.02261)
- [StockBench: Can LLM Agents Trade Profitably?](https://arxiv.org/abs/2510.02209)
- [AI-Trader: Benchmarking Autonomous Agents in Real-Time Markets](https://arxiv.org/abs/2512.10971)
- [LLM Agents Do Not Replicate Human Traders](https://arxiv.org/html/2502.15800v3)
- [Hybrid Bayesian Network for Options Trading](https://arxiv.org/html/2512.01123)
- [AgenticTrading: From Algorithmic to Agentic Trading](https://arxiv.org/abs/2512.02227)
- [Intraday Trading with LLM Analysis (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5246516)
- [Integrating LLMs in Financial Investments Survey](https://arxiv.org/html/2507.01990v1)
- [Can LLMs Outperform the Market Long-Term?](https://arxiv.org/html/2505.07078v3)
- [FinAgent: Multimodal Foundation Agent for Trading (KDD 2024)](https://personal.ntu.edu.sg/boan/papers/KDD24_FinAgent.pdf)

### Open-Source Repositories
- [TradingAgents](https://github.com/TauricResearch/TradingAgents) — Multi-agent LLM trading (LangGraph)
- [AgenticTrading](https://github.com/Open-Finance-Lab/AgenticTrading) — Protocol-oriented financial agents
- [AI Hedge Fund](https://github.com/virattt/ai-hedge-fund) — Multi-persona hedge fund simulator
- [AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge) — Swarm intelligence hedge fund
- [QuantAgent](https://github.com/Y-Research-SBU/QuantAgent) — Price-driven LangGraph agents
- [FinMem](https://github.com/pipiku915/FinMem-LLM-StockTrading) — Layered memory trading agent
- [FinRL](https://github.com/AI4Finance-Foundation/FinRL) — Reinforcement learning for trading
- [AITradingCrew](https://github.com/philippe-ostiguy/AITradingCrew) — CrewAI-based trading
- [TradingAgents IntraDay](https://github.com/random-alex/TradingAgentsIntraDay) — Intraday fork
- [TradeTrap](https://github.com/Yanlewen/TradeTrap) — Security evaluation framework

### Commercial and Institutional
- [GPTrader](https://gptrader.app/) — AI trading platform (crypto, stocks, forex)
- [Composer](https://www.composer.trade/) — AI-native no-code investing ($200M+ daily volume)
- [Bridgewater AIA Labs](https://www.bridgewater.com/aia-labs) — Institutional AI trading ($2B+ fund)
- [Y Combinator Spring 2026 RFS: AI-Native Hedge Funds](https://modelence.com/yc-rfs-spring-2026/ai-native-hedge-funds)
- [StockBench Benchmark](https://stockbench.github.io/)
- [AI-Trader Live Bench](https://ai4trade.ai)
- [OpenAI Self-Evolving Agents Cookbook](https://cookbook.openai.com/examples/partners/self_evolving_agents/autonomous_agent_retraining)
