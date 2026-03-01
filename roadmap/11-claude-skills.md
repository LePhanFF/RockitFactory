# Claude Code Skills & Automation — Roadmap

> **Goal:** Leverage Claude Code skills and hooks to automate development workflows.
> Skills are custom slash commands; hooks are event-triggered automations.

---

## Phase 0: Foundation Skills

- [ ] `/backtest` — Run strategy backtests with baseline comparison
- [ ] `/run-tests` — Run pytest suite with coverage, linting, type checking
- [ ] `/code-review` — Review changes against architecture standards
- [ ] `/generate-snapshot` — Generate deterministic analysis snapshot

## Phase 1: Development Automation

- [ ] Auto-test hook: Run affected tests when Python files in `packages/` are edited
- [ ] Protect architecture hook: Warn when modifying `architecture/` docs without updating cross-references
- [ ] Format hook: Auto-run `ruff format` on saved Python files

## Phase 2: Advanced Skills

- [ ] `/evaluate-model` — Run model evaluation against holdout test set
- [ ] `/compare-models` — Side-by-side comparison of two model versions
- [ ] `/generate-training-data` — Generate JSONL training data from deterministic snapshots
- [ ] `/replay-session` — Replay a historical session through the full agent pipeline

## Phase 3: Autonomous Operations

- [ ] `/meta-review` — Trigger Opus 4.6 meta-review of recent reflections
- [ ] `/update-baseline` — Create new baseline from current backtest results
- [ ] CI integration: Skills callable from GitHub Actions

---

## Skill Development Guidelines

Skills live in `.claude/skills/` as SKILL.md files with YAML frontmatter.

### SKILL.md Format
```yaml
---
name: skill-name
description: What this skill does
allowed-tools: ["Bash", "Read", "Glob", "Grep"]
---

Instructions for Claude Code to follow when this skill is invoked.
```

### Naming Convention
- Skill files: kebab-case (e.g., `run-tests.md`, `code-review.md`)
- Skill names: match filename without extension

### Testing Skills
- Test each skill manually before relying on it
- Skills should be idempotent where possible
- Skills should report clear success/failure status
