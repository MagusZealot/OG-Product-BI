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
from datetime import datetime

FOLDER = Path(WORKSPACE / "data" / "raw")
files = sorted(FOLDER.glob("*EXPORT_CSV*.csv"))

# Inspect 2 files thoroughly for:
# 1. Balance distribution & Balance-to-Debit ratio
# 2. Credit/Win times by hour
# 3. Inter-bet intervals (frequency)
# 4. Game correlations

balance_tiers = {
    "< 1K": defaultdict(int),
    "1K - 10K": defaultdict(int),
    "10K - 100K": defaultdict(int),
    "100K - 1M": defaultdict(int),
    "1M - 10M": defaultdict(int),
    "> 10M": defaultdict(int)
}

balance_bet_ratios = defaultdict(list)
hourly_wins = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0, "credit_total": 0.0, "debit_total": 0.0})
game_balance_avg = defaultdict(list)
game_debit_avg = defaultdict(list)

player_prev_time = {}
inter_bet_intervals = defaultdict(int) # <5s, 5-15s, 15-30s, 30-60s, >60s

sample_files = files[:2]
row_count = 0

for fpath in sample_files:
    print(f"Reading {fpath.name}...")
    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            row_count += 1
            pid = r.get("player_id", "").strip()
            g = r.get("game_name", "Unknown").strip() or "Unknown"
            debit = float(r.get("debit_amount", 0) or 0)
            credit = float(r.get("credit_amount", 0) or 0)
            winlose = float(r.get("winlose_amount", 0) or 0)
            bal_str = r.get("balance", "0").strip()
            try:
                bal = float(bal_str)
            except ValueError:
                bal = 0.0
            
            # Hourly credit / win times
            debit_time_str = r.get("formatted_debit_at", "").strip()
            credit_time_str = r.get("formatted_credit_at", "").strip()
            if credit_time_str and len(credit_time_str) >= 13:
                try:
                    c_hour = int(credit_time_str[11:13])
                    if winlose > 0:
                        hourly_wins[c_hour]["wins"] += 1
                    elif winlose < 0:
                        hourly_wins[c_hour]["losses"] += 1
                    else:
                        hourly_wins[c_hour]["ties"] += 1
                    hourly_wins[c_hour]["credit_total"] += credit
                    hourly_wins[c_hour]["debit_total"] += debit
                except ValueError:
                    pass
            
            # Balance Tier vs Game
            b_tier = "< 1K"
            if bal >= 10000000: b_tier = "> 10M"
            elif bal >= 1000000: b_tier = "1M - 10M"
            elif bal >= 100000: b_tier = "100K - 1M"
            elif bal >= 10000: b_tier = "10K - 100K"
            elif bal >= 1000: b_tier = "1K - 10K"
            balance_tiers[b_tier][g] += 1
            
            if bal > 0 and debit > 0:
                ratio = round((debit / bal) * 100, 1)
                if len(balance_bet_ratios[g]) < 1000:
                    balance_bet_ratios[g].append(ratio)
            
            if len(game_balance_avg[g]) < 5000:
                game_balance_avg[g].append(bal)
                game_debit_avg[g].append(debit)
                
            # Inter-bet intervals (Frequency)
            if pid and debit_time_str:
                try:
                    dt = datetime.strptime(debit_time_str, "%Y-%m-%d %H:%M:%S")
                    if pid in player_prev_time:
                        prev_dt = player_prev_time[pid]
                        delta_sec = (dt - prev_dt).total_seconds()
                        if 0 <= delta_sec <= 3600: # within 1 hour session
                            if delta_sec < 5: inter_bet_intervals["< 5s (Hyper-Speed)"] += 1
                            elif delta_sec <= 15: inter_bet_intervals["5s - 15s (Fast)"] += 1
                            elif delta_sec <= 30: inter_bet_intervals["15s - 30s (Round Pace)"] += 1
                            elif delta_sec <= 60: inter_bet_intervals["30s - 60s (Paced)"] += 1
                            else: inter_bet_intervals["> 60s (Deliberate)"] += 1
                    player_prev_time[pid] = dt
                except ValueError:
                    pass

print(f"\nProcessed {row_count:,} rows.")

print("\n=== BALANCE TIER TO GAME SELECTION ===")
for b_tier, g_counts in balance_tiers.items():
    tier_total = sum(g_counts.values())
    print(f"Tier {b_tier:<10} (Total: {tier_total:>8,} bets):")
    for g, cnt in sorted(g_counts.items(), key=lambda x: x[1], reverse=True)[:4]:
        pct = (cnt / tier_total * 100) if tier_total > 0 else 0
        print(f"   {g:<15}: {cnt:>7,} ({pct:>5.1f}%)")

print("\n=== GAME BALANCE & BET AVERAGES ===")
for g in game_balance_avg:
    b_list = game_balance_avg[g]
    d_list = game_debit_avg[g]
    avg_b = sum(b_list) / len(b_list) if b_list else 0
    avg_d = sum(d_list) / len(d_list) if d_list else 0
    r_list = balance_bet_ratios.get(g, [])
    avg_ratio = sum(r_list) / len(r_list) if r_list else 0
    print(f"{g:<18}: Avg Balance: {avg_b:>12,.1f} | Avg Bet: {avg_d:>10,.1f} | Avg Bet-to-Bal Ratio: {avg_ratio:>5.1f}%")

print("\n=== INTER-BET TIME INTERVALS (BETTING FREQUENCY) ===")
int_total = sum(inter_bet_intervals.values())
for k, cnt in sorted(inter_bet_intervals.items()):
    pct = (cnt / int_total * 100) if int_total > 0 else 0
    print(f"{k:<25}: {cnt:>8,} ({pct:>5.1f}%)")

print("\n=== HOURLY WIN TIMING SAMPLE (Hours 00, 06, 12, 18, 20) ===")
for h in [0, 6, 12, 18, 20]:
    hw = hourly_wins[h]
    tot = hw["wins"] + hw["losses"] + hw["ties"]
    wr = (hw["wins"] / tot * 100) if tot > 0 else 0
    rtp = (hw["credit_total"] / hw["debit_total"] * 100) if hw["debit_total"] > 0 else 0
    print(f"Hour {h:02d}:00 | Total: {tot:>7,} | Wins: {hw['wins']:>6,} ({wr:>4.1f}%) | Debit: {hw['debit_total']:>12,.0f} | Credit: {hw['credit_total']:>12,.0f} | RTP: {rtp:>6.2f}%")

