from pathlib import Path
import json
import shutil
import sys
import tempfile

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.txt").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.txt").exists():
            WORKSPACE = _parent
            break

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render import render_dashboard

DATA_FILE = WORKSPACE / "output" / "data" / "dashboard_data.json"
REPORT_DIR = WORKSPACE / "output"
DATA_DIR = WORKSPACE / "output" / "data"
CHUNK_SRC_DIR = WORKSPACE / "output" / "chunks"
CHUNK_DIR = REPORT_DIR / "dossier_chunks"
CHUNK_SIZE = 1000

SECTIONS_DIR = SCRIPT_DIR / "sections"
OUT_FILE = WORKSPACE / "output" / "dashboards" / "bi_dashboard.html"
TITLE = "Oriental Gaming Title BI & Risk Intelligence Console"


def merge_per_file_dossiers():
    """Merge 27 per-file indices into unified index + re-chunk trajectories."""
    print("Merging per-file dossier indices...")
    
    # Collect all player data from per-file indices
    player_data = {}  # pid -> {index_entry, detail_chunks}
    
    for f_idx in range(27):
        idx_path = DATA_DIR / f"all_players_index_{f_idx:02d}.json"
        if not idx_path.exists():
            continue
        
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        
        # Load all detail chunks for this file ONCE (avoid re-reading/parsing
        # the same ~1-5MB chunk file for every player entry).
        chunk_details = {}
        chunk_dir = CHUNK_SRC_DIR / f"dossier_chunks_{f_idx:02d}"
        for cid in range(idx["meta"]["total_chunks"]):
            chunk_path = chunk_dir / f"chunk_{cid:04d}.js"
            if chunk_path.exists():
                with open(chunk_path, "r", encoding="utf-8") as cf:
                    content = cf.read()
                    if content.startswith("window.DOSSIER_CHUNK_"):
                        content = content.split("=", 1)[1].rstrip(";")
                        chunk_details.update(json.loads(content))

        for entry in idx.get("players", []):
            pid = entry["pid"]
            if pid not in player_data:
                player_data[pid] = {
                    "index_entry": entry,
                    "total_debit": entry["debit"],
                    "total_winlose": entry["winlose"],
                    "total_bets": entry["bets"],
                    "chunks": []
                }
            else:
                # Accumulate
                player_data[pid]["total_debit"] += entry["debit"]
                player_data[pid]["total_winlose"] += entry["winlose"]
                player_data[pid]["total_bets"] += entry["bets"]

            if pid in chunk_details:
                player_data[pid]["chunks"].append((f_idx, chunk_details[pid]))
    
    # Rebuild unified index sorted by total debit
    unified_entries = []
    for pid, data in player_data.items():
        entry = data["index_entry"].copy()
        entry["debit"] = round(data["total_debit"], 2)
        entry["winlose"] = round(data["total_winlose"], 2)
        entry["bets"] = data["total_bets"]
        entry["avg_bet"] = round(data["total_debit"] / data["total_bets"], 2) if data["total_bets"] else 0.0
        unified_entries.append((data["total_debit"], pid, entry, data["chunks"]))
    
    unified_entries.sort(key=lambda x: x[0], reverse=True)
    
    # Re-chunk and write unified chunks
    unified_chunks = defaultdict(dict)
    final_index_entries = []
    
    for rank, (total_debit, pid, entry, chunks) in enumerate(unified_entries):
        entry["id"] = rank
        final_index_entries.append(entry)
        
        # Concatenate trajectories from all chunks chronologically by timestamps
        if chunks:
            # Sort chunks by first timestamp
            sorted_chunks = sorted(chunks, key=lambda x: x[1].get("first_seen", "") if x[1].get("first_seen") else "")
            
            merged_detail = {}
            merged_balance_series = []
            merged_timestamps = []
            merged_games = {}
            merged_hours = [0] * 24
            merged_devices = {}
            merged_operators = {}
            merged_recent_rounds = []
            
            first_seen = None
            last_seen = None
            peak_balance = 0.0
            min_balance = float('inf')
            total_balance_points = 0
            balance_sum = 0.0
            
            for f_idx, detail in sorted_chunks:
                # Track first/last seen
                if detail.get("first_seen"):
                    if first_seen is None or detail["first_seen"] < first_seen:
                        first_seen = detail["first_seen"]
                if detail.get("last_seen"):
                    if last_seen is None or detail["last_seen"] > last_seen:
                        last_seen = detail["last_seen"]
                
                # Merge balance_series and timestamps
                if "balance_series" in detail and "timestamps" in detail:
                    bs = detail["balance_series"]
                    ts = detail["timestamps"]
                    for b, t in zip(bs, ts):
                        merged_balance_series.append(b)
                        merged_timestamps.append(t)
                        balance_sum += b
                        total_balance_points += 1
                        if b > peak_balance:
                            peak_balance = b
                        if b < min_balance:
                            min_balance = b
                
                # Merge games
                for g in detail.get("games", []):
                    game_name = g.get("game", "Unknown")
                    if game_name not in merged_games:
                        merged_games[game_name] = {"game": game_name, "bets": 0, "debit": 0.0, "credit": 0.0, "wins": 0, "losses": 0}
                    merged_games[game_name]["bets"] += g.get("bets", 0)
                    merged_games[game_name]["debit"] += g.get("debit", 0.0)
                    merged_games[game_name]["credit"] += g.get("credit", 0.0)
                    merged_games[game_name]["wins"] += g.get("wins", 0)
                    merged_games[game_name]["losses"] += g.get("losses", 0)
                
                # Merge hours
                for h_idx, h_val in enumerate(detail.get("hours", [])):
                    if h_idx < 24:
                        merged_hours[h_idx] += h_val
                
                # Merge devices
                for dev, count in detail.get("devices", {}).items():
                    merged_devices[dev] = merged_devices.get(dev, 0) + count
                
                # Merge operators
                for op, count in detail.get("operators", {}).items():
                    merged_operators[op] = merged_operators.get(op, 0) + count
                
                # Merge recent_rounds (keep last 100 chronologically)
                merged_recent_rounds.extend(detail.get("recent_rounds", []))
            
            # Sort recent rounds by time and keep last 100
            merged_recent_rounds.sort(key=lambda x: x.get("time", ""))
            merged_recent_rounds = merged_recent_rounds[-100:]
            
            # Calculate win rates for games
            merged_games_list = []
            for g in merged_games.values():
                total = g["wins"] + g["losses"]
                g["win_rate_pct"] = round(g["wins"] / total * 100, 2) if total > 0 else 0.0
                merged_games_list.append(g)
            
            # Use base detail from first chunk and update with merged data
            merged_detail = sorted_chunks[0][1].copy()
            merged_detail["balance_series"] = merged_balance_series
            merged_detail["timestamps"] = merged_timestamps
            merged_detail["first_seen"] = first_seen
            merged_detail["last_seen"] = last_seen
            merged_detail["peak_balance"] = peak_balance
            merged_detail["min_balance"] = min_balance if min_balance != float('inf') else 0.0
            merged_detail["avg_balance"] = round(balance_sum / total_balance_points, 2) if total_balance_points > 0 else 0.0
            merged_detail["games"] = merged_games_list
            merged_detail["hours"] = merged_hours
            merged_detail["devices"] = merged_devices
            merged_detail["operators"] = merged_operators
            merged_detail["recent_rounds"] = merged_recent_rounds
            
            chunk_id = rank // CHUNK_SIZE
            unified_chunks[chunk_id][pid] = merged_detail
    
    # Write unified index
    unified_index = {
        "meta": {
            "total_players": len(final_index_entries),
            "total_rows": sum(e["bets"] for e in final_index_entries),
            "files": 27,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chunk_size": CHUNK_SIZE,
            "total_chunks": (len(final_index_entries) + CHUNK_SIZE - 1) // CHUNK_SIZE,
        },
        "players": final_index_entries,
    }
    
    INDEX_FILE = DATA_DIR / "all_players_index.json"
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(unified_index, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  -> {INDEX_FILE.name} ({INDEX_FILE.stat().st_size:,} bytes)")
    
    # Write unified chunks
    for cid in sorted(unified_chunks.keys()):
        js = "window.DOSSIER_CHUNK_%04d = " % cid + json.dumps(unified_chunks[cid], ensure_ascii=False, separators=(",", ":")) + ";"
        cpath = CHUNK_DIR / ("chunk_%04d.js" % cid)
        with open(cpath, "w", encoding="utf-8") as f:
            f.write(js)
    print(f"  -> {len(unified_chunks)} unified chunks in dossier_chunks/")
    
    return unified_index

# Load or build the unified index. Per-export chunks may contain fields added
# after the aggregate was created (for example, timestamps used by the dossier
# activity calendar), so rebuild whenever a source index is newer. Also force a
# rebuild when the unified chunks are missing/incomplete (skip-guard previously
# only compared timestamps, which let an existing-but-stale index short-circuit
# the merge and leave output/dossier_chunks/ empty → empty dossier tables).

INDEX_FILE = DATA_DIR / "all_players_index.json"
source_indexes = [DATA_DIR / f"all_players_index_{f_idx:02d}.json" for f_idx in range(27)]
source_indexes = [path for path in source_indexes if path.exists()]

def chunks_complete() -> bool:
    """Return True only if output/dossier_chunks/ holds the expected chunk files."""
    if not CHUNK_DIR.exists():
        return False
    expected = None
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                expected = json.load(f).get("meta", {}).get("total_chunks")
        except (json.JSONDecodeError, OSError):
            expected = None
    chunk_files = [p for p in CHUNK_DIR.glob("chunk_*.js") if p.is_file()]
    if expected is not None:
        return len(chunk_files) >= expected
    return len(chunk_files) > 0

CONTROLLER_JS = r'''    // Load dataset
    console.log("Oriental Gaming Title BI Dashboard Loaded Data:", DATA);

    let isPresentationMode = false;
    let currentSlide = 1;
    const totalSlides = 8;
    let isScatterLog = true;
    let isHeatmapNormalized = true;

    // Initialize Dashboard
    document.addEventListener('DOMContentLoaded', () => {
      populateWhaleTable();
      populateChaserTable();
      populateOperatorTable();
      populateWhaleGroupDossier();
      populateChaserGroupDossier();
      initCharts();
      setupKeyboardNavigation();
    });

    // Tab Navigation
    function switchTab(tabId) {
      if (isPresentationMode) togglePresentationMode();
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

      const targetPane = document.getElementById(`tab-${tabId}`);
      if (targetPane) targetPane.classList.remove('hidden');

      // Highlight tab button
      const clickedBtn = Array.from(document.querySelectorAll('.nav-tab')).find(b => b.getAttribute('onclick')?.includes(tabId));
      if (clickedBtn) clickedBtn.classList.add('active');

      // Initialize or resize charts for active tab
      setTimeout(() => {
        if (tabId === 'overview') {
          if (!chartInstances['overviewTraffic']) initOverviewTrafficChart();
          if (!chartInstances['overviewPillar']) initOverviewPillarChart();
        } else if (tabId === 'whales') {
          if (!chartInstances['whaleScatter']) initWhaleScatterChart();
          if (!chartInstances['whaleGeo']) initWhaleGeoChart();
        } else if (tabId === 'chasers') {
          if (!chartInstances['chaserTiers']) initChaserTiersChart();
          if (!chartInstances['chaserTilt']) initChaserTiltChart();
          if (!chartInstances['chaserOutcome']) initChaserOutcomePie();
        } else if (tabId === 'traffic') {
          if (!chartInstances['trafficCurve']) initTrafficCurveChart();
          if (!chartInstances['trafficHeatmap']) initTrafficHeatmapChart();
          if (!chartInstances['trafficDensity']) initTrafficDensityChart();
        } else if (tabId === 'operators') {
          if (!chartInstances['operatorRoi']) initOperatorRoiChart();
          if (!chartInstances['operatorBubble']) initOperatorBubbleChart();
        }
        resizeAllCharts();
      }, 50);
    }

    // Toggle Presentation Mode
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
        switchTab('overview');
      }
    }

    // Slide Controller
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

    // Theme Switcher
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

    // Helpers
    function formatCurrency(val) {
      if (val >= 1e9) return (val / 1e9).toFixed(2) + 'B';
      if (val >= 1e6) return (val / 1e6).toFixed(2) + 'M';
      if (val >= 1e3) return (val / 1e3).toFixed(1) + 'K';
      return Number(val).toLocaleString();
    }

    // Populate Whales Table
    function populateWhaleTable() {
      const tbody = document.getElementById('whalesTableBody');
      tbody.innerHTML = '';
      DATA.whales.top_20.forEach((w, idx) => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/40 transition";
        
        let archetype = "Burst Whale";
        let badgeClass = "bg-amber-500/10 text-amber-400 border border-amber-500/20";
        if (w.avg_session_hours < 0.05) {
          archetype = "Lightning / Bot";
          badgeClass = "bg-rose-500/10 text-rose-400 border border-rose-500/20";
        } else if (w.avg_session_hours > 0.4) {
          archetype = "Sustained Grinder";
          badgeClass = "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20";
        }

        tr.innerHTML = `
          <td class="py-3 px-3 text-slate-400 font-bold">#${idx + 1}</td>
          <td class="py-3 px-3 text-white font-semibold flex items-center gap-2">
            <i class="fa-solid fa-crown text-amber-400 text-[10px]"></i>
            <code>${w.player_id}</code>
          </td>
          <td class="py-3 px-3 text-slate-300 font-sans">
            <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] bg-slate-800 border border-slate-700">
              ${w.country === 'Indonesia' ? '🇮🇩 IDR' : '🇻🇳 VND'}
            </span>
          </td>
          <td class="py-3 px-3 text-right text-amber-400 font-bold">${w.total_debit.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-slate-300">${w.total_bets.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-slate-300">${w.avg_bet.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-cyan-300 font-bold">${w.avg_session_hours}h</td>
          <td class="py-3 px-3 text-center">
            <span class="text-[10px] px-2 py-0.5 rounded-full font-sans font-semibold ${badgeClass}">
              ${archetype}
            </span>
          </td>
          <td class="py-3 px-3 text-center">
            <button onclick="openPlayerDossierById('${w.player_id}', 'whales')" class="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/25 text-amber-400 text-[10px] font-bold border border-amber-500/30 transition flex items-center gap-1 mx-auto" title="Open Individual Player Dossier">
              <i class="fa-solid fa-user-secret"></i> Open
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Filter Whales Table
    function filterWhaleTable() {
      const query = document.getElementById('whaleSearchInput').value.toLowerCase();
      document.querySelectorAll('#whalesTableBody tr').forEach(row => {
        const txt = row.textContent.toLowerCase();
        row.style.display = txt.includes(query) ? '' : 'none';
      });
    }

    // Populate Chasers Table
    function populateChaserTable() {
      const tbody = document.getElementById('chasersTableBody');
      tbody.innerHTML = '';
      DATA.chasers.top_extreme.forEach(c => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/40 transition";
        const isNetLoss = c.total_winlose < 0;
        tr.innerHTML = `
          <td class="py-3 px-3 text-white font-semibold flex items-center gap-1.5">
            <i class="fa-solid fa-triangle-exclamation text-rose-400 text-[10px]"></i>
            <code>${c.player_id}</code>
          </td>
          <td class="py-3 px-3 text-right text-rose-400 font-bold">${c.spike_multiplier.toLocaleString()}x</td>
          <td class="py-3 px-3 text-center text-amber-300 font-bold">${c.max_consecutive_losses}</td>
          <td class="py-3 px-3 text-right text-slate-300">${c.avg_loss_debit.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-rose-300 font-bold">${c.spike_debit.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-slate-400">${c.total_bets.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-slate-300">${c.total_debit.toLocaleString()}</td>
          <td class="py-3 px-3 text-right ${isNetLoss ? 'text-rose-400' : 'text-emerald-400'} font-bold">
            ${c.total_winlose.toLocaleString()}
          </td>
          <td class="py-3 px-3 text-center font-sans">
            <span class="text-[10px] px-2 py-0.5 rounded-full font-semibold ${isNetLoss ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}">
              ${isNetLoss ? 'Net Loser' : 'Net Winner'}
            </span>
          </td>
          <td class="py-3 px-3 text-center">
            <button onclick="openPlayerDossierById('${c.player_id}', 'chasers')" class="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/25 text-amber-400 text-[10px] font-bold border border-amber-500/30 transition flex items-center gap-1 mx-auto" title="Open Individual Player Dossier">
              <i class="fa-solid fa-user-secret"></i> Open
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // =========================================================================
    // GROUP DOSSIER POPULATION
    // =========================================================================

    // Populate Whale Group Dossier
    function populateWhaleGroupDossier() {
      const whales = DATA.whales.top_20;
      const countryDist = DATA.whales.country_distribution;

      // KPI Values
      document.getElementById('whaleGroupTotalDebit').textContent = formatCurrency(DATA.whales.total_debit);
      document.getElementById('whaleGroupTotalBets').textContent = DATA.whales.total_bets.toLocaleString();
      
      // Calculate average session
      const avgSession = whales.reduce((sum, w) => sum + w.avg_session_hours, 0) / whales.length;
      document.getElementById('whaleGroupAvgSession').textContent = avgSession.toFixed(2) + 'h';
      
      document.getElementById('whaleGroupCountries').textContent = countryDist.length;
      
      // Concentration: whale debit / total casino debit
      const totalCasinoDebit = DATA.metadata.total_debit_all_operators;
      const whaleConcentration = (DATA.whales.total_debit / totalCasinoDebit * 100).toFixed(1);
      document.getElementById('whaleGroupConcentration').textContent = whaleConcentration + '%';

      // Geographic Breakdown
      const geoContainer = document.getElementById('whaleGroupGeoBreakdown');
      geoContainer.innerHTML = '';
      countryDist.forEach(c => {
        const pct = (c.debit / DATA.whales.total_debit * 100).toFixed(1);
        const FLAG_MAP = {'Indonesia':'🇮🇩','Vietnam':'🇻🇳','China':'🇨🇳','Bangladesh':'🇧🇩','Thailand':'🇹🇭','Malaysia':'🇲🇾','India':'🇮🇳','Myanmar':'🇲🇲','Philippines':'🇵🇭','Cambodia':'🇰🇭','Laos':'🇱🇦','Singapore':'🇸🇬','South Korea':'🇰🇷','Japan':'🇯🇵','USA':'🇺🇸','Hong Kong':'🇭🇰','Taiwan':'🇹🇼','Nepal':'🇳🇵','Turkey':'🇹🇷','Crypto':'₿','Unknown':'🌐'};
        const flag = FLAG_MAP[c.country] || '🌐';
        const div = document.createElement('div');
        div.className = 'p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 flex items-center justify-between';
        div.innerHTML = `
          <div class="flex items-center gap-2 text-xs">
            <span class="text-base">${flag}</span>
            <span class="font-semibold text-white">${c.country}</span>
            <span class="text-slate-400">({c.count} whales)</span>
          </div>
          <div class="text-right">
            <div class="font-bold text-slate-200 font-mono">${formatCurrency(c.debit)}</div>
            <div class="text-[10px] text-amber-400 font-semibold">${pct}%</div>
          </div>
        `;
        geoContainer.appendChild(div);
      });

      // Behavioral Archetypes
      const archetypeContainer = document.getElementById('whaleGroupArchetypes');
      let lightning = 0, burst = 0, grinder = 0;
      whales.forEach(w => {
        if (w.avg_session_hours < 0.05) lightning++;
        else if (w.avg_session_hours > 0.4) grinder++;
        else burst++;
      });
      const archetypes = [
        { label: 'Lightning / Bot', count: lightning, color: 'rose', icon: 'fa-bolt' },
        { label: 'Burst Whale', count: burst, color: 'amber', icon: 'fa-gem' },
        { label: 'Sustained Grinder', count: grinder, color: 'cyan', icon: 'fa-hourglass-half' }
      ];
      archetypeContainer.innerHTML = '';
      archetypes.forEach(a => {
        if (a.count > 0) {
          const div = document.createElement('div');
          div.className = 'p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 flex items-center justify-between';
          div.innerHTML = `
            <div class="flex items-center gap-2 text-xs">
              <i class="fa-solid ${a.icon} text-${a.color}-400"></i>
              <span class="font-semibold text-white">${a.label}</span>
            </div>
            <div class="text-right">
              <div class="font-bold text-${a.color}-400 font-mono">${a.count}</div>
              <div class="text-[10px] text-slate-400">${((a.count/whales.length)*100).toFixed(0)}% of group</div>
            </div>
          `;
          archetypeContainer.appendChild(div);
        }
      });

      // Key Insights
      const insightsContainer = document.getElementById('whaleGroupInsights');
      const topWhale = whales[0];
      const chinaShare = countryDist.find(c => c.country === 'China');
      const indonesiaShare = countryDist.find(c => c.country === 'Indonesia');
      const vietnamShare = countryDist.find(c => c.country === 'Vietnam');
      
const topCountry = countryDist[0];
            const topPct = ((topCountry.debit / DATA.whales.total_debit) * 100).toFixed(1);
            const top2 = countryDist.slice(0, 2);
            const top2Pct = ((top2.reduce((s, c) => s + c.debit, 0) / DATA.whales.total_debit) * 100).toFixed(1);
            const insights = [
              `<strong>Dominant Profile:</strong> ${lightning}/${whales.length} whales (${((lightning/whales.length)*100).toFixed(0)}%) are "Lightning" archetypes with sub-3-minute avg sessions — likely automated/high-frequency execution.`,
              `<strong>Geographic Concentration:</strong> ${topCountry.country} dominates with ${topCountry.count}/${whales.length} whales (${topPct}% of whale debit). The top ${top2.length} countries control ${top2Pct}% of group turnover.`,
              `<strong>Top Individual:</strong> <code>${topWhale.player_id}</code> (${topWhale.country}) — ${formatCurrency(topWhale.total_debit)} across ${topWhale.total_bets} bets (avg session: ${topWhale.avg_session_hours}h).`,
              `<strong>Volume Velocity:</strong> Group averages ${(DATA.whales.total_debit / DATA.whales.total_bets).toFixed(0)} PHP per bet. Whales execute ${(DATA.whales.total_bets / whales.length).toFixed(0)} bets each on average.`,
              `<strong>Session Brevity:</strong> ${((lightning/whales.length)*100).toFixed(0)}% of whales complete sessions in under 3 minutes, indicating burst-betting patterns rather than recreational play.`
            ];
      insightsContainer.innerHTML = insights.map(i => `<li>${i}</li>`).join('');
    }

    // Populate Chaser Group Dossier
    function populateChaserGroupDossier() {
      const chasers = DATA.chasers;
      const topExtreme = DATA.chasers.top_extreme;
      const l3Entry = chasers.loss_streak_distribution.find(d => d.streak === 3);
      const l3Pct = l3Entry ? l3Entry.pct : 0;
      const l3Count = l3Entry ? l3Entry.players : 0;

      // KPI Values
      document.getElementById('chaserGroupTotalDebit').textContent = formatCurrency(chasers.total_debit);
      document.getElementById('chaserGroupTotalCount').textContent = chasers.total_count.toLocaleString();
      document.getElementById('chaserGroupNetLosers').textContent = chasers.net_loser_pct.toFixed(1) + '%';
      document.getElementById('chaserGroupTotalHarm').textContent = formatCurrency(chasers.total_winlose);
      document.getElementById('chaserGroupMaxSpike').textContent = topExtreme.length > 0 ? topExtreme[0].spike_multiplier.toFixed(0) + 'x' : 'N/A';

// Static descriptive labels that hardcode the stale 11,978 count
      const navFlagged = document.getElementById('navChaserFlagged');
      if (navFlagged) navFlagged.textContent = chasers.total_count.toLocaleString() + ' Flagged';
      const chaserGroupProfiles = document.getElementById('chaserGroupProfiles');
      if (chaserGroupProfiles) chaserGroupProfiles.textContent = chasers.total_count.toLocaleString() + ' Profiles';
      const area2Flagged = document.getElementById('area2Flagged');
      if (area2Flagged) area2Flagged.textContent = chasers.total_count.toLocaleString();
      const chaserGroupSubtitle = document.getElementById('chaserGroupSubtitle');
      if (chaserGroupSubtitle) chaserGroupSubtitle.textContent = chasers.total_count.toLocaleString();
      const kpiExtremeSpike = document.getElementById('kpiExtremeSpike');
      if (kpiExtremeSpike) kpiExtremeSpike.textContent = (topExtreme.length > 0 ? topExtreme[0].spike_multiplier.toFixed(1) : 'N/A') + 'x Spike';
      const kpiNetLoserPct = document.getElementById('kpiNetLoserPct');
      if (kpiNetLoserPct) kpiNetLoserPct.textContent = chasers.net_loser_pct.toFixed(2) + '% Losers';
      const kpiNetLoserCount = document.getElementById('kpiNetLoserCount');
      if (kpiNetLoserCount) kpiNetLoserCount.textContent = chasers.net_losers.toLocaleString() + ' players suffered net loss';
      const kpiL3Pct = document.getElementById('kpiL3Pct');
      if (kpiL3Pct) kpiL3Pct.textContent = l3Pct.toFixed(1) + '% of chasers tilt at streak #3';
      const kpiChaserHarm = document.getElementById('kpiChaserHarm');
      if (kpiChaserHarm) kpiChaserHarm.textContent = formatCurrency(chasers.total_winlose);
      const pillarL3Pct = document.getElementById('pillarL3Pct');
      if (pillarL3Pct) pillarL3Pct.textContent = l3Pct.toFixed(1) + '%';

      // Risk Tier Distribution
      const tierContainer = document.getElementById('chaserGroupRiskTiers');
      tierContainer.innerHTML = '';
      const tierOrder = ['Extreme (>=1000x)', 'Critical (100x-999x)', 'High (20x-99x)', 'Moderate (5x-19x)', 'Low (<5x)'];
      const tierColors = { 'Extreme (>=1000x)': 'rose', 'Critical (100x-999x)': 'amber', 'High (20x-99x)': 'orange', 'Moderate (5x-19x)': 'yellow', 'Low (<5x)': 'green' };
      chasers.risk_tiers.forEach(tier => {
        const tierLabel = tier.tier;
        const pct = (tier.count / chasers.total_count * 100).toFixed(1);
        const div = document.createElement('div');
        div.className = 'p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 flex items-center justify-between';
        div.innerHTML = `
          <div class="flex items-center gap-2 text-xs">
            <span class="w-2 h-2 rounded-full bg-${tierColors[tierLabel]}-500"></span>
            <span class="font-semibold text-white">${tierLabel}</span>
          </div>
          <div class="text-right">
            <div class="font-bold text-${tierColors[tierLabel]}-400 font-mono">${tier.count.toLocaleString()}</div>
            <div class="text-[10px] text-slate-400">${pct}% of chasers</div>
          </div>
        `;
        tierContainer.appendChild(div);
      });

      // Tilt Threshold Analysis
      const tiltContainer = document.getElementById('chaserGroupTiltThresholds');
      tiltContainer.innerHTML = '';
      const keyStreaks = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
      keyStreaks.forEach(streak => {
        const data = chasers.loss_streak_distribution.find(d => d.streak === streak);
        if (data && data.players > 0) {
          const div = document.createElement('div');
          div.className = 'p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 flex items-center justify-between';
          const isPeak = streak === 3;
          div.innerHTML = `
            <div class="flex items-center gap-2 text-xs">
              <span class="font-mono text-${isPeak ? 'rose' : 'slate'}-400 font-bold">L${streak}</span>
              <span class="font-semibold text-${isPeak ? 'rose' : 'white'}-300">${streak} Consecutive Losses</span>
              ${isPeak ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold">PEAK</span>' : ''}
            </div>
            <div class="text-right">
              <div class="font-bold text-${isPeak ? 'rose' : 'slate'}-300 font-mono">${data.players.toLocaleString()}</div>
              <div class="text-[10px] text-slate-400">${data.pct.toFixed(1)}% of chasers</div>
            </div>
          `;
          tiltContainer.appendChild(div);
        }
      });

      // Key Risk Insights
      const insightsContainer = document.getElementById('chaserGroupInsights');
      const extremeCount = chasers.risk_tiers.find(t => t.tier === 'Extreme (>=1000x)')?.count || 0;
      const criticalCount = chasers.risk_tiers.find(t => t.tier === 'Critical (100x-999x)')?.count || 0;
      
      const insights = [
        `<strong>Loss-Streak Tipping Point:</strong> <span class="text-rose-400 font-bold">${l3Count} chasers (${l3Pct.toFixed(1)}%)</span> initiate panic spikes at exactly <strong>3 consecutive losses</strong> — the decisive psychological tilt threshold.`,
        `<strong>Chasing Is Financially Destructive:</strong> <span class="text-rose-400 font-bold">${chasers.net_loser_pct.toFixed(1)}%</span> of all chasers end in net drawdown (${formatCurrency(Math.abs(chasers.total_winlose))} cumulative loss). Bet escalation deepens losses rather than recovering them.`,
        `<strong>Extreme Risk Cohort:</strong> ${extremeCount} players in "Extreme" tier (≥1,000x spike) and ${criticalCount} in "Critical" tier (100-999x). Top spike: <code>${topExtreme[0]?.player_id || 'N/A'}</code> at ${topExtreme[0]?.spike_multiplier?.toFixed(0) || 'N/A'}x.`,
        `<strong>Streak Escalation:</strong> Streaks 3-5 capture ${((chasers.loss_streak_distribution.filter(d => d.streak >= 3 && d.streak <= 5).reduce((sum, d) => sum + d.players, 0)) / chasers.total_count * 100).toFixed(1)}% of all tilt events. Interventions at L3 would address the majority.`,
        `<strong>Net Winner Anomaly:</strong> Only ${chasers.net_winner_pct.toFixed(1)}% of chasers (${chasers.net_winners} players) achieve net positive P&L — likely luck-driven outliers, not sustainable strategy.`
      ];
      insightsContainer.innerHTML = insights.map(i => `<li>${i}</li>`).join('');
    }

    // Populate Operators Table
    function populateOperatorTable() {
      const tbody = document.getElementById('operatorsTableBody');
      tbody.innerHTML = '';
      DATA.operators.top_50.forEach((op, idx) => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-800/40 transition";
        const isPositiveGGR = op.ggr > 0;
        tr.innerHTML = `
          <td class="py-3 px-3 text-white font-semibold flex items-center gap-1.5">
            <span class="text-slate-500 text-[10px] font-mono">#${idx+1}</span>
            <code>${op.operator}</code>
          </td>
          <td class="py-3 px-3 text-slate-300 font-sans">${op.countries}</td>
          <td class="py-3 px-3 text-right text-emerald-400 font-bold">${op.total_debit.toLocaleString()}</td>
          <td class="py-3 px-3 text-right ${isPositiveGGR ? 'text-emerald-400' : 'text-rose-400'} font-bold">
            ${op.ggr.toLocaleString()}
          </td>
          <td class="py-3 px-3 text-right font-bold ${op.operator_hold_margin >= 3 ? 'text-emerald-300' : 'text-slate-300'}">
            ${op.operator_hold_margin}%
          </td>
          <td class="py-3 px-3 text-right text-slate-400 font-mono">${op.operator_roi}%</td>
          <td class="py-3 px-3 text-right text-slate-300">${op.total_bets.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-cyan-300 font-bold">${op.unique_players.toLocaleString()}</td>
          <td class="py-3 px-3 text-right text-slate-400">${op.avg_bet.toLocaleString()}</td>
          <td class="py-3 px-3 text-center">
            <button onclick="openOperatorDossierById('${op.operator}')" class="px-2.5 py-1 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/25 text-cyan-400 text-[10px] font-bold border border-cyan-500/30 transition flex items-center gap-1 mx-auto" title="Open Individual Operator Dossier">
              <i class="fa-solid fa-building-columns"></i> Open
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // Filter Operator Table
    function filterOperatorTable() {
      const query = document.getElementById('operatorSearchInput').value.toLowerCase();
      document.querySelectorAll('#operatorsTableBody tr').forEach(row => {
        const txt = row.textContent.toLowerCase();
        row.style.display = txt.includes(query) ? '' : 'none';
      });
    }

    // CSV Exporter
    function exportTableToCSV(tableId, filename) {
      let csv = [];
      const rows = document.querySelectorAll(`#${tableId} tr`);
      for (let i = 0; i < rows.length; i++) {
        let row = [], cols = rows[i].querySelectorAll('td, th');
        for (let j = 0; j < cols.length; j++) {
          let data = cols[j].innerText.replace(/(\\r\\n|\\n|\\r)/gm, '').replace(/(\\s\\s+)/gm, ' ');
          data = data.replace(/"/g, '""');
          row.push('"' + data + '"');
        }
        csv.push(row.join(','));
      }
      const csvFile = new Blob([csv.join('\\n')], { type: 'text/csv' });
      const downloadLink = document.createElement('a');
      downloadLink.download = filename;
      downloadLink.href = window.URL.createObjectURL(csvFile);
      downloadLink.style.display = 'none';
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
    }

    // =========================================================================
    // ECHARTS INITIALIZATION
    // =========================================================================

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

    function initCharts() {
      initOverviewTrafficChart();
      initOverviewPillarChart();
      initWhaleScatterChart();
      initWhaleGeoChart();
      initChaserTiersChart();
      initChaserTiltChart();
      initChaserOutcomePie();
      initTrafficCurveChart();
      initTrafficHeatmapChart();
      initTrafficDensityChart();
      initOperatorRoiChart();
      initOperatorBubbleChart();
    }

    function reinitAllCharts() {
      Object.values(chartInstances).forEach(c => c && c.dispose());
      chartInstances = {};
      initCharts();
      if (isPresentationMode) renderSlideCharts();
    }

    function resizeAllCharts() {
      Object.values(chartInstances).forEach(c => c && c.resize());
    }
    window.addEventListener('resize', resizeAllCharts);

    // 1. Overview Traffic
    function initOverviewTrafficChart() {
      const dom = document.getElementById('overviewTrafficChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['overviewTraffic'] = chart;

      const hours = DATA.traffic.hourly_curve.map(d => d.hour);
      const bets = DATA.traffic.hourly_curve.map(d => d.bets);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'axis',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => `<strong>${params[0].name}</strong>: ${params[0].value.toLocaleString()} Bets`
        },
        grid: { top: 20, right: 20, bottom: 30, left: 60 },
        xAxis: {
          type: 'category',
          data: hours,
          axisLine: { lineStyle: { color: t.gridBorder } },
          axisLabel: { color: t.textColor, fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10, formatter: v => (v/1000).toFixed(0) + 'K' }
        },
        series: [{
          data: bets,
          type: 'line',
          smooth: true,
          lineStyle: { color: '#6366f1', width: 3 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(99, 102, 241, 0.45)' },
              { offset: 1, color: 'rgba(99, 102, 241, 0.01)' }
            ])
          },
          markPoint: {
            data: [
              { type: 'max', name: 'Peak', itemStyle: { color: '#f43f5e' } }
            ]
          }
        }]
      });
    }

    // 2. Overview Pillar Chart
    function initOverviewPillarChart() {
      const dom = document.getElementById('overviewPillarChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['overviewPillar'] = chart;

      const nonWhaleDebit = DATA.metadata.total_debit_all_operators - DATA.whales.total_debit;
      const whalePct = ((DATA.whales.total_debit / DATA.metadata.total_debit_all_operators) * 100).toFixed(1);
      const otherPct = (100 - parseFloat(whalePct)).toFixed(1);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'item',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => `<strong>${params.name}</strong>: ${formatCurrency(params.value)} (${params.percent}%)`
        },
        legend: {
          bottom: 0,
          textStyle: { color: t.textColor, fontSize: 11 }
        },
        series: [{
          name: 'Revenue Concentration',
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['50%', '45%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 8, borderColor: isDark() ? '#111726' : '#ffffff', borderWidth: 2 },
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold', color: t.titleColor } },
          data: [
            { value: DATA.whales.total_debit, name: 'Top 20 Whales (' + whalePct + '%)', itemStyle: { color: '#f59e0b' } },
            { value: nonWhaleDebit, name: 'Other Players (' + otherPct + '%)', itemStyle: { color: '#3b82f6' } }
          ]
        }]
      });
    }

    // 3. Whale Scatter Chart
    function initWhaleScatterChart() {
      const dom = document.getElementById('whaleScatterChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['whaleScatter'] = chart;

      const scatterData = DATA.whales.top_20.map(w => [
        w.avg_session_hours,
        w.total_debit,
        w.total_bets,
        w.player_id,
        w.country,
        w.avg_bet
      ]);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'item',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => {
            const d = params.value;
            return `
              <div class="font-sans">
                <div class="font-bold text-indigo-400 mb-1">${d[3]} (${d[4]})</div>
                <div>Avg Session: <strong>${d[0]} Hours</strong></div>
                <div>Total Debit: <strong>${Number(d[1]).toLocaleString()}</strong></div>
                <div>Total Bets: <strong>${Number(d[2]).toLocaleString()}</strong></div>
                <div>Avg Bet Size: <strong>${Number(d[5]).toLocaleString()}</strong></div>
              </div>
            `;
          }
        },
        grid: { top: 30, right: 30, bottom: 50, left: 80 },
        xAxis: {
          name: 'Avg Session (Hours)',
          nameLocation: 'middle',
          nameGap: 30,
          nameTextStyle: { color: t.textColor, fontSize: 11 },
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10 },
          axisLine: { lineStyle: { color: t.gridBorder } }
        },
        yAxis: {
          name: isScatterLog ? 'Total Debit (Log Scale)' : 'Total Debit',
          type: isScatterLog ? 'log' : 'value',
          nameTextStyle: { color: t.textColor, fontSize: 11 },
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10, formatter: v => formatCurrency(v) },
          axisLine: { lineStyle: { color: t.gridBorder } }
        },
        series: [{
          type: 'scatter',
          data: scatterData,
          symbolSize: data => Math.min(60, Math.max(16, Math.sqrt(data[2]) * 0.25)),
          itemStyle: {
            color: p => p.value[4] === 'Indonesia' ? '#6366f1' : '#10b981',
            shadowBlur: 10,
            shadowColor: 'rgba(99, 102, 241, 0.4)'
          }
        }]
      });
    }

    function toggleScatterScale() {
      isScatterLog = !isScatterLog;
      document.getElementById('scatterScaleBtn').textContent = isScatterLog ? 'Logarithmic' : 'Linear';
      initWhaleScatterChart();
    }

    // 4. Whale Geo Donut Chart
    function initWhaleGeoChart() {
      const dom = document.getElementById('whaleGeoChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['whaleGeo'] = chart;

      const pieData = DATA.whales.country_distribution.map(c => ({
        name: c.country,
        value: c.debit
      }));

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'item',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => `<strong>${params.name}</strong>: ${formatCurrency(params.value)} (${params.percent}%)`
        },
        legend: { bottom: 0, textStyle: { color: t.textColor, fontSize: 11 } },
        series: [{
          type: 'pie',
          radius: ['45%', '75%'],
          center: ['50%', '42%'],
          avoidLabelOverlap: false,
          itemStyle: { borderRadius: 8, borderColor: isDark() ? '#111726' : '#ffffff', borderWidth: 2 },
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } },
          data: DATA.whales.country_distribution.map((c, i) => ({
            value: c.debit,
            name: c.country,
            itemStyle: { color: ['#6366f1','#10b981','#f59e0b','#06b6d4','#ef4444','#8b5cf6','#ec4899'][i % 7] }
          }))
        }]
      });
    }

    // 5. Chaser Tiers Chart
    function initChaserTiersChart() {
      const dom = document.getElementById('chaserTiersChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['chaserTiers'] = chart;

      const tiers = DATA.chasers.risk_tiers;
      const labels = tiers.map(t => t.tier);
      const counts = tiers.map(t => t.count);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'axis',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 }
        },
        grid: { top: 20, right: 30, bottom: 40, left: 140 },
        xAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10 }
        },
        yAxis: {
          type: 'category',
          data: labels,
          axisLine: { lineStyle: { color: t.gridBorder } },
          axisLabel: { color: t.textColor, fontSize: 10 }
        },
        series: [{
          type: 'bar',
          data: counts,
          itemStyle: {
            color: params => {
              const colors = ['#e11d48', '#f43f5e', '#f59e0b', '#3b82f6', '#64748b'];
              return colors[params.dataIndex] || '#6366f1';
            },
            borderRadius: [0, 6, 6, 0]
          },
          label: {
            show: true,
            position: 'right',
            color: t.textColor,
            fontSize: 10,
            formatter: p => p.value.toLocaleString() + ' players'
          }
        }]
      });
    }

    // 6. Chaser Tilt Chart
    function initChaserTiltChart() {
      const dom = document.getElementById('chaserTiltChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['chaserTilt'] = chart;

      // Only show streaks that actually trigger tilt (>= 3 consecutive losses).
      // Streaks 0-2 are players who lost rounds but never chained 3+ together,
      // so they are excluded from this chart.
      const dataSlice = DATA.chasers.loss_streak_distribution
        .filter(d => d.streak >= 3)
        .slice(0, 12);
      const streaks = dataSlice.map(d => `Streak ${d.streak}`);
      const players = dataSlice.map(d => d.players);

      // L3 = 3 consecutive losses is the tilt trigger threshold. After filtering
      // out streaks 0-2, L3 is now the first bar (index 0).
      const l3Idx = 0;
      const l3 = dataSlice[l3Idx];
      const l3Pct = l3 ? (l3.players / DATA.chasers.total_count * 100).toFixed(1) : 0;

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'axis',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => `<strong>${params[0].name}</strong>: ${params[0].value.toLocaleString()} players`
        },
        grid: { top: 30, right: 20, bottom: 30, left: 50 },
        xAxis: {
          type: 'category',
          data: streaks,
          axisLine: { lineStyle: { color: t.gridBorder } },
          axisLabel: { color: t.textColor, fontSize: 9, rotate: 30 }
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10 }
        },
        series: [{
          data: players,
          type: 'bar',
          itemStyle: { color: '#f43f5e', borderRadius: [6, 6, 0, 0] },
          markPoint: {
            data: [{ name: 'Tilt Threshold', coord: [l3Idx, players[l3Idx]], value: `${l3Pct}% of chasers`, label: { show: true, color: '#fff', fontSize: 12, fontWeight: 'bold', backgroundColor: 'rgba(15, 23, 42, 0.92)', padding: [4, 8], borderRadius: 6, borderColor: '#f59e0b', borderWidth: 1.5 } }],
            itemStyle: { color: '#f59e0b', width: 2, height: 34 }
          }
        }]
      });
    }

    // 7. Chaser Outcome Pie
    function initChaserOutcomePie() {
      const dom = document.getElementById('chaserOutcomePie');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['chaserOutcome'] = chart;

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'item',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => `<strong>${params.name}</strong>: ${params.value.toLocaleString()} (${params.percent}%)`
        },
        legend: { bottom: 0, textStyle: { color: t.textColor, fontSize: 10 } },
        series: [{
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['50%', '42%'],
          itemStyle: { borderRadius: 6, borderColor: isDark() ? '#111726' : '#ffffff', borderWidth: 2 },
          label: { show: false },
          emphasis: { label: { show: true, fontSize: 11, fontWeight: 'bold' } },
          data: [
            { value: DATA.chasers.net_losers, name: 'Net Losers (67.7%)', itemStyle: { color: '#f43f5e' } },
            { value: DATA.chasers.net_winners, name: 'Net Winners (32.2%)', itemStyle: { color: '#10b981' } }
          ]
        }]
      });
    }

    // 8. Traffic Curve Chart
    function initTrafficCurveChart() {
      const dom = document.getElementById('trafficCurveChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['trafficCurve'] = chart;

      const hours = DATA.traffic.hourly_curve.map(d => d.hour);
      const bets = DATA.traffic.hourly_curve.map(d => d.bets);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'axis',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 }
        },
        grid: { top: 40, right: 30, bottom: 40, left: 70 },
        xAxis: {
          type: 'category',
          data: hours,
          axisLine: { lineStyle: { color: t.gridBorder } },
          axisLabel: { color: t.textColor, fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          name: 'Bets / Hour',
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10, formatter: v => (v/1000).toFixed(0) + 'K' }
        },
        series: [{
          data: bets,
          type: 'line',
          smooth: true,
          lineStyle: { color: '#06b6d4', width: 3 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(6, 182, 212, 0.5)' },
              { offset: 1, color: 'rgba(6, 182, 212, 0.02)' }
            ])
          },
          markArea: {
            itemStyle: { color: 'rgba(244, 63, 94, 0.08)' },
            data: [
              [{ xAxis: '17:00' }, { xAxis: '21:00' }]
            ]
          },
          markLine: {
            data: [
              { yAxis: 1000000, name: '1M Peak Threshold', lineStyle: { color: '#f43f5e', type: 'dashed' } }
            ]
          }
        }]
      });
    }

    // 9. Traffic Heatmap
    function initTrafficHeatmapChart() {
      const dom = document.getElementById('trafficHeatmapChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['trafficHeatmap'] = chart;

      const countries = DATA.traffic.heatmap.countries;
      const hours = DATA.traffic.heatmap.hours;
      const cells = DATA.traffic.heatmap.cells;

      // Color-scale value. Absolute bet counts are heavily skewed (China = 12.8M of
      // 18.2M total; 90% of cells < 87K, max = 772K), so a linear scale buries
      // nearly every cell in the darkest band. Log10(bets+1) spreads the full
      // 7-color gradient meaningfully across the skew.
      const log10 = v => Math.log10(v + 1);
      let colorVals, heatmapMax;
      if (isHeatmapNormalized) {
        colorVals = cells.map(c => c.intensity);
        heatmapMax = 1;
      } else {
        const bets = cells.map(c => c.bets);
        colorVals = bets.map(log10);
        heatmapMax = log10(Math.max(...bets));
      }

      const heatmapVals = cells.map((c, i) => [
        c.hour_idx,
        c.country_idx,
        colorVals[i],
        c.bets
      ]);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          position: 'top',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 11 },
          formatter: params => {
            const h = hours[params.value[0]];
            const c = countries[params.value[1]];
            const bets = params.value[3].toLocaleString();
            const intensity = (params.value[2] / heatmapMax * 100).toFixed(1);
            return `<strong>${c}</strong> @ ${h}<br>Bets: <strong>${bets}</strong><br>Relative Intensity: <strong>${intensity}%</strong>`;
          }
        },
        grid: { top: 20, right: 30, bottom: 60, left: 110 },
        xAxis: {
          type: 'category',
          data: hours,
          splitArea: { show: true },
          axisLabel: { color: t.textColor, fontSize: 9, rotate: 45 },
          axisLine: { lineStyle: { color: t.gridBorder } }
        },
        yAxis: {
          type: 'category',
          data: countries,
          splitArea: { show: true },
          axisLabel: { color: t.textColor, fontSize: 10 },
          axisLine: { lineStyle: { color: t.gridBorder } }
        },
        visualMap: {
          min: 0,
          max: heatmapMax,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: 10,
          inRange: {
            color: ['#0f172a', '#1e1b4b', '#4338ca', '#6366f1', '#ec4899', '#f43f5e', '#fbbf24']
          },
          textStyle: { color: t.textColor, fontSize: 10 }
        },
        series: [{
          name: 'Bet Volume',
          type: 'heatmap',
          data: heatmapVals,
          label: { show: false },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' }
          }
        }]
      });
    }

    function toggleHeatmapNormalize() {
      isHeatmapNormalized = !isHeatmapNormalized;
      document.getElementById('heatmapModeLabel').textContent = isHeatmapNormalized ? 'Country Relative (Normalized)' : 'Absolute Bet Counts (Log Scale)';
      initTrafficHeatmapChart();
    }

    // 10. Traffic Density Chart
    function initTrafficDensityChart() {
      const dom = document.getElementById('trafficDensityChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['trafficDensity'] = chart;

      const densityData = DATA.traffic.country_density;
      const countries = densityData.map(d => d.country);
      const pcts = densityData.map(d => d.peak_percentage);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'axis',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => {
            const item = densityData[params[0].dataIndex];
            return `<strong>${item.country}</strong><br>Peak Hour: <strong>${item.peak_hour}</strong><br>Peak Concentration: <strong>${item.peak_percentage}%</strong><br>Total Bets: ${item.total_bets.toLocaleString()}`;
          }
        },
        grid: { top: 20, right: 30, bottom: 40, left: 110 },
        xAxis: {
          type: 'value',
          name: '% in Single Peak Hour',
          nameTextStyle: { color: t.textColor, fontSize: 10 },
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10, formatter: v => v + '%' }
        },
        yAxis: {
          type: 'category',
          data: countries,
          inverse: true,
          axisLine: { lineStyle: { color: t.gridBorder } },
          axisLabel: { color: t.textColor, fontSize: 9 }
        },
        series: [{
          type: 'bar',
          data: pcts,
          itemStyle: {
            color: p => p.value > 15 ? '#f43f5e' : (p.value > 8 ? '#f59e0b' : '#3b82f6'),
            borderRadius: [0, 6, 6, 0]
          },
          label: {
            show: true,
            position: 'right',
            color: t.textColor,
            fontSize: 9,
            formatter: p => p.value + '%'
          }
        }]
      });
    }

    // 11. Operator ROI / Margin Chart
    function initOperatorRoiChart() {
      const dom = document.getElementById('operatorRoiChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['operatorRoi'] = chart;

      const ops = DATA.operators.roi_comparison.slice(0, 15);
      const names = ops.map(o => o.operator);
      const margins = ops.map(o => o.operator_hold_margin);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'axis',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => {
            const op = ops[params[0].dataIndex];
            return `<strong>${op.operator}</strong> (${op.countries})<br>Net Hold Margin: <strong>${op.operator_hold_margin}%</strong><br>Raw RTP: <strong>${op.operator_roi}%</strong><br>Debit: ${formatCurrency(op.total_debit)}`;
          }
        },
        grid: { top: 20, right: 30, bottom: 40, left: 140 },
        xAxis: {
          type: 'value',
          name: 'House Hold Margin %',
          nameTextStyle: { color: t.textColor, fontSize: 10 },
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 10, formatter: v => v + '%' }
        },
        yAxis: {
          type: 'category',
          data: names,
          inverse: true,
          axisLine: { lineStyle: { color: t.gridBorder } },
          axisLabel: { color: t.textColor, fontSize: 9 }
        },
        series: [{
          type: 'bar',
          data: margins,
          itemStyle: { color: '#10b981', borderRadius: [0, 6, 6, 0] },
          label: {
            show: true,
            position: 'right',
            color: t.textColor,
            fontSize: 9,
            formatter: p => p.value + '%'
          }
        }]
      });
    }

    // 12. Operator Bubble Chart (Volume vs Value)
    function initOperatorBubbleChart() {
      const dom = document.getElementById('operatorBubbleChart');
      if (!dom) return;
      const t = getChartTheme();
      const chart = echarts.init(dom);
      chartInstances['operatorBubble'] = chart;

      const bubbleData = DATA.operators.top_50.map(o => [
        o.total_bets,
        o.total_debit,
        o.unique_players,
        o.operator,
        o.countries,
        o.operator_hold_margin
      ]);

      chart.setOption({
        backgroundColor: t.bg,
        tooltip: {
          trigger: 'item',
          backgroundColor: t.tooltipBg,
          borderColor: t.tooltipBorder,
          textStyle: { color: t.tooltipText, fontSize: 12 },
          formatter: params => {
            const d = params.value;
            return `
              <div class="font-sans">
                <div class="font-bold text-emerald-400 mb-1">${d[3]} (${d[4]})</div>
                <div>Total Bets: <strong>${Number(d[0]).toLocaleString()}</strong></div>
                <div>Total Debit: <strong>${formatCurrency(d[1])}</strong></div>
                <div>Unique Players: <strong>${Number(d[2]).toLocaleString()}</strong></div>
                <div>Hold Margin: <strong>${d[5]}%</strong></div>
              </div>
            `;
          }
        },
        grid: { top: 30, right: 30, bottom: 50, left: 70 },
        xAxis: {
          name: 'Total Bets',
          nameLocation: 'middle',
          nameGap: 30,
          nameTextStyle: { color: t.textColor, fontSize: 10 },
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 9, formatter: v => (v/1000).toFixed(0) + 'K' }
        },
        yAxis: {
          name: 'Total Turnover (Log Scale)',
          type: 'log',
          nameTextStyle: { color: t.textColor, fontSize: 10 },
          splitLine: { lineStyle: { color: t.gridBorder, type: 'dashed' } },
          axisLabel: { color: t.textColor, fontSize: 9, formatter: v => formatCurrency(v) }
        },
        series: [{
          type: 'scatter',
          data: bubbleData,
          symbolSize: data => Math.min(65, Math.max(12, Math.sqrt(data[2]) * 1.2)),
          itemStyle: {
            color: p => p.value[4].includes('Vietnam') ? '#10b981' : (p.value[4].includes('Indonesia') ? '#6366f1' : '#06b6d4'),
            shadowBlur: 10,
            shadowColor: 'rgba(16, 185, 129, 0.4)'
          }
        }]
      });
    }

    // =========================================================================
    // SLIDE DECK CHARTS
    // =========================================================================
    function renderSlideCharts() {
      const t = getChartTheme();
      const chasers = DATA.chasers;

      // Slide 3 static text reflects live chaser totals
      const slideFlagged = document.getElementById('slideFlaggedChasers');
      if (slideFlagged) slideFlagged.textContent = `${chasers.total_count.toLocaleString()} (${chasers.net_loser_pct.toFixed(1)}% Net Loss)`;
      const slideChaserCountEl = document.getElementById('slideChaserCount');
      if (slideChaserCountEl) slideChaserCountEl.textContent = chasers.total_count.toLocaleString();
      const l3Slide = chasers.loss_streak_distribution.find(d => d.streak === 3);
      const slideL3PctEl = document.getElementById('slideL3Pct');
      if (slideL3PctEl) slideL3PctEl.textContent = l3Slide ? l3Slide.pct.toFixed(1) : '—';
      const slideNetLoserPctEl = document.getElementById('slideNetLoserPct');
      if (slideNetLoserPctEl) slideNetLoserPctEl.textContent = chasers.net_loser_pct.toFixed(1);

      // Slide 2: Whale Geo
      const s2 = document.getElementById('slideWhaleGeoChart');
      if (s2 && currentSlide === 2) {
        const c2 = echarts.init(s2);
        chartInstances['slideWhaleGeo'] = c2;
        c2.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger: 'item' },
          legend: { bottom: 0, textStyle: { color: t.textColor } },
          series: [{
            type: 'pie',
            radius: ['45%', '70%'],
            itemStyle: { borderRadius: 8, borderColor: isDark() ? '#111726' : '#fff', borderWidth: 2 },
            data: DATA.whales.country_distribution.map((c, i) => ({
            value: c.debit,
            name: c.country + ' (' + ((c.debit / DATA.whales.total_debit) * 100).toFixed(1) + '%)',
            itemStyle: { color: ['#6366f1','#10b981','#f59e0b','#06b6d4','#ef4444','#8b5cf6','#ec4899'][i % 7] }
          }))
          }]
        });
      }

      // Slide 3: Chaser Tilt
      const s3 = document.getElementById('slideChaserTiltChart');
      if (s3 && currentSlide === 3) {
        const c3 = echarts.init(s3);
        chartInstances['slideChaserTilt'] = c3;
        const slice = DATA.chasers.loss_streak_distribution
        .filter(d => d.streak >= 3)
        .slice(0, 8);
        c3.setOption({
          backgroundColor: t.bg,
          grid: { top: 20, right: 20, bottom: 30, left: 40 },
          xAxis: { type: 'category', data: slice.map(d => `L${d.streak}`), axisLabel: { color: t.textColor } },
          yAxis: { type: 'value', splitLine: { lineStyle: { color: t.gridBorder } }, axisLabel: { color: t.textColor } },
          series: [{
            type: 'bar',
            data: slice.map(d => d.players),
            itemStyle: { color: '#f43f5e', borderRadius: [6, 6, 0, 0] }
          }]
        });
      }

      // Slide 4: Traffic
      const s4 = document.getElementById('slideTrafficChart');
      if (s4 && currentSlide === 4) {
        const c4 = echarts.init(s4);
        chartInstances['slideTraffic'] = c4;
        c4.setOption({
          backgroundColor: t.bg,
          grid: { top: 20, right: 20, bottom: 30, left: 50 },
          xAxis: { type: 'category', data: DATA.traffic.hourly_curve.map(d => d.hour), axisLabel: { color: t.textColor } },
          yAxis: { type: 'value', axisLabel: { color: t.textColor, formatter: v => (v/1000).toFixed(0) + 'K' } },
          series: [{
            data: DATA.traffic.hourly_curve.map(d => d.bets),
            type: 'line',
            smooth: true,
            lineStyle: { color: '#06b6d4', width: 3 },
            areaStyle: { color: 'rgba(6, 182, 212, 0.3)' }
          }]
        });
      }

      // Slide 5: Operator Bubble
      const s5 = document.getElementById('slideOperatorBubbleChart');
      if (s5 && currentSlide === 5) {
        const c5 = echarts.init(s5);
        chartInstances['slideOperatorBubble'] = c5;
        c5.setOption({
          backgroundColor: t.bg,
          grid: { top: 20, right: 20, bottom: 40, left: 60 },
          xAxis: { type: 'value', axisLabel: { color: t.textColor, formatter: v => (v/1000).toFixed(0) + 'K' } },
          yAxis: { type: 'log', axisLabel: { color: t.textColor, formatter: v => formatCurrency(v) } },
          series: [{
            type: 'scatter',
            data: DATA.operators.top_50.slice(0, 20).map(o => [o.total_bets, o.total_debit, o.unique_players]),
            symbolSize: d => Math.min(45, Math.max(12, Math.sqrt(d[2]) * 1.1)),
            itemStyle: { color: '#10b981' }
          }]
        });
      }
    }'''


def build_dashboard():
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)

    rebuild_unified = (
        not INDEX_FILE.exists()
        or not chunks_complete()
        or any(path.stat().st_mtime > INDEX_FILE.stat().st_mtime for path in source_indexes)
    )
    if rebuild_unified:
        from datetime import datetime

        unified_index = merge_per_file_dossiers()
    else:
        with open(INDEX_FILE, "r", encoding="utf-8") as inf:
            unified_index = json.load(inf)

    index_meta = unified_index.get("meta", {})
    index_players = unified_index.get("players", [])

    DOSSIER_DATA_FILE = WORKSPACE / "output" / "data" / "individual_dossiers_data.json"
    with open(DOSSIER_DATA_FILE, "r", encoding="utf-8") as df:
        detailed_operators = json.load(df).get("operators", [])

    combined_dossier = {"meta": index_meta, "players": index_players, "operators": detailed_operators}
    dossier_json_str = json.dumps(combined_dossier, ensure_ascii=False)

    with open(SECTIONS_DIR / "dossier.js", "r", encoding="utf-8") as dj:
        dossier_js_str = dj.read()

    render_sections_dir = Path(tempfile.mkdtemp(prefix="t14-sections-"))
    try:
        for name in ("nav_buttons.html", "tab_players.html", "tab_operators.html", "slides.html"):
            shutil.copy(SECTIONS_DIR / name, render_sections_dir / name)

        extra_scripts = (
            '<script id="dossier-raw-data" type="application/json">\n'
            + dossier_json_str
            + '\n</script>\n<script>\n'
            + dossier_js_str
            + '\n</script>\n<script>\n'
            + CONTROLLER_JS
            + '\n</script>'
        )

        render_dashboard(
            data_file=DATA_FILE,
            sections_dir=render_sections_dir,
            output_html=OUT_FILE,
            title=TITLE,
            extra_scripts=extra_scripts,
        )
    finally:
        shutil.rmtree(render_sections_dir, ignore_errors=True)

    print(f"Generated {OUT_FILE} ({OUT_FILE.stat().st_size:,} chars)")
    return True


if __name__ == "__main__":
    build_dashboard()
