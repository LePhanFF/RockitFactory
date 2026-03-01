# Phase 6: Retire Old Repos — Detailed Roadmap

> **Goal:** Archive original repositories. RockitFactory becomes the single source of truth.
> **Duration:** Week 16+
> **Depends on:** All phases complete + 2 weeks parallel operation

---

## Tasks

### 6.1 Parallel operation
- [ ] Run new system alongside old for 2+ weeks
- [ ] Compare outputs daily: backtest results, deterministic snapshots, training data

### 6.2 Feature parity confirmation
- [ ] Backtest results match original
- [ ] Deterministic snapshots match original
- [ ] Training pipeline produces equivalent models
- [ ] API serves correct data
- [ ] NinjaTrader and dashboard work correctly

### 6.3 Archive repos
- [ ] Archive BookMapOrderFlowStudies (set to read-only on GitHub)
- [ ] Archive rockit-framework (read-only)
- [ ] Archive RockitAPI (absorbed into rockit-serve)
- [ ] Archive RockitDataFeed (data migrated to GCS)
- [ ] RockitUI — nothing to archive (was only a spec)

### 6.4 Documentation
- [ ] Update all READMEs
- [ ] Archive links point to RockitFactory
- [ ] Onboarding doc for new contributors

---

## Definition of Done

- [ ] All original repos archived (read-only)
- [ ] RockitFactory is the only active repo
- [ ] No developer needs to touch the old repos for any workflow
