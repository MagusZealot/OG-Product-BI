#!/usr/bin/env python3
"""
Operator Performance Analysis - Profitability by operator
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR.parent))
from currency_converter import get_country

import workspace
from ingest.io import iter_raw_rows


def main():
    print("=" * 60)
    print("OPERATOR PERFORMANCE ANALYSIS")
    print("=" * 60)
    print(f"Target: {workspace.RAW_DIR}")
    print(f"Output: {workspace.OUTPUT_DIR}")

    workspace.OUTPUT_DIR.mkdir(exist_ok=True)
    workspace.update_progress('operator_analysis', 'Starting operator analysis...', 0)

    if not workspace.RAW_DIR.exists():
        print(f"ERROR: Folder not found: {workspace.RAW_DIR}")
        workspace.update_progress('error', 'Folder not found', 0)
        return 1

    csv_files = sorted(workspace.RAW_DIR.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files")
    workspace.update_progress('operator_analysis', f'Found {len(csv_files)} CSV files', 5,
                              {'total_files': len(csv_files)})

    if len(csv_files) == 0:
        print("ERROR: No CSV files found!")
        workspace.update_progress('error', 'No CSV files found', 0)
        return 1

    operator_data = defaultdict(lambda: {
        'total_winlose': 0.0,
        'total_debit': 0.0,
        'total_bets': 0,
        'players': set(),
        'countries': set()
    })

    rows_processed = 0
    for row in iter_raw_rows(workspace.RAW_DIR):
        rows_processed += 1

        operator = (row.get('operator_name') or '').strip()
        if not operator:
            operator = 'UNKNOWN'

        player_id = (row.get('player_id') or '').strip()
        country = get_country(row.get('currency') or '')

        operator_data[operator]['total_winlose'] += row['winlose_php']
        operator_data[operator]['total_debit'] += row['debit_php']
        operator_data[operator]['total_bets'] += 1
        if player_id:
            operator_data[operator]['players'].add(player_id)
        operator_data[operator]['countries'].add(country)

        if rows_processed % 25000 == 0:
            pct = 10 + min(40, int((rows_processed / 100000) * 40))
            workspace.update_progress('operator_analysis',
                                      f'Processing rows ({rows_processed})...', pct,
                                      {'rows_processed': rows_processed})

    operator_summary = []
    for operator, data in operator_data.items():
        total_winlose = data['total_winlose']
        total_debit = data['total_debit']
        total_bets = data['total_bets']

        roi = ((total_debit + total_winlose) / total_debit * 100) if total_debit > 0 else 0
        avg_bet = total_debit / total_bets if total_bets > 0 else 0

        operator_summary.append({
            'Operator': operator,
            'Total_Bets': total_bets,
            'Total_Debit': round(total_debit, 2),
            'Total_Winlose': round(total_winlose, 2),
            'Operator_ROI_%': round(roi, 2),
            'Avg_Bet': round(avg_bet, 2),
            'Unique_Players': len(data['players']),
            'Countries': ', '.join(sorted(data['countries']))
        })

    operator_summary.sort(key=lambda x: x['Total_Debit'], reverse=True)

    output_file = workspace.OUTPUT_DIR / "operator_performance.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Operator', 'Total_Bets', 'Total_Debit',
                                               'Total_Winlose', 'Operator_ROI_%',
                                               'Avg_Bet', 'Unique_Players', 'Countries'])
        writer.writeheader()
        writer.writerows(operator_summary)

    workspace.update_progress('operator_analysis', 'Operator analysis complete!', 100,
                              {'total_operators': len(operator_summary)})

    print(f"\n[OK] Operator performance: {workspace.OUTPUT_DIR / 'operator_performance.csv'}")
    print(f"     Operators analyzed: {len(operator_summary)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
