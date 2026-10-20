from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

import csv

# Check all raw CSV files for this player's game types
import glob
import os

folder = WORKSPACE / "data" / "raw"
files = sorted(glob.glob(os.path.join(folder, '*EXPORT_CSV*.csv')))

all_games_raw = {}
total_rows = 0

for fpath in files:
    with open(fpath, 'r', encoding='utf-8-sig', errors='replace', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('player_id') == 'p02cf17391168':
                total_rows += 1
                game = row.get('game_name', 'Unknown')
                if game not in all_games_raw:
                    all_games_raw[game] = 0
                all_games_raw[game] += 1

print('Raw CSV game counts for player:')
for game, count in sorted(all_games_raw.items(), key=lambda x: x[1], reverse=True):
    print('  ' + game + ': ' + str(count))
print('Total rows: ' + str(total_rows))