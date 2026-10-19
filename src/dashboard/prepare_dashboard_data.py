from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(SCRIPT_DIR.parent / "ingest"))
from player_index import PlayerIndexEntry  # noqa: E402


def prepare_dashboard_data(report_dir: Path = WORKSPACE / "output") -> dict:
    # 1. Whale Analysis
    whales = []
    with open(report_dir / "whale_analysis.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            debit = float(r["total_debit"])
            bets = int(r["total_bets"])
            avg_sess = float(r["avg_session_hours"])
            sess_cnt = int(r["session_count"])
            whales.append({
                "player_id": r["player_id"],
                "total_debit": debit,
                "total_bets": bets,
                "avg_session_hours": avg_sess,
                "session_count": sess_cnt,
                "country": r["countries"],
                "avg_bet": round(debit / bets, 2) if bets > 0 else 0,
                "hourly_velocity": round(debit / (avg_sess * (sess_cnt or 1)), 2) if avg_sess > 0 else debit
            })

    whale_country = defaultdict(lambda: {"count": 0, "debit": 0.0, "bets": 0})
    for w in whales:
        c = w["country"]
        whale_country[c]["count"] += 1
        whale_country[c]["debit"] += w["total_debit"]
        whale_country[c]["bets"] += w["total_bets"]

    # 2. Chaser Detection
    chasers_list: list[PlayerIndexEntry] = []
    tiers = {"Extreme (>=1000x)": 0, "Critical (100x-999x)": 0, "High (20x-99x)": 0, "Moderate (5x-19x)": 0, "Low (<5x)": 0}
    tier_debit = defaultdict(float)
    tier_winlose = defaultdict(float)
    loss_dist = defaultdict(int)
    net_losers = 0
    net_winners = 0
    breakeven = 0
    total_chasers = 0
    total_chaser_debit = 0.0
    total_chaser_winlose = 0.0

    with open(report_dir / "chaser_detection.csv", "r", encoding="utf-8") as f:
        for idx, r in enumerate(csv.DictReader(f)):
            total_chasers += 1
            sm = float(r["spike_multiplier"])
            mcl = int(r["max_consecutive_losses"])
            debit = float(r["total_debit"])
            winlose = float(r["total_winlose"])
            total_chaser_debit += debit
            total_chaser_winlose += winlose

            t_name = "Low (<5x)"
            if sm >= 1000: t_name = "Extreme (>=1000x)"
            elif sm >= 100: t_name = "Critical (100x-999x)"
            elif sm >= 20: t_name = "High (20x-99x)"
            elif sm >= 5: t_name = "Moderate (5x-19x)"

            tiers[t_name] += 1
            tier_debit[t_name] += debit
            tier_winlose[t_name] += winlose
            loss_dist[mcl] += 1

            if winlose < 0: net_losers += 1
            elif winlose > 0: net_winners += 1
            else: breakeven += 1

            # Keep top 100 chasers for drilldown table
            if idx < 100:
                chasers_list.append({
                    "player_id": r["player_id"],
                    "total_bets": int(r["total_bets"]),
                    "chase_events": int(r["chase_events"]),
                    "max_consecutive_losses": mcl,
                    "avg_loss_debit": float(r["avg_loss_debit"]),
                    "spike_debit": float(r["spike_debit"]),
                    "spike_multiplier": sm,
                    "total_debit": debit,
                    "total_winlose": winlose,
                    "tier": t_name
                })

    # 3. Traffic Data
    hourly_traffic = []
    with open(report_dir / "hourly_traffic.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            hourly_traffic.append({
                "hour": r["Hour"],
                "bets": int(r["Total_Bets"])
            })

    country_time_series = []
    with open(report_dir / "time_series_analysis.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            country_time_series.append({
                "country": r["Country"],
                "total_bets": int(r["Total_Bets"]),
                "peak_hour": r["Peak_Hour"],
                "peak_bets": int(r["Peak_Bets"]),
                "peak_percentage": float(r["Peak_Percentage"])
            })
    country_time_series.sort(key=lambda x: x["peak_percentage"], reverse=True)

    heatmap_matrix = []
    heatmap_hours = [f"{h:02d}:00" for h in range(24)]
    heatmap_countries = []
    heatmap_data = [] # [country_idx, hour_idx, value]

    with open(report_dir / "country_hourly_heatmap.csv", "r", encoding="utf-8") as f:
        r_list = list(csv.reader(f))
        for c_idx, row in enumerate(r_list[1:]):
            c_name = row[0]
            heatmap_countries.append(c_name)
            vals = [int(v) for v in row[1:25]]
            max_v = max(vals) if vals else 1
            for h_idx, val in enumerate(vals):
                heatmap_data.append({
                    "country": c_name,
                    "country_idx": c_idx,
                    "hour": heatmap_hours[h_idx],
                    "hour_idx": h_idx,
                    "bets": val,
                    "intensity": round(val / max_v, 3) if max_v > 0 else 0
                })

    # 4. Operator Performance
    operators = []
    country_op_map = defaultdict(list)
    with open(report_dir / "operator_performance.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            debit = float(r["Total_Debit"])
            winlose = float(r["Total_Winlose"])
            roi = float(r["Operator_ROI_%"])
            bets = int(r["Total_Bets"])
            players = int(r["Unique_Players"])
            countries = r["Countries"]
            hold = round(100.0 - roi, 2)
            ggr = round(-winlose, 2)

            op_obj = {
                "operator": r["Operator"],
                "total_bets": bets,
                "total_debit": debit,
                "total_winlose": winlose,
                "ggr": ggr,
                "operator_roi": roi,
                "operator_hold_margin": hold,
                "avg_bet": float(r["Avg_Bet"]),
                "unique_players": players,
                "countries": countries
            }
            operators.append(op_obj)
            for c in countries.split(", "):
                country_op_map[c].append(op_obj)

    # Top 50 operators by debit
    top_50_operators = operators[:50]

    # Dominant operator per country
    country_dominance = []
    for c, op_list in sorted(country_op_map.items()):
        c_ops = sorted(op_list, key=lambda x: x["total_debit"], reverse=True)
        top_c = c_ops[0]
        c_total_debit = sum(x["total_debit"] for x in c_ops)
        c_total_bets = sum(x["total_bets"] for x in c_ops)
        share = round((top_c["total_debit"] / c_total_debit * 100), 1) if c_total_debit > 0 else 0
        country_dominance.append({
            "country": c,
            "dominant_operator": top_c["operator"],
            "dominant_debit": top_c["total_debit"],
            "dominant_bets": top_c["total_bets"],
            "dominant_players": top_c["unique_players"],
            "market_share_pct": share,
            "country_total_debit": c_total_debit,
            "total_operators_in_country": len(op_list)
        })
    country_dominance.sort(key=lambda x: x["dominant_debit"], reverse=True)

    # Combine into master JSON
    master_data = {
        "metadata": {
            "generated_at": "August 2026",
            "total_bets": sum(h["bets"] for h in hourly_traffic),
            "total_operators": len(operators),
            "total_chasers": total_chasers,
            "total_whales": 20,
            "total_debit_all_operators": sum(o["total_debit"] for o in operators),
            "total_ggr_all_operators": sum(o["ggr"] for o in operators)
        },
        "whales": {
            "top_20": whales,
            "country_distribution": [
                {"country": c, "count": d["count"], "debit": d["debit"], "bets": d["bets"]}
                for c, d in sorted(whale_country.items(), key=lambda x: x[1]["debit"], reverse=True)
            ],
            "total_debit": sum(w["total_debit"] for w in whales),
            "total_bets": sum(w["total_bets"] for w in whales)
        },
        "chasers": {
            "total_count": total_chasers,
            "total_debit": round(total_chaser_debit, 2),
            "total_winlose": round(total_chaser_winlose, 2),
            "net_losers": net_losers,
            "net_winners": net_winners,
            "breakeven": breakeven,
            "net_loser_pct": round(net_losers / total_chasers * 100, 2),
            "net_winner_pct": round(net_winners / total_chasers * 100, 2),
            "risk_tiers": [
                {"tier": k, "count": tiers[k], "debit": round(tier_debit[k], 2), "winlose": round(tier_winlose[k], 2)}
                for k in tiers
            ],
            "loss_streak_distribution": [
                {"streak": k, "players": loss_dist[k], "pct": round(loss_dist[k] / total_chasers * 100, 2)}
                for k in sorted(loss_dist.keys()) if k <= 25 or loss_dist[k] > 5
            ],
            "top_extreme": chasers_list[:25]
        },
        "traffic": {
            "hourly_curve": hourly_traffic,
            "country_density": country_time_series,
            "heatmap": {
                "hours": heatmap_hours,
                "countries": heatmap_countries,
                "cells": heatmap_data
            }
        },
        "operators": {
            "top_50": top_50_operators,
            "country_dominance": country_dominance,
            "roi_comparison": sorted(
                [o for o in operators if o["total_debit"] >= 500000000][:25], # significant operators
                key=lambda x: x["operator_hold_margin"],
                reverse=True
            )
        }
    }

    return master_data


if __name__ == "__main__":
    out_json = WORKSPACE / "output" / "dashboard_data.json"
    master_data = prepare_dashboard_data()
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(master_data, f, indent=2)
    print(f"Master dashboard data exported to {out_json} ({os.path.getsize(out_json):,} bytes)")
