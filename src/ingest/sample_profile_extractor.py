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
from collections import defaultdict
import json

FOLDER = Path(WORKSPACE / "data" / "raw")
REPORT_DIR = Path(WORKSPACE / "output")

# 1. Load Whales and Top Chasers to identify the key players to profile
whales = []
with open(REPORT_DIR / "whale_analysis.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        whales.append(r["player_id"])

chasers = []
with open(REPORT_DIR / "chaser_detection.csv", "r", encoding="utf-8") as f:
    for idx, r in enumerate(csv.DictReader(f)):
        if idx < 30: # top 30 chasers
            chasers.append(r["player_id"])

target_players = set(whales + chasers)
print(f"Target player profiles to build: {len(target_players)}")

# Top operators
ops = []
with open(REPORT_DIR / "operator_performance.csv", "r", encoding="utf-8") as f:
    for idx, r in enumerate(csv.DictReader(f)):
        if idx < 30:
            ops.append(r["Operator"])

target_operators = set(ops)
print(f"Target operator profiles to build: {len(target_operators)}")

# We will scan the first 4-5 export files to aggregate granular game breakdown, hourly curves, and balance trends
files = sorted(FOLDER.glob("*EXPORT_CSV*.csv"))[:5]

player_profiles = defaultdict(lambda: {
    "player_id": "",
    "total_debit": 0.0,
    "total_credit": 0.0,
    "total_winlose": 0.0,
    "total_bets": 0,
    "wins": 0, "losses": 0, "ties": 0,
    "balances": [],
    "games": defaultdict(lambda: {"bets": 0, "debit": 0.0, "wins": 0}),
    "operators": defaultdict(int),
    "devices": defaultdict(int),
    "currencies": defaultdict(int),
    "hours": defaultdict(int),
    "history": [] # sample of round outcomes
})

operator_profiles = defaultdict(lambda: {
    "operator": "",
    "total_debit": 0.0,
    "total_credit": 0.0,
    "total_winlose": 0.0,
    "total_bets": 0,
    "wins": 0, "losses": 0, "ties": 0,
    "players": defaultdict(lambda: {"bets": 0, "debit": 0.0, "winlose": 0.0}),
    "games": defaultdict(lambda: {"bets": 0, "debit": 0.0, "credit": 0.0}),
    "devices": defaultdict(int),
    "hours": defaultdict(int)
})

row_count = 0
for fpath in files:
    print(f"Reading {fpath.name}...")
    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            row_count += 1
            pid = r.get("player_id", "").strip()
            op = r.get("operator_name", "").strip() or "UNKNOWN"
            g = r.get("game_name", "Unknown").strip() or "Unknown"
            dev = r.get("devicetype", "Unknown").strip() or "Unknown"
            curr = r.get("currency", "").strip()
            debit = float(r.get("debit_amount", 0) or 0)
            credit = float(r.get("credit_amount", 0) or 0)
            winlose = float(r.get("winlose_amount", 0) or 0)
            
            try:
                bal = float(r.get("balance", 0) or 0)
            except ValueError:
                bal = 0.0

            time_str = r.get("formatted_debit_at", "").strip()
            h = int(time_str[11:13]) if len(time_str) >= 13 else 0

            # Collect for target players
            if pid in target_players:
                p = player_profiles[pid]
                p["player_id"] = pid
                p["total_debit"] += debit
                p["total_credit"] += credit
                p["total_winlose"] += winlose
                p["total_bets"] += 1
                if winlose > 0: p["wins"] += 1
                elif winlose < 0: p["losses"] += 1
                else: p["ties"] += 1
                if len(p["balances"]) < 500: p["balances"].append(bal)
                
                pg = p["games"][g]
                pg["bets"] += 1
                pg["debit"] += debit
                if winlose > 0: pg["wins"] += 1
                
                p["operators"][op] += 1
                p["devices"][dev] += 1
                p["currencies"][curr] += 1
                p["hours"][h] += 1
                
                if len(p["history"]) < 30:
                    p["history"].append({
                        "time": time_str,
                        "game": g,
                        "debit": debit,
                        "credit": credit,
                        "winlose": winlose,
                        "balance": bal
                    })

            # Collect for target operators
            if op in target_operators:
                o = operator_profiles[op]
                o["operator"] = op
                o["total_debit"] += debit
                o["total_credit"] += credit
                o["total_winlose"] += winlose
                o["total_bets"] += 1
                if winlose > 0: o["wins"] += 1
                elif winlose < 0: o["losses"] += 1
                else: o["ties"] += 1

                if pid:
                    op_p = o["players"][pid]
                    op_p["bets"] += 1
                    op_p["debit"] += debit
                    op_p["winlose"] += winlose

                og = o["games"][g]
                og["bets"] += 1
                og["debit"] += debit
                og["credit"] += credit

                o["devices"][dev] += 1
                o["hours"][h] += 1

print(f"\nProcessed {row_count:,} rows. Found profiles for {len(player_profiles)} players and {len(operator_profiles)} operators.")

# Check sample player
if player_profiles:
    sample_pid = list(player_profiles.keys())[0]
    sp = player_profiles[sample_pid]
    print(f"Sample Player: {sample_pid}")
    print(f"  Debit: {sp['total_debit']:,.2f}, WinLose: {sp['total_winlose']:,.2f}, Bets: {sp['total_bets']}")
    print(f"  Games: {dict(sp['games'])}")

