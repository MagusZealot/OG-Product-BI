from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

with open(WORKSPACE / "src" / "dashboard" / "generate_dashboard_html.py", 'r', encoding='utf-8') as f:
    text = f.read()

old_tab = """    // Tab Navigation
    function switchTab(tabId) {{
      if (isPresentationMode) togglePresentationMode();
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

      const targetPane = document.getElementById(`tab-${{tabId}}`);
      if (targetPane) targetPane.classList.remove('hidden');

      // Highlight tab button
      const clickedBtn = Array.from(document.querySelectorAll('.nav-tab')).find(b => b.getAttribute('onclick')?.includes(tabId));
      if (clickedBtn) clickedBtn.classList.add('active');

      // Resize any charts in view
      setTimeout(resizeAllCharts, 100);
    }}"""

new_tab = """    // Tab Navigation
    function switchTab(tabId) {{
      if (isPresentationMode) togglePresentationMode();
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

      const targetPane = document.getElementById(`tab-${{tabId}}`);
      if (targetPane) targetPane.classList.remove('hidden');

      // Highlight tab button
      const clickedBtn = Array.from(document.querySelectorAll('.nav-tab')).find(b => b.getAttribute('onclick')?.includes(tabId));
      if (clickedBtn) clickedBtn.classList.add('active');

      // Initialize or resize charts for active tab
      setTimeout(() => {{
        if (tabId === 'overview') {{
          if (!chartInstances['overviewTraffic']) initOverviewTrafficChart();
          if (!chartInstances['overviewPillar']) initOverviewPillarChart();
        }} else if (tabId === 'whales') {{
          if (!chartInstances['whaleScatter']) initWhaleScatterChart();
          if (!chartInstances['whaleGeo']) initWhaleGeoChart();
        }} else if (tabId === 'chasers') {{
          if (!chartInstances['chaserTiers']) initChaserTiersChart();
          if (!chartInstances['chaserTilt']) initChaserTiltChart();
          if (!chartInstances['chaserOutcome']) initChaserOutcomePie();
        }} else if (tabId === 'traffic') {{
          if (!chartInstances['trafficCurve']) initTrafficCurveChart();
          if (!chartInstances['trafficHeatmap']) initTrafficHeatmapChart();
          if (!chartInstances['trafficDensity']) initTrafficDensityChart();
        }} else if (tabId === 'operators') {{
          if (!chartInstances['operatorRoi']) initOperatorRoiChart();
          if (!chartInstances['operatorBubble']) initOperatorBubbleChart();
        }}
        resizeAllCharts();
      }}, 50);
    }}"""

if old_tab in text:
    text = text.replace(old_tab, new_tab)
    with open('generate_dashboard_html.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Successfully updated generate_dashboard_html.py')
else:
    print('Pattern not found')

