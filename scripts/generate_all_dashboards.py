#!/usr/bin/env python3
"""
Generate all Oriental Gaming Title dashboards and their source data files.

Runs the complete data pipeline in dependency order:

  Lint check (ruff): runs before pipeline steps to validate Python syntax and conventions.

  1. whale_tracking.py                                      -> output/reports/whale_analysis.csv
  2. time_series_analysis.py                                -> output/reports/time_series_analysis.csv + hourly_traffic.csv
  3. chaser_detection.py                                    -> output/reports/chaser_detection.csv
  4. operator_analysis.py                                   -> output/reports/operator_performance.csv
  5. generate_heatmap_matrix.py                             -> output/reports/country_hourly_heatmap.csv
  6. build_all_players_dossiers.py                          -> output/data/all_players_index_XX.json + output/chunks/dossier_chunks_XX/
  7. generate_player_behavior_data.py                       -> output/data/player_behavior_data.json
  8. build_individual_dossiers.py                           -> output/data/individual_dossiers_data.json (42 players + 35 operators)
  9. prepare_dashboard_data.py                              -> output/data/dashboard_data.json (master BI payload)
  10. generate_dashboard_html.py                            -> output/dashboards/bi_dashboard.html (Main BI Console)
  11. generate_behavior_dashboard_html.py                   -> output/dashboards/player_behavior_dashboard.html
  12. inject_dossier_tabs.py                                -> injects dossier system into behavior console
  13. probability_he_ingest.py                              -> output/game_probability_he_data.json (always refreshes)
  14. generate_probability_dashboard_html.py                -> output/dashboards/game_probability_dashboard.html
  15. round_dealer_table_time_ingest.py                     -> output/round_dealer_table_time_data.json
  16. generate_round_dealer_table_time_dashboard_html.py    -> output/dashboards/round_dealer_table_time_dashboard.html

All scripts use hardcoded absolute paths under the workspace root, so they are
invoked as standalone processes from the workspace working directory.
"""

import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SRC_DIR = WORKSPACE / "src"


