# Coding Standards

This file documents conventions that cannot be automatically enforced by linting tools
(ruff). Mechanical violations (import ordering, line length, unused imports, etc.) are
caught by `ruff` via `pyproject.toml` and should not be documented here — they are
enforced by the guardrail, not by memory.

## General Conventions

- **Python version**: 3.12+ (use `py` launcher, not `python` which is a Microsoft Store stub)
- **Formatting**: ruff `--select E,F,W,N,I` is the authoritative checker; manual reformatting
  is only needed for judgement-call cases ruff cannot express
- **Imports**: Always use absolute imports from `src/` package; relative imports are discouraged
  outside of test fixtures. ruff `E402` catches module-level imports not at top of file

## File-Level Conventions

- **Shebang**: `#!/usr/bin/env python3` at line 1
- **Docstring**: Triple-quoted docstring at top of every script, describing purpose, params, output
- **Encoding**: UTF-8 (default on Python 3); `encoding="utf-8-sig"` for CSV readers to handle BOM
- **Error handling**: All scripts should gracefully handle missing files/csv parsing errors;
  never crash hard on bad input data

## Data Conventions

- **Currency conversion**: All monetary amounts must be converted to PHP using `currency_converter.convert_to_php()`
  with date-relative rates. Do not hardcode exchange rates.
- **Country mapping**: Use `currency_converter.get_country()` or `CURRENCY_COUNTRY` mapping for
  country attribution. Do not hardcode country names from currency codes.
- **Progress tracking**: Use `workspace.update_progress(stage, message, progress, details)` from
  `src/workspace.py`; never write `progress.json` directly.

## Dashboard Conventions

- **Skip guards**: Every pipeline step should have a skip-guard checking output existence and
  mtime relative to dependencies (see `scripts/generate_all_dashboards.py`).
- **Dashboard data JSON**: The master payload (`dashboard_data.json`) must contain:
  - `metadata` with `generated_at`, `total_bets`, `total_operators`, `total_chasers`, `total_whales`
  - `whales` with `top_20`, `country_distribution`, `total_debit`, `total_bets`
  - `chasers` with `total_count`, `total_debit`, `total_winlose`, `net_losers`, `net_winners`,
    `net_loser_pct`, `net_winner_pct`, `risk_tiers`, `loss_streak_distribution`
  - `traffic` with `hourly_curve`, `country_density`, `heatmap`
  - `operators` with `top_50`, `country_dominance`, `roi_comparison`

## Whale/Chaser Archetypes

- **Whales**: Top 20 players by total PHP debit (>= 80% cumulative debit threshold)
- **Chaser flags**: Set when `spike_multiplier >= 3x` after consecutive losses
- **A player CAN carry both Whale and Chaser flags**
- **Archetype assignment rule**: Spike Multiplier (max bet escalation after consecutive losses)
  + total wagered volume; Chasers escalate after losses, Whales are top 0.4% by total debit

## Verification Script Conventions

- **No hardcoded values**: Verification scripts in `src/verify/` must not hardcode totals or
  counts; derive them from the data files they inspect.
- **JSON validation**: Any embedded JSON payloads must be validated for brace/paren balance.
- **False positive awareness**: Note in comments when a check reports a false positive (e.g.,
  "double braces" on nested ECharts object literals — safe to ignore when net balance is 0).

## Notes for Agents

- This file is read during **review**, not **implementation**. Implementation agents should
  rely on ruff for mechanical checks and the `code-review` skill for standards enforcement.
- When in doubt, default to the ruff configuration in `pyproject.toml`; it is the
  authoritative source for Python code quality in this repo.
- Any new convention that ruff cannot express should be added to this file, and if it
  is mechanical (import order, line length, &c.), it should instead be added to
  `pyproject.toml` `[tool.ruff]` config.