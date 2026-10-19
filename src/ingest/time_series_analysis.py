#!/usr/bin/env python3
"""
Time-Series Analysis by Country - Peak traffic hours
"""
import csv
import importlib.util
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workspace import RAW_DIR, OUTPUT_DIR, update_progress

sys.path.insert(0, str(Path(__file__).resolve().parent))
from currency_converter import CURRENCY_COUNTRY

_io_path = Path(__file__).resolve().parent / "io.py"
_io_spec = importlib.util.spec_from_file_location("ingest_io", str(_io_path))
_ingest_io = importlib.util.module_from_spec(_io_spec)
_io_spec.loader.exec_module(_ingest_io)
iter_raw_rows = _ingest_io.iter_raw_rows


def main():
    print("=" * 60)
    print("TIME-SERIES ANALYSIS BY COUNTRY")
    print("=" * 60)
    print(f"Target: {RAW_DIR}")
    print(f"Output: {OUTPUT_DIR}")

    update_progress('time_series', 'Starting time-series analysis...', 0)

    if not RAW_DIR.exists():
        print(f"ERROR: Folder not found: {RAW_DIR}")
        update_progress('error', 'Folder not found', 0)
        return 1

    csv_files = sorted(RAW_DIR.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files")
    update_progress('time_series', f'Found {len(csv_files)} CSV files', 5,
                    {'total_files': len(csv_files)})

    if len(csv_files) == 0:
        print("ERROR: No CSV files found!")
        update_progress('error', 'No CSV files found', 0)
        return 1

    hourly_data = defaultdict(int)
    country_hourly = defaultdict(lambda: defaultdict(int))

    count = 0
    for row in iter_raw_rows(RAW_DIR):
        timestamp_str = row.get('formatted_debit_at', '')
        currency = row.get('currency', '')

        if not timestamp_str:
            continue

        try:
            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            hour = ts.hour
            hourly_data[hour] += 1

            country = CURRENCY_COUNTRY.get(currency, 'Unknown')
            country_hourly[country][hour] += 1
        except ValueError:
            pass

        count += 1
        if count % 100000 == 0:
            update_progress('time_series', f'Processing rows... ({count})', None,
                            {'rows': count})

    country_summary = []
    for country in sorted(country_hourly.keys()):
        hours = country_hourly[country]
        total_country_bets = sum(hours.values())
        peak_hour, peak_count = max(hours.items(), key=lambda x: x[1])

        country_summary.append({
            'Country': country,
            'Total_Bets': total_country_bets,
            'Peak_Hour': f"{peak_hour:02d}:00",
            'Peak_Bets': peak_count,
            'Peak_Percentage': round((peak_count / total_country_bets) * 100, 2)
        })

    output_file = OUTPUT_DIR / "time_series_analysis.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Country', 'Total_Bets', 'Peak_Hour',
                                               'Peak_Bets', 'Peak_Percentage'])
        writer.writeheader()
        writer.writerows(country_summary)

    hourly_output = OUTPUT_DIR / "hourly_traffic.csv"
    with open(hourly_output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Hour', 'Total_Bets'])
        for hour, count in sorted(hourly_data.items()):
            writer.writerow([f"{hour:02d}:00", count])

    update_progress('time_series', 'Time-series analysis complete!', 100,
                    {'countries': len(country_summary),
                     'total_bets': sum(hourly_data.values())})

    print(f"\n[OK] Time-series analysis: {OUTPUT_DIR / 'time_series_analysis.csv'}")
    print(f"[OK] Hourly traffic: {OUTPUT_DIR / 'hourly_traffic.csv'}")
    print(f"     Countries analyzed: {len(country_summary)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
