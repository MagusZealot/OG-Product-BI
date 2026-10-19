# Data Directory

This directory contains source data and local snapshot caches used by the
pipeline. Data files are excluded from Git because of their size (~9.5 GB).

## Source Data

### Transaction exports: `raw/`

Place transaction export CSV files in this directory. The current dataset
contains 27 exports totaling approximately 9.5 GB; individual files are
approximately 300–377 MB.

**Filename pattern:** `YYYY-MM-DD-HH-MM-SS_EXPORT_CSV_XXXXX_XXX_0.csv`

**Expected columns:** `player_id`, `operator_name`, `game_name`, `currency`,
`debit_amount`, `credit_amount`, `winlose`, `formatted_debit_at`,
`device_type`, `bet_id`

### Game probability and house-edge snapshots: `probability/`

Daily snapshots are cached here using the filename pattern
`mnt_game_probability_he_YYYYMMDD.csv`. The `_manifest.json` file records the
scan range and dates for which snapshots were unavailable. Each cached snapshot
is under 100 KB. The pipeline refreshes this cache during step 13.

### Dealer and table pace snapshots

Step 15 fetches the daily dealer and table pace snapshots and caches them in
`round_dealer_time/` and `round_table_time/`, respectively. No manual download
is required. The feed provides distinct dealer and table observations, not
dealer-to-table pairings.

## File Discovery and Processing

Ingestion scripts discover or fetch their inputs per pipeline step (see
[`workspace_map.txt`](workspace_map.txt) section 0 for the full table):

| Pipeline step | Input | Processes |
|---------------|-------|------------|
| 1–5 | `*.csv` in `raw/` | All matching transaction exports |
| 6 | `*EXPORT_CSV*.csv` in `raw/` | Each export independently |
| 7 | `*EXPORT_CSV*.csv` in `raw/` | Five exports selected randomly |
| 8 | First five exports + derived CSVs | First five exports only |
| 13 | `probability/` cache + published feed | All daily snapshots |
| 15 | `round_dealer_time/` + `round_table_time/` | All available snapshots |

**Adding transaction exports:** Place new CSVs in `raw/`; steps 1–6 discover
them on the next pipeline run. Skip guards use modification times, so updated
inputs trigger dependent steps to rerun.

## Pipeline Data Flow

Raw exports → `src/ingest/` scripts → derived CSVs/JSON → `src/dashboard/`
scripts → dashboards in `output/dashboards/`. The master wrapper runs all 16
steps in dependency order with skip guards and writes live progress to
`output/progress/progress.json`.

See [`workspace_map.txt`](workspace_map.txt) for complete script details,
data flow, skip guards, and architecture.

## Run the Pipeline

Run the full pipeline from the repository root:

```bash
py scripts/generate_all_dashboards.py
```

For the complete project data flow and pipeline documentation, see
[`workspace_map.txt`](../workspace_map.txt).
