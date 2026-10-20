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

csv_path = Path(WORKSPACE / "output" / "operator_performance.csv")
with open(csv_path, "r", encoding="utf-8") as f:
    ops = list(csv.DictReader(f))

print(f"Total operators: {len(ops)}")
# Let's inspect operators with highest debit, highest profit, highest margin
for o in ops[:10]:
    debit = float(o["Total_Debit"])
    winlose = float(o["Total_Winlose"])
    roi = float(o["Operator_ROI_%"])
    # If winlose is negative, that means players lost money, so operator gained money!
    # GGR (Gross Gaming Revenue) = -winlose
    # Operator Hold % = (-winlose / debit) * 100 = 100 - roi
    ggr = -winlose
    hold_pct = (ggr / debit * 100) if debit > 0 else 0
    print(f"{o['Operator']:<20}: Debit={debit:>15,.0f}, WinLose={winlose:>13,.0f}, GGR={ggr:>13,.0f}, ROI_col={roi:>6.2f}%, Hold%={hold_pct:>6.2f}%")

print("\n--- Operators with Highest Gross Gaming Revenue (GGR = -Winlose) ---")
by_ggr = sorted(ops, key=lambda x: -float(x["Total_Winlose"]), reverse=True)
for o in by_ggr[:10]:
    debit = float(o["Total_Debit"])
    winlose = float(o["Total_Winlose"])
    ggr = -winlose
    hold = (ggr / debit * 100) if debit > 0 else 0
    print(f"{o['Operator']:<20} | Debit={debit:>14,.0f} | GGR={ggr:>12,.0f} | Hold={hold:>5.2f}% | ROI={o['Operator_ROI_%']:>5}% | Players={o['Unique_Players']:>4} | {o['Countries']}")

print("\n--- Operators with Lowest ROI (Highest Operator Retention) with significant volume (>100k debit) ---")
sig_ops = [o for o in ops if float(o["Total_Debit"]) >= 100000000] # > 100M debit
by_retention = sorted(sig_ops, key=lambda x: float(x["Operator_ROI_%"]))
for o in by_retention[:10]:
    debit = float(o["Total_Debit"])
    winlose = float(o["Total_Winlose"])
    ggr = -winlose
    hold = (ggr / debit * 100) if debit > 0 else 0
    print(f"{o['Operator']:<20} | Debit={debit:>14,.0f} | GGR={ggr:>12,.0f} | Hold={hold:>5.2f}% | ROI={o['Operator_ROI_%']:>5}% | Players={o['Unique_Players']:>4} | {o['Countries']}")

