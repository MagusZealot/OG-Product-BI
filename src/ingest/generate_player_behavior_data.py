import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.workspace import OUTPUT_DIR, RAW_DIR
from src.ingest import io
from src.ingest.currency_converter import convert_to_php, get_country

files = sorted(RAW_DIR.glob("*EXPORT_CSV*.csv"))

selected_files = files[:5]
print(f"Processing {len(selected_files)} files for Player Behavior Deep-Dive...")

game_stats = defaultdict(lambda: {
    "bets": 0, "debit": 0.0, "credit": 0.0, "winlose": 0.0,
    "wins": 0, "losses": 0, "ties": 0, "players": set(),
    "balances": [], "bets_list": []
})

hourly_timing = defaultdict(lambda: {
    "total_bets": 0, "wins": 0, "losses": 0, "ties": 0,
    "debit": 0.0, "credit": 0.0, "winlose": 0.0
})

device_stats = defaultdict(lambda: {
    "bets": 0, "debit": 0.0, "wins": 0, "losses": 0, "players": set()
})

balance_tiers = {
    "< 1K": defaultdict(int),
    "1K - 10K": defaultdict(int),
    "10K - 100K": defaultdict(int),
    "100K - 1M": defaultdict(int),
    "1M - 10M": defaultdict(int),
    "> 10M": defaultdict(int)
}

balance_bet_points = []
inter_bet_intervals = defaultdict(int)
player_prev_time = {}

bet_progression = {
    "after_win_increased": 0,
    "after_win_decreased": 0,
    "after_win_same": 0,
    "after_loss_increased": 0,
    "after_loss_decreased": 0,
    "after_loss_same": 0
}
player_prev_bet = {}
player_prev_outcome = {}

bet_brackets = {
    "Micro (< 100)": 0,
    "Low (100 - 1K)": 0,
    "Medium (1K - 10K)": 0,
    "High (10K - 100K)": 0,
    "VIP (100K - 1M)": 0,
    "Whale (> 1M)": 0
}

total_processed = 0

