from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

import json

file_path = WORKSPACE / "output" / "player_behavior_dashboard.html"
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

print(f"File size: {len(text):,} characters")
start_tag = text.find('<script id="behavior-raw-data" type="application/json">')
end_tag = text.find('</script>', start_tag)
json_text = text[start_tag:end_tag].split('>', 1)[1].strip()

try:
    d = json.loads(json_text)
    print("Parsed behavior JSON successfully!")
    print(f"  Processed rows: {d['metadata']['processed_rows']:,}")
    print(f"  Games tracked: {len(d['games'])}")
    print(f"  Hourly credit/win points: {len(d['hourly_credit_and_wins'])}")
    print(f"  Frequency intervals: {len(d['bet_frequency_intervals'])}")
    print(f"  Balance-bet scatter points: {len(d['balance_vs_bet_scatter'])}")
    print(f"  Balance tiers: {len(d['balance_tiers'])}")
    print(f"  Bet brackets: {len(d['bet_brackets'])}")
    print(f"  Devices: {len(d['devices'])}")
except Exception as e:
    print("Error parsing JSON:", e)

# Also check for unescaped double braces in the script
js_part = text[end_tag:]
for idx, line in enumerate(js_part.splitlines(), 1):
    if "{{" in line or "}}" in line:
        print(f"Suspicious line {idx}: {line}")
print("Verification complete!")

