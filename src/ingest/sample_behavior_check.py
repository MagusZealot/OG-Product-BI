from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

import csv
import glob
import os
from collections import defaultdict
from pathlib import Path

FOLDER = Path(WORKSPACE / "data" / "raw")
files = sorted(FOLDER.glob("*EXPORT_CSV*.csv"))
print(f"Total CSV export files: {len(files)}")

# Sample analysis on first 3 files to inspect values, game names, devicetypes, balance stats
game_counts = defaultdict(int)
game_debit = defaultdict(float)
game_credit = defaultdict(float)
game_winlose = defaultdict(float)
game_wins = defaultdict(int)
game_losses = defaultdict(int)
game_ties = defaultdict(int)
device_counts = defaultdict(int)

sample_files = files[:3]
total_rows = 0

for fpath in sample_files:
    print(f"Reading sample: {fpath.name}")
    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            total_rows += 1
            g = r.get("game_name", "Unknown").strip() or "Unknown"
            dev = r.get("devicetype", "Unknown").strip() or "Unknown"
            debit = float(r.get("debit_amount", 0) or 0)
            credit = float(r.get("credit_amount", 0) or 0)
            winlose = float(r.get("winlose_amount", 0) or 0)
            
            game_counts[g] += 1
            game_debit[g] += debit
            game_credit[g] += credit
            game_winlose[g] += winlose
            device_counts[dev] += 1
            
            if winlose > 0:
                game_wins[g] += 1
            elif winlose < 0:
                game_losses[g] += 1
            else:
                game_ties[g] += 1

print(f"\nAnalyzed {total_rows:,} sample rows across {len(sample_files)} files.")
print("\n=== GAME BREAKDOWN ===")
for g, cnt in sorted(game_counts.items(), key=lambda x: x[1], reverse=True):
    deb = game_debit[g]
    cred = game_credit[g]
    wl = game_winlose[g]
    wins = game_wins[g]
    losses = game_losses[g]
    ties = game_ties[g]
    win_rate = (wins / cnt * 100) if cnt > 0 else 0
    rtp = (cred / deb * 100) if deb > 0 else 0
    print(f"{g:<20} | Bets: {cnt:>8,} ({cnt/total_rows*100:>5.1f}%) | Debit: {deb:>15,.0f} | WinRate: {win_rate:>5.1f}% | RTP: {rtp:>6.2f}% | AvgBet: {deb/cnt:>8,.1f}")

print("\n=== DEVICE TYPE BREAKDOWN ===")
for d, cnt in sorted(device_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{d:<15}: {cnt:,} ({cnt/total_rows*100:.1f}%)")

