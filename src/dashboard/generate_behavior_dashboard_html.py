from pathlib import Path
import json
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render import render_dashboard

DATA_FILE = WORKSPACE / "output" / "data" / "player_behavior_data.json"
SECTIONS_DIR = SCRIPT_DIR / "sections"

TITLE = "Player Behavioral Intelligence Console | Oriental Gaming Title"


def build_dashboard():
    if not DATA_FILE.exists():
        print(f"Data file {DATA_FILE} not found yet!")
        return False

    out_file = WORKSPACE / "output" / "dashboards" / "player_behavior_dashboard.html"

    extra_scripts = """<script>
    console.log("Player Behavior Data Loaded:", DATA);

    let isPresentationMode = false;
    let currentSlide = 1;
    const totalSlides = 5;

    document.addEventListener('DOMContentLoaded', () => {
      populateTimingTable();
      populateGamesTable();
      initTimingCharts();
      setupKeyboardNavigation();
    });

    function switchTab(tabId) {
      if (isPresentationMode) togglePresentationMode();
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

      const targetPane = document.getElementById(`tab-${tabId}`);
      if (targetPane) targetPane.classList.remove('hidden');

      const clickedBtn = Array.from(document.querySelectorAll('.nav-tab')).find(b => b.getAttribute('onclick')?.includes(tabId));
      if (clickedBtn) clickedBtn.classList.add('active');

      setTimeout(() => {
        if (tabId === 'timing') initTimingCharts();
        else if (tabId === 'games') initGamesCharts();
        else if (tabId === 'behavior') initBehaviorCharts();
        else if (tabId === 'frequency') initFrequencyCharts();
        else if (tabId === 'correlation') initCorrelationCharts();
        resizeAllCharts();
      }, 50);
    }

    function togglePresentationMode() {
      isPresentationMode = !isPresentationMode;
      const deck = document.getElementById('presentationDeck');
      const tabs = document.querySelectorAll('.tab-pane');
      const nav = document.getElementById('dashboardNav');
      const btnLabel = document.getElementById('viewModeLabel');

      if (isPresentationMode) {
        tabs.forEach(t => t.classList.add('hidden'));
        deck.classList.remove('hidden');
        nav.classList.add('hidden');
        btnLabel.textContent = "Dashboard View";
        showSlide(currentSlide);
      } else {
        deck.classList.add('hidden');
        nav.classList.remove('hidden');
        btnLabel.textContent = "Presentation Mode";
        switchTab('timing');
      }
    }

    function showSlide(idx) {
      currentSlide = idx;
      document.querySelectorAll('.slide').forEach((s, i) => {
        if (i + 1 === idx) s.classList.add('active');
        else s.classList.remove('active');
      });
      document.getElementById('currentSlideNum').textContent = idx;
      setTimeout(renderSlideCharts, 100);
    }

    function nextSlide() {
      if (currentSlide < totalSlides) showSlide(currentSlide + 1);
      else showSlide(1);
    }

    function prevSlide() {
      if (currentSlide > 1) showSlide(currentSlide - 1);
      else showSlide(totalSlides);
    }

    function setupKeyboardNavigation() {
      window.addEventListener('keydown', (e) => {
        if (!isPresentationMode) return;
        if (e.key === 'ArrowRight' || e.key === 'Space') nextSlide();
        else if (e.key === 'ArrowLeft') prevSlide();
        else if (e.key === 'Escape') togglePresentationMode();
      });
    }

    function toggleTheme() {
      const html = document.documentElement;
      const icon = document.getElementById('themeIcon');
      if (html.classList.contains('dark')) {
        html.classList.remove('dark');
        html.classList.add('light');
        icon.classList.remove('fa-moon');
        icon.classList.add('fa-sun');
      } else {
        html.classList.remove('light');
        html.classList.add('dark');
        icon.classList.remove('fa-sun');
        icon.classList.add('fa-moon');
      }
      setTimeout(reinitAllCharts, 150);
    }

    function formatCurrency(val) {
      if (val >= 1e9) return (val / 1e9).toFixed(2) + 'B';
      if (val >= 1e6) return (val / 1e6).toFixed(2) + 'M';
      if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
      return Number(val).toLocaleString();
    }

    function isDark() {
      return document.documentElement.classList.contains('dark');
    }

    function getChartTheme() {
      const dark = isDark();
      return {
        bg: 'transparent',
        textColor: dark ? '#94a3b8' : '#475569',
        titleColor: dark ? '#f8fafc' : '#0f172a',
        gridBorder: dark ? '#1e293b' : '#e2e8f0',
        tooltipBg: dark ? '#0f172a' : '#ffffff',
        tooltipBorder: dark ? '#334155' : '#cbd5e1',
        tooltipText: dark ? '#ffffff' : '#0f172a'
      };
    }

    function resizeAllCharts() {
      Object.values(chartInstances).forEach(c => c && c.resize());
    }
    window.addEventListener('resize', resizeAllCharts);

    function reinitAllCharts() {
      Object.values(chartInstances).forEach(c => c && c.dispose());
      chartInstances = {};
      initTimingCharts();
      initGamesCharts();
      initBehaviorCharts();
      initFrequencyCharts();
      initCorrelationCharts();
      if (isPresentationMode) renderSlideCharts();
    }

    // Populate Timing Table
    function populateTimingTable() {
      const tbody = document.getElementById('timingTableBody');
      tbody.innerHTML = '';
      DATA.hourly_credit_and_wins.forEach(h => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/40 transition";
        tr.innerHTML = `
          <td class="py-2.5 px-3 text-cyan-400 font-bold">${h.hour}</td>
          <td class="py-2.5 px-3 text-right text-slate-300">${h.total_bets.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-emerald-400 font-bold">${h.wins.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-slate-300">${h.win_rate_pct}%</td>
          <td class="py-2.5 px-3 text-right text-slate-300">${h.total_debit.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-cyan-300 font-bold">${h.total_credit.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right ${h.net_ggr >= 0 ? 'text-emerald-400' : 'text-rose-400'} font-bold">${h.net_ggr.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-slate-400">${h.rtp_pct}%</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Populate Games Table
    function populateGamesTable() {
      const tbody = document.getElementById('gamesTableBody');
      tbody.innerHTML = '';
      DATA.games.forEach(g => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/40 transition";
        tr.innerHTML = `
          <td class="py-2.5 px-3 text-white font-semibold flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <code>${g.game}</code>
          </td>
          <td class="py-2.5 px-3 text-right text-slate-300">${g.total_bets.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-emerald-400 font-bold">${g.total_debit.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-slate-300">${g.ggr.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right font-bold text-emerald-300">${g.hold_margin_pct}%</td>
          <td class="py-2.5 px-3 text-right text-slate-400">${g.rtp_pct}%</td>
          <td class="py-2.5 px-3 text-right text-cyan-300">${g.win_rate_pct}%</td>
          <td class="py-2.5 px-3 text-right text-amber-300">${g.avg_bet.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-slate-400">${g.avg_player_balance.toLocaleString()}</td>
          <td class="py-2.5 px-3 text-right text-purple-300 font-bold">${g.avg_bet_to_balance_pct}%</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // CSV Exporter
    function exportTableToCSV(tableId, filename) {
      let csv = [];
      const rows = document.querySelectorAll(`#${tableId} tr`);
      for (let i = 0; i < rows.length; i++) {
        let row = [], cols = rows[i].querySelectorAll('td, th');
        for (let j = 0; j < cols.length; j++) {
          let data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/(\s\s+)/gm, ' ');
          data = data.replace(/"/g, '""');
          row.push('"' + data + '"');
        }
        csv.push(row.join(','));
      }
      const csvFile = new Blob([csv.join('\n')], { type: 'text/csv' });
      const downloadLink = document.createElement('a');
      downloadLink.download = filename;
      downloadLink.href = window.URL.createObjectURL(csvFile);
      downloadLink.style.display = 'none';
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
    }

    // =========================================================================
    // ECHARTS BUILDERS
    // =========================================================================

    // 1. Timing Charts
    function initTimingCharts() {
      const dom1 = document.getElementById('timingOutcomeChart');
      if (dom1 && !chartInstances['timingOutcome']) {
        const t = getChartTheme();
        const c1 = echarts.init(dom1);
        chartInstances['timingOutcome'] = c1;

        const hours = DATA.hourly_credit_and_wins.map(d => d.hour);
        const wins = DATA.hourly_credit_and_wins.map(d => d.wins);
        const losses = DATA.hourly_credit_and_wins.map(d => d.losses);
        const ties = DATA.hourly_credit_and_wins.map(d => d.ties);

        c1.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          legend: { data: ['Wins', 'Losses', 'Pushes'], textStyle: { color: t.textColor } },
          grid: { top: 35, right: 20, bottom: 30, left: 50 },
          xAxis: { type: 'category', data: hours, axisLabel: { color: t.textColor, fontSize: 10 }, axisLine: { lineStyle: { color: t.gridBorder } } },
          yAxis: { type: 'value', splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } }, axisLabel: { color: t.textColor, fontSize: 10, formatter: v => (v / 1000).toFixed(0) + 'K' } },
          series: [
            { name: 'Wins', type: 'line', data: wins, lineStyle: { color: '#10b981', width: 2 }, itemStyle: { color: '#10b981' }, areaStyle: { color: 'rgba(16,185,129,0.15)' } },
            { name: 'Losses', type: 'line', data: losses, lineStyle: { color: '#f43f5e', width: 2 }, itemStyle: { color: '#f43f5e' }, areaStyle: { color: 'rgba(244,63,94,0.15)' } },
            { name: 'Pushes', type: 'line', data: ties, lineStyle: { color: '#6366f1', width: 2 }, itemStyle: { color: '#6366f1' }, areaStyle: { color: 'rgba(99,102,241,0.15)' } }
          ]
        });
      }

      const dom2 = document.getElementById('timingRtpChart');
      if (dom2 && !chartInstances['timingRtp']) {
        const t = getChartTheme();
        const c2 = echarts.init(dom2);
        chartInstances['timingRtp'] = c2;

        const hours = DATA.hourly_credit_and_wins.map(d => d.hour);
        const debit = DATA.hourly_credit_and_wins.map(d => d.total_debit);
        const credit = DATA.hourly_credit_and_wins.map(d => d.total_credit);
        const rtp = DATA.hourly_credit_and_wins.map(d => d.rtp_pct);

        c2.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          legend: { data: ['Debit Turnover', 'Credit Payouts', 'RTP %'], textStyle: { color: t.textColor } },
          grid: { top: 35, right: 50, bottom: 30, left: 60 },
          xAxis: { type: 'category', data: hours, axisLabel: { color: t.textColor, fontSize: 10 }, axisLine: { lineStyle: { color: t.gridBorder } } },
          yAxis: [
            { type: 'value', name: 'Turnover', splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } }, axisLabel: { color: t.textColor, fontSize: 10, formatter: v => formatCurrency(v) } },
            { type: 'value', name: 'RTP %', min: 90, max: 110, axisLabel: { color: t.textColor, fontSize: 10, formatter: v => v + '%' } }
          ],
          series: [
            { name: 'Debit Turnover', type: 'bar', data: debit, itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] } },
            { name: 'Credit Payouts', type: 'bar', data: credit, itemStyle: { color: '#10b981', borderRadius: [4, 4, 0, 0] } },
            { name: 'RTP %', type: 'line', yAxisIndex: 1, data: rtp, lineStyle: { color: '#f59e0b', width: 2 }, itemStyle: { color: '#f59e0b' } }
          ]
        });
      }
    }

    // 2. Games Charts
    function initGamesCharts() {
      const dom1 = document.getElementById('gameTurnoverChart');
      if (dom1 && !chartInstances['gameTurnover']) {
        const t = getChartTheme();
        const c1 = echarts.init(dom1);
        chartInstances['gameTurnover'] = c1;

        const games = DATA.games.map(d => d.game);
        const bets = DATA.games.map(d => d.total_bets);
        const debits = DATA.games.map(d => d.total_debit);

        c1.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          grid: { top: 30, right: 30, bottom: 40, left: 60 },
          xAxis: { type: 'category', data: games, axisLabel: { color: t.textColor, fontSize: 10, rotate: 20 }, axisLine: { lineStyle: { color: t.gridBorder } } },
          yAxis: { type: 'value', splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } }, axisLabel: { color: t.textColor, fontSize: 10, formatter: v => (v / 1000).toFixed(0) + 'K' } },
          series: [
            { name: 'Total Bets', type: 'bar', data: bets, itemStyle: { color: '#10b981', borderRadius: [4, 4, 0, 0] } }
          ]
        });
      }

      const dom2 = document.getElementById('gameOutcomeChart');
      if (dom2 && !chartInstances['gameOutcome']) {
        const t = getChartTheme();
        const c2 = echarts.init(dom2);
        chartInstances['gameOutcome'] = c2;

        const games = DATA.games.map(d => d.game);
        const winPcts = DATA.games.map(d => d.win_rate_pct);
        const lossPcts = DATA.games.map(d => d.loss_rate_pct);
        const tiePcts = DATA.games.map(d => d.tie_rate_pct);

        c2.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          legend: { data: ['Win %', 'Loss %', 'Tie/Push %'], textStyle: { color: t.textColor } },
          grid: { top: 35, right: 30, bottom: 40, left: 50 },
          xAxis: { type: 'category', data: games, axisLabel: { color: t.textColor, fontSize: 10, rotate: 20 }, axisLine: { lineStyle: { color: t.gridBorder } } },
          yAxis: { type: 'value', max: 100, axisLabel: { color: t.textColor, fontSize: 10, formatter: v => v + '%' } },
          series: [
            { name: 'Win %', type: 'bar', stack: 'total', data: winPcts, itemStyle: { color: '#10b981' } },
            { name: 'Loss %', type: 'bar', stack: 'total', data: lossPcts, itemStyle: { color: '#f43f5e' } },
            { name: 'Tie/Push %', type: 'bar', stack: 'total', data: tiePcts, itemStyle: { color: '#6366f1' } }
          ]
        });
      }
    }

    // 3. Behavior Charts
    function initBehaviorCharts() {
      const dom1 = document.getElementById('betBracketsChart');
      if (dom1 && !chartInstances['betBrackets']) {
        const t = getChartTheme();
        const c1 = echarts.init(dom1);
        chartInstances['betBrackets'] = c1;

        const labels = DATA.bet_brackets.map(b => b.bracket);
        const counts = DATA.bet_brackets.map(b => b.count);

        c1.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          grid: { top: 20, right: 30, bottom: 40, left: 110 },
          xAxis: { type: 'value', splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } }, axisLabel: { color: t.textColor, fontSize: 10 } },
          yAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: t.gridBorder } }, axisLabel: { color: t.textColor, fontSize: 9 } },
          series: [{
            type: 'bar',
            data: counts,
            itemStyle: { color: '#f59e0b', borderRadius: [0, 6, 6, 0] },
            label: { show: true, position: 'right', color: t.textColor, fontSize: 9, formatter: p => p.value.toLocaleString() }
          }]
        });
      }

      const dom2 = document.getElementById('betProgressionChart');
      if (dom2 && !chartInstances['betProgression']) {
        const t = getChartTheme();
        const c2 = echarts.init(dom2);
        chartInstances['betProgression'] = c2;

        const bp = DATA.bet_progression;
        const lossTot = bp.after_loss.increased + bp.after_loss.decreased + bp.after_loss.same;
        const winTot = bp.after_win.increased + bp.after_win.decreased + bp.after_win.same;

        c2.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          legend: { data: ['Increased Bet (Aggressive)', 'Same Bet (Neutral)', 'Decreased Bet (Conservative)'], textStyle: { color: t.textColor } },
          grid: { top: 35, right: 20, bottom: 30, left: 60 },
          xAxis: { type: 'category', data: ['After Loss (Martingale Risk)', 'After Win (Pressing Risk)'], axisLabel: { color: t.textColor, fontSize: 10 } },
          yAxis: { type: 'value', max: 100, axisLabel: { color: t.textColor, fontSize: 10, formatter: v => v + '%' } },
          series: [
            { name: 'Increased Bet (Aggressive)', type: 'bar', data: [((bp.after_loss.increased / lossTot) * 100).toFixed(1), ((bp.after_win.increased / winTot) * 100).toFixed(1)], itemStyle: { color: '#f43f5e' } },
            { name: 'Same Bet (Neutral)', type: 'bar', data: [((bp.after_loss.same / lossTot) * 100).toFixed(1), ((bp.after_win.same / winTot) * 100).toFixed(1)], itemStyle: { color: '#6366f1' } },
            { name: 'Decreased Bet (Conservative)', type: 'bar', data: [((bp.after_loss.decreased / lossTot) * 100).toFixed(1), ((bp.after_win.decreased / winTot) * 100).toFixed(1)], itemStyle: { color: '#10b981' } }
          ]
        });
      }
    }

    // 4. Frequency Charts
    function initFrequencyCharts() {
      const dom = document.getElementById('frequencyIntervalChart');
      if (dom && !chartInstances['frequencyInterval']) {
        const t = getChartTheme();
        const c = echarts.init(dom);
        chartInstances['frequencyInterval'] = c;

        const intervals = DATA.bet_frequency_intervals.map(d => d.interval);
        const pcts = DATA.bet_frequency_intervals.map(d => d.pct);

        c.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          grid: { top: 20, right: 30, bottom: 40, left: 140 },
          xAxis: { type: 'value', axisLabel: { color: t.textColor, fontSize: 10, formatter: v => v + '%' } },
          yAxis: { type: 'category', data: intervals, axisLabel: { color: t.textColor, fontSize: 10 } },
          series: [{
            type: 'bar',
            data: pcts,
            itemStyle: { color: '#f43f5e', borderRadius: [0, 6, 6, 0] },
            label: { show: true, position: 'right', color: t.textColor, fontSize: 10, formatter: p => p.value + '%' }
          }]
        });
      }
    }

    // 5. Correlation Charts
    function initCorrelationCharts() {
      const dom1 = document.getElementById('balanceScatterChart');
      if (dom1 && !chartInstances['balanceScatter']) {
        const t = getChartTheme();
        const c1 = echarts.init(dom1);
        chartInstances['balanceScatter'] = c1;

        const pts = DATA.balance_vs_bet_scatter.map(p => [
          p.balance,
          p.bet,
          p.ratio_pct,
          p.game,
          p.outcome
        ]);

        c1.setOption({
          backgroundColor: t.bg,
          tooltip: {
            trigger: 'item',
            backgroundColor: t.tooltipBg,
            borderColor: t.tooltipBorder,
            textStyle: { color: t.tooltipText, fontSize: 11 },
            formatter: p => `
              <div><strong>Game:</strong> ${p.value[3]}</div>
              <div><strong>Balance:</strong> ${formatCurrency(p.value[0])}</div>
              <div><strong>Bet Size:</strong> ${formatCurrency(p.value[1])}</div>
              <div><strong>Bet-to-Balance:</strong> ${p.value[2]}%</div>
              <div><strong>Outcome:</strong> ${p.value[4]}</div>
            `
          },
          grid: { top: 30, right: 30, bottom: 40, left: 60 },
          xAxis: { type: 'log', name: 'Balance', splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } }, axisLabel: { color: t.textColor, fontSize: 9, formatter: v => formatCurrency(v) } },
          yAxis: { type: 'log', name: 'Bet', splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } }, axisLabel: { color: t.textColor, fontSize: 9, formatter: v => formatCurrency(v) } },
          series: [{
            type: 'scatter',
            data: pts,
            symbolSize: 8,
            itemStyle: {
              color: p => p.value[3] === 'baccarat' ? '#10b981' : (p.value[3] === 'dragon_tiger' ? '#f59e0b' : (p.value[3] === 'roulette' ? '#8b5cf6' : '#ec4899')),
              opacity: 0.75
            }
          }]
        });
      }

      const dom2 = document.getElementById('balanceTierGameChart');
      if (dom2 && !chartInstances['balanceTierGame']) {
        const t = getChartTheme();
        const c2 = echarts.init(dom2);
        chartInstances['balanceTierGame'] = c2;

        const tiers = DATA.balance_tiers.map(b => b.tier);
        const baccaratPcts = DATA.balance_tiers.map(b => b.games['baccarat'] ? b.games['baccarat'].pct : 0);
        const dtPcts = DATA.balance_tiers.map(b => b.games['dragon_tiger'] ? b.games['dragon_tiger'].pct : 0);
        const roulettePcts = DATA.balance_tiers.map(b => b.games['roulette'] ? b.games['roulette'].pct : 0);

        c2.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'axis', backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder, textStyle: { color: t.tooltipText, fontSize: 11 } },
          legend: { data: ['Baccarat', 'Dragon Tiger', 'Roulette'], textStyle: { color: t.textColor } },
          grid: { top: 35, right: 30, bottom: 40, left: 50 },
          xAxis: { type: 'category', data: tiers, axisLabel: { color: t.textColor, fontSize: 10 } },
          yAxis: { type: 'value', max: 100, axisLabel: { color: t.textColor, fontSize: 10, formatter: v => v + '%' } },
          series: [
            { name: 'Baccarat', type: 'bar', data: baccaratPcts, itemStyle: { color: '#10b981' } },
            { name: 'Dragon Tiger', type: 'bar', data: dtPcts, itemStyle: { color: '#f59e0b' } },
            { name: 'Roulette', type: 'bar', data: roulettePcts, itemStyle: { color: '#8b5cf6' } }
          ]
        });
      }
    }

    // Slide Deck Render
    function renderSlideCharts() {
      const t = getChartTheme();
      if (currentSlide === 1) {
        const s1 = document.getElementById('slideTimingChart');
        if (s1) {
          const c = echarts.init(s1);
          chartInstances['slideTiming'] = c;
          c.setOption({
            backgroundColor: t.bg,
            grid: { top: 20, right: 20, bottom: 30, left: 40 },
            xAxis: { type: 'category', data: DATA.hourly_credit_and_wins.map(d => d.hour), axisLabel: { color: t.textColor, fontSize: 8 } },
            yAxis: { type: 'value', axisLabel: { color: t.textColor, fontSize: 8 } },
            series: [{ type: 'line', data: DATA.hourly_credit_and_wins.map(d => d.wins), lineStyle: { color: '#10b981' } }]
          });
        }
      } else if (currentSlide === 2) {
        const s2 = document.getElementById('slideGameChart');
        if (s2) {
          const c = echarts.init(s2);
          chartInstances['slideGame'] = c;
          c.setOption({
            backgroundColor: t.bg,
            grid: { top: 20, right: 20, bottom: 40, left: 50 },
            xAxis: { type: 'category', data: DATA.games.map(d => d.game), axisLabel: { color: t.textColor, fontSize: 9, rotate: 20 } },
            yAxis: { type: 'value', axisLabel: { color: t.textColor, fontSize: 8 } },
            series: [{ type: 'bar', data: DATA.games.map(d => d.total_bets), itemStyle: { color: '#10b981' } }]
          });
        }
      }
    }
  </script>"""

    render_dashboard(
        data_file=DATA_FILE,
        sections_dir=SECTIONS_DIR,
        output_html=out_file,
        title=TITLE,
        extra_scripts=extra_scripts,
    )

    print(f"Generated {out_file} ({out_file.stat().st_size:,} chars)")
    return True


if __name__ == "__main__":
    build_dashboard()
