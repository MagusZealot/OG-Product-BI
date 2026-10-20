#!/usr/bin/env python3
"""
inject_dossier_tabs.py

Injects Tab 6 (ALL Player Dossiers) and Tab 7 (Operator Dossiers) into
player_behavior_dashboard.html.

Tab 6 now covers EVERY player in the database (all_players_index.json),
not just the sampled whales & chasers. Each player's FULL balance
trajectory is lazy-loaded on demand from ../dossier_chunks/chunk_NNNN.js
(companion files sitting at ../dossier_chunks/ relative to the HTML), so the dashboard can open
any of the ~50k players with their complete round-by-round balance
history.
"""

import json
from pathlib import Path

# Discover workspace root relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
# src/dashboard -> go up 2 levels to reach workspace root
WORKSPACE = SCRIPT_DIR.parent.parent

# Fallback: look for workspace_map.md to confirm
if not (WORKSPACE / "workspace_map.md").exists():
    # Try to find by walking up further
    for parent in WORKSPACE.parents:
        if (parent / "workspace_map.md").exists():
            WORKSPACE = parent
            break

REPORT_DIR = WORKSPACE / "output" / "dashboards"
DATA_DIR = WORKSPACE / "output"
FOLDER = REPORT_DIR.parent
INDEX_FILE = DATA_DIR / "all_players_index.json"
DOSSIER_FILE = DATA_DIR / "individual_dossiers_data.json"
SRC_HTML = REPORT_DIR / "player_behavior_dashboard.html"


