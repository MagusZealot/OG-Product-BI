#!/usr/bin/env python3
"""Generate the standalone game probability and house-edge dashboard."""
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.txt").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.txt").exists():
            WORKSPACE = _parent
            break


import json
import sys
from pathlib import Path

WORKSPACE = Path(WORKSPACE)
sys.path.insert(0, str(SCRIPT_DIR))
from render import render_dashboard

DATA_FILE = WORKSPACE / "output" / "game_probability_he_data.json"
OUT_FILE = WORKSPACE / "output" / "dashboards" / "game_probability_dashboard.html"


def build_dashboard():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Probability data payload not found: {DATA_FILE}")

    with open(DATA_FILE, "r", encoding="utf-8") as source:
        data = json.load(source)

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Game Probability &amp; House Edge Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <link rel="stylesheet" href="dashboard-common.css">
  <style>
    :root { color-scheme: dark; font-family: Inter, "Segoe UI", sans-serif; background: #090e1a; color: #e2e8f0; scroll-behavior: smooth; }
    * { box-sizing: border-box; }
    body { margin: 0; min-width: 320px; background: radial-gradient(ellipse at top, #14213a 0, #090e1a 55%); }
    header { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; padding: 16px max(20px, calc((100vw - 1480px) / 2)); background: #0b1220ed; border-bottom: 1px solid #253247; backdrop-filter: blur(12px); }
    h1 { margin: 0; font-size: clamp(18px, 2.4vw, 26px); letter-spacing: .02em; }
    header p { margin: 5px 0 0; color: #93a4bc; font-size: 12px; }
    nav { display: flex; flex-wrap: wrap; gap: 8px; }
    nav a { padding: 9px 12px; border: 1px solid #344258; border-radius: 9px; color: #b9c7da; text-decoration: none; font-size: 12px; background: #111b2d; }
    nav a:hover { border-color: #34d399; color: #6ee7b7; }
    main { max-width: 1480px; margin: auto; padding: 22px; }
    .hero { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 18px; }
    .hero h2 { margin: 0; font-size: 18px; }
    .hero p, .muted { color: #94a3b8; font-size: 12px; }
    .filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }
    select, input[type="date"] { padding: 9px 12px; border: 1px solid #344258; border-radius: 8px; background: #111b2d; color: #e2e8f0; font-family: inherit; font-size: 12px; }
    .kpis { display: grid; grid-template-columns: repeat(5, minmax(130px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .card { border: 1px solid #24334a; border-radius: 14px; background: linear-gradient(145deg, #121d30e8, #0c1423f2); box-shadow: 0 10px 30px #0002; }
    .kpi { padding: 16px; }
    .kpi label { display: block; margin-bottom: 8px; color: #91a2ba; font-size: 10px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; }
    .kpi strong { font: 700 21px ui-monospace, Consolas, monospace; color: #f8fafc; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .chart-card { min-width: 0; padding: 15px; }
    .chart-card h3 { margin: 0 0 3px; font-size: 14px; }
    .chart { width: 100%; height: 350px; }
    .wide { grid-column: 1 / -1; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; white-space: nowrap; font-size: 12px; }
    th, td { padding: 10px 12px; border-bottom: 1px solid #253247; text-align: right; }
    th { color: #90a3bd; font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }
    td:first-child, th:first-child { text-align: left; }
    .table-total td { color: #f8fafc; font-weight: 700; background: #16213a80; }
    .game-sections { display: contents; }
    .grid.nested { margin-top: 12px; }
    .chart-card.single { margin-top: 12px; }
    .chart.tall { height: 430px; }
    article[id] { scroll-margin-top: 200px; }
    header .filters { flex-basis: 100%; align-items: center; margin-top: 10px; padding-top: 8px; border-top: 1px solid #253247; }
    .quick-nav { flex-basis: 100%; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 12px; padding-top: 10px; border-top: 1px solid #253247; }
    .quick-nav .quick-nav-label { color: #77869c; font-size: 10px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; margin-right: 2px; }
    .quick-nav a { padding: 5px 10px; border: 1px solid #2b3b57; border-radius: 7px; background: #0f1a2e; color: #9fb2ca; text-decoration: none; font-size: 11px; font-weight: 600; white-space: nowrap; }
    .quick-nav a:hover { border-color: #34d399; color: #6ee7b7; }
    .quick-nav a.game-link { color: #8fa3bd; }
    .quick-nav a.game-link:hover { border-color: #38bdf8; color: #7dd3fc; }
    .alert { margin: 14px 0; padding: 12px 15px; border: 1px solid #854d0e; border-radius: 10px; background: #713f121f; color: #fcd34d; font-size: 12px; }
    .alert.good { border-color: #166534; background: #14532d22; color: #86efac; }
    .date-range-reset { padding: 9px 12px; border: 1px solid #344258; border-radius: 8px; background: #111b2d; color: #b9c7da; font-size: 12px; cursor: pointer; transition: all .15s ease; }
    .date-range-reset:hover { border-color: #fb7185; color: #fda4af; }
    footer { padding: 22px 0 8px; color: #77869c; font-size: 11px; }
    @media (max-width: 900px) { .kpis { grid-template-columns: repeat(3, 1fr); } .grid { grid-template-columns: 1fr; } .wide { grid-column: auto; } }
    @media (max-width: 560px) { main { padding: 14px; } .kpis { grid-template-columns: repeat(2, 1fr); } .chart { height: 300px; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1><i class="fa-solid fa-dice" style="color:#34d399"></i> Game Probability &amp; House Edge</h1>
      <p id="feedStatus">Loading latest probability feed…</p>
    </div>
    <nav aria-label="Dashboards">
      <a href="bi_dashboard.html"><i class="fa-solid fa-chart-line"></i> BI Console</a>
      <a href="player_behavior_dashboard.html"><i class="fa-solid fa-gamepad"></i> Player Behavior</a>
      <a href="round_dealer_table_time_dashboard.html"><i class="fa-solid fa-gauge-high"></i> Dealer & Table Pace</a>
    </nav>
    <div class="filters">
      <label class="muted" for="periodFilter">Trend window<br><select id="periodFilter"><option value="7">Latest 7 days</option><option value="90">Latest 90 days</option><option value="365">Latest 365 days</option><option value="all">All available dates</option></select></label>
      <label class="muted" for="startDate">Start date<br><input type="date" id="startDate"></label>
      <label class="muted" for="endDate">End date<br><input type="date" id="endDate"></label>
      <button type="button" class="date-range-reset" id="resetDateRange" title="Clear the date range and fall back to the trend window"><i class="fa-solid fa-rotate-left"></i> Reset range</button>
    </div>
    <nav class="quick-nav" id="quickNav" aria-label="Quick navigation"></nav>
  </header>
  <main>
    <section class="hero">
      <div>
        <h2>Every game at a glance: combined trends and per-game detail</h2>
        <p>Percent values follow the source feed. Probability breaches are actual probability above threshold.</p>
      </div>
    </section>
    <div id="coverageAlert"></div>
    <section id="kpis" class="kpis"></section>
    <section class="grid">
      <article class="card chart-card wide" id="combinedPanel">
        <h3>Combined Summary — all games</h3>
        <div class="muted" id="combinedNote">Pooled daily means across every game type · follows the trend window and date range</div>
      </article>
      <article class="card chart-card"><h3>Probability vs expected probability and threshold</h3><div class="muted" id="probCompareNote">Compare the observed probability with the model and configured limit</div><div id="probCompare" class="chart"></div></article>
      <article class="card chart-card"><h3>Overall probability and threshold trend — all games</h3><div class="muted">Pooled daily mean actual vs expected probability and threshold</div><div id="combinedProb" class="chart"></div></article>
      <article class="card chart-card wide"><h3>Average actual vs expected HE by game</h3><div class="muted" id="heCompareNote">Daily bet-place records pooled across the selected history</div><div id="heCompare" class="chart"></div></article>
      <article class="card chart-card wide" id="breachAnalytics">
        <h3>Threshold Breach Analytics</h3>
        <div class="muted" id="breachNote">Rows where actual probability exceeds the configured threshold · follows the trend window and date range</div>
        <div class="grid nested">
          <article class="card chart-card wide"><h3>Number of times threshold exceeded by betting area</h3><div class="muted">Every betting area ranked by breaches in view · drag the axis slider to scroll the full list</div><div id="breachByPlace" class="chart"></div></article>
          <article class="card chart-card"><h3>Breach frequency calendar</h3><div class="muted">Daily count of threshold breaches across all games</div><div id="breachCalendar" class="chart tall"></div></article>
          <article class="card chart-card"><h3>Number of times threshold exceeded by billing date</h3><div class="muted">Stacked daily breach counts by game type</div><div id="breachByDate" class="chart"></div></article>
          <article class="card chart-card wide"><h3>Number of times threshold exceeded by game type</h3><div class="muted">Breaches in view per game, with full-history totals in the tooltip</div><div id="breachByGame" class="chart"></div></article>
        </div>
      </article>
      <div class="game-sections" id="gameSections"></div>
      <article class="card chart-card wide"><h3>Latest bet-place relationship: actual probability vs actual HE</h3><div class="muted">Each point is a bet place on the latest billing date; triangles indicate probability above threshold</div><div id="relationship" class="chart"></div></article>
      <article class="card chart-card wide" id="gameSummary"><h3>Game type summary</h3><div class="table-wrap"><table><thead><tr><th>Game</th><th>Days</th><th>HE rows</th><th>Actual HE</th><th>Expected HE</th><th>HE delta</th><th>Actual prob.</th><th>Expected prob.</th><th>Threshold</th><th>Breach rows %</th></tr></thead><tbody id="summaryRows"></tbody></table></div></article>
    </section>
    <footer>Source: daily published CSV snapshots. Missing dates are retained as gaps; no metric is interpolated. Refresh this dashboard by running the dashboard pipeline.</footer>
  </main>
  <script id="probability-data" type="application/json">__PAYLOAD__</script>
  <script>
    const DATA = JSON.parse(document.getElementById('probability-data').textContent);
    const colors = ['#38bdf8','#34d399','#fbbf24','#c084fc','#fb7185','#2dd4bf','#a3e635','#f97316'];
    const chartIds = ['heCompare','probCompare','combinedProb','breachCalendar','breachByDate','breachByGame','breachByPlace','relationship'];
    const charts = Object.fromEntries(chartIds.map(id => [id, echarts.init(document.getElementById(id))]));
    const gameCharts = [];
    const number = value => value == null ? '—' : `${Number(value).toFixed(2)}%`;
    const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[character]));
    const pair = (object, key) => object && object[key] || [];
    const axisStyle = { axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#334155' } }, splitLine: { lineStyle: { color: '#253247', type: 'dashed' } } };
    const tooltipStyle = { backgroundColor: '#0f172a', borderColor: '#334155', textStyle: { color: '#f8fafc' } };
    const trendCommon = {
      tooltip: { ...tooltipStyle, trigger: 'axis' }, legend: { textStyle: { color: '#cbd5e1' } },
      grid: { left: 58, right: 20, top: 45, bottom: 38 },
      xAxis: { type: 'time', ...axisStyle }, yAxis: { type: 'value', ...axisStyle },
      dataZoom: [
        { type: 'inside' },
        { type: 'slider', height: 14, bottom: 4, borderColor: '#334155', textStyle: { color: '#94a3b8', fontSize: 8 } }
      ]
    };
    const types = DATA.game_types || [];
    const gameAnchors = [];
    const gameHeAvailable = [];
    const usedAnchors = new Set();
    const slugify = value => String(value).toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    const uniqueGameAnchor = gameType => {
      let anchor = `game-${slugify(gameType)}`;
      let suffix = 2;
      while (usedAnchors.has(anchor)) anchor = `game-${slugify(gameType)}-${suffix++}`;
      usedAnchors.add(anchor);
      return anchor;
    };

    function renderKpis() {
      const m = DATA.meta;
      const tiles = [
        ['Latest snapshot', m.latest_file_date],
        ['Billing date range', `${m.billing_date_min} – ${m.billing_date_max}`],
        ['Game types', m.game_types.length],
        ['Bet places', m.bet_places_tracked],
        ['Missing snapshots', m.files_missing_count]
      ];
      document.getElementById('kpis').innerHTML = tiles.map(([label, value]) => `<div class="card kpi"><label>${escapeHtml(label)}</label><strong>${escapeHtml(value)}</strong></div>`).join('');
      document.getElementById('feedStatus').textContent = `Updated ${m.generated_at} · ${Number(m.files_available).toLocaleString()} snapshots · ${Number(m.unique_keys).toLocaleString()} unique daily bet-place records`;
      const gaps = DATA.missing_dates || [];
      document.getElementById('coverageAlert').innerHTML = gaps.length
        ? `<div class="alert"><strong>${gaps.length} missing snapshot dates</strong> after the first published file. Missing days are excluded from averages and shown as a coverage gap. Recent gaps: ${gaps.slice(-8).map(escapeHtml).join(', ')}</div>`
        : '<div class="alert good">No missing snapshot dates are currently recorded after feed start.</div>';
      document.getElementById('summaryRows').innerHTML = types.map(game => `<tr>
        <td>${escapeHtml(game.game_type)}</td><td>${game.days}</td><td>${game.he_rows}</td>
        <td>${number(game.mean_actual_he)}</td><td>${number(game.mean_expected_he)}</td><td>${number(game.mean_he_delta)}</td>
        <td>${number(game.mean_actual_probability)}</td><td>${number(game.mean_expected_probability)}</td><td>${number(game.mean_threshold)}</td><td>${Number(game.breach_pct).toFixed(2)}%</td>
      </tr>`).join('');
    }

    function getDateRange() {
      const start = document.getElementById('startDate').value;
      const end = document.getElementById('endDate').value;
      return { start: start || null, end: end || null };
    }

    function inDateRange(day) {
      const { start, end } = getDateRange();
      if (start && day < start) return false;
      if (end && day > end) return false;
      return true;
    }

    function inTimeframe(day) {
      if (!inDateRange(day)) return false;
      const days = document.getElementById('periodFilter').value;
      if (days !== 'all') {
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - Number(days));
        if (new Date(`${day}T00:00:00`) < cutoff) return false;
      }
      return true;
    }

    function timeframeSeries(seriesByGame, game) {
      return pair(seriesByGame, game).filter(([day]) => inTimeframe(day));
    }

    function timeframeMean(seriesByGame, game) {
      const values = timeframeSeries(seriesByGame, game).map(([, value]) => value).filter(value => value != null);
      return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
    }

    function comparisonValues(seriesKey, meanKey) {
      const { start, end } = getDateRange();
      const precomputed = () => types.map(game => game[meanKey]);
      if (!start && !end) return precomputed();
      return types.map(game => {
        const values = pair(DATA[seriesKey], game.game_type).filter(([day]) => inDateRange(day)).map(([, value]) => value).filter(value => value != null);
        return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
      });
    }

    function updateComparisonNotes() {
      const { start, end } = getDateRange();
      const suffix = (start || end) ? ` · ${start || '…'} to ${end || '…'}` : '';
      document.getElementById('heCompareNote').textContent = `Daily bet-place records pooled across the selected history${suffix}`;
      document.getElementById('probCompareNote').textContent = `Compare the observed probability with the model and configured limit${suffix}`;
    }

    function renderGameComparisons() {
      const names = types.map(game => game.game_type);
      charts.heCompare.setOption({
        color: ['#38bdf8','#fbbf24'], tooltip: { ...tooltipStyle, trigger: 'axis' }, legend: { textStyle: { color: '#cbd5e1' } },
        grid: { left: 55, right: 18, top: 38, bottom: 72 },
        xAxis: { type: 'category', data: names, axisLabel: { ...axisStyle.axisLabel, rotate: 25 } }, yAxis: { type: 'value', name: 'HE (%)', ...axisStyle },
        series: [
          { name: 'Actual HE', type: 'bar', data: comparisonValues('series_he', 'mean_actual_he'), itemStyle: { borderRadius: [4,4,0,0] } },
          { name: 'Expected HE', type: 'bar', data: comparisonValues('series_expected_he', 'mean_expected_he'), itemStyle: { borderRadius: [4,4,0,0] } }
        ]
      });
      charts.probCompare.setOption({
        color: ['#38bdf8','#a78bfa','#fb7185'], tooltip: { ...tooltipStyle, trigger: 'axis' }, legend: { textStyle: { color: '#cbd5e1' } },
        grid: { left: 55, right: 18, top: 38, bottom: 72 },
        xAxis: { type: 'category', data: names, axisLabel: { ...axisStyle.axisLabel, rotate: 25 } }, yAxis: { type: 'value', name: 'Probability (%)', ...axisStyle },
        series: [
          { name: 'Actual probability', type: 'bar', data: comparisonValues('series_actual_probability', 'mean_actual_probability'), itemStyle: { borderRadius: [4,4,0,0] } },
          { name: 'Expected probability', type: 'bar', data: comparisonValues('series_expected_probability', 'mean_expected_probability'), itemStyle: { borderRadius: [4,4,0,0] } },
          { name: 'Threshold', type: 'bar', data: comparisonValues('series_threshold', 'mean_threshold'), itemStyle: { borderRadius: [4,4,0,0] } }
        ]
      });
      updateComparisonNotes();
    }

    function renderCombinedSummary() {
      const rows = (DATA.daily || []).filter(row => inTimeframe(row.date));
      const totalRows = types.reduce((sum, game) => sum + (game.rows || 0), 0);
      const totalBreaches = types.reduce((sum, game) => sum + (game.breaches || 0), 0);
      const pooledBreach = totalRows ? (totalBreaches / totalRows * 100) : null;
      const { start, end } = getDateRange();
      const suffix = (start || end) ? ` · ${start || '…'} to ${end || '…'}` : '';
      document.getElementById('combinedNote').textContent =
        `${types.length} game types · ${(DATA.bet_places || []).length} bet places · ${Number(totalRows).toLocaleString()} pooled rows · pooled breach rate ${pooledBreach == null ? '—' : `${pooledBreach.toFixed(2)}%`} · ${rows.length} days in view${suffix}`;
      charts.combinedProb.setOption({
        ...trendCommon, yAxis: { ...trendCommon.yAxis, name: 'Probability (%)' },
        series: [
          { name: 'Actual probability', type: 'line', showSymbol: false, smooth: true, connectNulls: false, data: rows.map(row => [row.date, row.mean_actual_probability]), lineStyle: { width: 2 }, itemStyle: { color: '#38bdf8' } },
          { name: 'Expected probability', type: 'line', showSymbol: false, smooth: true, connectNulls: false, data: rows.map(row => [row.date, row.mean_expected_probability]), lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: '#a78bfa' } },
          { name: 'Threshold', type: 'line', showSymbol: false, smooth: true, connectNulls: false, data: rows.map(row => [row.date, row.mean_threshold]), lineStyle: { width: 2, type: 'dotted' }, itemStyle: { color: '#fb7185' } }
        ]
      }, true);
    }

    function buildGameSections() {
      const container = document.getElementById('gameSections');
      const fragment = document.createDocumentFragment();
      types.forEach((game, index) => {
        const hePoints = pair(DATA.series_he, game.game_type).filter(([, value]) => value != null);
        const heAvailable = game.mean_actual_he != null && hePoints.length > 0;
        gameHeAvailable.push(heAvailable);
        const article = document.createElement('article');
        article.className = 'card chart-card wide';
        article.id = uniqueGameAnchor(game.game_type);
        gameAnchors.push(article.id);
        article.innerHTML = `
          <h3>${escapeHtml(game.game_type)}</h3>
          <div class="muted" id="gameMeta-${index}"></div>
          <div class="table-wrap"><table>
            <thead id="gameHead-${index}"></thead>
            <tbody id="gameRows-${index}"></tbody>
          </table></div>
          <article class="card chart-card single" id="gameHeCard-${index}"${heAvailable ? '' : ' style="display:none"'}>
            <h3>${escapeHtml(game.game_type)} - HE Trend</h3>
            <div class="muted">Daily actual vs expected house edge · honours the trend window and date range</div>
            <div id="gameHe-${index}" class="chart"></div>
          </article>`;
        fragment.appendChild(article);
      });
      container.appendChild(fragment);
      types.forEach((game, index) => {
        gameCharts.push({ he: gameHeAvailable[index] ? echarts.init(document.getElementById(`gameHe-${index}`)) : null });
      });
    }

    function buildQuickNav() {
      const nav = document.getElementById('quickNav');
      const links = [
        { href: '#combinedPanel', label: 'Combined Summary' },
        { href: '#breachAnalytics', label: 'Threshold Breach Analytics' },
        ...types.map((game, index) => ({ href: `#${gameAnchors[index]}`, label: game.game_type, game: true })),
        { href: '#gameSummary', label: 'Game type summary' }
      ];
      nav.innerHTML = `<span class="quick-nav-label">Jump to</span>` + links.map(link =>
        `<a class="${link.game ? 'game-link' : ''}" href="${link.href}">${escapeHtml(link.label)}</a>`
      ).join('');
    }

    function renderBreachAnalytics() {
      const days = (DATA.daily || []).filter(row => inTimeframe(row.date));
      const totalBreaches = days.reduce((sum, row) => sum + (row.breaches || 0), 0);
      const worstDay = days.reduce((worst, row) => (!worst || row.breaches > worst.breaches ? row : worst), null);
      const { start, end } = getDateRange();
      const suffix = (start || end) ? ` · ${start || '…'} to ${end || '…'}` : '';
      document.getElementById('breachNote').textContent =
        `Rows where actual probability exceeds the configured threshold · ${Number(totalBreaches).toLocaleString()} breaches across ${days.length} days in view${worstDay ? ` · peak ${worstDay.breaches} on ${worstDay.date}` : ''}${suffix}`;

      const maxBreaches = Math.max(1, ...days.map(row => row.breaches || 0));
      charts.breachCalendar.setOption({
        tooltip: {
          ...tooltipStyle,
          formatter: point => `${point.value[0]}<br>${point.value[1]} threshold breach${point.value[1] === 1 ? '' : 'es'}`
        },
        visualMap: {
          min: 0, max: maxBreaches, orient: 'horizontal', left: 'center', bottom: 4, calculable: true,
          inRange: { color: ['#121d30', '#0c4a6e', '#0ea5e9', '#fbbf24', '#f43f5e'] },
          textStyle: { color: '#94a3b8' }, formatter: value => Math.round(value)
        },
        calendar: {
          top: 30, left: 44, right: 30, bottom: 46, cellSize: ['auto', 13],
          range: days.length ? [days[0].date, days[days.length - 1].date] : [DATA.meta.billing_date_min, DATA.meta.billing_date_max],
          itemStyle: { color: '#121d30', borderColor: '#253247', borderWidth: 1 },
          dayLabel: { color: '#94a3b8', firstDay: 1 }, monthLabel: { color: '#94a3b8' }, yearLabel: { color: '#cbd5e1' },
          splitLine: { lineStyle: { color: '#253247' } }
        },
        series: [{ type: 'heatmap', coordinateSystem: 'calendar', data: days.map(row => [row.date, row.breaches || 0]) }]
      }, true);

      const dates = days.map(row => row.date);
      charts.breachByDate.setOption({
        color: colors, tooltip: { ...tooltipStyle, trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { type: 'scroll', textStyle: { color: '#cbd5e1' } },
        grid: { left: 52, right: 18, top: 45, bottom: 58 },
        xAxis: { type: 'category', data: dates, axisLabel: { ...axisStyle.axisLabel, fontSize: 9 } },
        yAxis: { type: 'value', name: 'Breaches', ...axisStyle },
        dataZoom: [
          { type: 'inside' },
          { type: 'slider', height: 14, bottom: 4, borderColor: '#334155', textStyle: { color: '#94a3b8', fontSize: 8 } }
        ],
        series: types.map((game, index) => {
          const counts = new Map(timeframeSeries(DATA.series_breach_count, game.game_type));
          return {
            name: game.game_type, type: 'bar', stack: 'breaches', barMaxWidth: 12,
            emphasis: { focus: 'series' },
            itemStyle: { color: colors[index % colors.length] },
            data: dates.map(day => counts.get(day) || 0)
          };
        })
      }, true);

      const perGame = types.map(game => ({
        game,
        inView: timeframeSeries(DATA.series_breach_count, game.game_type).reduce((sum, [, value]) => sum + value, 0),
        daysInView: timeframeSeries(DATA.series_breach_count, game.game_type).length
      }));
      const breachesInView = perGame.reduce((sum, entry) => sum + entry.inView, 0);
      const byGame = perGame
        .filter(entry => entry.inView > 0)
        .sort((a, b) => b.inView - a.inView || a.game.game_type.localeCompare(b.game.game_type));
      charts.breachByGame.setOption({
        color: colors, tooltip: {
          ...tooltipStyle, trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: params => {
            const entry = byGame[params[0].dataIndex];
            return `<strong>${escapeHtml(entry.game.game_type)}</strong><br>Breaches in view: ${entry.inView.toLocaleString()}<br>Share of breaches in view: ${breachesInView ? `${(entry.inView / breachesInView * 100).toFixed(2)}%` : '—'}<br>Days in view: ${entry.daysInView} · per day: ${entry.daysInView ? (entry.inView / entry.daysInView).toFixed(2) : '—'}<br>Full history: ${Number(entry.game.breaches).toLocaleString()} (${Number(entry.game.breach_pct).toFixed(2)}%)`;
          }
        },
        grid: { left: 52, right: 18, top: 38, bottom: 62 },
        xAxis: { type: 'category', data: byGame.map(entry => entry.game.game_type), axisLabel: { ...axisStyle.axisLabel, rotate: 25 } },
        yAxis: { type: 'value', name: 'Breaches', ...axisStyle },
        series: [{
          name: 'Breaches in view', type: 'bar', barMaxWidth: 44,
          data: byGame.map((entry, index) => ({
            value: entry.inView,
            itemStyle: { color: colors[index % colors.length], borderRadius: [4, 4, 0, 0] }
          })),
          label: { show: true, position: 'top', color: '#cbd5e1', fontSize: 10 }
        }]
      }, true);

      const placeCounts = {};
      for (const [key, series] of Object.entries(DATA.bet_place_breaches || {})) {
        placeCounts[key] = series.filter(([day]) => inTimeframe(day)).reduce((sum, [, value]) => sum + value, 0);
      }
      const byPlace = (DATA.bet_places || [])
        .map(place => ({ place, inView: placeCounts[place.key] || 0 }))
        .filter(entry => entry.inView > 0)
        .sort((a, b) => b.inView - a.inView || b.place.breaches - a.place.breaches || a.place.key.localeCompare(b.place.key));
      const placeChart = document.getElementById('breachByPlace');
      const desiredHeight = Math.min(1100, Math.max(350, byPlace.length * 18 + 90));
      if (placeChart.style.height !== `${desiredHeight}px`) placeChart.style.height = `${desiredHeight}px`;
      charts.breachByPlace.setOption({
        tooltip: {
          ...tooltipStyle,
          formatter: point => {
            const entry = byPlace[point.dataIndex];
            return `<strong>${escapeHtml(entry.place.game_type)} · ${escapeHtml(entry.place.bet_place)}</strong><br>Breaches in view: ${entry.inView.toLocaleString()}<br>Full history: ${Number(entry.place.breaches).toLocaleString()} (${Number(entry.place.breach_pct).toFixed(2)}%)`;
          }
        },
        grid: { left: 175, right: 42, top: 30, bottom: 30 },
        xAxis: { type: 'value', name: 'Breaches', ...axisStyle },
        yAxis: {
          type: 'category', inverse: true,
          data: byPlace.map(entry => `${entry.place.game_type} · ${entry.place.bet_place}`),
          axisLabel: { ...axisStyle.axisLabel, fontSize: 10 }
        },
        dataZoom: [
          { type: 'inside', yAxisIndex: 0 },
          { type: 'slider', yAxisIndex: 0, width: 12, right: 10, top: 30, bottom: 30, borderColor: '#334155', backgroundColor: '#121d30', fillerColor: '#1e3a5f', dataBackground: { lineStyle: { color: '#334155' }, areaStyle: { color: '#1e3a5f' } }, textStyle: { color: '#94a3b8', fontSize: 8 } }
        ],
        series: [{
          name: 'Breaches in view', type: 'bar', barMaxWidth: 14,
          data: byPlace.map(entry => entry.inView),
          itemStyle: { color: '#38bdf8', borderRadius: [0, 3, 3, 0] },
          label: { show: true, position: 'right', color: '#94a3b8', fontSize: 9 }
        }]
      }, true);
      charts.breachByPlace.resize();
    }

    function renderGameSections() {
      types.forEach((game, index) => {
        const name = game.game_type;
        const daysInRange = timeframeSeries(DATA.series_he, name).length;
        const actualHe = timeframeMean(DATA.series_he, name);
        const expectedHe = timeframeMean(DATA.series_expected_he, name);
        const actualProb = timeframeMean(DATA.series_actual_probability, name);
        const expectedProb = timeframeMean(DATA.series_expected_probability, name);
        const threshold = timeframeMean(DATA.series_threshold, name);
        const breach = timeframeMean(DATA.series_breach, name);
        const heAvailable = gameHeAvailable[index];
        document.getElementById(`gameMeta-${index}`).textContent =
          `${Number(game.rows).toLocaleString()} rows · ${game.days} days on record · ${game.first_date} – ${game.last_date} · ${game.bet_places} bet places${heAvailable ? '' : ' · no house-edge model published for this game'} · the game row follows the trend window and date range; bet-place rows are full-history pooled means`;

        const columns = heAvailable
          ? ['Bet place', 'Days', 'Actual HE', 'Expected HE', 'HE delta', 'Actual prob.', 'Expected prob.', 'Threshold', 'Breach rows %']
          : ['Bet place', 'Days', 'Actual prob.', 'Expected prob.', 'Threshold', 'Breach rows %'];
        document.getElementById(`gameHead-${index}`).innerHTML = `<tr>${columns.map(column => `<th>${column}</th>`).join('')}</tr>`;
        const cells = (label, days, he, prob, thresholdValue, breachValue) => {
          const out = [`<td>${escapeHtml(label)}</td>`, `<td>${days}</td>`];
          if (heAvailable) out.push(
            `<td>${number(he.actual)}</td>`,
            `<td>${number(he.expected)}</td>`,
            `<td>${number(he.actual != null && he.expected != null ? he.actual - he.expected : null)}</td>`
          );
          out.push(
            `<td>${number(prob.actual)}</td>`,
            `<td>${number(prob.expected)}</td>`,
            `<td>${number(thresholdValue)}</td>`,
            `<td>${breachValue}</td>`
          );
          return out.join('');
        };
        const rows = [`<tr class="table-total">${cells(`${name} — all bet places`, daysInRange, { actual: actualHe, expected: expectedHe }, { actual: actualProb, expected: expectedProb }, threshold, breach == null ? `${Number(game.breach_pct).toFixed(2)}%` : `${breach.toFixed(2)}%`)}</tr>`];
        for (const place of (DATA.bet_places || []).filter(entry => entry.game_type === name)) {
          rows.push(`<tr>${cells(place.bet_place, place.days, { actual: place.mean_actual_he, expected: place.mean_expected_he }, { actual: place.mean_actual_probability, expected: place.mean_expected_probability }, place.mean_threshold, `${Number(place.breach_pct).toFixed(2)}%`)}</tr>`);
        }
        document.getElementById(`gameRows-${index}`).innerHTML = rows.join('');

        const hePoints = timeframeSeries(DATA.series_he, name).filter(([, value]) => value != null);
        const card = document.getElementById(`gameHeCard-${index}`);
        const hasHeToShow = heAvailable && hePoints.length > 0;
        if (card) card.style.display = hasHeToShow ? '' : 'none';
        if (!hasHeToShow) return;
        if (!gameCharts[index].he) gameCharts[index].he = echarts.init(document.getElementById(`gameHe-${index}`));
        const line = (seriesByGame, label, color, dash) => ({
          name: label, type: 'line', showSymbol: false, smooth: true, connectNulls: false,
          data: timeframeSeries(seriesByGame, name).map(([day, value]) => [day, value]),
          itemStyle: { color }, lineStyle: dash ? { width: 2, type: dash } : { width: 2 }
        });
        gameCharts[index].he.setOption({
          ...trendCommon, yAxis: { ...trendCommon.yAxis, name: 'HE (%)' },
          series: [ line(DATA.series_he, 'Actual HE', '#38bdf8'), line(DATA.series_expected_he, 'Expected HE', '#fbbf24', 'dashed') ]
        }, true);
      });
    }

    function renderRelationship() {
      const latest = DATA.latest_day;
      const rows = latest.rows || [];
      const groups = [...new Set(rows.filter(row => row.actual_probability != null && row.actual_he != null).map(row => row.game_type))];
      charts.relationship.setOption({
        color: colors, tooltip: {
          ...tooltipStyle, formatter: point => {
            const row = point.data.row;
            return `<strong>${escapeHtml(row.game_type)}</strong><br>${escapeHtml(row.bet_place)}<br>Actual probability: ${number(row.actual_probability)}<br>Threshold: ${number(row.threshold)}<br>Actual HE: ${number(row.actual_he)}<br>Expected HE: ${number(row.expected_he)}<br>${row.prob_breach ? 'Above threshold' : 'At/below threshold'}`;
          }
        },
        legend: { data: groups, textStyle: { color: '#cbd5e1' } },
        grid: { left: 65, right: 24, top: 42, bottom: 48 },
        xAxis: { type: 'value', name: 'Actual probability (%)', ...axisStyle },
        yAxis: { type: 'value', name: 'Actual HE (%)', ...axisStyle },
        series: groups.map(game => ({
          name: game, type: 'scatter', symbolSize: 11,
          data: rows.filter(row => row.game_type === game && row.actual_probability != null && row.actual_he != null).map(row => ({
            value: [row.actual_probability, row.actual_he],
            symbol: row.prob_breach ? 'triangle' : 'circle',
            row
          }))
        }))
      }, true);
      document.querySelector('#relationship').previousElementSibling.textContent =
        `Each point is a bet place on ${latest.billing_date}; triangles indicate probability above threshold`;
    }

    function render() {
      renderCombinedSummary();
      renderBreachAnalytics();
      renderGameComparisons();
      renderGameSections();
      renderRelationship();
    }

    function initDateRangeBounds() {
      const dates = [...Object.values(DATA.series_he || {}), ...Object.values(DATA.series_expected_he || {}),
                     ...Object.values(DATA.series_actual_probability || {}), ...Object.values(DATA.series_expected_probability || {}),
                     ...Object.values(DATA.series_threshold || {})].flat().map(([day]) => day).sort();
      const min = DATA.meta.billing_date_min || dates[0] || '';
      const max = DATA.meta.billing_date_max || dates[dates.length - 1] || '';
      const startInput = document.getElementById('startDate');
      const endInput = document.getElementById('endDate');
      for (const input of [startInput, endInput]) {
        input.min = min;
        input.max = max;
      }
      return { min, max };
    }

    function resetDateRange() {
      document.getElementById('startDate').value = '';
      document.getElementById('endDate').value = '';
      render();
    }

    const allCharts = () => [...Object.values(charts), ...gameCharts.map(entry => entry.he).filter(chart => chart)];

    renderKpis();
    initDateRangeBounds();
    buildGameSections();
    buildQuickNav();
    render();
    document.getElementById('periodFilter').addEventListener('change', render);
    document.getElementById('startDate').addEventListener('change', render);
    document.getElementById('endDate').addEventListener('change', render);
    document.getElementById('resetDateRange').addEventListener('click', resetDateRange);
    window.addEventListener('resize', () => allCharts().forEach(chart => chart.resize()));
  </script>
</body>
</html>
"""
    html = template.replace("__PAYLOAD__", payload)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as output:
        output.write(html)
    print(f"Generated {OUT_FILE} ({len(html):,} characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_dashboard())
