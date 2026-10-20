from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

with open(WORKSPACE / "output" / "bi_dashboard.html", "r", encoding="utf-8") as f:
    text = f.read()

print("File size:", len(text))
tag_start = text.find('<script id="dashboard-raw-data"')
tag_end = text.find('</script>', tag_start)
print("JSON Script tags found:", tag_start, tag_end)
json_text = text[tag_start:tag_end].split(">", 1)[1].strip()
import json
try:
    data = json.loads(json_text)
    print("Parsed JSON successfully!")
    print("Whales:", len(data["whales"]["top_20"]))
    print("Chasers:", data["chasers"]["total_count"])
    print("Hourly traffic:", len(data["traffic"]["hourly_curve"]))
    print("Heatmap countries:", len(data["traffic"]["heatmap"]["countries"]))
    print("Heatmap cells:", len(data["traffic"]["heatmap"]["cells"]))
    print("Operators:", len(data["operators"]["top_50"]))
except Exception as e:
    print("JSON Parse error:", e)

# Check javascript block
js_start = text.find('// Load dataset')
print("JS block starts at:", js_start)
js_block = text[js_start:text.rfind('</script>')]
print("JS block length:", len(js_block))