def lint_src():
    """Run ruff lint check on all src/ files."""
    print("\n" + "=" * 60)
    print("LINT CHECK (ruff)")
    print("=" * 60)
    result = subprocess.run(
        ["py", "-m", "ruff", "check", str(SRC_DIR), "--select", "E,F,W,N,I"],
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print(f"Lint check found {result.returncode} issue(s). Aborting pipeline.")
        return False
    print("Lint check passed - no issues found.")
    return True


STEPS = [
    ("[1/16] Whale tracking analysis",
     SRC_DIR / "ingest" / "whale_tracking.py"),
    ("[2/16] Time-series and hourly traffic analysis",
     SRC_DIR / "ingest" / "time_series_analysis.py"),
    ("[3/16] Chaser detection analysis",
     SRC_DIR / "ingest" / "chaser_detection.py"),
    ("[4/16] Operator performance analysis",
     SRC_DIR / "ingest" / "operator_analysis.py"),
    ("[5/16] Country x 24h heatmap matrix",
     SRC_DIR / "ingest" / "generate_heatmap_matrix.py"),
    ("[6/16] All-players dossier system (index + trajectory chunks)",
     SRC_DIR / "ingest" / "build_all_players_dossiers.py"),
    ("[7/16] Player behavior telemetry data",
     SRC_DIR / "ingest" / "generate_player_behavior_data.py"),
    ("[8/16] Individual player & operator dossiers",
     SRC_DIR / "ingest" / "build_individual_dossiers.py"),
    ("[9/16] Master BI dashboard payload",
     SRC_DIR / "dashboard" / "prepare_dashboard_data.py"),
    ("[10/16] Main BI & Risk Intelligence Console HTML",
     SRC_DIR / "dashboard" / "generate_dashboard_html.py"),
    ("[11/16] Player Behavioral Intelligence Console HTML",
     SRC_DIR / "dashboard" / "generate_behavior_dashboard_html.py"),
    ("[12/16] Inject dossier tabs into behavior console",
     SRC_DIR / "dashboard" / "inject_dossier_tabs.py"),
    ("[13/16] Refresh game probability / HE source data",
     SRC_DIR / "ingest" / "probability_he_ingest.py"),
    ("[14/16] Game probability / HE dashboard",
     SRC_DIR / "dashboard" / "generate_probability_dashboard_html.py"),
    ("[15/16] Refresh unified dealer & table time source data",
     SRC_DIR / "ingest" / "round_dealer_table_time_ingest.py"),
    ("[16/16] Unified dealer & table time dashboard",
     SRC_DIR / "dashboard" / "generate_round_dealer_table_time_dashboard_html.py"),
]


class ProgressBar:
    """Simple progress bar for visual feedback."""

    def __init__(self, total, prefix="Progress", length=50):
        self.total = total
        self.prefix = prefix
        self.length = length
        self.current = 0
        self.start_time = time.time()

    def update(self, step_name=""):
        self.current += 1
        self._draw(step_name)

    def _draw(self, step_name=""):
        percent = (self.current / self.total) * 100
        filled = int(self.length * self.current // self.total)
        bar = "█" * filled + "░" * (self.length - filled)
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = f" | ETA: {eta:.0f}s"
        else:
            eta_str = ""
        step_info = f" | {step_name}" if step_name else ""
        sys.stdout.write(f"\r{self.prefix}: |{bar}| {percent:5.1f}% ({self.current}/{self.total}){eta_str}{step_info}")
        sys.stdout.flush()

    def finish(self):
        elapsed = time.time() - self.start_time
        bar = "█" * self.length
        sys.stdout.write(f"\r{self.prefix}: |{bar}| 100.0% ({self.total}/{self.total}) | Done in {elapsed:.1f}s\n")
        sys.stdout.flush()


def should_skip_whale_analysis():
    output_dir = WORKSPACE / "output" / "reports"
    fpath = output_dir / "whale_analysis.csv"
    return fpath.exists() and fpath.stat().st_size > 0


def should_skip_time_series():
    output_dir = WORKSPACE / "output" / "reports"
    required = ["time_series_analysis.csv", "hourly_traffic.csv"]
    for fname in required:
        fpath = output_dir / fname
        if not fpath.exists() or fpath.stat().st_size == 0:
            return False
    return True


def should_skip_chaser():
    output_dir = WORKSPACE / "output" / "reports"
    fpath = output_dir / "chaser_detection.csv"
    return fpath.exists() and fpath.stat().st_size > 0


def should_skip_operator():
    output_dir = WORKSPACE / "output" / "reports"
    fpath = output_dir / "operator_performance.csv"
    return fpath.exists() and fpath.stat().st_size > 0


def should_skip_heatmap():
    output_dir = WORKSPACE / "output" / "reports"
    out_file = output_dir / "country_hourly_heatmap.csv"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    data_dir = WORKSPACE / "data" / "raw"
    if not data_dir.exists():
        return True
    out_mtime = out_file.stat().st_mtime
    for csv_file in data_dir.glob("*.csv"):
        if csv_file.stat().st_mtime > out_mtime:
            return False
    return True


def should_skip_all_players_dossiers():
    """Check if all 27 per-export indexes and their chunks exist and are up-to-date."""
    output_dir = WORKSPACE / "output"
    data_dir = WORKSPACE / "data" / "raw"
    if not data_dir.exists():
        return True
    export_files = sorted(data_dir.glob("*EXPORT_CSV*.csv"))
    if not export_files:
        return False
    for f_idx, fpath in enumerate(export_files):
        idx_path = output_dir / "data" / f"all_players_index_{f_idx:02d}.json"
        chunk_dir = output_dir / "chunks" / f"dossier_chunks_{f_idx:02d}"
        if not idx_path.exists() or idx_path.stat().st_size == 0:
            return False
        # Check that all expected chunks exist
        try:
            import json
            with open(idx_path, "r", encoding="utf-8") as f:
                meta = json.load(f).get("meta", {})
            total_chunks = meta.get("total_chunks", 0)
            if total_chunks == 0:
                return False
            for cid in range(total_chunks):
                chunk_path = chunk_dir / f"chunk_{cid:04d}.js"
                if not chunk_path.exists() or chunk_path.stat().st_size == 0:
                    return False
        except (OSError, ValueError, KeyError):
            return False
        # Check if any source file is newer than the index
        idx_mtime = idx_path.stat().st_mtime
        if fpath.stat().st_mtime > idx_mtime:
            return False
    return True


def should_skip_player_behavior():
    output_dir = WORKSPACE / "output" / "data"
    out_file = output_dir / "player_behavior_data.json"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    data_dir = WORKSPACE / "data" / "raw"
    if not data_dir.exists():
        return True
    out_mtime = out_file.stat().st_mtime
    # Only first 5 files are used
    for csv_file in sorted(data_dir.glob("*EXPORT_CSV*.csv"))[:5]:
        if csv_file.stat().st_mtime > out_mtime:
            return False
    return True


def should_skip_individual_dossiers():
    output_dir = WORKSPACE / "output"
    out_file = output_dir / "data" / "individual_dossiers_data.json"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    # Depends on whale, chaser, operator CSVs and first 5 export files
    deps = [
        output_dir / "reports" / "whale_analysis.csv",
        output_dir / "reports" / "chaser_detection.csv",
        output_dir / "reports" / "operator_performance.csv",
    ]
    data_dir = WORKSPACE / "data" / "raw"
    export_files = sorted(data_dir.glob("*EXPORT_CSV*.csv"))[:5]
    deps.extend(export_files)
    out_mtime = out_file.stat().st_mtime
    for dep in deps:
        if not dep.exists() or dep.stat().st_size == 0:
            return False
        if dep.stat().st_mtime > out_mtime:
            return False
    return True


def should_skip_prepare_dashboard():
    output_dir = WORKSPACE / "output"
    out_file = output_dir / "data" / "dashboard_data.json"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    # Depends on all derived CSVs
    deps = [
        output_dir / "reports" / "whale_analysis.csv",
        output_dir / "reports" / "time_series_analysis.csv",
        output_dir / "reports" / "hourly_traffic.csv",
        output_dir / "reports" / "chaser_detection.csv",
        output_dir / "reports" / "operator_performance.csv",
        output_dir / "reports" / "country_hourly_heatmap.csv",
    ]
    out_mtime = out_file.stat().st_mtime
    for dep in deps:
        if not dep.exists() or dep.stat().st_size == 0:
            return False
        if dep.stat().st_mtime > out_mtime:
            return False
    return True


def should_skip_main_dashboard():
    output_dir = WORKSPACE / "output"
    dashboards_dir = output_dir / "dashboards"
    out_file = dashboards_dir / "bi_dashboard.html"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    # Depends on dashboard_data.json, all per-export indexes and chunks, individual_dossiers_data.json
    deps = [
        output_dir / "data" / "dashboard_data.json",
        output_dir / "data" / "individual_dossiers_data.json",
        WORKSPACE / "src" / "dashboard" / "generate_dashboard_html.py",
        *sorted((WORKSPACE / "src" / "dashboard" / "sections").glob("*.html")),
        WORKSPACE / "src" / "dashboard" / "sections" / "dossier.js",
    ]
    # Also check per-export indexes and their chunks exist and are up-to-date
    export_files = sorted((WORKSPACE / "data" / "raw").glob("*EXPORT_CSV*.csv"))
    for f_idx, _ in enumerate(export_files):
        deps.append(output_dir / "data" / f"all_players_index_{f_idx:02d}.json")
        # Check chunk directory mtimes too
        chunk_dir = output_dir / "chunks" / f"dossier_chunks_{f_idx:02d}"
        if chunk_dir.exists():
            for chunk_file in chunk_dir.glob("chunk_*.js"):
                deps.append(chunk_file)
    out_mtime = out_file.stat().st_mtime
    for dep in deps:
        if not dep.exists() or dep.stat().st_size == 0:
            return False
        if dep.stat().st_mtime > out_mtime:
            return False
    return True


def should_skip_behavior_dashboard():
    output_dir = WORKSPACE / "output"
    dashboards_dir = output_dir / "dashboards"
    out_file = dashboards_dir / "player_behavior_dashboard.html"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    # Depends on player_behavior_data.json
    dep = output_dir / "data" / "player_behavior_data.json"
    if not dep.exists() or dep.stat().st_size == 0:
        return False
    out_mtime = out_file.stat().st_mtime
    if dep.stat().st_mtime > out_mtime:
        return False
    return True


def should_skip_inject_dossier_tabs():
    output_dir = WORKSPACE / "output"
    dashboards_dir = output_dir / "dashboards"
    out_file = dashboards_dir / "player_behavior_dashboard.html"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    # Depends on all 27 per-export indexes in output/data/ and individual_dossiers_data.json
    index_files = sorted((output_dir / "data").glob("all_players_index_*.json"))
    if len(index_files) < 27:
        return False
    deps = list(index_files)
    deps.append(output_dir / "data" / "individual_dossiers_data.json")
    out_mtime = out_file.stat().st_mtime
    for dep in deps:
        if not dep.exists() or dep.stat().st_size == 0:
            return False
        if dep.stat().st_mtime > out_mtime:
            return False
    return True


def should_skip_probability_dashboard():
    dashboards_dir = WORKSPACE / "output" / "dashboards"
    out_file = dashboards_dir / "game_probability_dashboard.html"
    dependencies = [
        WORKSPACE / "output" / "game_probability_he_data.json",
        SRC_DIR / "dashboard" / "generate_probability_dashboard_html.py",
    ]
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    out_mtime = out_file.stat().st_mtime
    return all(dep.exists() and dep.stat().st_mtime <= out_mtime for dep in dependencies)


def should_skip_round_dealer_table_ingest():
    output_dir = WORKSPACE / "output"
    out_file = output_dir / "round_dealer_table_time_data.json"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    deps = [
        SRC_DIR / "ingest" / "round_dealer_table_time_ingest.py",
    ]
    out_mtime = out_file.stat().st_mtime
    return all(dep.exists() and dep.stat().st_mtime <= out_mtime for dep in deps)


def should_skip_round_dealer_table_dashboard():
    output_dir = WORKSPACE / "output" / "dashboards"
    out_file = output_dir / "round_dealer_table_time_dashboard.html"
    if not out_file.exists() or out_file.stat().st_size == 0:
        return False
    dependencies = [
        output_dir / "round_dealer_table_time_data.json",
        SRC_DIR / "dashboard" / "generate_round_dealer_table_time_dashboard_html.py",
    ]
    out_mtime = out_file.stat().st_mtime
    return all(dep.exists() and dep.stat().st_mtime <= out_mtime for dep in dependencies)


def run_step(label, script_path):
    """Run a single pipeline step as a standalone process."""
    print(f"\n{'=' * 60}")
    print(f"{label}")
    print(f"  {script_path.name}")
    print(f"{'=' * 60}")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(WORKSPACE),
            check=False,
            text=True,
        )
        if result.returncode == 0:
            print(f"    [OK] {script_path.name} completed")
            return True
        print(f"    [FAIL] {script_path.name} exited with code {result.returncode}")
        return False
    except Exception as e:
        print(f"    [ERROR] {e}")
        return False


def main():
    # Lint check before running pipeline
    if not lint_src():
        return 1

    print("=" * 60)
    print("Oriental Gaming Title - Full Dashboard Pipeline")
    print("=" * 60)
    print(f"\nWorkspace: {WORKSPACE}")
    print(f"Steps: {len(STEPS)}")

    progress = ProgressBar(len(STEPS), "Pipeline Progress", 40)

    failed = []
    for label, script_path in STEPS:
        if not script_path.exists():
            print(f"\n    [SKIP] {script_path.name} not found")
            failed.append((label, "script not found"))
            progress.update(label)
            continue
        # Skip individual analysis steps if outputs already exist
        if label.startswith("[1/16]") and should_skip_whale_analysis():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist")
            progress.update(label)
            continue
        if label.startswith("[2/16]") and should_skip_time_series():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist")
            progress.update(label)
            continue
        if label.startswith("[3/16]") and should_skip_chaser():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist")
            progress.update(label)
            continue
        if label.startswith("[4/16]") and should_skip_operator():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist")
            progress.update(label)
            continue
        if label.startswith("[5/16]") and should_skip_heatmap():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[6/16]") and should_skip_all_players_dossiers():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[7/16]") and should_skip_player_behavior():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[8/16]") and should_skip_individual_dossiers():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[9/16]") and should_skip_prepare_dashboard():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[10/16]") and should_skip_main_dashboard():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[11/16]") and should_skip_behavior_dashboard():
            print(f"\n    [SKIP] {script_path.name} - outputs already exist and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[12/16]") and should_skip_inject_dossier_tabs():
            print(f"\n    [SKIP] {script_path.name} - dossier tabs already injected and current")
            progress.update(label)
            continue
        # Step 13 (probability_he_ingest) intentionally has no skip guard - always runs to refresh
        if label.startswith("[14/16]") and should_skip_probability_dashboard():
            print(f"\n    [SKIP] {script_path.name} - output already exists and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[15/16]") and should_skip_round_dealer_table_ingest():
            print(f"\n    [SKIP] {script_path.name} - output already exists and inputs unchanged")
            progress.update(label)
            continue
        if label.startswith("[16/16]") and should_skip_round_dealer_table_dashboard():
            print(f"\n    [SKIP] {script_path.name} - output already exists and inputs unchanged")
            progress.update(label)
            continue
        if not run_step(label, script_path):
            failed.append((label, script_path.name))
        progress.update(label)

    progress.finish()

    print("\n" + "=" * 60)
    if failed:
        print(f"PIPELINE COMPLETE WITH {len(failed)} FAILURE(S):")
        for label, detail in failed:
            print(f"  - {label}: {detail}")
        return 1

    print("ALL STEPS COMPLETED SUCCESSFULLY")
    print("\nRegenerated outputs:")
    print("  - output/dashboards/bi_dashboard.html")
    print("  - output/dashboards/player_behavior_dashboard.html")
    print("  - output/dashboards/game_probability_dashboard.html")
    print("  - output/game_probability_he_data.json")
    print("  - output/data/dashboard_data.json")
    print("  - output/data/player_behavior_data.json")
    print("  - output/data/all_players_index_00.json ... all_players_index_26.json")
    print("  - output/data/individual_dossiers_data.json")
    print("  - output/chunks/dossier_chunks_00/ ... dossier_chunks_26/")
    print("  - output/reports/whale_analysis.csv")
    print("  - output/reports/chaser_detection.csv")
    print("  - output/reports/operator_performance.csv")
    print("  - output/reports/hourly_traffic.csv")
    print("  - output/reports/time_series_analysis.csv")
    print("  - output/reports/country_hourly_heatmap.csv")
    print("  - output/dashboards/round_dealer_table_time_dashboard.html")
    print("  - output/round_dealer_table_time_data.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
