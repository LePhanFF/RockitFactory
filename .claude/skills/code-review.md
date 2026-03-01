---
name: code-review
description: Review code changes for architecture compliance
allowed-tools: ["Bash", "Read", "Glob", "Grep"]
---

Review staged or PR changes against RockitFactory architecture standards.

## Usage
- `/code-review` — Review staged changes
- `/code-review branch-name` — Review changes on a branch vs main

## Checklist
Review against these standards (from technical-design/01-conventions.md):
1. **Python Standards**: Python 3.11+, type hints on public interfaces, Google-style docstrings
2. **Naming**: snake_case modules, PascalCase classes, UPPER_SNAKE constants
3. **Imports**: stdlib -> third-party -> local (rockit packages)
4. **Error Handling**: Specific exceptions, strategies return None on error (never catch silently)
5. **Metrics**: Public modules support optional MetricsCollector
6. **Architecture**:
   - Strategies emit signals, NEVER manage positions
   - rockit-core has ZERO dependencies on other rockit packages
   - Entry/Stop/Target models are composable and registered
   - Deterministic modules follow `get_X(df, time, **kwargs) -> dict` pattern
7. **Tests**: Unit tests exist for new code, coverage targets met
8. **No over-engineering**: No unnecessary abstractions, no docstrings on migrated unchanged code

## Steps
1. Get the diff: `git diff --staged` or `git diff main...{branch}`
2. Read each changed file
3. Check against the checklist above
4. Report findings organized by: Critical / Warning / Suggestion