for f_idx, fpath in enumerate(selected_files, 1):
    t0 = datetime.now()
    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            total_processed += 1
            pid = r.get("player_id", "").strip()
            g = r.get("game_name", "Unknown").strip() or "Unknown"
            dev = r.get("devicetype", "Unknown").strip() or "Unknown"
            debit = float(r.get("debit_amount", 0) or 0)
            credit = float(r.get("credit_amount", 0) or 0)
            winlose = float(r.get("winlose_amount", 0) or 0)
            
            try:
                bal = float(r.get("balance", 0) or 0)
            except ValueError:
                bal = 0.0

            currency = r.get("currency", "").strip()
            debit_time_str = r.get("formatted_debit_at", "").strip()
            
            debit_php = convert_to_php(debit, currency, debit_time_str)
            credit_php = convert_to_php(credit, currency, debit_time_str)
            winlose_php = convert_to_php(winlose, currency, debit_time_str)
            bal_php = convert_to_php(bal, currency, debit_time_str)

            dev_norm = "Mobile" if "mobile" in dev.lower() else ("Desktop" if "desktop" in dev.lower() else "Other")
            device_stats[dev_norm]["bets"] += 1
            device_stats[dev_norm]["debit"] += debit_php
            if pid: device_stats[dev_norm]["players"].add(pid)
            if winlose_php > 0: device_stats[dev_norm]["wins"] += 1
            elif winlose_php < 0: device_stats[dev_norm]["losses"] += 1

            gs = game_stats[g]
            gs["bets"] += 1
            gs["debit"] += debit_php
            gs["credit"] += credit_php
            gs["winlose"] += winlose_php
            if pid: gs["players"].add(pid)
            if winlose_php > 0: gs["wins"] += 1
            elif winlose_php < 0: gs["losses"] += 1
            else: gs["ties"] += 1
            
            if len(gs["balances"]) < 5000:
                gs["balances"].append(bal_php)
                gs["bets_list"].append(debit_php)

            if debit_php > 1000000: bet_brackets["Whale (> 1M)"] += 1
            elif debit_php >= 100000: bet_brackets["VIP (100K - 1M)"] += 1
            elif debit_php >= 10000: bet_brackets["High (10K - 100K)"] += 1
            elif debit_php >= 1000: bet_brackets["Medium (1K - 100K)"] += 1
            elif debit_php >= 100: bet_brackets["Low (100 - 1K)"] += 1
            else: bet_brackets["Micro (< 100)"] += 1

            credit_time_str = r.get("formatted_credit_at", "").strip()
            if credit_time_str and len(credit_time_str) >= 13:
                try:
                    c_hour = int(credit_time_str[11:13])
                    ht = hourly_timing[c_hour]
                    ht["total_bets"] += 1
                    ht["debit"] += debit_php
                    ht["credit"] += credit_php
                    ht["winlose"] += winlose_php
                    if winlose_php > 0: ht["wins"] += 1
                    elif winlose_php < 0: ht["losses"] += 1
                    else: ht["ties"] += 1
                except ValueError:
                    pass

            b_tier = "< 1K"
            if bal_php >= 10000000: b_tier = "> 10M"
            elif bal_php >= 1000000: b_tier = "1M - 10M"
            elif bal_php >= 100000: b_tier = "100K - 1M"
            elif bal_php >= 10000: b_tier = "10K - 100K"
            elif bal_php >= 1000: b_tier = "1K - 10K"
            balance_tiers[b_tier][g] += 1

            if total_processed % 350 == 0 and len(balance_bet_points) < 1500:
                if bal_php > 0 and debit_php > 0:
                    balance_bet_points.append({
                        "balance": round(bal_php, 2),
                        "bet": round(debit_php, 2),
                        "game": g,
                        "ratio_pct": round((debit_php / bal_php) * 100, 2) if bal_php > 0 else 0,
                        "outcome": "Win" if winlose_php > 0 else ("Loss" if winlose_php < 0 else "Tie")
                    })

            if pid and debit_time_str:
                try:
                    dt = datetime.strptime(debit_time_str, "%Y-%m-%d %H:%M:%S")
                    if pid in player_prev_time:
                        prev_dt = player_prev_time[pid]
                        delta_sec = (dt - prev_dt).total_seconds()
                        if 0 <= delta_sec <= 1800:
                            if delta_sec < 5: inter_bet_intervals["< 5s (Hyper-Speed)"] += 1
                            elif delta_sec <= 15: inter_bet_intervals["5s - 15s (Fast)"] += 1
                            elif delta_sec <= 30: inter_bet_intervals["15s - 30s (Round Pace)"] += 1
                            elif delta_sec <= 60: inter_bet_intervals["30s - 60s (Paced)"] += 1
                            else: inter_bet_intervals["> 60s (Deliberate)"] += 1

                    if pid in player_prev_bet and pid in player_prev_outcome:
                        prev_b = player_prev_bet[pid]
                        prev_out = player_prev_outcome[pid]
                        if prev_out == "win":
                            if debit_php > prev_b * 1.05: bet_progression["after_win_increased"] += 1
                            elif debit_php < prev_b * 0.95: bet_progression["after_win_decreased"] += 1
                            else: bet_progression["after_win_same"] += 1
                        elif prev_out == "loss":
                            if debit_php > prev_b * 1.05: bet_progression["after_loss_increased"] += 1
                            elif debit_php < prev_b * 0.95: bet_progression["after_loss_decreased"] += 1
                            else: bet_progression["after_loss_same"] += 1

                    player_prev_time[pid] = dt
                    player_prev_bet[pid] = debit_php
                    player_prev_outcome[pid] = "win" if winlose_php > 0 else ("loss" if winlose_php < 0 else "tie")
                except ValueError:
                    pass

    print(f"[{f_idx}/{len(selected_files)}] Processed in {(datetime.now() - t0).total_seconds():.1f}s")

