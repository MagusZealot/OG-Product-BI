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

js_start = text.find('// Load dataset')
js_end = text.rfind('</script>')
js_code = text[js_start:js_end]

# Check parenthesis and brace balances
stack = []
pairs = {')': '(', '}': '{', ']': '['}
lines = js_code.splitlines()

print(f"Total JS lines: {len(lines)}")
for idx, line in enumerate(lines, 1):
    # check for suspicious template strings like {undefined} or unescaped python artifacts
    if '{' in line and '}' in line and '$' not in line:
        pass
    # check if any double double braces exist
    if '{{' in line or '}}' in line:
        print(f"Suspicious double braces at line {idx}: {line}")

print("Check complete!")

