#!/usr/bin/env python3
"""
Regenerate whale_analysis.csv and chaser_detection.csv from unified index
to ensure consistency with player dossiers.
"""
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break


import json
import csv
from pathlib import Path
from collections import defaultdict

REPORT_DIR = Path(WORKSPACE / "output")

# Load unified index
with open(REPORT_DIR / "all_players_index.json", "r", encoding="utf-8") as f:
    unified = json.load(f)

players = {p["pid"]: p for p in unified["players"]}

# Load per-file indices to get session info and spike data
# We need to compute sessions and spike multipliers from the unified chunks
# For now, use unified index data and approximate

print(f"Loaded {len(players)} players from unified index")

# ─── Regenerate whale_analysis.csv ───
# Whale criteria: top players by debit, with session info
# We'll use the unified data and compute sessions from timestamps in chunks

# First, load all unified chunks to get session/timestamp data
import os
from datetime import datetime

chunk_dir = REPORT_DIR / "dossier_chunks"
player_sessions = defaultdict(list)
player_timestamps = defaultdict(list)

for fname in sorted(os.listdir(chunk_dir)):
    if fname.endswith(".js"):
        fpath = chunk_dir / fname
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            if content.startswith("window.DOSSIER_CHUNK_"):
                content = content.split("=", 1)[1].rstrip(";")
                data = json.loads(content)
                for pid, pdata in data.items():
                    if "timestamps" in pdata:
                        player_timestamps[pid].extend(pdata["timestamps"])

# Compute sessions per player (gap > 30 min = new session)
SESSION_GAP = 30 * 60  # 30 minutes in seconds

for pid, timestamps in player_timestamps.items():
    if not timestamps:
        continue
    timestamps.sort()
    sessions = []
    current_session = [timestamps[0]]
    for ts in timestamps[1:]:
        if ts - current_session[-1] <= SESSION_GAP:
            current_session.append(ts)
        else:
            sessions.append(current_session)
            current_session = [ts]
    sessions.append(current_session)
    player_sessions[pid] = sessions

# Build whale data from unified index
whale_rows = []
for pid, pdata in players.items():
    debit = pdata.get("debit", 0)
    bets = pdata.get("bets", 0)
    if bets == 0:
        continue
    
    sessions = player_sessions.get(pid, [])
    session_count = len(sessions)
    
    if session_count == 0:
        avg_session_hours = 0.0
    else:
        total_hours = 0.0
        for sess in sessions:
            if len(sess) >= 2:
                total_hours += (sess[-1] - sess[0]) / 3600.0
            else:
                total_hours += 0.01  # minimal session
        avg_session_hours = total_hours / session_count
    
    countries = pdata.get("country", "")
    
    whale_rows.append({
        "player_id": pid,
        "total_debit": round(debit, 2),
        "total_bets": bets,
        "avg_session_hours": round(avg_session_hours, 4),
        "session_count": session_count,
        "countries": countries
    })

# Sort by debit descending
whale_rows.sort(key=lambda x: x["total_debit"], reverse=True)

# Keep only top 20 whales
whale_rows = whale_rows[:20]

# Write whale_analysis.csv
whale_path = REPORT_DIR / "whale_analysis.csv"
with open(whale_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["player_id", "total_debit", "total_bets", "avg_session_hours", "session_count", "countries"])
    writer.writeheader()
    writer.writerows(whale_rows)

print(f"Written {len(whale_rows)} rows to {whale_path}")

# ─── Regenerate chaser_detection.csv ───
# Chaser criteria: spike multiplier (max single bet / avg bet) and consecutive losses
# We need balance_series and timestamps from chunks to compute this accurately

# Load detailed data from chunks for chaser computation
player_detail = {}
for fname in sorted(os.listdir(chunk_dir)):
    if fname.endswith(".js"):
        fpath = chunk_dir / fname
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            if content.startswith("window.DOSSIER_CHUNK_"):
                content = content.split("=", 1)[1].rstrip(";")
                data = json.loads(content)
                for pid, pdata in data.items():
                    if pid not in player_detail:
                        player_detail[pid] = pdata
                    else:
                        # Should not happen with unified chunks, but merge if needed
                        pass

# Compute chaser metrics from unified data
chaser_rows = []
for pid, pdata in players.items():
    debit = pdata.get("debit", 0)
    winlose = pdata.get("winlose", 0)
    bets = pdata.get("bets", 0)
    avg_bet = pdata.get("avg_bet", 0)
    spike = pdata.get("spike", 0)  # from index
    
    if bets < 10:  # minimum bets for chaser analysis
        continue
    
    detail = player_detail.get(pid, {})
    balance_series = detail.get("balance_series", [])
    timestamps = detail.get("timestamps", [])
    max_consecutive_losses = detail.get("max_consecutive_losses", 0)
    total_losses = detail.get("total_losses", 0)
    total_wins = detail.get("total_wins", 0)
    
    # Compute spike multiplier from balance series if not in index
    if spike == 0 and balance_series:
        non_zero_bets = [b for b in balance_series if b != 0]
        if non_zero_bets:
            max_bet = max(non_zero_bets)
            avg_b = sum(non_zero_bets) / len(non_zero_bets)
            spike = max_bet / avg_b if avg_b > 0 else 0
    
    # Compute chase events (consecutive loss sequences)
    chase_events = 0
    if balance_series:
        in_chase = False
        for b in balance_series:
            if b < 0:  # loss (negative balance change)
                if not in_chase:
                    chase_events += 1
                    in_chase = True
            else:
                in_chase = False
    
    # Average loss debit
    loss_debits = [abs(b) for b in balance_series if b < 0]
    avg_loss_debit = sum(loss_debits) / len(loss_debits) if loss_debits else 0
    
    # Spike debit (max single bet)
    spike_debit = max([abs(b) for b in balance_series]) if balance_series else 0
    
    chaser_rows.append({
        "player_id": pid,
        "total_bets": bets,
        "chase_events": chase_events,
        "max_consecutive_losses": max_consecutive_losses,
        "avg_loss_debit": round(avg_loss_debit, 2),
        "spike_debit": round(spike_debit, 2),
        "spike_multiplier": round(spike, 2),
        "total_debit": round(debit, 2),
        "total_winlose": round(winlose, 2)
    })

# Sort by spike_multiplier descending
chaser_rows.sort(key=lambda x: x["spike_multiplier"], reverse=True)

# Write chaser_detection.csv
chaser_path = REPORT_DIR / "chaser_detection.csv"
with open(chaser_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["player_id", "total_bets", "chase_events", "max_consecutive_losses", "avg_loss_debit", "spike_debit", "spike_multiplier", "total_debit", "total_winlose"])
    writer.writeheader()
    writer.writerows(chaser_rows)

print(f"Written {len(chaser_rows)} rows to {chaser_path}")

print("Done! Summary CSVs now consistent with unified index.")