games_summary = []
for g, s in game_stats.items():
    cnt = s["bets"]
    deb = s["debit"]
    cred = s["credit"]
    wl = s["winlose"]
    avg_b = sum(s["balances"]) / len(s["balances"]) if s["balances"] else 0
    avg_d = sum(s["bets_list"]) / len(s["bets_list"]) if s["bets_list"] else 0
    ratio = (avg_d / avg_b * 100) if avg_b > 0 else 0
    games_summary.append({
        "game": g,
        "total_bets": cnt,
        "total_debit": round(deb, 2),
        "total_credit": round(cred, 2),
        "ggr": round(-wl, 2),
        "win_rate_pct": round(s["wins"] / cnt * 100, 2) if cnt > 0 else 0,
        "loss_rate_pct": round(s["losses"] / cnt * 100, 2) if cnt > 0 else 0,
        "tie_rate_pct": round(s["ties"] / cnt * 100, 2) if cnt > 0 else 0,
        "rtp_pct": round(cred / deb * 100, 2) if deb > 0 else 0,
        "hold_margin_pct": round(-wl / deb * 100, 2) if deb > 0 else 0,
        "avg_bet": round(deb / cnt, 2) if cnt > 0 else 0,
        "unique_players": len(s["players"]),
        "avg_player_balance": round(avg_b, 2),
        "avg_bet_to_balance_pct": round(ratio, 2)
    })

games_summary.sort(key=lambda x: x["total_bets"], reverse=True)

hourly_list = []
for h in range(24):
    ht = hourly_timing[h]
    tot = ht["total_bets"]
    wr = (ht["wins"] / tot * 100) if tot > 0 else 0
    rtp = (ht["credit"] / ht["debit"] * 100) if ht["debit"] > 0 else 0
    hourly_list.append({
        "hour": f"{h:02d}:00",
        "total_bets": tot,
        "wins": ht["wins"],
        "losses": ht["losses"],
        "ties": ht["ties"],
        "win_rate_pct": round(wr, 2),
        "total_debit": round(ht["debit"], 2),
        "total_credit": round(ht["credit"], 2),
        "net_ggr": round(-ht["winlose"], 2),
        "rtp_pct": round(rtp, 2)
    })

balance_tier_matrix = []
for tier, g_dict in balance_tiers.items():
    t_total = sum(g_dict.values())
    row = {"tier": tier, "total_bets": t_total, "games": {}}
    for g, cnt in g_dict.items():
        row["games"][g] = {
            "count": cnt,
            "pct": round(cnt / t_total * 100, 2) if t_total > 0 else 0
        }
    balance_tier_matrix.append(row)

devices_summary = []
for d, s in device_stats.items():
    tot = s["bets"]
    wr = (s["wins"] / tot * 100) if tot > 0 else 0
    devices_summary.append({
        "device": d,
        "total_bets": tot,
        "total_debit": round(s["debit"], 2),
        "avg_bet": round(s["debit"] / tot, 2) if tot > 0 else 0,
        "win_rate_pct": round(wr, 2),
        "unique_players": len(s["players"])
    })

master_behavior_data = {
    "metadata": {
        "processed_rows": total_processed,
        "files_sampled": len(selected_files),
        "audit_period": "August 2026"
    },
    "games": games_summary,
    "hourly_credit_and_wins": hourly_list,
    "bet_frequency_intervals": [
        {"interval": k, "count": inter_bet_intervals[k], "pct": round(inter_bet_intervals[k] / sum(inter_bet_intervals.values()) * 100, 2) if inter_bet_intervals else 0}
        for k in sorted(inter_bet_intervals.keys())
    ],
    "balance_vs_bet_scatter": balance_bet_points,
    "balance_tiers": balance_tier_matrix,
    "bet_brackets": [
        {"bracket": k, "count": bet_brackets[k], "pct": round(bet_brackets[k] / total_processed * 100, 2)}
        for k in bet_brackets
    ],
    "bet_progression": {
        "after_loss": {
            "increased": bet_progression["after_loss_increased"],
            "decreased": bet_progression["after_loss_decreased"],
            "same": bet_progression["after_loss_same"]
        },
        "after_win": {
            "increased": bet_progression["after_win_increased"],
            "decreased": bet_progression["after_win_decreased"],
            "same": bet_progression["after_win_same"]
        }
    },
    "devices": devices_summary
}

out_file = OUTPUT_DIR / "player_behavior_data.json"
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(master_behavior_data, f, indent=2)

print(f"Exported master player behavior data to {out_file} ({Path(out_file).stat().st_size:,} bytes)")
