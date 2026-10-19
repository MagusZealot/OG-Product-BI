#!/usr/bin/env python3
"""
Country x 24-hour bet-count heatmap matrix.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import workspace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from currency_converter import get_country

from ingest.io import iter_raw_rows


def main():
    print("=" * 60)
    print("COUNTRY HOURLY HEATMAP MATRIX")
    print("=" * 60)
    print(f"Target: {workspace.RAW_DIR}")
    print(f"Output: {workspace.OUTPUT_DIR}")

    workspace.OUTPUT_DIR.mkdir(exist_ok=True)
    workspace.update_progress('heatmap_matrix', 'Starting heatmap matrix...', 0)

    csv_files = sorted(workspace.RAW_DIR.glob("*.csv"))
    print(f"Processing {len(csv_files)} files for country hourly heatmap...")
    workspace.update_progress('heatmap_matrix',
                              f'Found {len(csv_files)} CSV files', 5,
                              {'total_files': len(csv_files)})

    country_hourly = defaultdict(lambda: defaultdict(int))
    rows_processed = 0

    for row in iter_raw_rows(workspace.RAW_DIR):
        rows_processed += 1
        curr = (row.get('currency') or '').strip()
        t_str = (row.get('formatted_debit_at') or '').strip()
        if not t_str:
            continue
        try:
            hour = int(t_str[11:13])
            country = get_country(curr)
            country_hourly[country][hour] += 1
        except (ValueError, IndexError):
            pass

        if rows_processed % 100000 == 0:
            workspace.update_progress('heatmap_matrix',
                                      f'Processing rows... ({rows_processed})', None,
                                      {'rows_processed': rows_processed})

    out_file = workspace.OUTPUT_DIR / "country_hourly_heatmap.csv"
    hours = [f"{h:02d}:00" for h in range(24)]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Country"] + hours + ["Total"])
        for country in sorted(country_hourly.keys()):
            row = [country]
            c_total = 0
            for h in range(24):
                val = country_hourly[country][h]
                row.append(val)
                c_total += val
            row.append(c_total)
            writer.writerow(row)

    workspace.update_progress('heatmap_matrix', 'Heatmap matrix complete!', 100,
                              {'countries': len(country_hourly),
                               'total_bets': sum(sum(h.values())
                                                 for h in country_hourly.values())})
    print(f"Successfully generated {out_file}")
    print(f"     Countries: {len(country_hourly)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
