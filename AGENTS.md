# Agent Instructions

## MANDATORY: Read workspace map first

Before doing ANY work in this repository, you MUST read `workspace_map.txt` at the repository root. This is non-negotiable and must happen at the start of every coding agent session.

The workspace map contains critical information:

- **Data safety constraints**: 17M row dataset in `data/raw/` (27 CSV files, ~9.5GB). NEVER open, read, scan, or process these files or any file larger than 100KB. Large files are listed by name only - inspect them only via Python scripts that print small summaries.
- **Project structure**: Complete folder layout, scripts, and outputs
- **Pipeline**: 14-step master pipeline (`scripts/generate_all_dashboards.py`), dependencies, and skip guards
- **Architecture**: All-players dossier system, chunked loading, dashboard structure
- **Recent changes**: Important fixes and updates

- **Navigation pointers**:
  - `integration/standardize-src-architecture` branch — created from `master`; merges spec changes from `spec/standardize-src-architecture`
  - Ticket T1-T18 correspond to files in `src/workspace.py`, `src/ingest/io.py`, `src/ingest/player_index.py`, and refactored ingest/dashboard scripts
  - Implementer worktrees are created per-ticket under `t<N>-*` directories; clean up with `git worktree remove --force <path>`
  - Lint check runs via `scripts/generate_all_dashboards.py` before pipeline steps; ruff config at `pyproject.toml`

**Do not proceed with planning, searching, or making changes until you have read and understood `workspace_map.txt`.**

## Agent skills

### Issue tracker

Issues live in GitHub (repo: MagusZealot/August-2026). Use the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.