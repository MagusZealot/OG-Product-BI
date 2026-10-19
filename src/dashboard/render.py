import json
from pathlib import Path


def _read_section(sections_dir, name):
    path = Path(sections_dir) / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def render_dashboard(data_file, sections_dir, output_html, title, extra_scripts):
    data_file = Path(data_file)
    sections_dir = Path(sections_dir)
    output_html = Path(output_html)

    with open(data_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    json_str = json.dumps(payload)

    nav_html = _read_section(sections_dir, "nav_buttons.html")
    tabs_html = (_read_section(sections_dir, "tab_players.html") + "\n"
                 + _read_section(sections_dir, "tab_operators.html"))
    slides_html = _read_section(sections_dir, "slides.html")
    dossier_js = _read_section(sections_dir, "dossier.js")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <link rel="stylesheet" href="dashboard-common.css">
  <script>
    tailwind.config = {{
      darkMode: 'class',
    }}
  </script>
</head>
<body>
  {nav_html}
  {slides_html}
  {tabs_html}

  <script id="dashboard-raw-data" type="application/json">
{json_str}
  </script>

  <script>
    const DATA = JSON.parse(document.getElementById('dashboard-raw-data').textContent);
    let chartInstances = {{}};

    function isDark() {{
      return document.documentElement.classList.contains('dark');
    }}

    function getChartTheme() {{
      const dark = isDark();
      return {{
        bg: 'transparent',
        textColor: dark ? '#94a3b8' : '#475569',
        titleColor: dark ? '#f8fafc' : '#0f172a',
        gridBorder: dark ? '#1e293b' : '#e2e8f0',
        tooltipBg: dark ? '#0f172a' : '#ffffff',
        tooltipBorder: dark ? '#334155' : '#cbd5e1',
        tooltipText: dark ? '#ffffff' : '#0f172a'
      }};
    }}

    function initCharts() {{
    }}

    function reinitAllCharts() {{
      Object.values(chartInstances).forEach(c => c && c.dispose());
      chartInstances = {{}};
      initCharts();
    }}

    function resizeAllCharts() {{
      Object.values(chartInstances).forEach(c => c && c.resize());
    }}
    window.addEventListener('resize', resizeAllCharts);

    document.addEventListener('DOMContentLoaded', () => {{
      initCharts();
    }});
  </script>

  {dossier_js}
  {extra_scripts}
</body>
</html>"""

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")
