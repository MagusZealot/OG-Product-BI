#!/usr/bin/env python3
"""
Whale Tracking Analysis - Pareto Principle (Top 20% generating 80% of debit)
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR.parent))
import workspace
from ingest.io import iter_raw_rows


def main():
    print("=" * 60)
    print("WHALE TRACKING ANALYSIS")
    print("=" * 60)
    print(f"Target: {workspace.RAW_DIR}")
    print(f"Output: {workspace.OUTPUT_DIR}")

    workspace.OUTPUT_DIR.mkdir(exist_ok=True)
    workspace.update_progress('whale_tracking', 'Starting whale tracking analysis...', 0)

    if not workspace.RAW_DIR.exists():
        print(f"ERROR: Folder not found: {workspace.RAW_DIR}")
        workspace.update_progress('error', 'Folder not found', 0)
        return 1

    csv_files = sorted(workspace.RAW_DIR.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files")
    workspace.update_progress('whale_tracking', f'Found {len(csv_files)} CSV files', 5,
                              {'total_files': len(csv_files)})

    if len(csv_files) == 0:
        print("ERROR: No CSV files found!")
        workspace.update_progress('error', 'No CSV files found', 0)
        return 1

    player_debit = defaultdict(float)
    player_bets = defaultdict(int)
    player_sessions = defaultdict(list)
    player_countries = defaultdict(set)

    rows_processed = 0
    for row in iter_raw_rows(workspace.RAW_DIR):
        rows_processed += 1

        player_id = (row.get('player_id') or '').strip()
        if not player_id:
            continue

        debit_php = row['debit_php']
        currency = (row.get('currency') or '').strip()
        timestamp_str = (row.get('formatted_debit_at') or '').strip()

        player_debit[player_id] += debit_php
        player_bets[player_id] += 1
        player_countries[player_id].add(currency)

        if timestamp_str:
            try:
                ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                player_sessions[player_id].append(ts)
            except ValueError:
                pass

        if rows_processed % 25000 == 0:
            pct = 5 + min(40, int((rows_processed / 100000) * 40))
            workspace.update_progress('whale_tracking',
                                      f'Processing rows ({rows_processed})...', pct,
                                      {'rows_processed': rows_processed})

    total_debit = sum(player_debit.values())
    sorted_players = sorted(player_debit.items(), key=lambda x: x[1], reverse=True)

    cumulative_debit = 0
    whale_count_80 = 0
    whale_threshold_80 = 0

    for idx, (player_id, debit) in enumerate(sorted_players, 1):
        cumulative_debit += debit
        cumulative_pct = (cumulative_debit / total_debit) * 100

        if cumulative_pct >= 80 and whale_count_80 == 0:
            whale_threshold_80 = debit
            whale_count_80 = idx

    whales = [(pid, debit) for pid, debit in sorted_players if debit >= whale_threshold_80]

    workspace.update_progress('whale_tracking', 'Analyzing whale behavior...', 50,
                              {'total_players': len(player_debit), 'whales': len(whales)})

    whale_sessions = []
    for player_id, debit in whales[:20]:
        sessions = player_sessions.get(player_id, [])
        if sessions:
            sessions_sorted = sorted(sessions)
            session_times = []
            for i in range(0, len(sessions_sorted) - 1, 2):
                if i + 1 < len(sessions_sorted):
                    duration = (sessions_sorted[i+1] - sessions_sorted[i]).total_seconds() / 3600
                    session_times.append(duration)

            avg_session = sum(session_times) / len(session_times) if session_times else 0
            countries = list(player_countries.get(player_id, ['Unknown']))

            whale_sessions.append({
                'player_id': player_id,
                'total_debit': debit,
                'total_bets': player_bets[player_id],
                'avg_session_hours': round(avg_session, 2),
                'session_count': len(sessions),
                'countries': ', '.join(countries)
            })

    if whale_sessions:
        output_file = workspace.OUTPUT_DIR / "whale_analysis.csv"
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['player_id', 'total_debit', 'total_bets',
                                                   'avg_session_hours', 'session_count', 'countries'])
            writer.writeheader()
            writer.writerows(whale_sessions)

    workspace.update_progress('whale_tracking', 'Whale tracking complete!', 100,
                              {'total_players': len(player_debit), 'whales': len(whales)})

    print(f"\n[OK] Whale analysis: {workspace.OUTPUT_DIR / 'whale_analysis.csv'}")
    print(f"     Found {len(whales)} whales ({whale_count_80} players = 80% of debit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
