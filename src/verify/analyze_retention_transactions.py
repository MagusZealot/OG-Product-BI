from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

import csv
from pathlib import Path

p = Path(WORKSPACE / "output")

with open(p / "operator_performance.csv", "r", encoding="utf-8") as f:
    ops = list(csv.DictReader(f))

for o in ops:
    players = int(o["Unique_Players"])
    bets = int(o["Total_Bets"])
    o["bets_per_player"] = bets / players if players > 0 else 0

ops.sort(key=lambda x: x["bets_per_player"], reverse=True)
print("=== TOP 10 OPERATORS BY BETS PER PLAYER (High Engagement/Retention) ===")
for o in ops[:10]:
    print(f"{o['Operator']:<20} ({o['Countries']:<12}): {o['bets_per_player']:>7.1f} bets/player | Bets: {int(o['Total_Bets']):>8,} | Players: {int(o['Unique_Players']):>5}")

print("\n=== LOWEST OPERATORS BY BETS PER PLAYER (Players >= 50, High Churn / Low Frequency) ===")
low_ops = [o for o in ops if int(o["Unique_Players"]) >= 50]
low_ops.sort(key=lambda x: x["bets_per_player"])
for o in low_ops[:10]:
    print(f"{o['Operator']:<20} ({o['Countries']:<12}): {o['bets_per_player']:>7.1f} bets/player | Bets: {int(o['Total_Bets']):>8,} | Players: {int(o['Unique_Players']):>5}")

# Chaser analysis for retention
with open(p / "chaser_detection.csv", "r", encoding="utf-8") as f:
    chasers = list(csv.DictReader(f))

# Let's inspect total bets of net losers vs net winners among chasers
loser_bets = sum(int(c["total_bets"]) for c in chasers if float(c["total_winlose"]) < 0)
winner_bets = sum(int(c["total_bets"]) for c in chasers if float(c["total_winlose"]) > 0)
print(f"\nChasers bets count: Net Losers ({loser_bets:,} bets) vs Net Winners ({winner_bets:,} bets)")
print(f"Avg bets per net loser chaser: {loser_bets / 8105:.1f}")
print(f"Avg bets per net winner chaser: {winner_bets / 3858:.1f}")

# Whales session frequency vs bet frequency
with open(p / "whale_analysis.csv", "r", encoding="utf-8") as f:
    whales = list(csv.DictReader(f))

print("\nWhales Bet Velocity:")
for w in whales[:5]:
    debit = float(w["total_debit"])
    bets = int(w["total_bets"])
    hours = float(w["avg_session_hours"])
    print(f"  {w['player_id']}: {bets:,} bets in {hours}h avg sessions -> Bet Rate: {bets/hours:.0f} bets/hour" if hours > 0 else f"  {w['player_id']}: {bets} bets")

