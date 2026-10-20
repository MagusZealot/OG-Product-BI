# Workspace Map — August 2026 {#workspace-map--august-2026}


> **Project**: Oriental Gaming Title — BI & Risk Intelligence Pipeline  
> **Scope**: Transaction-level analytics for **18.2M wagers** across **50,227 players** (27 exports, ~9.5 GB)  
> **Outputs**: Generated artifacts in `output/` (excluded from Git)  
> **Purpose**: Single source of truth for project structure, scripts, data flow, architecture, and recent changes


---

> ⚠️ **CRITICAL DATA SAFETY WARNING** {#critical-data-safety-warning}
>
> | Constraint | Details |
> |------------|---------|
> | **Dataset size** | ~17M rows (18,275,592 wagers) across 27 raw CSV exports |
> | **File sizes** | Each export: 300–377 MB (~9.5 GB total) in `data\raw\` |
> | **AI restriction** | **NEVER** open, read, scan, or process raw exports or any file > 100 KB |
> | **Large files** | Listed by **NAME ONLY** in this document |
> | **Inspection** | ONLY via Python scripts that print small summaries |
>
> <details>
> <summary><strong>Large files (name-only — DO NOT READ)</strong></summary>
>
> | Path | Description | Size |
> |------|-------------|------|
> | `data\raw\2026-10-0X-XX-XX-XX_EXPORT_CSV_XXXXX_XXX_0.csv` | 27 raw exports | ~9.5 GB total |
> | `legacy output\all_players_dossiers.json` | Full merged dump | ~329 MB |
> | `legacy output\all_players_index.json` | 50,227-player index | ~9.1 MB |
> | `legacy output\dossier_chunks\chunk_0000.js ... chunk_0050.js` | 51 aggregate chunks | ~180 MB |
> | `output\all_players_index_XX.json` | Per-export indexes | Varies |
> | `output\dossier_chunks_XX\*\` | Per-export chunks | Varies |
> | `output\bi_dashboard.html` | Embeds full player index | ~11 MB |
> | `output\chaser_detection.csv` | | ~2.5 MB |
> | `output\dashboard_data.json` | | ~145 KB |
> | `output\individual_dossiers_data.json` | | ~267 KB |
> | `output\player_behavior_data.json` | | ~221 KB |
>
> </details>

---


---

## Table of Contents {#table-of-contents}

- [0. Expected Columns & File Discovery](#0-expected-columns--file-discovery)
- [1. Folder Tree Diagram](#1-folder-tree-diagram)
- [2. PYTHON DATA SCRIPTS & PARAMETERS](#2-python-data-scripts--parameters)
- [3. ALL-PLAYERS DOSSIER SYSTEM (Oriental Gaming Title BI & Risk Intelligence Console) — ARCHITECTURE](#3-all-players-dossier-system-oriental-gaming-title-bi--risk-intelligence-console--architecture)
- [4. DATA FLOW SUMMARY](#4-data-flow-summary)
- [5. CURRENCY STANDARDIZATION](#5-currency-standardization)
- [6. MASTER PIPELINE WRAPPER (scripts/generate_all_dashboards.py)](#6-master-pipeline-wrapper-scriptsgenerate_all_dashboardspy)
- [7. RECENT CHANGES (2026-10-09)](#7-recent-changes-2026-10-09)
- [8. RECENT UPDATE (2026-10-12)](#8-recent-update-2026-10-12)
- [9. RECENT UPDATE (2026-10-13) — PROBABILITY & HE CONSOLE TREND TABS](#9-recent-update-2026-10-13--probability--he-console-trend-tabs)
- [10. RECENT UPDATE (2026-10-13) — PROBABILITY CONSOLE SHOWS ALL GAMES AT ONCE](#10-recent-update-2026-10-13--probability-console-shows-all-games-at-once)
- [11. RECENT UPDATE (2026-10-13) — QUICK NAV + THRESHOLD BREACH ANALYTICS](#11-recent-update-2026-10-13--quick-nav-threshold-breach-analytics)
- [12. RECENT UPDATE (2026-10-13) — STICKY HEADER FILTERS + BREACH CHARTS](#12-recent-update-2026-10-13--sticky-header-filters-breach-charts)
- [13. RECENT UPDATE (2026-10-13) — HE TRENDS SPLIT PER GAME](#13-recent-update-2026-10-13--he-trends-split-per-game)
- [14. RECENT UPDATE (2026-10-13) — UI CLEANUP: CONDITIONAL HE + BREACH CHARTS](#14-recent-update-2026-10-13--ui-cleanup-conditional-he-breach-charts)
- [15. RECENT UPDATE (2026-10-15) — UNIFIED DEALER & TABLE PACE CONSOLE](#15-recent-update-2026-10-15--unified-dealer--table-pace-console)

---

## 0. Expected Columns & File Discovery {#0-expected-columns--file-discovery}


### Transaction Export Columns (`data/raw/*.csv`)

```
player_id, operator_name, game_name, currency, debit_amount, credit_amount,
winlose, formatted_debit_at, device_type, bet_id
```

### Supporting Data Files

| Type | Pattern | Notes |
|------|---------|-------|
| Currency snapshots | `data/probability/mnt_game_probability_he_YYYYMMDD.csv` | + `_manifest.json` |
| Dealer pace snapshots | `data/round_dealer_time/mnt_round_dealer_time_daily_YYYYMMDD.csv` | + `_manifest.json` |
| Table pace snapshots | `data/round_table_time/mnt_round_table_time_daily_YYYYMMDD.csv` | + `_manifest.json` |

### File Discovery per Pipeline Step

| Step(s) | Pattern | Scope |
|---------|---------|-------|
| 1–5 | `*.csv` in `data/raw/` | All matching files |
| 6 | `*EXPORT_CSV*.csv` in `data/raw/` | Each file independently |
| 7 | Random 5 `*EXPORT_CSV*.csv` | 5 sampled exports (`random.sample`) |
| 8 | First 5 exports + derived CSVs | First 5 exports only |
| 13 | `mnt_game_probability_he_YYYYMMDD.csv` | All daily snapshots |
| 15 | `round_dealer_time/` + `round_table_time/` | All available snapshots |

> **Adding exports**: Place new CSVs in `data/raw/`; steps 1–6 discover them on next run. Steps 7–8 remain limited to five exports. Skip guards use file modification times.



---

## 1. Folder Tree Diagram {#1-folder-tree-diagram}


```mermaid
graph TD
    root[August 2026/]
    
    root --> kilo[.kilo/]
    kilo --> kgit[.gitignore]
    kilo --> kjson[kilo.jsonc]
    
    root --> data[data/]
    data --> prob[probability/]
    prob --> prob_csv[mnt_game_probability_he_YYYYMMDD.csv]
    prob --> prob_manifest[_manifest.json]
    data --> dealer[round_dealer_time/]
    dealer --> dealer_csv[mnt_round_dealer_time_daily_YYYYMMDD.csv]
    dealer --> dealer_manifest[_manifest.json]
    data --> table[round_table_time/]
    table --> table_csv[mnt_round_table_time_daily_YYYYMMDD.csv]
    table --> table_manifest[_manifest.json]
    data --> raw[raw/]
    raw --> raw_csvs[27 raw CSV exports<br/>(NAME ONLY — DO NOT READ)]
    
    root --> scripts[scripts/]
    scripts --> gen_all[generate_all_dashboards.py]
    scripts --> gen_chart[generate_chart.js]
    
    root --> src[src/]
    src --> ingest[ingest/]
    ingest --> whale[whale_tracking.py]
    ingest --> ts[time_series_analysis.py]
    ingest --> chase[chaser_detection.py]
    ingest --> op[operator_analysis.py]
    ingest --> heatmap[generate_heatmap_matrix.py]
    ingest --> build_dossiers[build_all_players_dossiers.py]
    ingest --> behavior[generate_player_behavior_data.py]
    ingest --> indiv[build_individual_dossiers.py]
    ingest --> prob_he[probability_he_ingest.py]
    ingest --> currency[currency_converter.py]
    ingest --> currency_cache[currency_cache.json]
    ingest --> inspect[inspect_behavior_metrics.py]
    ingest --> sample_check[sample_behavior_check.py]
    ingest --> sample_extract[sample_profile_extractor.py]
    ingest --> legacy[advanced_analysis.py (LEGACY)]
    
    src --> dashboard[dashboard/]
    dashboard --> prep[prepare_dashboard_data.py]
    dashboard --> gen_bi[generate_dashboard_html.py]
    dashboard --> gen_behavior[generate_behavior_dashboard_html.py]
    dashboard --> gen_prob[generate_probability_dashboard_html.py]
    dashboard --> inject[inject_dossier_tabs.py]
    dashboard --> regen[regenerate_summary_csvs.py]
    dashboard --> sections[sections/]
    sections --> nav[nav_buttons.html]
    sections --> tab_players[tab_players.html]
    sections --> tab_ops[tab_operators.html]
    sections --> slides[slides.html]
    sections --> dossier[dossier.js]
    
    src --> verify[verify/]
    verify --> retention[analyze_retention_transactions.py]
    verify --> js_check[check_js_syntax.py]
    verify --> stats[inspect_all_stats.py]
    verify --> ops[inspect_operators.py]
    verify --> link[link_dashboards.py]
    verify --> update[update_generator.py]
    verify --> verify_bi[verify_dashboard.py]
    verify --> verify_behavior[verify_behavior_dashboard.py]
    
    root --> output[output/]
    output --> dashboards[dashboards/]
    dashboards --> css[dashboard-common.css]
    dashboards --> bi[bi_dashboard.html]
    dashboards --> prob_dash[game_probability_dashboard.html]
    dashboards --> behavior_dash[player_behavior_dashboard.html]
    dashboards --> dealer_dash[round_dealer_table_time_dashboard.html]
    dashboards --> viewer[viewer.html]
    output --> data_out[data/]
    data_out --> idx[all_players_index.json]
    data_out --> idx_per[all_players_index_00.json ... all_players_index_26.json]
    data_out --> dash_data[dashboard_data.json]
    data_out --> prob_data[game_probability_he_data.json]
    data_out --> indiv_data[individual_dossiers_data.json]
    data_out --> behavior_data[player_behavior_data.json]
    data_out --> dealer_data[round_dealer_table_time_data.json]
    output --> dossiers[dossiers/]
    dossiers --> dossiers_per[all_players_dossiers_00.json ... all_players_dossiers_26.json]
    output --> chunks[chunks/]
    chunks --> agg_chunks[dossier_chunks/<br/>chunk_0000.js ... chunk_0050.js]
    chunks --> per_chunks[dossier_chunks_00/ ... dossier_chunks_26/]
    output --> progress[progress/]
    progress --> prog_json[progress.json]
    output --> reports[reports/]
    reports --> chaser_csv[chaser_detection.csv]
    reports --> heatmap_csv[country_hourly_heatmap.csv]
    reports --> hourly_csv[hourly_traffic.csv]
    reports --> op_csv[operator_performance.csv]
    reports --> ts_csv[time_series_analysis.csv]
    reports --> whale_csv[whale_analysis.csv]
    
    root --> docs[docs/]
    docs --> log[analysis_log.txt]
    
    root --> analysis_reports[analysis_reports/ (LEGACY/EMPTY)]
    root --> wmap[workspace_map.md]
```

<details>
<summary><strong>ASCII tree (legacy reference)</strong></summary>

```
August 2026/                                     (workspace root)
│
├── .kilo/                                       (Kilo agent config)
│   ├── .gitignore
│   └── kilo.jsonc
│
├── data/
    │   ├── probability/                                 (cached published game probability snapshots)
    │   │   ├── mnt_game_probability_he_YYYYMMDD.csv
    │   │   └── _manifest.json                           (scan range and unavailable dates)
    │   ├── round_dealer_time/                            (cached daily dealer pace snapshots)
    │   │   ├── mnt_round_dealer_time_daily_YYYYMMDD.csv
    │   │   └── _manifest.json
    │   ├── round_table_time/                             (cached daily table pace snapshots)
    │   │   ├── mnt_round_table_time_daily_YYYYMMDD.csv
    │   │   └── _manifest.json
    │   └── raw/                                         (27 raw CSV exports — NAME ONLY)
    │       ├── 2026-10-06-13-38-11_EXPORT_CSV_45625_808_0.csv
    │       ├── 2026-10-06-14-02-59_EXPORT_CSV_45627_085_0.csv
    │       ├── ... (25 more, 2026-10-06 through 2026-10-07) ...
    │       └── 2026-10-07-17-46-44_EXPORT_CSV_45680_721_0.csv
    │
|-- scripts/ (pipeline entry point and chart helper)
  |   |-- generate_all_dashboards.py (18-step master wrapper; section 6)
  |   `-- generate_chart.js
├── src/                                               (ALL Python data scripts)
│   ├── ingest/                                        (raw-data ingestion & analysis)
│   │   ├── advanced_analysis.py                       (LEGACY monolith: all 4 analyses in one process — superseded by the four split scripts below; kept for reference)
│   │   ├── whale_tracking.py                          (step 1: Pareto top-20% by debit)
│   │   ├── time_series_analysis.py                    (step 2: country peak-hour + hourly traffic)
│   │   ├── chaser_detection.py                        (step 3: problem-gambling flags)
│   │   ├── operator_analysis.py                       (step 4: operator profitability)
│   │   ├── generate_heatmap_matrix.py                 (step 5: country x 24h bet matrix)
│   │   ├── build_all_players_dossiers.py              (step 6: two-pass per-file index + trajectory chunks)
│   │   ├── generate_player_behavior_data.py           (step 7: behavior telemetry)
│   │   ├── build_individual_dossiers.py               (step 8: curated player/operator dossiers)
│   │   ├── probability_he_ingest.py                   (step 13: fetch/backfill daily probability snapshots)
│   │   ├── currency_converter.py                      (shared module: PHP conversion + country map)
│   │   ├── currency_cache.json                        (cached historical FX rates, 30-day TTL)
│   │   ├── inspect_behavior_metrics.py
│   │   ├── sample_behavior_check.py
│   │   └── sample_profile_extractor.py
│   ├── dashboard/                                     (dashboard data prep & rendering)
│   │   ├── prepare_dashboard_data.py                  (step 9: master BI payload)
│   │   ├── generate_dashboard_html.py                 (step 10: MAIN BI console)
│   │   ├── generate_behavior_dashboard_html.py        (step 11: behavior console)
│   │   ├── generate_probability_dashboard_html.py     (step 14: probability & HE console)
│   │   ├── inject_dossier_tabs.py                     (step 12: dossier tabs in behavior console)
│   │   ├── regenerate_summary_csvs.py                 (helper: regenerates whale/chaser CSVs from unified index for consistency)
│   │   └── sections/                                  (reusable HTML/JS components)
│   │       ├── nav_buttons.html                       (nav buttons for tabs 6 & 7)
│   │       ├── tab_players.html                       (Tab 6: ALL-player browser UI)
│   │       ├── tab_operators.html                     (Tab 7: operator dossiers UI)
│   │       ├── slides.html                            (presentation slides 7 & 8)
│   │       └── dossier.js                             (dossier module: index + chunk loader)
│   └── verify/                                        (inspection / verification)
│       ├── analyze_retention_transactions.py
│       ├── check_js_syntax.py
│       ├── inspect_all_stats.py
│       ├── inspect_operators.py
│       ├── link_dashboards.py
│       ├── update_generator.py
│       ├── verify_behavior_dashboard.py
│       └── verify_dashboard.py
│
|-- output/ (generated artifacts)
  |   |-- dashboards/
  |   |   |-- dashboard-common.css   # Shared stylesheet (consistent look across all dashboards)
  |   |   |-- bi_dashboard.html
  |   |   |-- game_probability_dashboard.html
  |   |   |-- player_behavior_dashboard.html
  |   |   |-- round_dealer_table_time_dashboard.html
  |   |   `-- viewer.html
  |   |-- data/
  |   |   |-- all_players_index.json
  |   |   |-- all_players_index_00.json ... all_players_index_26.json
  |   |   |-- dashboard_data.json
  |   |   |-- game_probability_he_data.json
  |   |   |-- individual_dossiers_data.json
  |   |   |-- player_behavior_data.json
  |   |   `-- round_dealer_table_time_data.json
  |   |-- dossiers/
  |   |   `-- all_players_dossiers_00.json ... all_players_dossiers_26.json
  |   |-- chunks/
  |   |   |-- dossier_chunks/                            (aggregate chunks; chunk_0000.js ... chunk_0050.js)
  |   |   |-- dossier_chunks_00/ ... dossier_chunks_26/  (per-export chunks)
  |   |-- progress/
  |   |   `-- progress.json
  |   `-- reports/
  |       |-- chaser_detection.csv
  |       |-- country_hourly_heatmap.csv
  |       |-- hourly_traffic.csv
  |       |-- operator_performance.csv
  |       |-- time_series_analysis.csv
  |       `-- whale_analysis.csv
  |
├── docs/
│   └── analysis_log.txt                               (run log)
│
├── analysis_reports/                                (LEGACY/EMPTY — outputs moved to output/)
└── workspace_map.md                                (this file)
```

</details>


 August 2026/                                     (workspace root)
 │
 ├── .kilo/                                       (Kilo agent config)
 │   ├── .gitignore
 │   └── kilo.jsonc
 │
├── data/
  │   ├── probability/                                 (cached published game probability snapshots)
  │   │   ├── mnt_game_probability_he_YYYYMMDD.csv
  │   │   └── _manifest.json                           (scan range and unavailable dates)
  │   ├── round_dealer_time/                            (cached daily dealer pace snapshots)
  │   │   ├── mnt_round_dealer_time_daily_YYYYMMDD.csv
  │   │   └── _manifest.json
  │   ├── round_table_time/                             (cached daily table pace snapshots)
  │   │   ├── mnt_round_table_time_daily_YYYYMMDD.csv
  │   │   └── _manifest.json
  │   └── raw/                                         (27 raw CSV exports — NAME ONLY)
 │       ├── 2026-10-06-13-38-11_EXPORT_CSV_45625_808_0.csv
 │       ├── 2026-10-06-14-02-59_EXPORT_CSV_45627_085_0.csv
 │       ├── ... (25 more, 2026-10-06 through 2026-10-07) ...
 │       └── 2026-10-07-17-46-44_EXPORT_CSV_45680_721_0.csv
 │
|-- scripts/ (pipeline entry point and chart helper)
  |   |-- generate_all_dashboards.py (18-step master wrapper; section 6)
  |   `-- generate_chart.js
 ├── src/                                               (ALL Python data scripts)
 │   ├── ingest/                                        (raw-data ingestion & analysis)
 │   │   ├── advanced_analysis.py                       (LEGACY monolith: all 4 analyses in one process — superseded by the four split scripts below; kept for reference)
 │   │   ├── whale_tracking.py                          (step 1: Pareto top-20% by debit)
 │   │   ├── time_series_analysis.py                    (step 2: country peak-hour + hourly traffic)
 │   │   ├── chaser_detection.py                        (step 3: problem-gambling flags)
 │   │   ├── operator_analysis.py                       (step 4: operator profitability)
 │   │   ├── generate_heatmap_matrix.py                 (step 5: country x 24h bet matrix)
 │   │   ├── build_all_players_dossiers.py              (step 6: two-pass per-file index + trajectory chunks)
 │   │   ├── generate_player_behavior_data.py           (step 7: behavior telemetry)
 │   │   ├── build_individual_dossiers.py               (step 8: curated player/operator dossiers)
 │   │   ├── probability_he_ingest.py                   (step 13: fetch/backfill daily probability snapshots)
 │   │   ├── currency_converter.py                      (shared module: PHP conversion + country map)
 │   │   ├── currency_cache.json                        (cached historical FX rates, 30-day TTL)
 │   │   ├── inspect_behavior_metrics.py
 │   │   ├── sample_behavior_check.py
 │   │   └── sample_profile_extractor.py
 │   ├── dashboard/                                     (dashboard data prep & rendering)
 │   │   ├── prepare_dashboard_data.py                  (step 9: master BI payload)
 │   │   ├── generate_dashboard_html.py                 (step 10: MAIN BI console)
 │   │   ├── generate_behavior_dashboard_html.py        (step 11: behavior console)
 │   │   ├── generate_probability_dashboard_html.py     (step 14: probability & HE console)
 │   │   ├── inject_dossier_tabs.py                     (step 12: dossier tabs in behavior console)
 │   │   ├── regenerate_summary_csvs.py                 (helper: regenerates whale/chaser CSVs from unified index for consistency)
│   │   ├── generate_dashboard_html.py         # Fixed paths: REPORT_DIR→DATA_DIR for index files,
│   │   │                     # new CHUNK_SRC_DIR for per-file chunks; hardened skip-guard
│   │   │                     # with chunks_complete() check; removed unverified Executive
│   │   │                     # Findings & Strategic Directives matrix (Whale Exposure /
│   │   │                     # Tilt Intervention / Regional Push Windows / B2B Skin Hegemony
│   │   │                     # cards + dead execTilt JS)
 │   │   └── sections/                                  (reusable HTML/JS components)
 │   │       ├── nav_buttons.html                       (nav buttons for tabs 6 & 7)
 │   │       ├── tab_players.html                       (Tab 6: ALL-player browser UI)
 │   │       ├── tab_operators.html                     (Tab 7: operator dossiers UI)
 │   │       ├── slides.html                            (presentation slides 7 & 8)
 │   │       └── dossier.js                             (dossier module: index + chunk loader)
 │   └── verify/                                        (inspection / verification)
 │       ├── analyze_retention_transactions.py
 │       ├── check_js_syntax.py
 │       ├── inspect_all_stats.py
 │       ├── inspect_operators.py
 │       ├── link_dashboards.py
 │       ├── update_generator.py
 │       ├── verify_behavior_dashboard.py
 │       └── verify_dashboard.py
 │
|-- output/ (generated artifacts)
  |   |-- dashboards/
  |   |   |-- dashboard-common.css   # Shared stylesheet (consistent look across all dashboards)
  |   |   |-- bi_dashboard.html
  |   |   |-- game_probability_dashboard.html
  |   |   |-- player_behavior_dashboard.html
  |   |   |-- round_dealer_table_time_dashboard.html
  |   |   `-- viewer.html
  |   |-- data/
  |   |   |-- all_players_index.json
  |   |   |-- all_players_index_00.json ... all_players_index_26.json
  |   |   |-- dashboard_data.json
  |   |   |-- game_probability_he_data.json
  |   |   |-- individual_dossiers_data.json
  |   |   |-- player_behavior_data.json
  |   |   `-- round_dealer_table_time_data.json
  |   |-- dossiers/
  |   |   `-- all_players_dossiers_00.json ... all_players_dossiers_26.json
  |   |-- chunks/
  |   |   |-- dossier_chunks/                            (aggregate chunks; chunk_0000.js ... chunk_0050.js)
  |   |   |-- dossier_chunks_00/ ... dossier_chunks_26/  (per-export chunks)
  |   |-- progress/
  |   |   `-- progress.json
  |   `-- reports/
  |       |-- chaser_detection.csv
  |       |-- country_hourly_heatmap.csv
  |       |-- hourly_traffic.csv
  |       |-- operator_performance.csv
  |       |-- time_series_analysis.csv
  |       `-- whale_analysis.csv
 |
 ├── docs/
 │   └── analysis_log.txt                               (run log)
 │
 ├── analysis_reports/                                (LEGACY/EMPTY — outputs moved to output/)
 └── workspace_map.md                                (this file)



---

## 2. PYTHON DATA SCRIPTS & PARAMETERS {#2-python-data-scripts--parameters}


NOTE: None of these scripts use argparse or accept command-line arguments.
All paths are HARDCODED as module-level constants (FOLDER / REPORT_DIR / etc.).
To change the target, edit the constants at the top of each file.
Run with: py <script.py>   (the `python` alias is a Microsoft Store stub;
use the `py` launcher on this machine)

PROGRESS TRACKING: every ingest/dashboard script writes output\progress.json
via update_progress(stage, message, progress%, details) — {timestamp, stage,
message, progress, details}. The standalone viewer.html polls this file.

### A. RAW-DATA INGESTION & ANALYSIS  (src/ingest/ — read data\raw\)
─────────────────────────────────────────────────────────────

• whale_tracking.py            [pipeline step 1]
    Params: FOLDER=data\raw, REPORT_DIR=output, PROGRESS_FILE=output\progress.json.
    Streams all 27 exports, converts debit_amount to PHP (date-relative rate)
    and maps currency to country. Ranks players by total PHP debit, finds the
    Pareto cutoff (smallest top-cohort whose cumulative debit >= 80% of the
    grand total), takes the top 20 whales, estimates session lengths from
    paired timestamps.
    Output: whale_analysis.csv (20 rows — player_id, total_debit, total_bets,
             avg_session_hours, session_count, countries)
    Skip-guard: skipped by the wrapper if whale_analysis.csv already exists.

• time_series_analysis.py      [pipeline step 2]
    Params: FOLDER=data\raw, REPORT_DIR=output.
    Streams all 27 exports, parses formatted_debit_at, buckets bets per hour
    globally and per country (country derived from currency via
    currency_converter.CURRENCY_COUNTRY).
    Outputs: time_series_analysis.csv (country x total/peak-hour/peak share),
             hourly_traffic.csv (24h global bet curve)
    Skip-guard: skipped by the wrapper if both CSVs already exist.

• chaser_detection.py          [pipeline step 3]
    Params: FOLDER=data\raw, REPORT_DIR=output.
    Streams all 27 exports, converts winlose/debit to PHP, builds each
    player's chronological (timestamp, winlose, debit) sequence. Flags a
    "chase event" when 3+ consecutive losing rounds (winlose < 0) are followed
    by a debit spike >= 3x the average debit of the losing streak. Reports the
    worst (highest spike multiplier) event per player.
Output: chaser_detection.csv (25,263 rows — player_id, total_bets,
              chase_events, max_consecutive_losses, avg_loss_debit, spike_debit,
              spike_multiplier, total_debit, total_winlose), sorted by
              spike_multiplier desc.
NOTE: post-regeneration (regenerate_summary_csvs.py) the CSV holds every
      player with >=10 bets, not just those meeting the 3-loss + 3x spike chase
      threshold. dashboard_data.json now counts rows from the CSV at build time
      (total_chasers = 25,263), so all pct fields in loss_streak_distribution
      use the live denominator.
    Skip-guard: skipped by the wrapper if chaser_detection.csv already exists.

• operator_analysis.py         [pipeline step 4]
    Params: FOLDER=data\raw, REPORT_DIR=output.
    Streams all 27 exports, converts to PHP, aggregates winlose/debit/bet
    counts, unique players and countries per operator_name. Derives
    Operator_ROI_% = (debit + winlose) / debit * 100 and Avg_Bet.
    Output: operator_performance.csv (750 rows — Operator, Total_Bets,
             Total_Debit, Total_Winlose, Operator_ROI_%, Avg_Bet,
             Unique_Players, Countries), sorted by Total_Debit desc.
    Skip-guard: skipped by the wrapper if operator_performance.csv already exists.

• generate_heatmap_matrix.py   [pipeline step 5]
    Params: FOLDER=data\raw, REPORT_DIR=output. Reads ALL "*.csv".
    Builds country x 24-hour bet-count matrix from currency +
    formatted_debit_at.
    Output: country_hourly_heatmap.csv
    Skip-guard: skipped by the wrapper if country_hourly_heatmap.csv already
    exists and is newer than all raw CSV exports.

• build_all_players_dossiers.py  [pipeline step 6 — ALL-PLAYERS DOSSIER BUILDER]
    Params: FOLDER=data\raw, REPORT_DIR=output, CHUNK_SIZE=1000,
            MAX_WORKERS=min(available CPUs bounded to 2..4).
    Processes each export independently in two passes. Step 1 streams rows,
    uses currency_converter.convert_to_php() with its currency/date rate cache,
    aggregates compact telemetry (bets, money totals, game/operator/device
    mixes, hourly counts, recent rounds), and immediately atomically writes
    all_players_index_XX.json. It does not keep full balance histories.
    Step 2 rereads that export into per-player typed arrays (array('q') times,
    array('d') balances, array('b') win/lose signs), skips sorting when
    time_order_ok is true, then asynchronously writes
    dossier_chunks_XX/chunk_NNNN.js (window.DOSSIER_CHUNK_NNNN keyed by pid).
    Per-player detail now includes timestamps[] array (Unix seconds per round)
    for the Monthly Activity Calendar. Existing per-file indexes and complete
    expected chunk sets are skipped on rerun. The large merged JSON is disabled
    by default; set BUILD_DOSSIER_MONOLITH=1 to emit optional per-export
    all_players_dossiers_XX.json files.
    Skip-guard: skipped by the wrapper if all 27 per-export indexes and
    their complete chunk sets exist and are newer than their source exports.

• generate_player_behavior_data.py  [pipeline step 7]
    Params: FOLDER=data\raw, REPORT_DIR=output. Randomly samples 5
    "*EXPORT_CSV*.csv" files from all 27 exports using random.sample().
    Computes game stats, hourly credit/win, device split, balance tiers,
    bet brackets, inter-bet intervals, win/loss bet progression.
    Logs the 5 randomly selected filenames for traceability.
    Output: player_behavior_data.json
    Skip-guard: skipped by the wrapper if player_behavior_data.json exists
    and is newer than the sampled raw exports.

• build_individual_dossiers.py  [pipeline step 8]
    Params: FOLDER=data\raw, REPORT_DIR=output. Reads whale/chaser/
    operator CSVs + FIRST 5 exports. Compiles 42 per-player and 35
    per-operator detailed dossier profiles (game mix, hourly load,
    device split, top players, hold margin).
    Output: individual_dossiers_data.json
    Skip-guard: skipped by the wrapper if individual_dossiers_data.json
    exists and is newer than its dependencies (whale/chaser/operator CSVs
    and first 5 exports).

• probability_he_ingest.py     [pipeline step 13]
    Fetches dated CSV snapshots from the published probability/HE feed into
    data\probability\, probes backward for the newest available snapshot,
    checks the full cached date range for missing files, and backfills newly
    available dates. Writes _manifest.json and
    output\game_probability_he_data.json. The payload includes daily game-type
    series for actual/expected HE, actual/expected probability and threshold,
    cross-game summaries, latest bet-place records, and explicitly listed
    source gaps. The master pipeline runs this step on every invocation so
    newer snapshots and previously missing dates are picked up automatically.

• currency_converter.py        (shared library — no standalone run)
    CACHE_FILE=src\ingest\currency_cache.json, CACHE_TTL_DAYS=30.
    convert_to_php(amount, currency, date_str) — date-specific rate from
    frankfurter.app, memory+disk cached, BASE_RATES fallback (VND, TWD, MMK,
    NPR, BDT never supported by the API -> always base rate).
    get_country(currency) / CURRENCY_COUNTRY — currency to country map,
    imported by every ingest script so country attribution is identical
    everywhere. BASE_RATES covers 20 currencies; PHP is the base (1.0).

• inspect_behavior_metrics.py / sample_behavior_check.py /
  sample_profile_extractor.py
    Params: FOLDER=data\raw. Print sanity checks to stdout (no file output).

• advanced_analysis.py         (LEGACY monolith)
    Superseded by the four split scripts (whale_tracking / time_series /
    chaser_detection / operator_analysis). Runs the same 4 analyses in one
    process in a single pass over the exports. Retained for reference;
    NOT part of the 14-step pipeline. Same inputs/outputs as steps 1-4.

### B. DASHBOARD DATA PREPARATION  (src/dashboard/ — read output/, write output/)
───────────────────────────────────────────────────────────────────
  • prepare_dashboard_data.py          [pipeline step 9]
      Params: REPORT_DIR=output. Reads whale/chaser/hourly/time_series/
      heatmap/operator CSVs. Assembles master BI payload.
      Output: dashboard_data.json
      Skip-guard: skipped by the wrapper if dashboard_data.json exists
      and is newer than all derived CSVs.

  • generate_dashboard_html.py   <<< MAIN BI CONSOLE GENERATOR >>>  [pipeline step 10]
      Params: DATA_FILE=output\dashboard_data.json,
              INDEX_FILE=output\all_players_index.json (existing aggregate input),
              DOSSIER_DATA_FILE=output\individual_dossiers_data.json,
              SECTIONS_DIR=src\dashboard\sections\.
      Embeds: dashboard payload + COMBINED DOSSIER PAYLOAD
              {meta, players: ALL 50,227 index entries,
               operators: 35 detailed operator dossiers} into
              <script id="dossier-raw-data">. Injects section components
              (nav buttons, tabs 6/7, slides 7/8, dossier.js module).
      Output: output\bi_dashboard.html (~10.6 MB, Oriental Gaming Title BI & Risk Intelligence Console)
      Skip-guard: skipped by the wrapper if bi_dashboard.html exists
      and is newer than dashboard_data.json, individual_dossiers_data.json,
      and all per-export all_players_index_XX.json files.

  • generate_behavior_dashboard_html.py  [pipeline step 11]
      Params: REPORT_DIR=output, DATA_FILE=output\player_behavior_data.json.
      Output: player_behavior_dashboard.html (Oriental Gaming Title Player Behavioral Intelligence Console)
      Skip-guard: skipped by the wrapper if player_behavior_dashboard.html
      exists and is newer than player_behavior_data.json.

  • inject_dossier_tabs.py      [pipeline step 12]
      Params: REPORT_DIR=output, INDEX_FILE=output\all_players_index.json (existing aggregate input),
              DOSSIER_FILE=output\individual_dossiers_data.json,
              SRC_HTML=output\player_behavior_dashboard.html.
      Injects the same all-players dossier system into the behavior
      dashboard (output\player_behavior_dashboard.html is the POST-injection
      version after step 12; re-run to upgrade).
      Skip-guard: skipped by the wrapper if player_behavior_dashboard.html
      (post-injection) exists and is newer than all_players_index.json and
      individual_dossiers_data.json.

   • generate_probability_dashboard_html.py  [pipeline step 14]
       Params: output\game_probability_he_data.json.
       Generates a standalone ECharts dashboard with cross-game HE/probability
       comparisons, selected-game time series, threshold monitoring, and a
       latest-day actual-probability/actual-HE scatter by bet place. Displays
       missing snapshot dates and links to both existing dashboards.
       The two selected-game trend charts ("HE trend for selected game" and
       "Probability and threshold trend") are consolidated into ONE tabbed
       article (id="trendPanel") using .trend-tabs / .trend-tab-btn /
       .trend-pane classes that mimic the bi_dashboard.html .tab-pane +
       .nav-tab.active pattern; switchTrendTab() toggles panes, updates
       aria-selected and resizes the revealed chart. A Start Date / End Date
       input pair sits alongside the existing game/period filters; the range is
       applied by getDateRange()/inDateRange() inside selectedTrendValues() so
       both trend tabs filter live, and by comparisonValues() so the two
       cross-game comparison charts (heCompare, probCompare) re-average the
       pooled daily values over the selected days — with the precomputed
       game_types[].mean_* values used verbatim when no range is active. A
       Reset button clears the range and falls back to the full payload.
       Inputs are bounded by meta.billing_date_min / meta.billing_date_max via
       initDateRangeBounds(). The Game type summary table stays full-history.
       See section 9.
       Output: output\game_probability_dashboard.html.
       Skip-guard: skipped when the HTML is newer than its JSON payload and
       generator; step 13 always refreshes the source data before this check.

### C. INSPECTION / VERIFICATION / UTILITY  (src/verify/ — read output/)
──────────────────────────────────────────────────────────────
  • inspect_all_stats.py        Params: REPORT_DIR=output. Prints summary stats.
  • inspect_operators.py        Params: csv_path=output\operator_performance.csv.
  • analyze_retention_transactions.py
      Params: p=output. Prints retention & bet-velocity rankings.
  • verify_dashboard.py         Params: hardcoded output\bi_dashboard.html path.
      Validates embedded JSON payload and JS block.
  • verify_behavior_dashboard.py
      Params: hardcoded player_behavior_dashboard.html path.
  • check_js_syntax.py          Params: hardcoded bi_dashboard.html path.
      Checks JS brace/paren balance, flags unescaped Python artifacts
      (note: reports false-positive "double braces" on nested ECharts
      object literals — safe to ignore when net balance is 0).
  • link_dashboards.py          Edits generate_dashboard_html.py in place
      (adds cross-dashboard nav link to Behavior Telemetry console).
  • update_generator.py         Edits generate_dashboard_html.py in place
      (lazy-init charts per tab in switchTab()).

  • fix_heatmap_colors.py       Edits generate_dashboard_html.py in place
      (logarithmic color scale for the country x 24h heatmap so the
      full 7-color gradient is visible across the skewed bet-volume
      distribution; previously a linear scale buried ~90% of cells
      in the darkest band). Note: file currently not present in src/verify\.



---

## 3. ALL-PLAYERS DOSSIER SYSTEM (Oriental Gaming Title BI & Risk Intelligence Console) — ARCHITECTURE {#3-all-players-dossier-system-oriental-gaming-title-bi--risk-intelligence-console--architecture}


GOAL: every one of the 50,227 players is browsable on the dashboard with
their FULL round-by-round balance trajectory.

BUILT BY: build_all_players_dossiers.py (step 6) — processes each export in
two streaming passes. It writes a per-export compact index after pass one,
then builds trajectories and writes that export's lazy-load chunks in pass
two. Time-ordered sequences bypass sorting. Per-export merged dumps are
optional and disabled by default.

• Embedded payload (bi_dashboard.html, <script id="dossier-raw-data">):
    { meta: {total_players: 50227, total_rows: 18275592, files: 27,
             chunk_size: 1000, total_chunks: 51},
      players: [50,227 compact index entries — id==array position==rank,
                sorted by total debit desc],
      operators: [35 detailed operator dossiers] }

• Compact player index entry (all_players_index_XX.json / DOSSIER.players[]):
    id (array index == rank), pid, country, arch, debit, winlose, bets,
    avg_bet, whale (bool), chaser (bool), op, spike.

• Trajectory chunk (dossier_chunks_XX/chunk_NNNN.js,
  window.DOSSIER_CHUNK_NNNN; XX identifies the source export):
    Keyed by pid. Per player: balance_series[] (FULL trajectory),
    timestamps[] (Unix timestamps for each round), hours[24] (bet counts per hour), games[] ({game, bets, debit,
    win_rate_pct}), devices{Mobile, Desktop}, recent_rounds[]
    ({time, game, debit, credit, winlose, balance}).

• Tab 6 "Player Dossiers" (tab_players.html + dossier.js):
    - Hero shows total profiles + "Export All Players CSV" button
    - Search bar: player ID / country / archetype / operator
      (filterPlayerDossiers(), runs on every input event)
    - Tier filter dropdown: All Tiers / Whales / Chasers + all 13 archetypes
    - Country filter (populated from index at init) + 5 sort modes
      (debit, bets, pnl, spike, avg_bet)
    - Paginated card grid (60/120/240 per page) with WHALE/CHASER tags,
      country flag, archetype pill, and 4 KPIs (debit, net P&L, bets, avg bet)
    - Card click -> openPlayerDossier(id) (id is the INDEX ARRAY POSITION)
        -> chunkId = Math.floor(id / CHUNK_SIZE)
        -> loadDossierChunk(chunkId) lazy-loads
           dossier_chunks/chunk_NNNN.js via injected <script> tag
           (defines window.DOSSIER_CHUNK_NNNN keyed by player_id);
           concurrent requests for the same chunk share one callback queue
        -> renderDossierDetail() draws FULL balance_series, cumulative
           P&L curve (derived: balance[i] - balance[0]), hourly activity,
           game-mix pie, device split, recent-rounds forensics table
    - Monthly Activity Calendar: interactive month grid showing active days
      (highlighted with activity bar), click any day to expand 24-hour
      breakdown with per-hour bet counts. Navigate months with prev/next.
    - Charts are ECharts instances disposed on close/theme-toggle;
      trajectories load ON DEMAND (chunks total ~180 MB) so the page
      stays responsive; loaded chunks are cached in window.DOSSIER_CHUNK_*

• Tab 7 "Operator Dossiers" (tab_operators.html + dossier.js):
    Card grid of the 35 operator dossiers (GGR, hold margin, players,
    bets/player, volume, avg bet); openOperatorDossier(idx) renders games
    bar chart, hourly load, device mix and the top-players table.

• Entry points — every "Open" button resolves ANY of the 50,227 players:
    - openPlayerDossierById(pid, contextTab): linear-finds pid in the index,
      switches to the players tab, opens the dossier. Called from the whale
      leaderboard, chaser registry, operator top-players table and the
      whale scatter chart click handler.
    - openOperatorDossierById(name): same pattern for operators, called from
      the operator bubble chart.
    - exportDossierCSV('players' | 'operators'): exports all index rows.

• Slide deck integration: renderDossierSlideCharts(idx) renders slide 7
  (archetype distribution bar + top-8 players by debit) and slide 8
  (top-8 operators by GGR + top-8 hold margins) from the embedded index.

• Theme handling: dossierTheme() reads getChartTheme() so charts follow the
  light/dark toggle; reinitAllCharts() disposes dossier charts and re-opens
  any dossier panel left open.

• REQUIREMENT: dossier_chunks\ must sit next to bi_dashboard.html (and next
  to player_behavior_dashboard.html after step 12). Works when opened
  directly over file:// (script-tag loading is not CORS-blocked) or served
  over HTTP (python -m http.server).

• INTERFACE NOTE: the existing dashboard generators and dossier.js still
  expect the aggregate all_players_index.json plus sibling dossier_chunks\
  layout documented above. The refactored step 6 now emits per-export
  all_players_index_XX.json and dossier_chunks_XX\ directories. An aggregate
  index/chunk assembly or dashboard loader update is required before these
  new per-export outputs can directly replace the existing dashboard inputs.

• Monthly Activity Calendar (NEW — added to Tab 6 dossier detail):
  - Interactive month calendar grid in player dossier panel showing active
    days (amber highlight + activity bar proportional to bet count)
  - Month navigation (prev/next buttons) with dynamic rendering
  - Click any active day → expands inline 24-hour breakdown (0:00–23:00)
    with per-hour bet counts; peak hour highlighted in red
  - Powered by new timestamps[] array in trajectory chunks (Unix seconds
    per round), added by build_all_players_dossiers.py Step 2
  - Functions: initDossierCalendar, renderDossierCalendar,
    dossierCalendarPrevMonth, dossierCalendarNextMonth, openDayDetail,
    closeDayDetail, buildDayTimestampMap



---

## 4. DATA FLOW SUMMARY {#4-data-flow-summary}


27 raw exports (data\raw\)
    │
    ├─> whale_tracking.py ........ whale_analysis.csv ──────────────┐
    ├─> time_series_analysis.py .. time_series_analysis.csv ────────┤
    │                               hourly_traffic.csv ─────────────┤
    ├─> chaser_detection.py ...... chaser_detection.csv ────────────┤
    ├─> operator_analysis.py ..... operator_performance.csv ────────┤
    ├─> generate_heatmap_matrix.py country_hourly_heatmap.csv ──────┤
    ├─> generate_player_behavior_data.py player_behavior_data.json ─┤
    ├─> build_all_players_dossiers.py ─┬ all_players_index_XX.json ─┤
    │                                  ├ dossier_chunks_XX/*.js ────┤
    │                                  └ optional per-file monolith │
    (chunks now include timestamps[] for Monthly Activity Calendar)
    └─> build_individual_dossiers.py ── individual_dossiers_data.json
                                              (reads whale/chaser/operator
                                               CSVs + first 5 exports)
                                                                        │
derived CSVs ─> prepare_dashboard_data.py ─> dashboard_data.json ───────┤
                                                                        │
dashboard_data.json + all_players_index.json + individual_dossiers_data.json
      + sections/* ─> generate_dashboard_html.py ─> bi_dashboard.html
                      (Oriental Gaming Title BI & Risk Intelligence Console)
player_behavior_data.json ─> generate_behavior_dashboard_html.py ─> player_behavior_dashboard.html
player_behavior_dashboard.html ─> inject_dossier_tabs.py ─> dossier-enabled behavior HTML

data\probability\mnt_game_probability_he_YYYYMMDD.csv
      ─> probability_he_ingest.py ─> game_probability_he_data.json
      ─> generate_probability_dashboard_html.py
      ─> game_probability_dashboard.html

RUNTIME (browser): bi_dashboard.html embeds the index + operator dossiers;
each player card click lazy-loads its chunk_NNNN.js from dossier_chunks\.
The four dashboard HTML files link to one another via shared dashboard-common.css stylesheet.



---

## 5. CURRENCY STANDARDIZATION {#5-currency-standardization}

  All monetary amounts in the raw data are in various currencies (CNY, IDR, VND, KRW,
  JPY, THB, USD, SGD, HKD, TWD, MYR, INR, MMK, NPR, BDT, TRY, USDT, IDRK, VNDK).
  To enable accurate cross-player and cross-country analysis, ALL amounts are
  converted to PHP (Philippine Peso) using date-relative historical exchange rates.

  • Module: src/ingest/currency_converter.py
    - Fetches historical rates from frankfurter.app API (no API key required)
    - Caches rates to disk (currency_cache.json) with 30-day TTL
    - convert_to_php(amount, currency, date_str): Converts using date-specific rate
    - get_country(currency): Maps currency to country (consistent across scripts)
    - Rate fallback: Uses BASE_RATES when API unavailable or currency unsupported
    - Unsupported currencies (VND, TWD, MMK, NPR, BDT): Uses base fallback rates

  • Scripts updated to use currency conversion:
    - whale_tracking.py: whale debit totals (PHP)
    - time_series_analysis.py: country mapping (uses CURRENCY_COUNTRY)
    - chaser_detection.py: loss streaks and spike multipliers (PHP)
    - operator_analysis.py: operator ROI and GGR (PHP)
    - build_all_players_dossiers.py: All player trajectories, balance series, P&L
    - generate_player_behavior_data.py: Game stats, hourly timing, bet brackets
    - generate_heatmap_matrix.py: Country mapping (uses get_country)
    - build_individual_dossiers.py: Player/operator profiles, balances, P&L

  • Output impact: All derived CSVs, JSON files, and dashboards now reflect
    PHP-normalized values. Whale thresholds, chaser spike multipliers, operator
    ROI, and player archetypes are computed on PHP-standardized amounts.



---

## 6. MASTER PIPELINE WRAPPER (scripts/generate_all_dashboards.py) {#6-master-pipeline-wrapper-scriptsgenerate_all_dashboardspy}

Runs the ENTIRE Oriental Gaming Title data pipeline in strict dependency order
as standalone processes (each script uses hardcoded absolute paths, so no
argv is passed; each writes output\progress.json). Invoke with:
    py scripts\generate_all_dashboards.py

  [1/14]  whale_tracking.py          -> whale_analysis.csv
  [2/14]  time_series_analysis.py    -> time_series_analysis.csv + hourly_traffic.csv
  [3/14]  chaser_detection.py        -> chaser_detection.csv
  [4/14]  operator_analysis.py       -> operator_performance.csv
  [5/14]  generate_heatmap_matrix.py -> country_hourly_heatmap.csv
  [6/14]  build_all_players_dossiers.py -> all_players_index_XX.json +
                                           dossier_chunks_XX/chunk_NNNN.js
                                           (optional all_players_dossiers_XX.json;
                                            BUILD_DOSSIER_MONOLITH=1)
                                           NEW: chunks now include timestamps[]
                                           array for Monthly Activity Calendar
  [7/14]  generate_player_behavior_data.py -> player_behavior_data.json
  [8/14]  build_individual_dossiers.py -> individual_dossiers_data.json
                                           (42 players + 35 operators, curated)
  [9/14]  prepare_dashboard_data.py  -> dashboard_data.json (master BI payload)
  [10/14] generate_dashboard_html.py -> bi_dashboard.html (Main BI Console)
  [11/14] generate_behavior_dashboard_html.py -> player_behavior_dashboard.html
  [12/14] inject_dossier_tabs.py     -> injects dossier system into behavior console
  [13/14] probability_he_ingest.py   -> game_probability_he_data.json (refresh/backfill)
  [14/14] generate_probability_dashboard_html.py -> game_probability_dashboard.html

  [15/15] round_dealer_table_time_ingest.py -> round_dealer_table_time_data.json
  [16/16] generate_round_dealer_table_time_dashboard_html.py -> round_dealer_table_time_dashboard.html

Features:
  - ProgressBar (bar + % + ETA) rendered to stdout as steps complete
  - Skip-guards: steps are skipped when outputs exist and are newer than their
    dependencies; the probability ingest always runs to find new snapshots:
    * Steps 1-4: output CSVs exist and non-empty
    * Step 5: country_hourly_heatmap.csv newer than all raw exports
    * Step 6: all 27 per-export indexes + chunk sets newer than source exports
    * Step 7: player_behavior_data.json newer than first 5 raw exports
    * Step 8: individual_dossiers_data.json newer than whale/chaser/operator CSVs and first 5 exports
    * Step 9: dashboard_data.json newer than all derived CSVs
    * Step 10: bi_dashboard.html newer than dashboard_data.json, individual_dossiers_data.json, and all per-export indexes
    * Step 11: player_behavior_dashboard.html newer than player_behavior_data.json
    * Step 12: player_behavior_dashboard.html (post-injection) newer than all_players_index.json and individual_dossiers_data.json
    * Step 13: always runs; uses cached files and checks/backfills source gaps
    * Step 14: game_probability_dashboard.html newer than game_probability_he_data.json and its generator
    * Step 15: round_dealer_table_time_data.json newer than its generator script
    * Step 16: round_dealer_table_time_dashboard.html newer than the data payload and its generator
  - Missing scripts are reported as [SKIP] and counted as failures
  - Exit code 0 = all steps OK, 1 = one or more failures (listed at the end)

Steps 6 and 8 are NOT redundant:
  • build_all_players_dossiers.py processes each of the 27 exports separately
    → per-export compact indexes and lazy-loadable trajectory chunks, with
    file-level resume guards and no full history retained during index
    extraction. The optional merged dump is off unless
    BUILD_DOSSIER_MONOLITH=1.
  • build_individual_dossiers.py reads only the first 5 exports + the derived
    CSVs → a curated set of 42 players and 35 operators with aggregated
    forensics (game mix, hourly load, device split, top players). No full
    trajectory. Powers the operator-dossier "Open" buttons and detailed
    player/operator profiles.
  Both are required: generate_dashboard_html.py embeds BOTH payloads.

Dependency note: steps 6 and 8 both consume the step 1-4 CSVs, so those must
run first. generate_dashboard_html.py (step 10) reads the outputs of steps
6, 8, and 9, so those must precede it. inject_dossier_tabs.py (step 12) needs
the step 8 output and the step 11 HTML.


---

## 7. RECENT CHANGES (2026-10-09) {#7-recent-changes-2026-10-09}


Fixed data consistency and completeness issues identified during dashboard audit:

1. FIXED: merge_per_file_dossiers() in generate_dashboard_html.py
   - Previously: Only used first chunk's detail for each player (dropped multi-file trajectories)
   - Now: Concatenates trajectories from all source chunks chronologically by timestamps
   - Result: All 19,045 multi-file players now have merged balance_series, timestamps, games, hours, recent_rounds

2. REGENERATED: Unified index and chunks (all_players_index.json + dossier_chunks/)
   - Correct totals for all 50,227 players
   - Player ZR_62633509_15105215938: 799 bets across Aug 20 & 28 now in merged chunk
   - Monthly Activity Calendar now shows all dates from merged timestamps

3. CREATED: src/dashboard/regenerate_summary_csvs.py
   - Regenerates whale_analysis.csv and chaser_detection.csv from unified index
   - Ensures summary tabs (Whales/Chasers) use same data source as Player Dossiers tab
   - Computes sessions from timestamps (30-min gap), spike multipliers from balance_series

4. FIXED: Whale/Chaser data consistency (0 mismatches)
   - Before: 20/20 whales and 10/10 chasers mismatched (different aggregation pipelines)
   - After: All CSV totals match unified index exactly

5. FIXED: whale_analysis.csv limited to top 20
   - VIP Whales tab now shows exactly 20 players (was showing all 50,227)

6. ADDED: Whale Group Dossier in Tab 1 (VIP Whales)
   - Aggregate KPI strip: Total Debit (7.27B), Total Wagers (123,924), Avg Session (0.74h), Countries (4), Casino Concentration (42.3%)
   - Geographic Composition breakdown with country flags and debit percentages
   - Behavioral Archetypes: Lightning/Bot (sub-3min), Burst Whale, Sustained Grinder
   - 5 Key Group Insights: dominant profile, geographic concentration, top individual, volume velocity, session brevity

7. ADDED: Chaser Group Dossier in Tab 2 (Risk & Chasers)
   - Aggregate KPI strip: Total Debit (22.61B), Total Flagged (25,263), Net Losers (69.1%), Net P&L (-334.6M), Peak Spike (7,500x)
   - Risk Tier Distribution: Extreme (≥1000x: 5), Critical (100-999x: 240), High (20-99x: 1,850), Moderate (5-19x: 6,522), Low (<5x: 16,646)
   - Tilt Threshold Analysis: L1-L10 loss streak breakdown with L3 (3 consecutive losses) highlighted as PEAK trigger (11.2%)
   - 5 Key Risk Insights: loss-streak tipping point, financial destructiveness, extreme risk cohort, streak escalation, net winner anomaly

8. FIXED: "Loss Thresholds: The 'Tilt' Curve" chart (Tab 2, initChaserTiltChart)
    - CHART SCOPE: now filters loss_streak_distribution to streak >= 3 before
      slicing, so streaks 0-2 (players who lost rounds but never chained 3+
      consecutive losses) no longer appear. Bars start at L3.
    - BUG 1 (stale denominator): dashboard_data.json hardcoded total_chasers=11978
      while chaser_detection.csv had 25,263 rows, so every pct in
      loss_streak_distribution was divided by 11,978 (streak 0 showed 5.81%
      instead of 2.76%). Fixed in prepare_dashboard_data.py: total_chasers is now
      counted from the CSV at build time; all pct fields use it as denominator.
    - BUG 2 (markPoint on wrong bar): the "Threshold Point" was at
      coord [0, players[0]] (the streak-0 bar) despite labeling "33.5% Tilt".
      Now positioned at coord [l3Idx, players[l3Idx]] — index 0 after the
      streak>=3 filter, i.e. the L3 bar — with a dynamic label computed as
      (L3 players / total_count * 100).
    - Also replaced remaining hardcoded "11,978" labels across the console
      (nav badge, KPI strip, dossier subtitle, slide 1/3 text, Pillar 2 strategy)
      with live DATA.chasers-driven elements so they stay consistent.

9. FIXED: "24-Hour Outcome Volume: Wins, Losses & Pushes" chart (Tab 1, initTimingCharts)
     - BUG: All three line series (Wins, Losses, Pushes) used `stack: 'Total'`, causing
       ECharts to stack them on top of each other instead of showing independent values.
       The loss/push lines appeared as cumulative sums rather than true hourly counts.
     - FIX: Removed `stack: 'Total'` from all three series. Each outcome now displays its
       actual hourly count independently. Added width:2 and areaStyle for clarity.
     - Files: generate_behavior_dashboard_html.py:1029-1033, output/player_behavior_dashboard.html:1013-1015

10. ADDED: "Player Archetype Legend" card in Tab 6 (All Player Dossiers)
     - Purpose: explains every player label (VIP Whale, Low Chaser, etc.) so users
       understand what each archetype means and how it is assigned.
     - Card sits directly above the Search & Filter Bar. Contains a 13-item grid
       (Extreme Chaser / Critical Chaser / High Chaser / Moderate Chaser / Low
       Chaser / Lightning Burst Whale / Sustained Grinder Whale / VIP Whale /
       VIP High Roller / High Roller / Mid Roller / Active Player / Casual Player),
       each rendered in its own ARCHETYPE_COLORS color with a one-line
       description from ARCHETYPE_DESC.
     - Footnote explains the assignment rule: Spike Multiplier (max bet
       escalation after consecutive losses) + total wagered volume; Chasers
       escalate after losses (spike >= 3x), Whales are the top 0.4% by total
       debit (>= ~384M); a player can carry both a Whale flag and a Chaser flag.
     - Files: src/dashboard/sections/tab_players.html, src/dashboard/sections/dossier.js,
       src/dashboard/inject_dossier_tabs.py, output/bi_dashboard.html,
       output/player_behavior_dashboard.html

11. ADDED: Clickable archetype toggle filter on the legend cards
     - Each legend card is now a button (cursor-pointer, Enter/Space activates,
       aria-pressed). Clicking toggles that archetype into a Set
       (`_selectedArchetypes`); clicking again removes it.
     - `filterPlayerDossiers()` gained a `matchArch` clause:
       `_selectedArchetypes.size === 0 || _selectedArchetypes.has(p.arch)`.
       Selection is AND-combined with the existing search box, tier dropdown
       and country dropdown, so typing a player ID while VIP Whale is selected
       shows only VIP Whales matching that ID. Empty selection = show all.
     - Selected cards are visually highlighted (filled background, double-ring
       border in the archetype color). A count badge (`· N selected`) and a
       **Clear** button appear in the legend header whenever any archetype is
       selected; Clear resets to show all.
     - `renderArchetypeLegend()` now also updates the badge and Clear button
       visibility, and is called on init and after every toggle.
     - Files: src/dashboard/sections/dossier.js (toggleArchetypeFilter,
       clearArchetypeFilters, renderArchetypeLegend, _selectedArchetypes,
       matchArch in filterPlayerDossiers), src/dashboard/sections/tab_players.html
       (legend header with badge + Clear button),
       src/dashboard/inject_dossier_tabs.py (same wiring for behavior console),
       output/bi_dashboard.html (patched directly — Python regenerator not
       runnable on this machine), output/player_behavior_dashboard.html
       (regenerated via inject_dossier_tabs.py)


---

## 8. RECENT UPDATE (2026-10-12) {#8-recent-update-2026-10-12}


1. PIPELINE LOCATION
   - The 14-step master wrapper is scripts/generate_all_dashboards.py (not the
     workspace root). scripts/generate_chart.js is a helper.
   - Pipeline scripts write live progress to output/progress.json.

2. PROBABILITY / HOUSE-EDGE SNAPSHOT CACHE
   - data/probability/ contains daily published CSV snapshots from
     2025-01-31 through 2026-10-11; the cache was scanned through 2026-10-11
     on 2026-10-12.
   - data/probability/_manifest.json records unavailable dates. The current
     missing interval is 2026-01-13 through 2026-01-29.
   - Pipeline steps 13 and 14 refresh output/game_probability_he_data.json
     and output/game_probability_dashboard.html from this cache/feed.
   - Cached CSV snapshots are each under 100 KB; inspect only as needed.


---

## 9. RECENT UPDATE (2026-10-13) — PROBABILITY & HE CONSOLE TREND TABS {#9-recent-update-2026-10-13--probability--he-console-trend-tabs}


Consolidated the two selected-game trend charts on
output/dashboards/game_probability_dashboard.html (generated by
src/dashboard/generate_probability_dashboard_html.py, pipeline step 14) into a
single tabbed interface with a date-range selector. The three other charts
(Average actual vs expected HE by game, Probability vs expected probability and
threshold, Latest bet-place relationship) are unchanged.

1. TABBED TREND CONTAINER
   - The two former standalone articles ("HE trend for selected game",
     "Probability and threshold trend") were replaced by ONE
     <article class="card chart-card wide" id="trendPanel"> that holds a
     .trend-tabs button row plus two .trend-pane panels (pane-heTrend,
     pane-probTrend). Only the active pane is displayed; the other is
     display:none.
   - Pattern intentionally mirrors bi_dashboard.html: .tab-pane sections
     toggled by a nav row, active state expressed as a class on both the pane
     and its button (.trend-pane.active / .trend-tab-btn.active), with a
     fadeIn animation and ECharts resize() after the switch so the newly
     revealed chart gets real dimensions.
   - switchTrendTab('he'|'prob') removes .active from all .trend-pane and
     .trend-tab-btn elements, adds .active to the target pane/button, syncs
     aria-selected for accessibility, then calls
     charts.heTrend/ProbTrend.resize() in a 50 ms timeout.
   - ECharts instance registration is unchanged: chartIds still contains
     ['heCompare','probCompare','heTrend','probTrend','relationship'], so the
     existing instances and the other two charts are untouched. Charts are
     created up-front (hidden panes are dimensioned 0 but are resized on first
     reveal).

2. DATE RANGE SELECTOR
   - New <input type="date" id="startDate"> and <input type="date" id="endDate">
     sit in the .filters row next to the existing Trend game / Trend window
     selects, plus a #resetDateRange button.
   - initDateRangeBounds() sets both inputs' min/max from
     meta.billing_date_min / meta.billing_date_max (with a series-data
     fallback) so users cannot pick dates outside the cached feed range.
   - getDateRange() reads the two inputs; inDateRange(day) tests each ISO date
     string (series day values and input values are both YYYY-MM-DD, so plain
     string comparison is correct).
   - selectedTrendValues() applies the date range in addition to the existing
     period-window cutoff, so BOTH trend tabs filter live on 'change' of either
     date input. Empty inputs mean "no bound" on that side.
   - The date range ALSO drives the two cross-game comparison charts:
     "Average actual vs expected HE by game" (heCompare) and "Probability vs
     expected probability and threshold" (probCompare). comparisonValues()
     re-averages DATA.series_he / series_expected_he /
     series_actual_probability / series_expected_probability / series_threshold
     per game over the filtered days. When NO range is set it returns the
     payload's precomputed game_types[].mean_* values verbatim, so the default
     (unfiltered) view is byte-identical to before this change. Each card's
     #heCompareNote / #probCompareNote caption appends "· start to end" while a
     range is active.
   - The Game type summary table keeps the precomputed full-history means and
     is intentionally NOT range-filtered.
   - resetDateRange() clears both inputs and re-renders everything.

3. VERIFICATION
   - JS syntax validated (node --check).
   - Functional smoke test with a stubbed DOM/ECharts: 36/36 checks pass —
     all 5 ECharts instances still initialise, default tab state is correct,
     tab switching toggles panes/buttons/aria and resizes the target chart,
     date bounds come from meta, date range filters the trend series
     (single-day and start-only cases), the Comparison charts reproduce the
     precomputed means when no range is set and re-average the filtered series
     when one is (with live caption updates), reset restores the precomputed
     values, and renderTrends()/render() run without error.

Note: the generator writes output/game_probability_dashboard.html; the copy in
output/dashboards/ is the sibling-linked console that users open (its nav links
point at bi_dashboard.html / player_behavior_dashboard.html). Both were
regenerated/synced.


---

## 10. RECENT UPDATE (2026-10-13) — PROBABILITY CONSOLE SHOWS ALL GAMES AT ONCE {#10-recent-update-2026-10-13--probability-console-shows-all-games-at-once}


output\dashboards\game_probability_dashboard.html (generator:
src\dashboard\generate_probability_dashboard_html.py, pipeline step 14) no
longer relies on the "Trend game" dropdown — every game type is displayed
simultaneously, with a new combined aggregate section on top.

1. REMOVED: <select id="gameFilter"> and its label from the .filters row. The
   hero h2 now reads "Every game at a glance: combined trends and per-game
   detail". The .filters row keeps Trend window (#periodFilter), Start date,
   End date and the Reset range button.

2. ADDED: "Combined Summary — all games" section at the top of the main grid:
   a wide header card (#combinedNote shows pooled row/bet-place counts, pooled
   breach rate and the active range) plus two ECharts instances —
   #combinedHe (overall HE trend: pooled daily mean actual vs expected HE) and
   #combinedProb (overall probability and threshold trend) — both built from
   DATA.daily (per-day cross-game means). renderCombinedSummary() drives them.

3. REPLACED: the tabbed trend panel (id="trendPanel", .trend-tabs /
   .trend-pane, switchTrendTab) is gone. Its two per-selected-game charts are
   superseded by the per-game charts below; the unused trend-tab CSS was
   removed.

4. ADDED: buildGameSections() — a JS loop over DATA.game_types that injects one
   <article class="card chart-card wide" id-free> per game into
   <div class="game-sections" id="gameSections"> (CSS display:contents so the
   articles participate directly in the 2-column .grid). Each section contains:
   - A dedicated <table> inside <div class="table-wrap">: a bold
     .table-total row ("<GAME> — all bet places") with timeframe-filtered
     game-level means followed by one row per bet place from
     DATA.bet_places (full-history pooled means; the caption notes this).
   - Two .chart-card charts inside a nested .grid: "HE trend — <GAME>"
     (#gameHe-<i>) and "Probability and threshold trend — <GAME>"
     (#gameProb-<i>), series style matching the old trend charts (time axis,
     inside+slider dataZoom, smooth lines, dashed expected, dotted threshold).
   ECharts instances are registered in the gameCharts array.

5. GLOBAL TIMEFRAME: inTimeframe(day) = date range ∩ trend window
   (#periodFilter, default 90 days). It now applies simultaneously to the
   Combined Summary charts, every per-game table (game row) and every per-game
   chart; changing #periodFilter, #startDate or #endDate re-renders all of
   them via render(). timeframeSeries()/timeframeMean() recompute the
   game-level metrics from the per-game series over the visible days. The two
   cross-game comparison charts (heCompare/probCompare) keep their existing
   date-range behaviour with precomputed mean_* fallback, and the "Game type
   summary" table keeps the precomputed full-history means.

6. VERIFICATION: node --check on the inline script; stubbed DOM/ECharts smoke
   test — 39/39 checks pass (21 chart instances: 5 static + 16 per-game; 8
   per-game tables with 1 + bet-place rows each; window switch widens series
   and updates table days; date range filters the combined charts and updates
   the captions; reset restores full history; relationship scatter groups match
   the valid latest-day rows).


---

## 11. RECENT UPDATE (2026-10-13) — QUICK NAV + THRESHOLD BREACH ANALYTICS {#11-recent-update-2026-10-13--quick-nav-threshold-breach-analytics}


Follow-up to section 10 on output\dashboards\game_probability_dashboard.html
(plus a supporting payload change from
src\ingest\probability_he_ingest.py, pipeline step 13).

1. STICKY QUICK NAVIGATION (inside the existing sticky <header>):
   <nav class="quick-nav" id="quickNav"> wraps to its own row (flex-basis:100%)
   with a top separator, so it stays pinned while scrolling. buildQuickNav()
   fills it from a "Jump to" label + links: #combinedPanel (Combined Summary),
   #breachAnalytics (Threshold Breach Analytics), one link per game, and
   #gameSummary (Game type summary). Each per-game article now carries a unique
   anchor id (id="game-BACCARAT", …) assigned by uniqueGameAnchor() —
   slugify() uppercases and hyphenates the name and a numeric suffix resolves
   the CLASSIC DT / Classic DT casing alias collision. html has
   scroll-behavior:smooth and article[id]{scroll-margin-top:140px} so jumps
   clear the sticky header.

2. THRESHOLD BREACH ANALYTICS: new <article class="card chart-card wide"
   id="breachAnalytics"> directly below the Combined Summary block, holding a
   nested .grid with:
   - #breachCalendar — ECharts calendar coordinate system + heatmap series of
     daily breach counts (DATA.daily[].breaches) over the visible range, with a
     horizontal visualMap scaled to the worst day in view.
   - #breachByDate — stacked bar chart, one stacked series per game type over
     billing-date categories, from the new series_breach_count payload field.
   - Two .table-wrap tables: "Number of times threshold exceeded by game type"
     (#breachByGameRows: breaches in view, share, days in view, breaches/day,
     full-history breaches and breach %) and "… by betting area"
     (#breachByBetPlaceRows: all 111 bet places with in-view and full-history
     breaches from the new bet_place_breaches payload field).

3. PAYLOAD SUPPORT (probability_he_ingest.py): the per-(date, game) breach
   COUNTS were computed internally but only the percentage was published.
   Added series_breach_count {game: [[date, count], …]} (dense) and
   bet_place_breaches {"GAME|bet_place": [[date, count], …]} (sparse, breach
   days only). Payload grew 821 KB -> ~1.07 MB. Verified: per-game daily counts
   sum exactly to game_types[].breaches and each bet-place series sums to
   bet_places[].breaches (61 of 111 bet places ever breach).

4. GLOBAL TIMEFRAME: renderBreachAnalytics() is part of render(), so the
   calendar, stacked bar and both tables recalculate whenever #periodFilter,
   #startDate or #endDate changes (inTimeframe = date range ∩ trend window);
   #breachNote reports totals, days in view and the peak day.

5. VERIFICATION: node --check; stubbed DOM/ECharts smoke test — 38/38 checks
   pass (23 chart instances: 7 static + 16 per-game; 11 quick-nav links all
   resolving to existing anchors; unique game ids incl. the DT alias pair;
   calendar/stacked-bar series and table totals reconcile with the payload for
   the 90-day window, "all" history, an August start date and reset).


---

## 12. RECENT UPDATE (2026-10-13) — STICKY HEADER FILTERS + BREACH CHARTS {#12-recent-update-2026-10-13--sticky-header-filters-breach-charts}


Follow-up to sections 10-11 on
output\dashboards\game_probability_dashboard.html (generator:
src\dashboard\generate_probability_dashboard_html.py; no payload change).

1. FILTERS MOVED INTO THE STICKY HEADER
   - The .filters container (Trend window #periodFilter, Start date
     #startDate, End date #endDate, Reset range #resetDateRange) moved out of
     the hero and inside <header>, where header .filters { flex-basis: 100% }
     gives it its own separated row between the dashboard links and the
     quick-nav. The header now stacks: title + BI/Behavior links, time filters,
     jump links — all pinned while scrolling. The hero keeps only the h2 +
     intro paragraph. article[id]{scroll-margin-top} raised 140px -> 200px so
     anchor jumps still clear the taller header.
   - #periodFilter gained <option value="7">Latest 7 days</option> as the first
     choice; 90 days remains the default. inTimeframe() already derives the
     cutoff from Number(days), so 7 works everywhere with no logic change.

2. BREACH TABLES REPLACED WITH ECHARTS
   - "Number of times threshold exceeded by betting area" -> #breachByPlace:
     horizontal bar chart (yAxis category, inverse so the largest sits on top)
     listing all 111 "GAME · bet_place" areas with value labels, an in+slider
     dataZoom on the yAxis, and a height that scales at 18px per bar capped at
     1100px (set inline, then resize()). Tooltip shows in-view and full-history
     counts.
   - "Number of times threshold exceeded by game type" -> #breachByGame:
     vertical bar chart sorted descending, per-game colors, top value labels,
     and an axis tooltip with share of in-view breaches, days in view,
     breaches/day and full-history totals.
   - The old .table-wrap tables (#breachByGameRows / #breachByBetPlaceRows)
     were removed entirely; chartIds now registers breachByGame and
     breachByPlace (9 static + 16 per-game = 25 instances).

3. LAYOUT REORDER FOR HIGH-PRIORITY METRICS
   - Top of the main grid: #combinedPanel header, then "Probability vs
     expected probability and threshold" (#probCompare) — immediately below
     the global KPIs — then #combinedHe, #combinedProb and #heCompare.
   - #breachAnalytics follows, its first item now the betting-area chart
     (#breachByPlace), then the calendar (#breachCalendar), the stacked
     by-date bars (#breachByDate) and the by-game chart (#breachByGame).
   - Per-game sections, latest-day scatter and the full-history Game type
     summary table keep their positions after the breach section.

4. VERIFICATION: node --check; stubbed DOM/ECharts smoke test — 28/28 checks
   pass (25 chart instances; filters + listeners inside the header; 7-day
   option present with 90 still default; both breach charts horizontal/vertical
   as specified, sorted, capped height, slider zoom; chart totals reconcile
   with daily[].breaches for the 7-day, 90-day, custom-start and reset cases;
   previous per-game/quick-nav regressions still green).


---

## 13. RECENT UPDATE (2026-10-13) — HE TRENDS SPLIT PER GAME {#13-recent-update-2026-10-13--he-trends-split-per-game}


Follow-up to section 12 on output\dashboards\game_probability_dashboard.html
(generator: src\dashboard\generate_probability_dashboard_html.py; no payload
change). Requested because the pooled HE line chart mixed all games on one
pair of axes.

1. REMOVED: the combined "Overall HE trend — all games" chart — its article,
   the 'combinedHe' entry in chartIds and the charts.combinedHe.setOption block
   inside renderCombinedSummary(). No game-agnostic HE line chart remains; the
   dashboard no longer plots multiple game types on one HE trend axis.

2. RENAMED: the per-game charts generated by buildGameSections() now read
   "<GAME> - HE Trend" (e.g. "BACCARAT - HE Trend") and
   "<GAME> - Probability and threshold trend", so each standalone chart is
   self-labelling inside its own game section. Series names stay "Actual HE" /
   "Expected HE" (dashed) and "Actual probability" / "Expected probability" /
   "Threshold" (dotted). Per-game HE trend charts still follow the global
   timeframe (trend window ∩ date range) via timeframeSeries().

3. KEPT: heCompare ("Average actual vs expected HE by game") — it is a grouped
   BAR comparison, not a trend line chart, so it does not overlap lines; it is
   now .wide to fill the Combined Summary row left open by the removed chart.
   Combined Summary order: header, probCompare (probability comparison),
   combinedProb (pooled probability trend), heCompare — followed by Threshold
   Breach Analytics.

4. VERIFICATION: node --check; stubbed DOM/ECharts smoke test — 23/23 checks
   pass (24 chart instances: 8 static + 16 per-game; combinedHe never
   initialised and no setOption sent to it; every game section contains its own
   labelled "<GAME> - HE Trend" chart with exactly 2 series plotting only that
   game's series; 90-day / "all" / start-date / reset cases all re-filter the
   per-game HE charts; breach and quick-nav regressions still green).


---

## 14. RECENT UPDATE (2026-10-13) — UI CLEANUP: CONDITIONAL HE + BREACH CHARTS {#14-recent-update-2026-10-13--ui-cleanup-conditional-he-breach-charts}


Follow-up to section 13 on output\dashboards\game_probability_dashboard.html
(generator: src\dashboard\generate_probability_dashboard_html.py; no payload
change).

1. REMOVED: every per-game "Probability and threshold trend" chart — the second
   card of each game section (gameProb-<i> div, ECharts instance, setOption and
   the nested .grid that paired the two cards). Each game section is now a
   standard single-view container: heading, meta caption, table, then one
   full-width .chart-card.single "<GAME> - HE Trend" chart. (The old tabbed
   trend panel from section 9 was already gone; nothing tab-related remains.)
   The Combined Summary charts probCompare and combinedProb are untouched.

2. CONDITIONAL HE TREND CHARTS: buildGameSections() computes
   gameHeAvailable[index] = game.mean_actual_he != null AND series_he has at
   least one non-null point. Games without HE data get NO ECharts instance
   (gameCharts[i].he === null) and their wrapper <article
   id="gameHeCard-<i>"> is generated with style="display:none". At render time
   renderGameSections() re-evaluates the window-filtered points: the wrapper is
   shown/hidden and setOption is skipped whenever the visible timeframe has no
   HE points (e.g. SICBO, whose HE series only spans 2025-01-25..2025-05-03,
   disappears under the default 90-day window and returns under "all" dates).
   allCharts() filters out the null instances so resize stays safe.

3. CONDITIONAL TABLE COLUMNS: the per-game <thead> is now built dynamically
   (gameHead-<i>). Games without usable HE data drop the "Actual HE",
   "Expected HE" and "HE delta" columns from the header AND from every row
   (6-cell rows instead of 9) — BULL BULL (mean_actual_he null, 0/599 series
   points, no HE model published) renders that way, and its meta caption notes
   "no house-edge model published for this game".

4. ZERO-BREACH FILTERING: the two breach charts now filter before hitting
   ECharts — byGame keeps only games with in-view breaches > 0 and byPlace only
   betting areas with in-view breaches > 0 (axes, bars, labels, tooltips and
   the dynamic byPlace height all derive from the filtered arrays). Under the
   default 90-day window that is 5 games; under "all" dates 7 games (the
   zero-breach "Classic DT" alias drops out) and 61 of 111 betting areas.
   Tooltips still show full-history totals for the listed entries.

5. VERIFICATION: node --check; stubbed DOM/ECharts smoke test — 30/30 checks
   pass (15 chart instances: 8 static + 7 per-game HE, BULL BULL skipped;
   wrapper visibility matches in-window HE points incl. the SICBO hide/reveal
   cases; BULL BULL 6-cell rows and 6-column head vs ROULETTE's 9; breach
   charts exclude zero-breach games/areas across 7-day, 90-day and "all"
   windows, stay sorted descending, and the byPlace height matches the filtered
   count).



---

## 15. RECENT UPDATE (2026-10-15) — UNIFIED DEALER & TABLE PACE CONSOLE {#15-recent-update-2026-10-15--unified-dealer--table-pace-console}


The master dashboard pipeline now uses one combined pace data source and one
dashboard generator:

  - Pipeline step 15: src\ingest\round_dealer_table_time_ingest.py writes
    output\round_dealer_table_time_data.json from the dealer and table daily
    snapshots cached in data\round_dealer_time\ and data\round_table_time\.
  - Pipeline step 16: src\dashboard\generate_round_dealer_table_time_dashboard_html.py
    writes output\dashboards\round_dealer_table_time_dashboard.html.
  - The console payload maps each observation to BILLING_DATE, GAME_TYPE,
    DEALER, TABLE_NO, AVG_TIMEDIFF and STD_TIMEDIFF. Dealer and table source
    rows remain distinct; the source does not provide dealer-table pairings.
  - A GAME_TYPE selector scopes every KPI, chart and table to one game.
    Dashboard features include selected-game dealer trends and baseline,
    slow-dealer watchlist, efficiency matrix, pace extremes and one forensics
    table. ECharts use getChartTheme() styling and resize on layout changes.
  - The standalone round_dealer_time_dashboard.html and
    round_table_time_dashboard.html outputs, plus their two dashboard HTML
    generator scripts, have been retired. The standalone ingest scripts remain
    in src\ingest\ but are not part of the master pipeline.

  Data sources:
    - Dealer snapshots: https://ogp.oss-ap-southeast-1.aliyuncs.com/share/
      mnt_round_dealer_time_daily_YYYYMMDD.csv  (cached in data/round_dealer_time/)
    - Table snapshots: https://ogp.oss-ap-southeast-1.aliyuncs.com/share/
      mnt_round_table_time_daily_YYYYMMDD.csv  (cached in data/round_table_time/)
    - CSV columns: BILLING_DATE, GAME_TYPE, DEALER|TABLE_NO, AVG_TIMEDIFF,
      STD_TIMEDIFF (verified 2026-10-12)

  Console features:
    - KPI strip: Global Average Pace, Selected Game Baseline, Average Std Dev,
      Active Fleet (dealer/table counts)
    - Watchlist: Slow Dealers — dealers slower than the selected game's baseline
      by >= 1.50 s or in its slowest 10%, horizontal bar chart with color-coded
      severity and click-to-open dealer dossier
    - Watchlist: High-Variance Shifts — rows where dealer's daily STD_TIMEDIFF
      exceeds 200% of its 30-day moving average, horizontal bar chart (top 30,
      dataZoom slider for the rest, dashed 2.0x threshold line); clicking a bar
      opens that dealer's dossier. Also rendered per-dealer inside each dealer
      dossier panel (top 20 of that dealer's shifts).
      (consistency) for all dealer+table profiles in the selected game
    - Dealer Speed Over Time — daily baseline line plus up to five fastest and
      five slowest dealer trend lines, with dataZoom and a dashed golden markLine
      labeled "Baseline Avg: X.XX s"
    - Top / Bottom 10 Dealer & Table Profiles — horizontal bar chart ranked by
      average time, fastest in green, slowest in red
    - Day-of-the-Week Volatility — highest/lowest bars highlighted in red/green
      for both AVG_TIMEDIFF and STD_TIMEDIFF series, with a centered color
      legend naming the extreme day and value for each series
    - Individualized Dealer Dossier — card grid of dealers with KPIs and a
      per-dealer trend chart (lazy-loaded on click). Filters: baseline
      (above/below), min days (14/30/60+), week-over-week (faster/slower/no-data),
      high-variance shifts (has / none). Clicking a card opens the dealer dossier
      panel with context-switching penalty and per-dealer high-variance shifts
    - Forensics table — full telemetry listing with billing date, game type,
      dealer, table no, avg time and std dev; paginated 100/page
    - Jump to interface — sticky header nav with links to all sections
      (KPIs, Day-of-Week Volatility, both watchlists, Dealer Speed Over Time,
      Efficiency Matrix, Top/Bottom 10 Profiles, Individualized Dealer Dossier,
      Forensics Table)

EOF
