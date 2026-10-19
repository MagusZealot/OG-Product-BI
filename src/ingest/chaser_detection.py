#!/usr/bin/env python3
"""
Chaser Detection - Problem Gambling Indicator (Consecutive losses + debit spike)
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

chase_threshold_losses = 3
chase_spike_multiplier = 3


def main():
    print("=" * 60)
    print("CHASER DETECTION (Problem Gambling)")
    print("=" * 60)
    print(f"Target: {workspace.RAW_DIR}")
    print(f"Output: {workspace.OUTPUT_DIR}")

    workspace.OUTPUT_DIR.mkdir(exist_ok=True)
    workspace.update_progress('chaser_detection', 'Starting chaser detection...', 0)

    if not workspace.RAW_DIR.exists():
        print(f"ERROR: Folder not found: {workspace.RAW_DIR}")
        workspace.update_progress('error', 'Folder not found', 0)
        return 1

    csv_files = sorted(workspace.RAW_DIR.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files")
    workspace.update_progress('chaser_detection', f'Found {len(csv_files)} CSV files', 5,
                              {'total_files': len(csv_files)})

    if len(csv_files) == 0:
        print("ERROR: No CSV files found!")
        workspace.update_progress('error', 'No CSV files found', 0)
        return 1

    player_sequences = defaultdict(list)

    for row in iter_raw_rows(workspace.RAW_DIR):
        player_id = (row.get('player_id') or '').strip()
        if not player_id:
            continue

        timestamp_str = (row.get('formatted_debit_at') or '').strip()
        winlose_php = row['winlose_php']
        debit_php = row['debit_php']

        if timestamp_str:
            try:
                ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                player_sequences[player_id].append((ts, winlose_php, debit_php))
            except ValueError:
                pass

    workspace.update_progress('chaser_detection', 'Analyzing player sequences...', 55,
                              {'total_players': len(player_sequences)})

    chasers = []

    for player_id, sequence in player_sequences.items():
        if len(sequence) < 5:
            continue

        sequence.sort(key=lambda x: x[0])

        consecutive_losses = 0
        loss_start_idx = 0
        chase_events = []

        for idx, (ts, winlose, debit) in enumerate(sequence):
            if winlose < 0:
                if consecutive_losses == 0:
                    loss_start_idx = idx
                consecutive_losses += 1
            else:
                if consecutive_losses >= chase_threshold_losses:
                    loss_bets = sequence[loss_start_idx:idx]
                    avg_loss_debit = sum(b[2] for b in loss_bets) / len(loss_bets) if loss_bets else 0

                    post_loss_bets = sequence[idx:idx + 3]
                    if post_loss_bets:
                        spike_debits = [b[2] for b in post_loss_bets]
                        max_spike = max(spike_debits)

                        if avg_loss_debit > 0 and max_spike > avg_loss_debit * chase_spike_multiplier:
                            chase_events.append({
                                'loss_streak': consecutive_losses,
                                'avg_loss_debit': avg_loss_debit,
                                'spike_debit': max_spike,
                                'spike_multiplier': max_spike / avg_loss_debit
                            })

                consecutive_losses = 0

        if chase_events:
            worst_chase = max(chase_events, key=lambda x: x['spike_multiplier'])

            chasers.append({
                'player_id': player_id,
                'total_bets': len(sequence),
                'chase_events': len(chase_events),
                'max_consecutive_losses': worst_chase['loss_streak'],
                'avg_loss_debit': round(worst_chase['avg_loss_debit'], 2),
                'spike_debit': round(worst_chase['spike_debit'], 2),
                'spike_multiplier': round(worst_chase['spike_multiplier'], 2),
                'total_debit': round(sum(b[2] for b in sequence), 2),
                'total_winlose': round(sum(b[1] for b in sequence), 2)
            })

    chasers.sort(key=lambda x: x['spike_multiplier'], reverse=True)

    output_file = workspace.OUTPUT_DIR / "chaser_detection.csv"
    if chasers:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['player_id', 'total_bets', 'chase_events',
                                                   'max_consecutive_losses', 'avg_loss_debit',
                                                   'spike_debit', 'spike_multiplier',
                                                   'total_debit', 'total_winlose'])
            writer.writeheader()
            writer.writerows(chasers)

    workspace.update_progress('chaser_detection', 'Chaser detection complete!', 100,
                              {'total_players': len(player_sequences), 'chasers': len(chasers)})

    print(f"\n[OK] Chaser detection: {output_file}")
    print(f"     Flagged {len(chasers)} chasers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
