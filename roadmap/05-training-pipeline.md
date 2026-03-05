# Phase 4: Training Pipeline — Detailed Roadmap

> **Goal:** LLM tape reader trained on deterministic snapshots. Analyst/tape reader, NOT trader.
> **Duration:** Week 8-11 (overlaps with Phase 3)
> **Depends on:** Phase 1 (deterministic modules for snapshot generation)
> **Blocks:** Phase 5a (agent system needs trained model for Advocate/Skeptic/Orchestrator)

---

## Current State (2026-03-04)

**COMPLETED:**
- [x] System prompt: `configs/prompts/rockit_system_prompt.md` (shared training + inference)
- [x] Output schema: `configs/prompts/output_schema.json` (13 fields, V1)
- [x] Snapshot generator: `scripts/generate_deterministic_snapshots.py` (78 per day RTH)
- [x] Training pair generator: `/generate-training-pairs` skill (3 parallel agents)
- [x] Training pipeline: `scripts/training_pipeline.py` (prepare/generate/batch/merge/status)
- [x] ChatML converter: `scripts/convert_to_chatml.py` + `/convert-chatml` skill
- [x] LoRA training script: `scripts/train_lora.py` (Unsloth, BF16, r=64)
- [x] Architecture doc: `architecture/15-llm-training-pipeline.md` (Rev 2)
- [x] 164 training pairs generated (4 days: Feb 26-27, Mar 02-03)
- [x] ChatML validated: avg ~10K tokens, max ~11.4K (under 16K limit)

**IN PROGRESS:**
- [ ] V2 output schema: rename `strategy_assessment` → `tape_observations`, add `invalidation`, add `two_hour_trader`
- [ ] Deterministic engine additions: IB touch counter, C-period close, DPOC retention %, VA entry depth %
- [ ] Brainstorm: `brainstorm/07-augmenting-training-tape-reading-intelligence.md` (2100+ lines)

**BLOCKED:**
- Training pair regeneration with V2 schema (needs V2 schema + deterministic additions first)
- Full 266-session training data (needs V2 schema, ~20,000+ pairs)

---

## Tasks

### 4.1 V2 Schema & System Prompt Update
- [ ] Rename `strategy_assessment` → `tape_observations` (8 strategies: OR Rev, OR Accept, 80P, 20P, B-Day/Edge Fade, Trend Following, Mean Reversion, Two Hour Trader)
- [ ] Add `invalidation` field (condition/what_it_means/action)
- [ ] Rename `step_6_setups` → `step_6_tape_read` in thinking
- [ ] Add study-derived stats to system prompt (B-Day first-touch 82% WR, etc.)
- [ ] Add Two Hour Trader options overlay observation
- [ ] Update time-phase rules for precision first-hour framework

### 4.2 Deterministic Engine Additions (V1 priorities)
- [ ] IB edge touch counter (touch_count_ibh, touch_count_ibl, first_touch_time)
- [ ] C-period close classification (above_ibh / below_ibl / inside_ib)
- [ ] Session open type (Acceptance / Judas / Rotation / Both)
- [ ] VA entry depth % (for 80P quality: losers enter at 23%, winners at 45%)
- [ ] DPOC retention % (exhaustion detector: <40% = skip trade)

### 4.3 Training Data Generation (V2 schema)
- [ ] Regenerate 164 existing pairs with V2 schema
- [ ] Scale to 266 sessions × 78 snapshots = ~20,000+ pairs
- [ ] Use `training_pipeline.py` prepare + generate modes (parallelizable across cloud instances)
- [ ] Validate all pairs against V2 JSON schema

### 4.4 ChatML Conversion & LoRA Training
- [ ] Convert V2 pairs to ChatML with `/convert-chatml`
- [ ] Target: Qwen3.5-35B-A3B, BF16 LoRA r=64, Unsloth on DGX Spark 128GB
- [ ] 75% with `<think>` reasoning, 25% empty `<think></think>` (Qwen3 guidance)
- [ ] `adamw_torch_fused` optimizer, Flash Attention 2, gradient checkpointing

### 4.5 Holdout Evaluation Set
- [ ] Create 50-session holdout set (never trained on)
- [ ] Balanced: 10 Trend, 10 P-Day, 10 B-Day, 10 Neutral, 10 edge cases
- [ ] Automated evaluation: schema compliance, time-phase correctness, study stat accuracy, tape quality

### 4.6 Model Registry & Evaluation Gates
- [ ] Set up GCS bucket or local storage for model versions
- [ ] New model must match or beat baseline on ALL metrics
- [ ] Auto-deploy if all gates pass, with 5-day canary period

### 4.7 End-to-End Pipeline Test
- [ ] `scripts/training_pipeline.py prepare --days 90 --with-snapshots`
- [ ] `scripts/training_pipeline.py generate --chunk chunk_*.jsonl` (parallel)
- [ ] `scripts/training_pipeline.py merge` → `scripts/convert_to_chatml.py --merge`
- [ ] `scripts/train_lora.py --data data/training_chatml/train.jsonl`
- [ ] Verify: schema change → regen pairs → convert → train → eval

---

## Key Architecture Decisions

- **LLM = analyst/tape reader, NOT trader** — strategy signals trigger trades
- **Same LoRA, three personas** — Advocate/Skeptic/Orchestrator via system prompts, not separate models
- **Caution over conviction** — LLM never chases, recommends retracement entry, warns about balance day traps
- **First hour precision** — 9:30-10:30 is the money-making window, LLM must be fast and cite exact prices
- **8 tape observations** — OR Rev, OR Accept, 80P, 20P, B-Day/Edge Fade, Trend Following, Mean Reversion, Two Hour Trader

## Definition of Done

- [ ] V2 schema and system prompt updated with all study findings
- [ ] 500+ training pairs generated with V2 schema (minimum for LoRA)
- [ ] LoRA training completes on DGX Spark (BF16 r=64)
- [ ] Evaluation gates block a deliberately degraded model
- [ ] Tape reading quality matches study report level (exact prices, evidence chains, invalidation)
