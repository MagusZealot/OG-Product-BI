from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

import os
import csv
from collections import defaultdict

REPORT_DIR = WORKSPACE / "output"

print("=================== 1. WHALE ANALYSIS ===================")
with open(os.path.join(REPORT_DIR, "whale_analysis.csv"), "r", encoding="utf-8") as f:
    whales = list(csv.DictReader(f))

total_whale_debit = sum(float(w["total_debit"]) for w in whales)
total_whale_bets = sum(int(w["total_bets"]) for w in whales)
print(f"Top 20 Whales Total Debit: {total_whale_debit:,.2f}")
print(f"Top 20 Whales Total Bets: {total_whale_bets:,}")

country_stats = defaultdict(lambda: {"count": 0, "debit": 0.0, "bets": 0})
for w in whales:
    c = w["countries"]
    country_stats[c]["count"] += 1
    country_stats[c]["debit"] += float(w["total_debit"])
    country_stats[c]["bets"] += int(w["total_bets"])

for c, s in sorted(country_stats.items(), key=lambda x: x[1]["debit"], reverse=True):
    print(f"  {c}: {s['count']} players, Debit: {s['debit']:,.2f} ({s['debit']/total_whale_debit*100:.2f}%), Bets: {s['bets']:,}")

for i, w in enumerate(whales, 1):
    print(f"  #{i:02d} {w['player_id']}: Debit={float(w['total_debit']):,.0f}, Bets={int(w['total_bets']):,}, AvgSess={w['avg_session_hours']}h, Sessions={w['session_count']}, Country={w['countries']}")

print("\n=================== 2. CHASER DETECTION ===================")
with open(os.path.join(REPORT_DIR, "chaser_detection.csv"), "r", encoding="utf-8") as f:
    chasers = list(csv.DictReader(f))

print(f"Total Chaser Players: {len(chasers):,}")
total_chaser_debit = sum(float(c["total_debit"]) for c in chasers)
total_chaser_winlose = sum(float(c["total_winlose"]) for c in chasers)
print(f"Total Chaser Debit: {total_chaser_debit:,.2f}")
print(f"Total Chaser Win/Lose: {total_chaser_winlose:,.2f}")

# Multiplier brackets
tiers = {
    "Extreme (>= 1,000x)": [],
    "Critical (100x - 999.9x)": [],
    "High (20x - 99.9x)": [],
    "Moderate (5x - 19.9x)": [],
    "Low (< 5x)": []
}

loss_distribution = defaultdict(int)
net_losers = 0
net_winners = 0
breakeven = 0

for c in chasers:
    sm = float(c["spike_multiplier"])
    if sm >= 1000:
        tiers["Extreme (>= 1,000x)"].append(c)
    elif sm >= 100:
        tiers["Critical (100x - 999.9x)"].append(c)
    elif sm >= 20:
        tiers["High (20x - 99.9x)"].append(c)
    elif sm >= 5:
        tiers["Moderate (5x - 19.9x)"].append(c)
    else:
        tiers["Low (< 5x)"].append(c)

    mcl = int(c["max_consecutive_losses"])
    loss_distribution[mcl] += 1

    wl = float(c["total_winlose"])
    if wl < 0:
        net_losers += 1
    elif wl > 0:
        net_winners += 1
    else:
        breakeven += 1

print("\nRisk Severity Tiers:")
for tier, plist in tiers.items():
    tier_debit = sum(float(p["total_debit"]) for p in plist)
    tier_winlose = sum(float(p["total_winlose"]) for p in plist)
    print(f"  {tier}: {len(plist):,} players ({len(plist)/len(chasers)*100:.1f}%), Debit={tier_debit:,.0f}, WinLose={tier_winlose:,.0f}")

print("\nLoss Thresholds (Max Consecutive Losses):")
for k in sorted(loss_distribution.keys()):
    print(f"  Streak {k}: {loss_distribution[k]:,} players ({loss_distribution[k]/len(chasers)*100:.1f}%)")

print(f"\nChasers Financial Reality:")
print(f"  Net Losers: {net_losers:,} ({net_losers/len(chasers)*100:.2f}%)")
print(f"  Net Winners: {net_winners:,} ({net_winners/len(chasers)*100:.2f}%)")
print(f"  Break-even: {breakeven:,}")

top_extreme = chasers[:10]
print("\nTop 10 Extreme Chasers:")
for p in top_extreme:
    print(f"  {p['player_id']}: Mult={float(p['spike_multiplier']):,.1f}x, Streak={p['max_consecutive_losses']}, AvgLossDebit={float(p['avg_loss_debit']):,.0f}, SpikeDebit={float(p['spike_debit']):,.0f}, Debit={float(p['total_debit']):,.0f}, WinLose={float(p['total_winlose']):,.0f}")

print("\n=================== 3. TRAFFIC & TIME SERIES ===================")
with open(os.path.join(REPORT_DIR, "hourly_traffic.csv"), "r", encoding="utf-8") as f:
    hourly = list(csv.DictReader(f))

total_traffic_bets = sum(int(h["Total_Bets"]) for h in hourly)
print(f"Total Bets across 24h: {total_traffic_bets:,}")
for h in hourly:
    b = int(h["Total_Bets"])
    print(f"  {h['Hour']}: {b:,} ({b/total_traffic_bets*100:.2f}%)")

with open(os.path.join(REPORT_DIR, "time_series_analysis.csv"), "r", encoding="utf-8") as f:
    ts_country = list(csv.DictReader(f))
print("\nTime Series by Country:")
for t in ts_country:
    print(f"  {t['Country']}: Total={int(t['Total_Bets']):,}, Peak={t['Peak_Hour']} ({int(t['Peak_Bets']):,}, {t['Peak_Percentage']}%)")

print("\n=================== 4. OPERATOR PERFORMANCE ===================")
with open(os.path.join(REPORT_DIR, "operator_performance.csv"), "r", encoding="utf-8") as f:
    operators = list(csv.DictReader(f))

print(f"Total Operators: {len(operators):,}")
total_op_bets = sum(int(o["Total_Bets"]) for o in operators)
total_op_debit = sum(float(o["Total_Debit"]) for o in operators)
total_op_winlose = sum(float(o["Total_Winlose"]) for o in operators)
print(f"Total Bets: {total_op_bets:,}, Total Debit: {total_op_debit:,.0f}, Total WinLose: {total_op_winlose:,.0f}")

top20_ops = operators[:20]
print("\nTop 20 Operators by Total Debit:")
for o in top20_ops:
    print(f"  {o['Operator']:<20} | Debit={float(o['Total_Debit']):>15,.0f} | WinLose={float(o['Total_Winlose']):>13,.0f} | ROI={o['Operator_ROI_%']:>6}% | Bets={int(o['Total_Bets']):>8,} | Players={o['Unique_Players']:>5} | Country={o['Countries']}")

# Country monopolies/dominance
country_op = defaultdict(list)
for o in operators:
    for c in o["Countries"].split(", "):
        country_op[c].append(o)

print("\nCountry Dominant Operators (Top 1 by Debit per country):")
for c in sorted(country_op.keys()):
    c_ops = sorted(country_op[c], key=lambda x: float(x["Total_Debit"]), reverse=True)
    top_c = c_ops[0]
    c_total_debit = sum(float(x["Total_Debit"]) for x in c_ops)
    market_share = (float(top_c["Total_Debit"]) / c_total_debit * 100) if c_total_debit > 0 else 0
    print(f"  {c:<15}: Top={top_c['Operator']:<20} (Debit={float(top_c['Total_Debit']):,.0f}, Share={market_share:.1f}%, Players={top_c['Unique_Players']})")