def build():
    # Dossier tabs (Player/Operator Dossiers) are intentionally NOT injected into
    # player_behavior_dashboard.html — they are already present in the sibling
    # bi_dashboard.html, so duplicating them here is redundant. This script is a
    # no-op unless explicitly enabled via INJECT_DOSSIER_TABS=1.
    import os
    if os.environ.get("INJECT_DOSSIER_TABS", "0") != "1":
        print("inject_dossier_tabs.py is a no-op (set INJECT_DOSSIER_TABS=1 to enable)")
        return False
    if not INDEX_FILE.exists():
        print(f"Index file not found: {INDEX_FILE}")
        return False
    if not SRC_HTML.exists():
        print(f"Source dashboard not found: {SRC_HTML}")
        return False

    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    operators = []
    if DOSSIER_FILE.exists():
        with open(DOSSIER_FILE, "r", encoding="utf-8") as f:
            operators = json.load(f).get("operators", [])

    # Combined embedded payload: all-players index + operators
    combined = {
        "meta": index_data["meta"],
        "players": index_data["players"],
        "operators": operators,
    }
    dossier_json = json.dumps(combined, ensure_ascii=False)

    total_players = index_data["meta"]["total_players"]
    total_rows = index_data["meta"]["total_rows"]

    # ── NAV BUTTONS ───────────────────────────────────────────────
    NAV_INJECT = """
          <button onclick="switchTab('players')" class="nav-tab px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition flex items-center gap-2">
            <i class="fa-solid fa-user-secret text-amber-400"></i> 6. Player Dossiers
          </button>
          <button onclick="switchTab('operators')" class="nav-tab px-3.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition flex items-center gap-2">
            <i class="fa-solid fa-building-columns text-cyan-400"></i> 7. Operator Dossiers
          </button>"""

    with open(SRC_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # ── TAB 6: ALL PLAYER DOSSIERS ────────────────────────────────
    TAB6_HTML = f"""
      <!-- ================================================================= -->
      <!-- TAB 6: ALL PLAYER DOSSIERS (FULL DATABASE)                    -->
      <!-- ================================================================= -->
      <section id="tab-players" class="tab-pane hidden space-y-6">
        <!-- Hero -->
        <div class="glass-card rounded-2xl p-5 bg-gradient-to-r from-amber-950/40 via-slate-900 to-slate-900 border border-amber-500/20">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold">
                <i class="fa-solid fa-database"></i> Full Database Player Forensics
              </div>
              <h2 class="text-2xl font-extrabold text-white tracking-tight mt-1">All Player Dossiers</h2>
              <p class="text-xs text-slate-300">Complete coverage of <strong class="text-amber-300">{total_players:,}</strong> players across <strong class="text-amber-300">{total_rows:,}</strong> wagers — every player has a full round-by-round balance trajectory, cumulative P&amp;L, game mix, operator fingerprint, hourly activity and recent-round forensics.</p>
            </div>
            <div class="flex items-center gap-3">
              <div class="text-right font-mono text-xs text-slate-400">
                <span class="text-amber-400 font-bold text-sm" id="playerDossierCount">0</span> Profiles Loaded
              </div>
              <button onclick="exportDossierCSV('players')" class="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 flex items-center gap-2 transition">
                <i class="fa-solid fa-download text-amber-400"></i> Export Dossiers CSV
              </button>
            </div>
          </div>
        </div>

        <!-- Player Archetype Legend -->
        <div class="glass-card rounded-2xl p-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <div class="text-xs text-slate-400 uppercase font-semibold"><i class="fa-solid fa-tags text-amber-400 mr-1"></i>Player Archetype Legend</div>
              <span id="archetypeFilterCount" class="text-[10px] text-amber-400 font-mono"></span>
            </div>
            <div class="flex items-center gap-2">
              <button id="clearArchetypeFiltersBtn" onclick="clearArchetypeFilters()" class="hidden px-2 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-semibold border border-slate-700"><i class="fa-solid fa-times mr-1"></i>Clear</button>
              <span class="text-[10px] text-slate-500">Click to filter · click again to clear</span>
            </div>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2" id="archetypeLegend">
            <!-- legend items injected by JS -->
          </div>
          <div class="mt-3 pt-3 border-t border-slate-800 text-[10px] text-slate-500 leading-relaxed">
            <strong class="text-slate-400">How archetypes are assigned:</strong>
            Each player is classified by their <span class="text-amber-300">Spike Multiplier</span> (max bet escalation after consecutive losses) and total wagered volume.
            <span class="text-rose-400">Chasers</span> escalate bets rapidly after losses (spike ≥ 3x). <span class="text-amber-400">Whales</span> are the top 0.4% of players by total debit (≥ ~384M). A player can carry both a <span class="text-amber-400">Whale</span> flag and a <span class="text-rose-400">Chaser</span> flag simultaneously.
          </div>
        </div>

        <!-- Search & Filter Bar -->
        <div class="glass-card rounded-2xl p-4 flex flex-wrap gap-3 items-center">
          <div class="flex-1 min-w-[200px] relative">
            <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
            <input type="text" id="playerSearch" placeholder="Search player ID, country, archetype, operator..."
              class="w-full pl-8 pr-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-amber-500"
              oninput="filterPlayerDossiers()">
          </div>
          <select id="playerTierFilter" onchange="filterPlayerDossiers()"
            class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-xs focus:outline-none focus:border-amber-500">
            <option value="">All Tiers</option>
            <option value="whale">Whales</option>
            <option value="chaser">Chasers</option>
            <option value="VIP High Roller">VIP High Roller</option>
            <option value="High Roller">High Roller</option>
            <option value="Mid Roller">Mid Roller</option>
            <option value="Active Player">Active Player</option>
            <option value="Casual Player">Casual Player</option>
          </select>
          <select id="playerCountryFilter" onchange="filterPlayerDossiers()"
            class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-xs focus:outline-none focus:border-amber-500">
            <option value="">All Countries</option>
          </select>
          <select id="playerSortFilter" onchange="filterPlayerDossiers()"
            class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-xs focus:outline-none focus:border-amber-500">
            <option value="debit">Sort: Total Debit</option>
            <option value="bets">Sort: Total Bets</option>
            <option value="pnl">Sort: Net P&amp;L</option>
            <option value="spike">Sort: Spike Multiplier</option>
            <option value="avg_bet">Sort: Avg Bet Size</option>
            <option value="losses">Sort: Max Loss Streak</option>
          </select>
          <span class="text-xs text-slate-400 font-mono" id="playerFilterCount"></span>
        </div>

        <!-- Player Cards Grid -->
        <div id="playerCardsGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"></div>

        <!-- Pagination Controls -->
        <div class="glass-card rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3 no-print">
          <div class="flex items-center gap-2 text-xs text-slate-400">
            <span>Rows per page</span>
            <select id="playerPageSize" onchange="changePageSize()" class="px-2 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-xs focus:outline-none">
              <option value="60">60</option>
              <option value="120">120</option>
              <option value="240">240</option>
            </select>
          </div>
          <div class="text-xs font-mono text-slate-300" id="playerPageInfo"></div>
          <div class="flex items-center gap-2">
            <button onclick="prevPlayerPage()" id="playerPrevBtn" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"><i class="fa-solid fa-chevron-left mr-1"></i>Prev</button>
            <button onclick="nextPlayerPage()" id="playerNextBtn" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed">Next<i class="fa-solid fa-chevron-right ml-1"></i></button>
          </div>
        </div>

        <!-- Player Dossier Panel (hidden until card click) -->
        <div id="playerDossierPanel" class="hidden glass-card rounded-2xl p-6 space-y-6 border border-amber-500/30">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <div id="dossierPlayerBadge" class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold mb-2"></div>
              <h3 id="dossierPlayerTitle" class="text-xl font-extrabold text-white font-mono"></h3>
              <p id="dossierPlayerSub" class="text-xs text-slate-400 mt-1"></p>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="closePlayerDossier()" class="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 text-xs font-semibold border border-indigo-500/40 transition">
                <i class="fa-solid fa-arrow-left mr-1"></i>Back to Browser
              </button>
              <button onclick="closePlayerDossier()" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm border border-slate-700">
                <i class="fa-solid fa-xmark"></i>
              </button>
            </div>
          </div>

          <!-- KPI Strip -->
          <div id="dossierPlayerKPIs" class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3"></div>

          <!-- Trajectory loading indicator -->
          <div id="dossierLoading" class="flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-900/70 border border-slate-800 text-xs text-slate-400">
            <i class="fa-solid fa-spinner fa-spin text-amber-400"></i>
            <span>Loading full balance trajectory from database chunk...</span>
          </div>

          <!-- Charts Row: Balance + P&L -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
              <div class="flex items-center justify-between mb-2">
                <div class="text-xs text-slate-400 uppercase font-semibold"><i class="fa-solid fa-chart-line text-cyan-400 mr-1"></i>Full Balance Trajectory</div>
                <div class="text-[10px] font-mono text-slate-500" id="dossierTrajPoints"></div>
              </div>
              <div id="dossierBalanceChart" style="height:240px;width:100%"></div>
            </div>
            <div class="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-chart-line text-rose-400 mr-1"></i>Cumulative P&amp;L Curve</div>
              <div id="dossierPnlChart" style="height:240px;width:100%"></div>
            </div>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 rounded-xl bg-slate-900/60 border border-slate-800 p-4">
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-clock text-amber-400 mr-1"></i>Hourly Betting Activity</div>
              <div id="dossierHoursChart" style="height:200px;width:100%"></div>
            </div>
            <div class="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-dice text-emerald-400 mr-1"></i>Game Mix (by Bets)</div>
              <div id="dossierGamesChart" style="height:200px;width:100%"></div>
            </div>
          </div>

          <!-- Device + Recent Rounds -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="rounded-xl bg-slate-900/60 border border-slate-800 p-4">
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-mobile-screen text-indigo-400 mr-1"></i>Device Split</div>
              <div id="dossierDeviceChart" style="height:160px;width:100%"></div>
            </div>
            <div class="lg:col-span-2 rounded-xl bg-slate-900/60 border border-slate-800 p-4">
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-list text-slate-400 mr-1"></i>Recent Rounds Forensics</div>
              <div id="dossierRecentRoundsTable" class="overflow-auto max-h-44"></div>
            </div>
          </div>
        </div>
      </section>"""

    # ── TAB 7: OPERATOR DOSSIERS (unchanged) ──────────────────────
    TAB7_HTML = """
      <!-- ================================================================= -->
      <!-- TAB 7: OPERATOR DOSSIERS                                          -->
      <!-- ================================================================= -->
      <section id="tab-operators" class="tab-pane hidden space-y-6">
        <div class="glass-card rounded-2xl p-5 bg-gradient-to-r from-cyan-950/40 via-slate-900 to-slate-900 border border-cyan-500/20">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-semibold">
                <i class="fa-solid fa-building-columns"></i> Operator Intelligence
              </div>
              <h2 class="text-2xl font-extrabold text-white tracking-tight mt-1">Operator Dossier Browser</h2>
              <p class="text-xs text-slate-300">GGR margin, player ecosystems, game breakdowns, hourly load patterns and top contributing players per brand</p>
            </div>
            <div class="flex items-center gap-3">
              <div class="text-right font-mono text-xs text-slate-400">
                <span class="text-cyan-400 font-bold text-sm" id="operatorDossierCount">0</span> Operators Profiled
              </div>
            </div>
          </div>
        </div>

        <div class="glass-card rounded-2xl p-4 flex flex-wrap gap-3 items-center">
          <div class="flex-1 min-w-[200px] relative">
            <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs"></i>
            <input type="text" id="operatorSearch" placeholder="Search operator name or country..."
              class="w-full pl-8 pr-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-100 text-xs focus:outline-none focus:border-cyan-500"
              oninput="filterOperatorDossiers()">
          </div>
          <select id="operatorCountryFilter" onchange="filterOperatorDossiers()"
            class="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-xs focus:outline-none focus:border-cyan-500">
            <option value="">All Countries</option>
          </select>
          <span class="text-xs text-slate-400 font-mono" id="operatorFilterCount"></span>
        </div>

        <div id="operatorCardsGrid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"></div>

        <div id="operatorDossierPanel" class="hidden glass-card rounded-2xl p-6 space-y-6 border border-cyan-500/30">
          <div class="flex items-center justify-between">
            <div>
              <div id="dossierOperatorBadge" class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold mb-2"></div>
              <h3 id="dossierOperatorTitle" class="text-xl font-extrabold text-white font-mono"></h3>
              <p id="dossierOperatorSub" class="text-xs text-slate-400 mt-1"></p>
            </div>
            <button onclick="closeOperatorDossier()" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm border border-slate-700">
              <i class="fa-solid fa-xmark"></i>
            </button>
          </div>
          <div id="dossierOperatorKPIs" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3"></div>
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-dice text-emerald-400 mr-1"></i>Game Breakdown</div>
              <div id="dossierOpGamesChart" style="height:220px;width:100%"></div>
            </div>
            <div>
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-clock text-cyan-400 mr-1"></i>Hourly Load Profile</div>
              <div id="dossierOpHoursChart" style="height:220px;width:100%"></div>
            </div>
          </div>
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div>
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-mobile-screen text-indigo-400 mr-1"></i>Device Mix</div>
              <div id="dossierOpDeviceChart" style="height:160px;width:100%"></div>
            </div>
            <div class="lg:col-span-2">
              <div class="text-xs text-slate-400 uppercase font-semibold mb-2"><i class="fa-solid fa-crown text-amber-400 mr-1"></i>Top Contributing Players</div>
              <div id="dossierOpPlayersTable" class="overflow-auto max-h-52"></div>
            </div>
          </div>
        </div>
      </section>"""

    # ── JS MODULE ─────────────────────────────────────────────────
    DOSSIER_JS = r"""
    // ========================================================================
    // DOSSIER MODULE — ALL PLAYERS (full database) + OPERATORS
    // ========================================================================
    // Lazy-loaded on DOMContentLoaded so the module works no matter where the
    // dossier-raw-data JSON block ends up in the document.
    let DOSSIER = null;
    let CHUNK_SIZE = 1000;
    document.addEventListener('DOMContentLoaded', function () {
      try {
        const el = document.getElementById('dossier-raw-data');
        if (el) {
          DOSSIER = JSON.parse(el.textContent);
          if (DOSSIER && DOSSIER.meta) CHUNK_SIZE = DOSSIER.meta.chunk_size || 1000;
        }
      } catch (e) { console.warn('Dossier data unavailable', e); DOSSIER = null; }
    });

    const FLAG_MAP = {"Indonesia":"🇮🇩","Vietnam":"🇻🇳","China":"🇨🇳","Bangladesh":"🇧🇩","Thailand":"🇹🇭","Malaysia":"🇲🇾","India":"🇮🇳","Myanmar":"🇲🇲","Philippines":"🇵🇭","Cambodia":"🇰🇭","Laos":"🇱🇦","Singapore":"🇸🇬","South Korea":"🇰🇷","Japan":"🇯🇵","USA":"🇺🇸","Hong Kong":"🇭🇰","Taiwan":"🇹🇼","Nepal":"🇳🇵","Turkey":"🇹🇷","Crypto":"🪙","Unknown":"🌐"};
    const ARCHETYPE_COLORS = {
      'Extreme Chaser': '#f43f5e', 'Critical Chaser': '#f97316', 'High Chaser': '#f59e0b',
      'Moderate Chaser': '#eab308', 'Low Chaser': '#84cc16',
      'Lightning Burst Whale': '#f59e0b', 'Sustained Grinder Whale': '#d97706', 'VIP Whale': '#fbbf24',
      'VIP High Roller': '#a78bfa', 'High Roller': '#8b5cf6', 'Mid Roller': '#6366f1',
      'Active Player': '#0ea5e9', 'Casual Player': '#64748b'
    };
    const ARCHETYPE_DESC = {
      'Extreme Chaser': 'Spike ≥1000x — bet escalation after consecutive losses is extreme. Highest-risk gambler.',
      'Critical Chaser': 'Spike 100–999x — severe escalation, strong problem-gambling signal.',
      'High Chaser': 'Spike 50–99x — rapid bet inflation after losses.',
      'Moderate Chaser': 'Spike 10–49x — noticeable chase behaviour.',
      'Low Chaser': 'Spike 3–9x — mild chase tendency.',
      'Lightning Burst Whale': 'Whale who wagers in short, intense bursts — high volume in brief sessions.',
      'Sustained Grinder Whale': 'Whale with long, steady sessions — consistent high-volume grinding.',
      'VIP Whale': 'Top-tier whale by total debit — among the largest depositors in the database.',
      'VIP High Roller': 'VIP whale with very high average bet size on premium games.',
      'High Roller': 'High average bet size, elevated spend per wager.',
      'Mid Roller': 'Moderate bet sizes and steady activity.',
      'Active Player': 'Frequent wagers but modest bet sizes — regular participant.',
      'Casual Player': 'Low frequency / low bet size — infrequent, small-stakes play.'
    };
    const GAME_COLORS = {'baccarat':'#10b981','dragon_tiger':'#f59e0b','roulette':'#8b5cf6','sicbo':'#06b6d4','niuniu':'#ec4899','Unknown':'#64748b'};

    function archetypeColor(arch) {
      if (!arch) return '#6366f1';
      for (const k of Object.keys(ARCHETYPE_COLORS)) { if (arch.includes(k)) return ARCHETYPE_COLORS[k]; }
      return '#6366f1';
    }
    function archetypeBg(arch) {
      const c = archetypeColor(arch);
      return `background:${c}22; border:1px solid ${c}55; color:${c}`;
    }
    function renderArchetypeLegend() {
      const host = document.getElementById('archetypeLegend');
      if (!host) return;
      const order = [
        'Extreme Chaser', 'Critical Chaser', 'High Chaser', 'Moderate Chaser', 'Low Chaser',
        'Lightning Burst Whale', 'Sustained Grinder Whale', 'VIP Whale', 'VIP High Roller',
        'High Roller', 'Mid Roller', 'Active Player', 'Casual Player'
      ];
      host.innerHTML = order.map(a => {
        const c = ARCHETYPE_COLORS[a] || '#6366f1';
        const active = _selectedArchetypes.has(a);
        return `<div class="rounded-lg p-2 border cursor-pointer transition-all hover:scale-105" ${active ? `style="background:${c}44; border-color:${c}; box-shadow:0 0 0 2px ${c} inset;"` : `style="background:${c}15; border-color:${c}44;"`} onclick="toggleArchetypeFilter('${a}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleArchetypeFilter('${a}');}" tabindex="0" role="button" aria-pressed="${active}" title="Filter by ${a}">
          <div class="text-[11px] font-bold" style="color:${c}">${a}</div>
          <div class="text-[9px] text-slate-400 mt-0.5 leading-snug">${ARCHETYPE_DESC[a] || ''}</div>
        </div>`;
      }).join('');
      const countEl = document.getElementById('archetypeFilterCount');
      if (countEl) countEl.textContent = _selectedArchetypes.size ? `· ${_selectedArchetypes.size} selected` : '';
      const clearBtn = document.getElementById('clearArchetypeFiltersBtn');
      if (clearBtn) clearBtn.classList.toggle('hidden', _selectedArchetypes.size === 0);
    }
    function fmtN(v, dec) {
      if (v == null || isNaN(v)) return 'N/A';
      dec = dec == null ? 2 : dec;
      const abs = Math.abs(v);
      if (abs >= 1e9) return (v/1e9).toFixed(dec)+'B';
      if (abs >= 1e6) return (v/1e6).toFixed(dec)+'M';
      if (abs >= 1e3) return (v/1e3).toFixed(dec)+'K';
      return (typeof v === 'number' ? v.toFixed(dec) : v);
    }
    function kpiCard(label, value, color, icon) {
      return `<div class="glass-card rounded-xl p-3 text-center">
        <div class="text-[10px] text-slate-400 uppercase font-semibold">${icon ? '<i class="'+icon+' mr-1"></i>' : ''}${label}</div>
        <div class="text-base font-extrabold font-mono mt-1 ${color || 'text-white'}">${value}</div>
      </div>`;
    }
    function dossierTheme() {
      if (typeof getChartTheme === 'function') return getChartTheme();
      return { bg:'transparent', textColor:'#94a3b8', titleColor:'#f8fafc', gridBorder:'#1e293b', tooltipBg:'#0f172a', tooltipBorder:'#334155', tooltipText:'#ffffff' };
    }
    function flagOf(country) { return FLAG_MAP[country] || '🌐'; }

    // ── CHUNK LOADER (lazy-load full trajectories) ─────────────────
    const _chunkCallbacks = {};
    function loadDossierChunk(chunkId, callback) {
      const gname = 'DOSSIER_CHUNK_' + String(chunkId).padStart(4, '0');
      if (window[gname]) { callback(window[gname]); return; }
      if (_chunkCallbacks[chunkId]) { _chunkCallbacks[chunkId].push(callback); return; }
      _chunkCallbacks[chunkId] = [callback];
      const s = document.createElement('script');
      s.src = '../dossier_chunks/chunk_' + String(chunkId).padStart(4, '0') + '.js';
      s.onload = function () {
        const cbs = _chunkCallbacks[chunkId] || [];
        delete _chunkCallbacks[chunkId];
        cbs.forEach(cb => cb(window[gname] || null));
      };
      s.onerror = function () {
        const cbs = _chunkCallbacks[chunkId] || [];
        delete _chunkCallbacks[chunkId];
        cbs.forEach(cb => cb(null));
      };
      document.head.appendChild(s);
    }

    // ── PLAYER DOSSIERS (ALL PLAYERS, PAGINATED) ─────────────────
    let filteredPlayers = DOSSIER ? [...DOSSIER.players] : [];
    let playerPage = 1;
    let playerPageSize = 60;
    let _selectedArchetypes = new Set();  // empty = show all

    function toggleArchetypeFilter(arch) {
      if (_selectedArchetypes.has(arch)) _selectedArchetypes.delete(arch);
      else _selectedArchetypes.add(arch);
      renderArchetypeLegend();
      filterPlayerDossiers();
    }
    function clearArchetypeFilters() {
      _selectedArchetypes.clear();
      renderArchetypeLegend();
      filterPlayerDossiers();
    }

    function initPlayerDossiers() {
      if (!DOSSIER) return;
      renderArchetypeLegend();
      const countries = [...new Set(DOSSIER.players.map(p => p.country).filter(Boolean))].sort();
      const sel = document.getElementById('playerCountryFilter');
      if (sel) countries.forEach(c => { const o = document.createElement('option'); o.value = c; o.text = c; sel.appendChild(o); });
      const cnt = document.getElementById('playerDossierCount');
      if (cnt) cnt.textContent = DOSSIER.players.length.toLocaleString();
      filterPlayerDossiers();
    }

    function filterPlayerDossiers() {
      if (!DOSSIER) return;
      const q = (document.getElementById('playerSearch')?.value || '').toLowerCase();
      const tier = document.getElementById('playerTierFilter')?.value || '';
      const country = document.getElementById('playerCountryFilter')?.value || '';
      const sort = document.getElementById('playerSortFilter')?.value || 'debit';
      filteredPlayers = DOSSIER.players.filter(p => {
        const matchQ = !q || (p.pid||'').toLowerCase().includes(q) || (p.country||'').toLowerCase().includes(q) || (p.arch||'').toLowerCase().includes(q) || (p.op||'').toLowerCase().includes(q);
        let matchTier = true;
        if (tier === 'whale') matchTier = !!p.whale;
        else if (tier === 'chaser') matchTier = !!p.chaser;
        else if (tier) matchTier = (p.arch||'') === tier;
        const matchArch = _selectedArchetypes.size === 0 || _selectedArchetypes.has(p.arch);
        const matchCountry = !country || p.country === country;
        return matchQ && matchTier && matchArch && matchCountry;
      });
      const sorters = {
        debit: (a,b) => (b.debit||0) - (a.debit||0),
        bets: (a,b) => (b.bets||0) - (a.bets||0),
        pnl: (a,b) => (b.winlose||0) - (a.winlose||0),
        spike: (a,b) => (b.spike||0) - (a.spike||0),
        avg_bet: (a,b) => (b.avg_bet||0) - (a.avg_bet||0),
        losses: (a,b) => (b.max_consecutive_losses||0) - (a.max_consecutive_losses||0)
      };
      filteredPlayers.sort(sorters[sort] || sorters.debit);
      playerPage = 1;
      renderPlayerCards();
    }

    function changePageSize() {
      playerPageSize = parseInt(document.getElementById('playerPageSize')?.value || '60', 10);
      playerPage = 1;
      renderPlayerCards();
    }
    function prevPlayerPage() { if (playerPage > 1) { playerPage--; renderPlayerCards(); } }
    function nextPlayerPage() {
      const totalPages = Math.max(1, Math.ceil(filteredPlayers.length / playerPageSize));
      if (playerPage < totalPages) { playerPage++; renderPlayerCards(); }
    }

    function renderPlayerCards() {
      const grid = document.getElementById('playerCardsGrid');
      if (!grid || !DOSSIER) return;
      const fc = document.getElementById('playerFilterCount');
      if (fc) fc.textContent = `${filteredPlayers.length.toLocaleString()} of ${DOSSIER.players.length.toLocaleString()} players`;

      const totalPages = Math.max(1, Math.ceil(filteredPlayers.length / playerPageSize));
      if (playerPage > totalPages) playerPage = totalPages;
      const start = (playerPage - 1) * playerPageSize;
      const pageItems = filteredPlayers.slice(start, start + playerPageSize);

      const pi = document.getElementById('playerPageInfo');
      if (pi) pi.textContent = `Page ${playerPage.toLocaleString()} / ${totalPages.toLocaleString()}`;
      const pb = document.getElementById('playerPrevBtn');
      if (pb) pb.disabled = playerPage <= 1;
      const nb = document.getElementById('playerNextBtn');
      if (nb) nb.disabled = playerPage >= totalPages;

      const html = pageItems.map(p => {
        const flag = flagOf(p.country);
        const winloseColor = (p.winlose||0) < 0 ? 'text-emerald-400' : 'text-rose-400';
        const winloseLabel = (p.winlose||0) < 0 ? `Casino +${fmtN(Math.abs(p.winlose))}` : `Player +${fmtN(p.winlose)}`;
        const tags = [];
        if (p.whale) tags.push('<span class="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-[9px] font-bold">🐋 WHALE</span>');
        if (p.chaser) tags.push('<span class="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 text-[9px] font-bold">🎯 CHASER</span>');
        const c = archetypeColor(p.arch);
        return `<div onclick="openPlayerDossier(${p.id})"
          class="glass-card rounded-2xl p-4 cursor-pointer hover:scale-[1.02] transition-all duration-200 border"
          style="border-color:${c}44">
          <div class="flex items-start justify-between mb-2">
            <div>
              <div class="font-mono text-sm font-bold text-white truncate max-w-[150px]" title="${p.pid}">${p.pid}</div>
              <div class="text-[10px] text-slate-400 mt-0.5">${flag} ${p.country||'Unknown'}</div>
            </div>
            <div class="flex flex-wrap gap-1 justify-end">${tags.join('')}</div>
          </div>
          <div class="text-[10px] px-2 py-0.5 rounded-full inline-block mb-2 font-semibold" style="${archetypeBg(p.arch)}">${p.arch||'Player'}</div>
          <div class="grid grid-cols-2 gap-2 text-xs mt-2">
            <div><span class="text-slate-400 text-[10px]">Total Debit</span><br><strong class="text-cyan-400 font-mono">${fmtN(p.debit)}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Net P&amp;L</span><br><strong class="${winloseColor} font-mono">${winloseLabel}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Total Bets</span><br><strong class="text-white font-mono">${(p.bets||0).toLocaleString()}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Avg Bet</span><br><strong class="text-amber-400 font-mono">${fmtN(p.avg_bet)}</strong></div>
          </div>
        </div>`;
      }).join('');

      // Smooth fade transition so filter/search/pagination changes feel fluid
      // instead of an abrupt innerHTML swap.
      grid.style.transition = 'opacity .16s ease';
      grid.style.opacity = '0';
      clearTimeout(grid._fadeTimer);
      grid._fadeTimer = setTimeout(() => {
        grid.innerHTML = html;
        grid.style.opacity = '1';
      }, 150);
    }

    let playerChartInstances = {};
    function disposePlayerCharts() {
      Object.values(playerChartInstances).forEach(c => { try { c.dispose(); } catch(e){} });
      playerChartInstances = {};
    }

    function openPlayerDossier(id) {
      if (!DOSSIER) return;
      const p = DOSSIER.players[id];
      if (!p) return;
      const panel = document.getElementById('playerDossierPanel');
      panel.classList.remove('hidden');
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      disposePlayerCharts();

      const c = archetypeColor(p.arch);
      const badge = document.getElementById('dossierPlayerBadge');
      badge.innerHTML = `<i class="fa-solid fa-user-secret mr-1"></i>${p.arch||'Player'}`;
      badge.style = archetypeBg(p.arch);
      document.getElementById('dossierPlayerTitle').textContent = p.pid;
      document.getElementById('dossierPlayerSub').textContent = `${flagOf(p.country)} ${p.country||'Unknown'} · Primary Operator: ${p.op||'N/A'} · ${(p.bets||0).toLocaleString()} wagers · Avg Bet: ${fmtN(p.avg_bet)}`;

      document.getElementById('dossierPlayerKPIs').innerHTML = [
        kpiCard('Total Debit', fmtN(p.debit), 'text-cyan-400', 'fa-solid fa-coins'),
        kpiCard('Net P&L', (p.winlose<0?'Casino +':'Player +')+fmtN(Math.abs(p.winlose)), p.winlose<0?'text-emerald-400':'text-rose-400', 'fa-solid fa-scale-balanced'),
        kpiCard('Total Bets', (p.bets||0).toLocaleString(), 'text-white', 'fa-solid fa-dice'),
        kpiCard('Avg Bet', fmtN(p.avg_bet), 'text-amber-400', 'fa-solid fa-arrow-up-right-dots'),
        kpiCard('Spike Multiplier', (p.spike||1)+'x', 'text-orange-400', 'fa-solid fa-bolt'),
        kpiCard('Max Loss Streak', (p.max_consecutive_losses||0)+' rounds', 'text-rose-400', 'fa-solid fa-skull'),
        kpiCard('Tier', p.whale ? '🐋 Whale' : (p.chaser ? '🎯 Chaser' : 'Player'), 'text-indigo-400', 'fa-solid fa-shield-halved')
      ].join('');

      // Show loading, then lazy-load the full trajectory chunk
      const loading = document.getElementById('dossierLoading');
      if (loading) loading.classList.remove('hidden');
      ['dossierBalanceChart','dossierPnlChart','dossierHoursChart','dossierGamesChart','dossierDeviceChart'].forEach(d => {
        const el = document.getElementById(d);
        if (el) el.innerHTML = '';
      });
      const rrDom = document.getElementById('dossierRecentRoundsTable');
      if (rrDom) rrDom.innerHTML = '<p class="text-xs text-slate-500 italic">Loading...</p>';
      const tp = document.getElementById('dossierTrajPoints');
      if (tp) tp.textContent = '';

      const chunkId = Math.floor(id / CHUNK_SIZE);
      loadDossierChunk(chunkId, function (chunk) {
        if (loading) loading.classList.add('hidden');
        if (!chunk) {
          const rrDom2 = document.getElementById('dossierRecentRoundsTable');
          if (rrDom2) rrDom2.innerHTML = '<p class="text-xs text-rose-400 italic">Trajectory chunk could not be loaded. Serve this folder over HTTP (e.g. `python -m http.server`) or ensure dossier_chunks/ is at ../dossier_chunks/ relative to the HTML.</p>';
          return;
        }
        const detail = chunk[p.pid];
        if (!detail) return;
        renderDossierDetail(p, detail);
      });
    }

    function renderDossierDetail(p, d) {
      const t = dossierTheme();
      const bal = d.balance_series || [];
      const n = bal.length;

      const tp = document.getElementById('dossierTrajPoints');
      if (tp) tp.textContent = n.toLocaleString() + ' rounds · FULL';

      // Balance trajectory (FULL)
      const balDom = document.getElementById('dossierBalanceChart');
      if (balDom && n) {
        const bc = echarts.init(balDom);
        playerChartInstances['balance'] = bc;
        bc.setOption({
          backgroundColor: t.bg,
          grid: { top:20, right:20, bottom:30, left:70 },
          tooltip: { trigger:'axis', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10},
            formatter: ps => `Round ${ps[0].dataIndex+1} of ${n.toLocaleString()}<br>Balance: <strong>${fmtN(ps[0].value)}</strong>` },
          xAxis: { type:'category', axisLabel:{color:t.textColor,fontSize:8}, boundaryGap:false },
          yAxis: { type:'value', axisLabel:{color:t.textColor,fontSize:8,formatter:v=>fmtN(v)}, splitLine:{lineStyle:{color:t.gridBorder,type:'dashed'}} },
          dataZoom: [{ type:'inside' }, { type:'slider', height:14, bottom:4, borderColor:t.gridBorder, textStyle:{color:t.textColor,fontSize:8} }],
          series: [{ type:'line', data: bal, smooth:false, showSymbol:false, sampling:'lttb',
            lineStyle:{color:'#06b6d4',width:1.5},
            areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(6,182,212,0.22)'},{offset:1,color:'rgba(6,182,212,0)'}]}} }]
        });
      }

      // Cumulative P&L (derived from balance: net change from first observation)
      const pnlDom = document.getElementById('dossierPnlChart');
      if (pnlDom && n) {
        const base = bal[0];
        const pnl = bal.map(b => b - base);
        const pc = echarts.init(pnlDom);
        playerChartInstances['pnl'] = pc;
        pc.setOption({
          backgroundColor: t.bg,
          grid: { top:20, right:20, bottom:30, left:70 },
          tooltip: { trigger:'axis', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10},
            formatter: ps => `Round ${ps[0].dataIndex+1} of ${n.toLocaleString()}<br>Cumulative P&amp;L: <strong>${fmtN(ps[0].value)}</strong>` },
          xAxis: { type:'category', axisLabel:{color:t.textColor,fontSize:8}, boundaryGap:false },
          yAxis: { type:'value', axisLabel:{color:t.textColor,fontSize:8,formatter:v=>fmtN(v)}, splitLine:{lineStyle:{color:t.gridBorder,type:'dashed'}} },
          dataZoom: [{ type:'inside' }, { type:'slider', height:14, bottom:4, borderColor:t.gridBorder, textStyle:{color:t.textColor,fontSize:8} }],
          series: [{ type:'line', data: pnl, smooth:false, showSymbol:false, sampling:'lttb',
            lineStyle:{color:'#f43f5e',width:1.5},
            markLine:{ silent:true, symbol:'none', lineStyle:{color:t.textColor,type:'dashed'}, data:[{yAxis:0}], label:{show:false} },
            areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(244,63,94,0.18)'},{offset:1,color:'rgba(244,63,94,0)'}]}} }]
        });
      }

      // Hourly activity
      const hrsDom = document.getElementById('dossierHoursChart');
      if (hrsDom && d.hours && d.hours.length) {
        const hc = echarts.init(hrsDom);
        playerChartInstances['hours'] = hc;
        const peak = Math.max(...d.hours);
        hc.setOption({
          backgroundColor: t.bg,
          grid: { top:10, right:20, bottom:30, left:45 },
          tooltip: { trigger:'axis', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10}, formatter: ps => `${ps[0].name}<br>Bets: <strong>${ps[0].value.toLocaleString()}</strong>` },
          xAxis: { type:'category', data: Array.from({length:24},(_,i)=>`${i}:00`), axisLabel:{color:t.textColor,fontSize:8} },
          yAxis: { type:'value', axisLabel:{color:t.textColor,fontSize:8}, splitLine:{lineStyle:{color:t.gridBorder,type:'dashed'}} },
          series: [{ type:'bar', data: d.hours.map(v=>({ value:v, itemStyle:{ color: v===peak ? '#f43f5e' : '#f59e0b', borderRadius:[3,3,0,0] } })) }]
        });
      }

      // Game mix pie
      const gmDom = document.getElementById('dossierGamesChart');
      if (gmDom && d.games && d.games.length) {
        const gc = echarts.init(gmDom);
        playerChartInstances['games'] = gc;
        gc.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger:'item', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10},
            formatter: pr => `<strong>${pr.name}</strong><br>Bets: ${pr.value.toLocaleString()} (${pr.percent}%)<br>Volume: ${fmtN(pr.data.debit)}<br>Win Rate: ${pr.data.win_rate_pct}%` },
          series: [{ type:'pie', radius:['40%','70%'],
            data:d.games.map(g=>({ name:g.game, value:g.bets, debit:g.debit, win_rate_pct:g.win_rate_pct, itemStyle:{color:GAME_COLORS[g.game]||'#64748b'} })),
            label:{color:t.textColor,fontSize:9}, emphasis:{itemStyle:{shadowBlur:8}} }]
        });
      }

      // Device split
      const devDom = document.getElementById('dossierDeviceChart');
      if (devDom && d.devices) {
        const dc = echarts.init(devDom);
        playerChartInstances['device'] = dc;
        const devData = Object.keys(d.devices).map(k => ({ name:k, value:d.devices[k] }));
        dc.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger:'item', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10} },
          series: [{ type:'pie', radius:['35%','60%'], data: devData.map(x => ({ name:x.name, value:x.value, itemStyle:{ color: x.name==='Mobile' ? '#6366f1' : (x.name==='Desktop' ? '#06b6d4' : '#94a3b8') } })), label:{color:t.textColor,fontSize:9} }]
        });
      }

      // Recent rounds table
      const rr = d.recent_rounds || [];
      const rrDom = document.getElementById('dossierRecentRoundsTable');
      if (rrDom) {
        if (!rr.length) {
          rrDom.innerHTML = '<p class="text-xs text-slate-500 italic">No recent rounds captured for this player in the audit window.</p>';
        } else {
          rrDom.innerHTML = `<table class="w-full text-xs text-slate-300 border-collapse">
            <thead><tr class="border-b border-slate-700 text-slate-500 text-[10px] uppercase">
              <th class="py-1 px-2 text-left">Time</th><th class="py-1 px-2 text-left">Game</th>
              <th class="py-1 px-2 text-right">Debit</th><th class="py-1 px-2 text-right">Credit</th>
              <th class="py-1 px-2 text-center">Outcome</th><th class="py-1 px-2 text-right">Balance</th>
            </tr></thead>
            <tbody>${rr.slice(0,20).map(r=>`<tr class="border-b border-slate-800/50 hover:bg-slate-800/30">
              <td class="py-1 px-2 text-slate-500 text-[10px] font-mono">${(r.time||'').substring(5,16)}</td>
              <td class="py-1 px-2 text-slate-300">${r.game||''}</td>
              <td class="py-1 px-2 text-right text-amber-400 font-mono">${fmtN(r.debit||0)}</td>
              <td class="py-1 px-2 text-right text-emerald-400 font-mono">${fmtN(r.credit||0)}</td>
              <td class="py-1 px-2 text-center"><span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${(r.winlose||0)>0?'bg-emerald-500/20 text-emerald-400':((r.winlose||0)<0?'bg-rose-500/20 text-rose-400':'bg-slate-500/20 text-slate-400')}">${(r.winlose||0)>0?'WIN':((r.winlose||0)<0?'LOSS':'TIE')}</span></td>
              <td class="py-1 px-2 text-right text-slate-400 font-mono">${fmtN(r.balance||0)}</td>
            </tr>`).join('')}</tbody>
          </table>`;
        }
      }
    }

    function closePlayerDossier() {
      document.getElementById('playerDossierPanel').classList.add('hidden');
      disposePlayerCharts();
    }

    function openPlayerDossierById(pid, contextTab) {
      if (!DOSSIER) return;
      const entry = DOSSIER.players.find(p => p.pid === pid);
      if (!entry) return;
      if (contextTab) window._playerContextTab = contextTab;
      switchTab('players');
      setTimeout(() => openPlayerDossier(entry.id), 90);
    }

    // ── OPERATOR DOSSIERS ────────────────────────────────────────
    let filteredOperators = DOSSIER ? [...(DOSSIER.operators||[])] : [];

    function initOperatorDossiers() {
      if (!DOSSIER) return;
      const countries = [...new Set((DOSSIER.operators||[]).map(o => o.countries).filter(Boolean))].sort();
      const sel = document.getElementById('operatorCountryFilter');
      if (sel) countries.forEach(c => { const opt = document.createElement('option'); opt.value = c; opt.text = c; sel.appendChild(opt); });
      const cnt = document.getElementById('operatorDossierCount');
      if (cnt) cnt.textContent = (DOSSIER.operators||[]).length;
      renderOperatorCards();
    }

    function filterOperatorDossiers() {
      const q = (document.getElementById('operatorSearch')?.value || '').toLowerCase();
      const country = document.getElementById('operatorCountryFilter')?.value || '';
      filteredOperators = (DOSSIER.operators||[]).filter(o => {
        const matchQ = !q || (o.operator||'').toLowerCase().includes(q) || (o.countries||'').toLowerCase().includes(q);
        const matchCountry = !country || o.countries === country;
        return matchQ && matchCountry;
      });
      renderOperatorCards();
    }

    function renderOperatorCards() {
      const grid = document.getElementById('operatorCardsGrid');
      if (!grid || !DOSSIER) return;
      const fc = document.getElementById('operatorFilterCount');
      if (fc) fc.textContent = `${filteredOperators.length} of ${(DOSSIER.operators||[]).length} operators`;
      grid.innerHTML = filteredOperators.map(o => {
        const flag = flagOf(o.countries);
        const holdColor = o.hold_margin_pct > 3 ? '#10b981' : (o.hold_margin_pct > 1 ? '#f59e0b' : '#f43f5e');
        const holdBg = o.hold_margin_pct > 3 ? 'bg-emerald-500/20 text-emerald-400' : (o.hold_margin_pct > 1 ? 'bg-amber-500/20 text-amber-400' : 'bg-rose-500/20 text-rose-400');
        return `<div onclick="openOperatorDossier(${(DOSSIER.operators||[]).indexOf(o)})"
          class="glass-card rounded-2xl p-4 cursor-pointer hover:scale-[1.02] transition-all duration-200 border border-cyan-500/20">
          <div class="flex items-start justify-between mb-2">
            <div class="font-mono text-sm font-bold text-white truncate max-w-[190px]" title="${o.operator}">${o.operator}</div>
            <span class="px-2 py-0.5 rounded-full text-[9px] font-bold ${holdBg}">${(o.hold_margin_pct||0).toFixed(2)}% Hold</span>
          </div>
          <div class="text-[10px] text-slate-400 mb-2">${flag} ${o.countries||'Unknown'}</div>
          <div class="grid grid-cols-3 gap-2 text-xs">
            <div><span class="text-slate-400 text-[10px]">GGR</span><br><strong class="text-emerald-400 font-mono">${fmtN(o.ggr)}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Players</span><br><strong class="text-white font-mono">${(o.unique_players||0).toLocaleString()}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Bets/Player</span><br><strong class="text-cyan-400 font-mono">${(o.bets_per_player||0).toFixed(0)}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Total Volume</span><br><strong class="text-amber-400 font-mono">${fmtN(o.total_debit)}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Total Bets</span><br><strong class="text-slate-300 font-mono">${(o.total_bets||0).toLocaleString()}</strong></div>
            <div><span class="text-slate-400 text-[10px]">Avg Bet</span><br><strong class="text-indigo-400 font-mono">${fmtN(o.avg_bet)}</strong></div>
          </div>
        </div>`;
      }).join('');
    }

    let operatorChartInstances = {};
    function disposeOperatorCharts() {
      Object.values(operatorChartInstances).forEach(c => { try { c.dispose(); } catch(e){} });
      operatorChartInstances = {};
    }

    function openOperatorDossier(idx) {
      const o = (DOSSIER.operators||[])[idx];
      if (!o) return;
      const panel = document.getElementById('operatorDossierPanel');
      panel.classList.remove('hidden');
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      disposeOperatorCharts();

      const badge = document.getElementById('dossierOperatorBadge');
      badge.innerHTML = `<i class="fa-solid fa-building-columns mr-1"></i>${flagOf(o.countries)} ${o.countries||'Unknown'}`;
      badge.style = 'background:#06b6d422;border:1px solid #06b6d455;color:#06b6d4';
      document.getElementById('dossierOperatorTitle').textContent = o.operator;
      document.getElementById('dossierOperatorSub').textContent = `Hold Margin: ${(o.hold_margin_pct||0).toFixed(2)}% · Raw RTP: ${(o.operator_roi||0).toFixed(2)}% · ${(o.unique_players||0).toLocaleString()} unique players · ${(o.bets_per_player||0).toFixed(0)} bets/player`;

      document.getElementById('dossierOperatorKPIs').innerHTML = [
        kpiCard('Total Volume', fmtN(o.total_debit), 'text-cyan-400', 'fa-solid fa-coins'),
        kpiCard('Net GGR', fmtN(o.ggr), 'text-emerald-400', 'fa-solid fa-sack-dollar'),
        kpiCard('Hold %', (o.hold_margin_pct||0).toFixed(2)+'%', o.hold_margin_pct>3?'text-emerald-400':o.hold_margin_pct>1?'text-amber-400':'text-rose-400', 'fa-solid fa-percent'),
        kpiCard('Unique Players', (o.unique_players||0).toLocaleString(), 'text-white', 'fa-solid fa-users'),
        kpiCard('Bets/Player', (o.bets_per_player||0).toFixed(0), 'text-indigo-400', 'fa-solid fa-chart-bar'),
        kpiCard('Avg Bet', fmtN(o.avg_bet), 'text-amber-400', 'fa-solid fa-arrow-up-right-dots')
      ].join('');

      const t = dossierTheme();

      const opGmDom = document.getElementById('dossierOpGamesChart');
      if (opGmDom && o.games && o.games.length) {
        const gc = echarts.init(opGmDom);
        operatorChartInstances['games'] = gc;
        const games = o.games.filter(g => g.game !== 'Unknown');
        gc.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger:'axis', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10},
            formatter: ps => { const d = ps[0].data; return `<strong>${ps[0].name}</strong><br>Bets: ${(d.bets||0).toLocaleString()}<br>Volume: ${fmtN(d.debit||0)}<br>Hold Margin: ${(d.hold_margin_pct||0).toFixed(2)}%`; } },
          grid: { top:20, right:20, bottom:50, left:60 },
          xAxis: { type:'category', data:games.map(g=>g.game), axisLabel:{color:t.textColor,fontSize:9,rotate:20} },
          yAxis: { type:'value', axisLabel:{color:t.textColor,fontSize:8,formatter:v=>fmtN(v)}, splitLine:{lineStyle:{color:t.gridBorder,type:'dashed'}} },
          series: [{ type:'bar', data:games.map(g=>({value:g.bets, bets:g.bets, debit:g.debit, hold_margin_pct:g.hold_margin_pct, itemStyle:{color:GAME_COLORS[g.game]||'#64748b', borderRadius:[4,4,0,0]}})) }]
        });
      }

      const opHrsDom = document.getElementById('dossierOpHoursChart');
      if (opHrsDom && o.hours && o.hours.length) {
        const hc = echarts.init(opHrsDom);
        operatorChartInstances['hours'] = hc;
        const peak = Math.max(...o.hours);
        hc.setOption({
          backgroundColor: t.bg,
          grid: { top:10, right:20, bottom:30, left:55 },
          tooltip: { trigger:'axis', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10}, formatter: ps => `${ps[0].name}<br>Bets: <strong>${ps[0].value.toLocaleString()}</strong>` },
          xAxis: { type:'category', data:Array.from({length:24},(_,i)=>`${i}:00`), axisLabel:{color:t.textColor,fontSize:8} },
          yAxis: { type:'value', axisLabel:{color:t.textColor,fontSize:8}, splitLine:{lineStyle:{color:t.gridBorder,type:'dashed'}} },
          series: [{ type:'bar', data:o.hours.map(v=>({ value:v, itemStyle:{ color: v===peak ? '#f43f5e' : '#06b6d4', borderRadius:[3,3,0,0] } })) }]
        });
      }

      const opDevDom = document.getElementById('dossierOpDeviceChart');
      if (opDevDom && o.devices) {
        const dc = echarts.init(opDevDom);
        operatorChartInstances['device'] = dc;
        dc.setOption({
          backgroundColor: t.bg,
          tooltip: { trigger:'item', backgroundColor:t.tooltipBg, borderColor:t.tooltipBorder, textStyle:{color:t.tooltipText,fontSize:10} },
          series: [{ type:'pie', radius:['35%','60%'], data:[
            {name:'Mobile',value:o.devices['Mobile']||0,itemStyle:{color:'#6366f1'}},
            {name:'Desktop',value:o.devices['Desktop']||0,itemStyle:{color:'#06b6d4'}}
          ], label:{color:t.textColor,fontSize:9} }]
        });
      }

      const tp = o.top_players || [];
      const tpDom = document.getElementById('dossierOpPlayersTable');
      if (tpDom) {
        if (!tp.length) {
          tpDom.innerHTML = '<p class="text-xs text-slate-500 italic">No player-level data captured for this operator in the audit window.</p>';
        } else {
          tpDom.innerHTML = `<table class="w-full text-xs text-slate-300 border-collapse">
            <thead><tr class="border-b border-slate-700 text-slate-500 text-[10px] uppercase">
              <th class="py-1 px-2 text-left">#</th><th class="py-1 px-2 text-left">Player ID</th>
              <th class="py-1 px-2 text-right">Bets</th><th class="py-1 px-2 text-right">Volume</th>
              <th class="py-1 px-2 text-right">Net W/L</th><th class="py-1 px-2 text-right">Share</th>
              <th class="py-1 px-2 text-center">Dossier</th>
            </tr></thead>
            <tbody>${tp.map((pl,i)=>`<tr class="border-b border-slate-800/50 hover:bg-slate-800/30">
              <td class="py-1 px-2 text-slate-500">${i+1}</td>
              <td class="py-1 px-2 font-mono text-[10px] text-slate-300">${pl.player_id}</td>
              <td class="py-1 px-2 text-right text-slate-400">${(pl.bets||0).toLocaleString()}</td>
              <td class="py-1 px-2 text-right text-amber-400 font-mono">${fmtN(pl.debit||0)}</td>
              <td class="py-1 px-2 text-right font-mono ${(pl.winlose||0)<0?'text-emerald-400':'text-rose-400'}">${(pl.winlose||0)<0?'+'+fmtN(Math.abs(pl.winlose)):'−'+fmtN(Math.abs(pl.winlose))}</td>
              <td class="py-1 px-2 text-right text-cyan-400">${(pl.share_pct||0).toFixed(2)}%</td>
              <td class="py-1 px-2 text-center"><button onclick="event.stopPropagation(); openPlayerDossierById('${pl.player_id}', 'opdossiers')" class="px-1.5 py-0.5 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-[9px] font-semibold border border-amber-500/30"><i class="fa-solid fa-user-secret mr-0.5"></i>Open</button></td>
            </tr>`).join('')}</tbody>
          </table>`;
        }
      }
    }

    function closeOperatorDossier() {
      document.getElementById('operatorDossierPanel').classList.add('hidden');
      disposeOperatorCharts();
    }

    function openOperatorDossierById(name) {
      if (!DOSSIER) return;
      const idx = (DOSSIER.operators||[]).findIndex(o => o.operator === name);
      if (idx < 0) return;
      switchTab('operators');
      setTimeout(() => openOperatorDossier(idx), 90);
    }

    // ── CSV EXPORT ───────────────────────────────────────────────
    function exportDossierCSV(type) {
      if (!DOSSIER) return;
      let rows = [];
      if (type === 'players') {
        rows.push(['player_id','archetype','country','primary_operator','total_debit','total_winlose','total_bets','avg_bet','spike_multiplier','is_whale','is_chaser']);
        DOSSIER.players.forEach(p => rows.push([p.pid, p.arch, p.country, p.op, p.debit, p.winlose, p.bets, p.avg_bet, p.spike, p.whale, p.chaser]));
      } else {
        rows.push(['operator','countries','total_debit','total_winlose','net_ggr','hold_margin_pct','operator_roi_pct','total_bets','unique_players','bets_per_player','avg_bet']);
        (DOSSIER.operators||[]).forEach(o => rows.push([o.operator, o.countries, o.total_debit, o.total_winlose, o.ggr, o.hold_margin_pct, o.operator_roi, o.total_bets, o.unique_players, o.bets_per_player, o.avg_bet]));
      }
      const csv = rows.map(r => r.map(v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"').join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const a = document.createElement('a');
      a.download = type === 'players' ? 'all_player_dossiers.csv' : 'operator_dossiers.csv';
      a.href = URL.createObjectURL(blob);
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }

    // ── INTEGRATION HOOKS ────────────────────────────────────────
    (function patchDashboardHooks() {
      const origSwitchTab = window.switchTab;
      window.switchTab = function(tabId) {
        origSwitchTab(tabId);
        if (tabId === 'players' && !window._playersInited) { window._playersInited = true; initPlayerDossiers(); }
        if (tabId === 'operators' && !window._operatorsInited) { window._operatorsInited = true; initOperatorDossiers(); }
      };

      const origReinit = window.reinitAllCharts;
      window.reinitAllCharts = function() {
        origReinit();
        disposePlayerCharts();
        disposeOperatorCharts();
      };
    })();
    """

    # ── Inject nav buttons (find anchor) ──────────────────────────
    anchor = "5. Balance &amp; Bet Correlation\n          </button>"
    pos = html.find(anchor)
    if pos == -1:
        anchor = "5. Balance & Bet Correlation\n          </button>"
        pos = html.find(anchor)
    if pos != -1:
        html = html[:pos + len(anchor)] + NAV_INJECT + html[pos + len(anchor):]
    else:
        print("WARNING: nav anchor not found — tabs may not appear")

    # ── Inject tab HTML before </main> ────────────────────────────
    html = html.replace("    </main>", TAB6_HTML + "\n" + TAB7_HTML + "\n    </main>", 1)

    # ── Inject JS into controller script (after switchTab definition) ─
    switchtab_pos = html.find("function switchTab")
    if switchtab_pos != -1:
        script_close = html.find("</script>", switchtab_pos)
        if script_close != -1:
            html = html[:script_close] + DOSSIER_JS + "\n  " + html[script_close:]
        else:
            print("WARNING: could not locate controller script close tag")
    else:
        print("WARNING: switchTab not found - JS injection skipped")

    # ── Inject dossier JSON before </body> ────────────────────────
    DOSSIER_SCRIPT_BLOCK = f"""
  <!-- DOSSIER DATA (ALL {total_players:,} PLAYERS + OPERATORS) -->
  <script id="dossier-raw-data" type="application/json">
{dossier_json}
  </script>"""
    html = html.replace("</body>", DOSSIER_SCRIPT_BLOCK + "\n</body>", 1)

    # ── Write outputs ─────────────────────────────────────────────
    out1 = REPORT_DIR / "player_behavior_dashboard.html"
    out2 = REPORT_DIR / "player_behavior_dashboard.html"
    for out in [out1, out2]:
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"Injected ALL-player dossier tabs -> {out1}")
    print(f"Injected ALL-player dossier tabs -> {out2}")
    print(f"Final HTML size: {len(html):,} chars ({total_players:,} players embedded)")
    return True


if __name__ == "__main__":
    build()
