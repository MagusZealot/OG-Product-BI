from pathlib import Path
import html
import json
import math

import polars as pl

# ---------------------------------------------------------------------------
# Constants / workspace resolution
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

WORKSPACE = Path(WORKSPACE)
# NEW: Expected input is JSON Lines (.jsonl) file; bootstrap from legacy JSON if needed
DATA_FILE = WORKSPACE / "output" / "round_dealer_table_time_data.jsonl"
OUT_FILE = WORKSPACE / "output" / "dashboards" / "round_dealer_table_time_dashboard.html"

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PALETTE = [
    "#38bdf8", "#34d399", "#fbbf24", "#c084fc", "#fb7185",
    "#2dd4bf", "#a3e635", "#f97316", "#818cf8", "#f472b6",
]


def _r2(v):
    """Round to 2 decimal places; None if null/NaN/Inf."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 2)


def _ensure_jsonl():
    """Ensure a JSON Lines telemetry feed exists; convert legacy JSON once if needed."""
    if DATA_FILE.exists():
        return True
    legacy = WORKSPACE / "output" / "round_dealer_table_time_data.json"
    if not legacy.exists():
        print(f"[WARN] Neither {DATA_FILE} nor legacy {legacy} found.")
        return False
    # Stream-convert legacy JSON entity_entries -> JSONL (one line per record)
    try:
        with open(legacy, "r", encoding="utf-8") as fin, \
             open(DATA_FILE, "w", encoding="utf-8") as fout:
            data = json.load(fin)
            entries = data.get("entity_entries", {})
            for entity_id, recs in entries.items():
                if not isinstance(recs, list):
                    continue
                for e in recs:
                    if not isinstance(e, dict):
                        continue
                    line = {
                        "entity_id": entity_id,
                        "source": e.get("source", "dealer"),
                        "date": e.get("date"),
                        "game_type": e.get("game_type"),
                        "actual_duration": e.get("actual_duration"),
                        "expected_duration": e.get("expected_duration"),
                        "std_actual_duration": e.get("std_actual_duration"),
                        "duration_delta": e.get("duration_delta"),
                        "is_breach": e.get("is_breach"),
                    }
                    fout.write(json.dumps(line, ensure_ascii=False) + chr(10))
        print(f"[INFO] Converted legacy JSON to JSONL: {DATA_FILE.name}")
        return True
    except Exception as ex:
        print(f"[ERROR] Failed to convert JSON to JSONL: {ex}")
        return False


def _aggregate(df):
    """Given a Polars DataFrame from JSONL, produce the summarized dashboard payload."""
    import math as _m
    game_types = sorted(df["game_type"].unique().to_list())
    games = {}

    # --- Per-game-type baseline data & game baselines ----------------------
    # Game baseline = mean actual_duration for dealers only in that game
    game_baseline_df = (
        df.filter(pl.col("source") == "dealer")
        .group_by("game_type")
        .agg(pl.col("actual_duration").mean().alias("game_baseline"))
    )
    game_baseline_map = dict(
        zip(game_baseline_df["game_type"].to_list(),
            game_baseline_df["game_baseline"].to_list())
    )
    # Global mean & std across all rows for each game
    global_stats = (
        df.group_by("game_type")
        .agg(
            pl.col("actual_duration").mean().alias("global_mean"),
            pl.col("std_actual_duration").mean().alias("global_std"),
        )
    )
    global_map = {r["game_type"]: {"mean": _r2(r["global_mean"]), "std": _r2(r["global_std"])}
                  for r in global_stats.iter_rows(named=True)}

    # --- Versatility score per dealer (global across game types) -----------
    # dealer -> list of (dealer_avg - game_baseline) / game_baseline * 100
    dealer_game_avg = (
        df.filter(pl.col("source") == "dealer")
        .group_by("entity_id", "game_type")
        .agg(pl.col("actual_duration").mean().alias("dealer_avg"))
    )
    dealer_deltas = {}
    for row in dealer_game_avg.iter_rows(named=True):
        base = game_baseline_map.get(row["game_type"])
        if base and base > 0 and row["dealer_avg"] is not None:
            dealer_deltas.setdefault(row["entity_id"], []).append(
                (row["dealer_avg"] - base) / base * 100
            )
    versatility_map = {}
    for dealer, deltas in dealer_deltas.items():
        if len(deltas) <= 1:
            versatility_map[dealer] = 0.0
        else:
            versatility_map[dealer] = round(sum(deltas) / len(deltas), 2)

    # --- Per-game aggregation loop ---------------------------------------
    for gt in game_types:
        sub = df.filter(pl.col("game_type") == gt)

        # --- KPIs --------------------------------------------------------
        global_mean = _r2(sub["actual_duration"].mean())
        std_baseline = _r2(sub["std_actual_duration"].mean())
        dealer_sub = sub.filter(pl.col("source") == "dealer")
        game_baseline = _r2(dealer_sub["actual_duration"].mean() if dealer_sub.height else None)
        dealer_count = int(sub.filter(pl.col("source") == "dealer")["entity_id"].n_unique())
        table_count = int(sub.filter(pl.col("source") == "table")["entity_id"].n_unique())

        # --- DOW volatility ----------------------------------------------
        # Polars weekday() is 1=Mon..7=Sun; remap to JS getDay() 0=Sun..6=Sat
        dow_df = (
            sub.with_columns(((pl.col("date").str.to_date().dt.weekday() % 7)).alias("dow"))
            .group_by("dow")
            .agg(
                pl.col("actual_duration").mean().alias("mean_avgtimediff"),
                pl.col("std_actual_duration").mean().alias("mean_stdtime"),
            )
        )
        dow_map = {int(r["dow"]): r for r in dow_df.iter_rows(named=True)}
        dow_vol = []
        for d in range(7):
            row = dow_map.get(d, {})
            dow_vol.append({
                "day": d,
                "dayName": DAY_NAMES[d],
                "avgAVG": _r2(row.get("mean_avgtimediff")),
                "avgSTD": _r2(row.get("mean_stdtime")),
            })

        # --- Per-dealer summary (for dealer cards + watchlists) ---------
        dealer_agg = (
            dealer_sub.group_by("entity_id")
            .agg(
                pl.col("actual_duration").mean().alias("avg"),
                pl.col("std_actual_duration").mean().alias("std"),
                pl.col("date").n_unique().alias("days"),
                pl.len().alias("records"),
            )
            .sort("avg")
        )
        # Slow-decile floor for watchlist threshold
        n_dealers = len(dealer_agg)
        slow_idx = max(0, _m.ceil(n_dealers * 0.9) - 1) if n_dealers else -1
        slow_floor = _r2(dealer_agg["avg"][slow_idx]) if slow_idx >= 0 and n_dealers > 0 else None
        baseline_val = game_baseline if game_baseline is not None else 0.0

        # Flagged slow dealers
        watchlist_dealers = []
        for r in dealer_agg.iter_rows(named=True):
            delta = (r["avg"] or 0) - baseline_val
            flagged = delta > 0 and (delta >= 1.5 or (slow_floor is not None and r["avg"] >= slow_floor))
            if flagged:
                watchlist_dealers.append({
                    "dealer": r["entity_id"],
                    "avg": r["avg"],
                    "delta": delta,
                })
        watchlist_dealers.sort(key=lambda x: -x["avg"])

        # --- Table aggregation -------------------------------------------
        table_sub = sub.filter(pl.col("source") == "table")
        table_agg = (
            table_sub.group_by("entity_id")
            .agg(
                pl.col("actual_duration").mean().alias("avg"),
                pl.col("std_actual_duration").mean().alias("std"),
            )
            .sort("avg")
        )
        n_tables = len(table_agg)
        t_slow_idx = max(0, _m.ceil(n_tables * 0.9) - 1) if n_tables else -1
        t_slow_floor = _r2(table_agg["avg"][t_slow_idx]) if t_slow_idx >= 0 and n_tables > 0 else None

        watchlist_tables = []
        for r in table_agg.iter_rows(named=True):
            delta = (r["avg"] or 0) - baseline_val
            flagged = delta > 0 and (delta >= 1.5 or (t_slow_floor is not None and r["avg"] >= t_slow_floor))
            if flagged:
                watchlist_tables.append({
                    "table": r["entity_id"],
                    "avg": r["avg"],
                    "delta": delta,
                })
        watchlist_tables.sort(key=lambda x: -x["avg"])

        # --- Efficiency matrix -------------------------------------------
        eff_dealers = [
            {"name": r["entity_id"], "avg": _r2(r["avg"]), "std": _r2(r["std"])}
            for r in dealer_agg.filter(pl.col("avg").is_not_null() & pl.col("std").is_not_null()).iter_rows(named=True)]
        eff_tables = [
            {"name": r["entity_id"], "avg": _r2(r["avg"]), "std": _r2(r["std"])}
            for r in table_agg.filter(pl.col("avg").is_not_null() & pl.col("std").is_not_null()).iter_rows(named=True)]

        # --- Micro-disruption alerts: 30-day rolling mean of std ---------
        micro_alerts = []
        if dealer_sub.height:
            dsorted = dealer_sub.sort(["entity_id", "date"])
            with_ma = dsorted.with_columns(
                pl.col("std_actual_duration").rolling_mean(30).over("entity_id").alias("ma30")
            )
            seen = set()
            for r in with_ma.iter_rows(named=True):
                cur = r["std_actual_duration"]
                ma = r["ma30"]
                if cur is not None and ma is not None and ma > 0 and (cur / ma) > 2.0:
                    key = (r["entity_id"], r["date"])
                    if key not in seen:
                        seen.add(key)
                        micro_alerts.append({
                            "dealer": r["entity_id"],
                            "date": r["date"],
                            "currentStd": _r2(cur),
                            "movingAvg": _r2(ma),
                            "ratio": round((cur / ma) * 100) / 100,
                        })

        # --- Series duration & breach (daily) ----------------------------
        series_df = (
            sub.group_by("date")
            .agg(
                pl.col("actual_duration").mean().alias("mean_act"),
                (pl.col("is_breach").sum() / pl.len() * 100).alias("breach_pct"),
            )
            .sort("date")
        )
        series_duration = [[r["date"], _r2(r["mean_act"])] for r in series_df.iter_rows(named=True)]
        series_breach = [[r["date"], _r2(r["breach_pct"])] for r in series_df.iter_rows(named=True)]

        # --- Dealer trend: dates + daily baseline + top/bottom dealers -----
        dates = sorted(sub["date"].unique().to_list())
        # Daily baseline = mean of all dealer actual_durations per date
        daily_base = (
            dealer_sub.group_by("date")
            .agg(pl.col("actual_duration").mean().alias("avg"))
            .sort("date")
        )
        daily_baseline_map = dict(
            zip(daily_base["date"].to_list(), daily_base["avg"].to_list())
        )
        baseline_series = [_r2(daily_baseline_map.get(d)) for d in dates]

        # Rank dealers by overall avg, pick top 5 + bottom 5
        ranked = dealer_agg.sort("avg")
        chosen = set()
        if len(ranked) >= 5:
            chosen |= set(ranked["entity_id"][:5].to_list())
            chosen |= set(ranked["entity_id"][-5:].to_list())
        else:
            chosen |= set(ranked["entity_id"].to_list())

        # Per-chosen dealer: daily avg across their dates
        dealer_daily_map = {}
        if chosen:
            cd = dealer_sub.filter(pl.col("entity_id").is_in(list(chosen)))
            dd = cd.group_by(["entity_id", "date"]).agg(pl.col("actual_duration").mean().alias("avg"))
            for r in dd.iter_rows(named=True):
                dealer_daily_map.setdefault(r["entity_id"], {})[r["date"]] = _r2(r["avg"])
        top_dealers = []
        for name in chosen:
            dm = dealer_daily_map.get(name, {})
            top_dealers.append({
                "name": name,
                "data": [_r2(dm.get(d)) for d in dates],
            })

        # --- Pace extremes: top/bottom 10 by avg across all profiles ------
        all_profiles = eff_dealers + eff_tables
        all_sorted = sorted(all_profiles, key=lambda x: x["avg"])
        pace_extremes = {
            "fastest": [{"entity": p["name"], "avg": p["avg"]} for p in all_sorted[:10]],
            "slowest": [{"entity": p["name"], "avg": p["avg"]} for p in all_sorted[-10:]],
        }

        # --- Dealer cards: per-dealer stats + WoW + versatility ---------
        latest_date = max(sub["date"].unique().to_list()) if len(sub) else None
        hv_dealer_set = set(a["dealer"] for a in micro_alerts) if micro_alerts else set()
        dealer_cards = []
        for r in dealer_agg.iter_rows(named=True):
            name = r["entity_id"]
            days = int(r["days"]) if r["days"] is not None else 0
            # Week-over-week: recent 7d avg vs prev-week avg for this dealer
            wow = None
            if latest_date and days >= 14:
                dsub = dealer_sub.filter(pl.col("entity_id") == name).sort("date")
                dd = dsub.group_by("date").agg(pl.col("actual_duration").mean().alias("avg")).sort("date")
                dlist = dd["date"].to_list()
                if len(dlist) >= 14:
                    recent_vals = [_r2(x) for x in dd.filter(pl.col("date").is_in(dlist[-7:]))["avg"].to_list()]
                    prev_vals = [_r2(x) for x in dd.filter(pl.col("date").is_in(dlist[-14:-7]))["avg"].to_list()]
                    if recent_vals and prev_vals:
                        ra = sum(recent_vals) / len(recent_vals)
                        pa = sum(prev_vals) / len(prev_vals)
                        wow = {"diff": _r2(ra - pa),
                               "pct": round((ra - pa) / pa * 100, 1) if pa else None,
                               "recentAvg": _r2(ra),
                               "prevWeekAvg": _r2(pa),
                               "isWorse": (ra > pa) if (pa is not None and ra is not None) else None}
            dealer_cards.append({
                "dealer": name,
                "avgTime": _r2(r["avg"]),
                "stdTime": _r2(r["std"]),
                "days": days,
                "records": int(r["records"]),
                "versatilityScore": versatility_map.get(name, 0),
                "wow": wow,
                "hasHighVariance": name in hv_dealer_set,
            })
        dealer_cards.sort(key=lambda x: -(x["avgTime"] or 0))

        # --- Dealer profiles (for dossier: per-game breakdown, context switching) --
        dealer_rows = dealer_sub
        dealer_prof = {}
        for name in dealer_rows["entity_id"].unique().to_list():
            dsub = dealer_rows.filter(pl.col("entity_id") == name)
            avg = _r2(dsub["actual_duration"].mean())
            std = _r2(dsub["std_actual_duration"].mean())
            days = int(dsub["date"].n_unique())
            records = int(len(dsub))
            # Per-game breakdown
            per_game = {}
            for gt_i in dsub["game_type"].unique().to_list():
                gs = dsub.filter(pl.col("game_type") == gt_i)
                gs_dates = gs.group_by("date").agg(pl.col("actual_duration").mean().alias("avg")).sort("date")
                per_game[gt_i] = {
                    "avg": _r2(gs["actual_duration"].mean()),
                    "std": _r2(gs["std_actual_duration"].mean()),
                    "days": int(gs["date"].n_unique()),
                    "records": int(len(gs)),
                    "daily": [[str(x["date"]), _r2(x["avg"])] for x in gs_dates.iter_rows(named=True)],
                }
            # Context-switching: distinct game types per date
            ctx = dsub.group_by("date").agg(
                pl.col("game_type").n_unique().alias("ng"),
                pl.col("actual_duration").mean().alias("avg"))
            single = ctx.filter(pl.col("ng") == 1)
            multi = ctx.filter(pl.col("ng") > 1)
            sa = _r2(single["avg"].mean()) if len(single) else None
            ma = _r2(multi["avg"].mean()) if len(multi) else None
            penalty = _r2((ma - sa) if (ma is not None and sa is not None and ma > sa) else 0)
            dealer_prof[name] = {
                "avg": avg,
                "std": std,
                "days": days,
                "records": records,
                "versatilityScore": versatility_map.get(name, 0),
                "games": per_game,
                "context": {
                    "singleAvg": sa,
                    "multiAvg": ma,
                    "singleCount": int(len(single)),
                    "multiCount": int(len(multi)),
                    "penalty": penalty,
                },
            }

        games[gt] = {
            "kpis": {
                "globalAvg": global_map[gt]["mean"],
                "gameBaseline": game_baseline,
                "stdBaseline": global_map[gt]["std"],
                "dealerCount": dealer_count,
                "tableCount": table_count,
            },
            "dowVolatility": dow_vol,
            "watchlistDealers": watchlist_dealers,
            "watchlistTables": watchlist_tables,
            "efficiencyMatrix": {"dealers": eff_dealers, "tables": eff_tables},
            "seriesDuration": series_duration,
            "seriesBreach": series_breach,
            "dealerTrend": {
                "dates": dates,
                "baseline": baseline_series,
                "dealers": top_dealers,
            },
            "paceExtremes": pace_extremes,
            "dealerCards": dealer_cards,
            "microAlerts": micro_alerts,
            "dealerProfiles": dealer_prof,
        }

    # --- Build final payload ---------------------------------------------
    payload = {
        "meta": {"game_types": game_types},
        "game_order": game_types,
        "games": games,
    }
    # Keep each game's precomputed dealer trajectory and context metrics.
    # The browser renders these values directly; it does not rebuild aggregates.
    for gt in game_types:
        profiles = payload["games"][gt].get("dealerProfiles", {})
        for profile in profiles.values():
            game_profile = profile.get("games", {}).get(gt, {})
            profile["daily"] = game_profile.get("daily", [])
            profile.pop("games", None)

    return payload


def _forensics_rows(df):
    return [
        {
            "BILLING_DATE": row["date"],
            "GAME_TYPE": row["game_type"],
            "DEALER": row["entity_id"] if row["source"] == "dealer" else None,
            "TABLE_NO": row["entity_id"] if row["source"] == "table" else None,
            "AVG_TIMEDIFF": row["actual_duration"],
            "STD_TIMEDIFF": row["std_actual_duration"],
        }
        for row in df.select(
            "date", "game_type", "source", "entity_id",
            "actual_duration", "std_actual_duration",
        ).sort("date", descending=True).iter_rows(named=True)
    ]


# ---------------------------------------------------------------------------
# HTML template (streamlined: JS maps pre-computed payload data only)
# ---------------------------------------------------------------------------
TEMPLATE_START = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dealer & Table Pace Intelligence</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
  <link rel="stylesheet" href="dashboard-common.css">
  <style>
    :root { color-scheme: dark; font-family: Inter, "Segoe UI", sans-serif; background: #090e1a; color: #e2e8f0; }
    * { box-sizing: border-box; }
    body { margin: 0; min-width: 320px; background: radial-gradient(ellipse at top, #14213a 0, #090e1a 55%); }
    header { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px; padding: 14px max(20px, calc((100vw - 1480px) / 2)); background: #0b1220ed; border-bottom: 1px solid #253247; backdrop-filter: blur(12px); }
    h1 { margin: 0; font-size: clamp(18px, 2.4vw, 26px); letter-spacing: .02em; }
    header p { margin: 5px 0 0; color: #93a4bc; font-size: 12px; }
    .filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }
    select { min-width: 190px; padding: 9px 12px; border: 1px solid #344258; border-radius: 8px; background: #111b2d; color: #e2e8f0; font-family: inherit; font-size: 12px; }
    .game-tags button {
      padding: 6px 12px; border: 1px solid #344258; border-radius: 20px; background: #111b2d; color: #94a3b8; font-family: inherit; font-size: 12px; cursor: pointer; transition: all 0.15s;
    }
    .game-tags button.active { background: #1e3a5f; border-color: #34d399; color: #34d399; }
    .game-tags button:hover:not(.active) { border-color: #4a5a7a; background: #1a2740; }
    .quick-nav { position: sticky; top: 72px; z-index: 10; flex-basis: 100%; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 12px; padding: 10px 0; border-top: 1px solid #253247; background: #090e1a; }
    .header-quick-nav { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
    .header-quick-nav .quick-nav-label { color: #77869c; font-size: 10px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; margin-right: 2px; }
    .header-quick-nav a { padding: 5px 10px; border: 1px solid #2b3b57; border-radius: 7px; background: #0f1a2e; color: #9fb2ca; text-decoration: none; font-size: 11px; font-weight: 600; white-space: nowrap; }
    .header-quick-nav a:hover { border-color: #34d399; color: #6ee7b7; }
    .header-quick-nav a.section-link { color: #8fa3bd; }
    .header-quick-nav a.section-link:hover { border-color: #38bdf8; color: #7dd3fc; }
    main { max-width: 1480px; margin: auto; padding: 22px; }
    .section { margin-bottom: 16px; }
    .hero { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: 18px; }
    .hero h2 { margin: 0; font-size: 18px; }
    .hero p, .muted { color: #94a3b8; font-size: 12px; }
    .hero p { max-width: 900px; margin-bottom: 0; line-height: 1.55; }
    .kpis { display: grid; grid-template-columns: repeat(4, minmax(180px, 1fr)); gap: 10px; margin-bottom: 16px; }
    .card { border: 1px solid #24334a; border-radius: 14px; background: linear-gradient(145deg, #121d30e8, #0c1423f2); box-shadow: 0 10px 30px #0002; }
    .kpi { padding: 16px; }
    .kpi label { display: block; margin-bottom: 8px; color: #91a2ba; font-size: 10px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; }
    .kpi strong { font: 700 20px ui-monospace, Consolas, monospace; color: #f8fafc; }
    .kpi .sub { display: block; margin-top: 6px; color: #64748b; font-size: 10px; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .chart-card { min-width: 0; padding: 15px; }
    .chart-card h3 { margin: 0 0 8px; font-size: 14px; }
    .chart-card .muted { margin: 0 0 12px; }
    .chart { width: 100%; height: 360px; }
    .wide { grid-column: 1 / -1; }
    .full-width { width: 100vw; max-width: none; margin-left: calc(50% - 50vw); margin-right: calc(50% - 50vw); }
    .watchlist { padding: 16px; border-color: #7f1d1d; }
    .watchlist h3 { margin: 0 0 4px; color: #fda4af; font-size: 15px; }
    .watchlist .muted { margin: 0 0 12px; }
    .watchlist .pagination { display: flex; justify-content: space-between; align-items: center; margin: 12px 0 0; }
    .watchlist .pagination button { cursor: pointer; color: #94a3b8; }
    .watchlist .pagination button:disabled { opacity: 0.45; }
    .watchlist table th { color: #fda4af; }
    .watchlist table td { color: #fecdd3; }
    .watchlist .action { color: #fbbf24; font-weight: 700; }
    .table-wrap { overflow: auto; max-height: 680px; border: 1px solid #253247; border-radius: 10px; }
    table { width: 100%; border-collapse: collapse; white-space: nowrap; font-size: 12px; }
    th, td { padding: 10px 12px; border-bottom: 1px solid #253247; text-align: right; }
    th { position: sticky; top: 0; z-index: 1; background: #111b2d; color: #90a3bd; font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }
    td:first-child, th:first-child { text-align: left; }
    tbody tr:hover { background: #17243a; }
    .table-empty { padding: 18px 12px; color: #94a3b8; font-size: 12px; font-style: italic; text-align: left; }
    .dealer-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; width: 100%; max-width: 100%; box-sizing: border-box; margin: 0 auto; }
    @media (max-width: 1600px) { .dealer-grid { grid-template-columns: repeat(5, 1fr); } }
    @media (max-width: 1300px) { .dealer-grid { grid-template-columns: repeat(4, 1fr); } }
    @media (max-width: 1000px) { .dealer-grid { grid-template-columns: repeat(3, 1fr); } }
    @media (max-width: 700px) { .dealer-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 560px) { .dealer-grid { grid-template-columns: 1fr; } }
    .dossier-section { padding: 16px; }
    .dossier-section .card { padding: 16px; }
    .dossier-section h3 { margin: 0 0 8px; font-size: 14px; }
    .dossier-section .muted { margin: 0 0 12px; }
    .dossier-section .game-switcher { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .dossier-section .game-switcher button { padding: 4px 10px; border: 1px solid #344258; border-radius: 16px; background: #111b2d; color: #94a3b8; font-size: 11px; cursor: pointer; transition: all 0.15s; }
    .dossier-section .game-switcher button.active { background: #1e3a5f; border-color: #34d399; color: #34d399; }
    footer { padding: 22px 0 8px; color: #77869c; font-size: 11px; }
    @media (max-width: 900px) { .kpis { grid-template-columns: repeat(2, 1fr); } .grid { grid-template-columns: 1fr; } .wide { grid-column: auto; } .full-width { width: auto; margin-left: 0; margin-right: 0; } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1><i class="fa-solid fa-gauge-high" style="color:#34d399"></i> Dealer & Table Pace Intelligence</h1>
      <p id="feedStatus">Loading pace telemetry...</p>
    </div>
      <div class="filters">
        <div class="muted" style="font-size: 11px; margin-bottom: 6px;">Game type (all views are isolated to this game)</div>
        <div id="gameTags" class="game-tags" style="display: flex; flex-wrap: wrap; gap: 6px;"></div>
      </div>
      <nav class="dashboard-nav">
        <a href="bi_dashboard.html"><i class="fa-solid fa-chart-line"></i> BI Console</a>
        <a href="game_probability_dashboard.html"><i class="fa-solid fa-dice"></i> Probability & HE</a>
        <a href="player_behavior_dashboard.html"><i class="fa-solid fa-gamepad"></i> Player Behavior</a>
      </nav>
      <nav class="header-quick-nav" id="paceQuickNav" aria-label="Jump to sections"></nav>
    </div>
  </header>
  <main>
    <section class="hero section">
      <div>
        <h2>Operational Efficiency & Pace Console</h2>
        <p>Dealer speeds are compared only with the selected game's baseline. The source feed reports dealers and tables as separate observations, not dealer-table pairings; the matrix and rankings preserve that distinction rather than inventing matches.</p>
      </div>
    </section>
    <section id="kpis" class="kpis section" aria-label="Selected game key performance indicators"></section>
    <section id="dowVolatilitySection" class="wide section">
      <article class="card chart-card wide full-width">
        <h3>Day-of-the-Week Volatility</h3>
        <div class="muted">Mean AVG_TIMEDIFF and STD_TIMEDIFF across the 7 days of the week</div>
        <div id="dowVolatilityChart" class="chart"></div>
        <div id="dowVolatilityLegend" style="margin-top: 8px; font-size: 11px; color: #94a3b8; display: flex; justify-content: center; gap: 16px; align-items: center;"></div>
      </article>
    </section>
    <section class="card watchlist section" id="slowDealersSection" aria-labelledby="watchlistTitle">
      <h3 id="watchlistTitle"><i class="fa-solid fa-triangle-exclamation"></i> Watchlist: Slow Dealers</h3>
      <p class="muted">Dealers slower than the selected game's baseline by at least 1.50 seconds or in its slowest 10%.</p>
      <div class="pagination">
        <span id="watchlistPageInfo" style="color: #94a3b8; font-size: 12px;">Loading watchlist...</span>
      </div>
      <div class="chart-card">
        <div id="watchlistChart" class="chart"></div>
      </div>
    </section>
    <section id="highVarianceWatchlistSection" class="wide section">
      <article class="card chart-card wide full-width">
        <h3><i class="fa-solid fa-triangle-exclamation"></i> Watchlist: High-Variance Shifts</h3>
        <p class="muted">Rows where dealer's daily STD_TIMEDIFF > 200% of 30-day moving average</p>
        <div id="highVarianceChart" class="chart"></div>
      </article>
    </section>
    <section class="card watchlist section" id="slowTablesSection" aria-labelledby="tableWatchlistTitle">
      <h3 id="tableWatchlistTitle"><i class="fa-solid fa-table"></i> Watchlist: Slow Tables</h3>
      <p class="muted">Tables slower than the selected game's baseline by at least 1.50 seconds or in its slowest 10%.</p>
      <div class="pagination">
        <span id="tableWatchlistPageInfo" style="color: #94a3b8; font-size: 12px;">Loading watchlist...</span>
      </div>
      <div class="chart-card">
        <div id="tableWatchlistChart" class="chart"></div>
      </div>
    </section>
    <section class="grid section" id="dealerTrendSection">
      <article class="card chart-card wide full-width">
        <h3>Dealer Speed Over Time</h3>
        <div class="muted">Selected game's daily dealer baseline and up to five fastest and five slowest dealer trends</div>
        <div id="dealerTrend" class="chart"></div>
      </article>
    </section>
    <section class="grid section" id="efficiencyMatrixSection">
      <article class="card chart-card wide full-width">
        <h3>Combined Efficiency Matrix</h3>
        <div class="muted">Average time (speed) vs standard deviation (consistency), selected game only</div>
        <div id="efficiencyMatrix" class="chart"></div>
      </article>
    </section>
    <section class="grid section" id="paceExtremesSection">
      <article class="card chart-card wide">
        <h3>Top / Bottom 10 Dealer & Table Profiles</h3>
        <div class="muted">Fastest and slowest entity profiles by average time, ranked within the selected game only</div>
        <div id="paceExtremes" class="chart"></div>
      </article>
    </section>
    <section class="section" id="dealerDossierCardsSection">
      <article class="card chart-card wide full-width">
        <h3>Individualized Dealer Dossier</h3>
        <div class="muted">Select a dealer to view their KPIs and performance trend</div>
        <div class="filters" style="margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-size: 11px; color: #94a3b8;">Baseline:</label>
            <select id="filterBaseline" style="padding: 6px 10px; border: 1px solid #344258; border-radius: 6px; background: #111b2d; color: #e2e8f0; font-size: 11px;">
              <option value="">All</option>
              <option value="above">Above (Slower)</option>
              <option value="below">Below (Faster)</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-size: 11px; color: #94a3b8;">Min Days:</label>
            <select id="filterMinDays" style="padding: 6px 10px; border: 1px solid #344258; border-radius: 6px; background: #111b2d; color: #e2e8f0; font-size: 11px;">
              <option value="">Any</option>
              <option value="14">14+ Days</option>
              <option value="30">30+ Days</option>
              <option value="60">60+ Days</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-size: 11px; color: #94a3b8;">Week-over-Week (WoW):</label>
            <select id="filterWow" style="padding: 6px 10px; border: 1px solid #344258; border-radius: 6px; background: #111b2d; color: #e2e8f0; font-size: 11px;">
              <option value="">All</option>
              <option value="faster">Faster (Improved)</option>
              <option value="slower">Slower (Declined)</option>
              <option value="no-data">No Week-over-Week Data</option>
            </select>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-size: 11px; color: #94a3b8;">High Variance Shifts:</label>
            <select id="filterHighVariance" style="padding: 6px 10px; border: 1px solid #344258; border-radius: 6px; background: #111b2d; color: #e2e8f0; font-size: 11px;">
              <option value="">All</option>
              <option value="yes">Has High-Variance Shifts</option>
              <option value="no">No High-Variance Shifts</option>
            </select>
          </div>
          <button id="clearFilters" type="button" style="padding: 6px 12px; border: 1px solid #344258; border-radius: 6px; background: #111b2d; color: #94a3b8; font-size: 11px; cursor: pointer;">Clear Filters</button>
        </div>
        <div id="dealerCardGrid" class="dealer-grid" style="padding: 16px; max-width: 100%; box-sizing: border-box;"></div>
        <div id="loadMoreBtn" style="margin: 16px auto; cursor: pointer; color: #94a3b8; text-align: center; display: none;">Load More Dealers &rarr;</div>
      </article>
    </section>
<section id="dealerDossierSection" class="full-width dossier-section" style="display: none;">
        <div class="card" style="max-width: none; margin: 0;">
          <div style="padding: 16px; max-height: 90vh; overflow-y: auto;">
            <div style="font-size: 12px; color: #91a2ba; text-transform: uppercase; letter-spacing: .09em; margin-bottom: 12px;">Dealer Dossier</div>
            <div id="dealerDossierKpis" style="min-height: 120px;"></div>
            <div style="margin-top: 16px;">
              <strong>Other games for this dealer:</strong>
              <div id="dealerGameSwitcher" class="game-switcher"></div>
            </div>
            <div style="margin-top: 24px;">
              <strong>Trend Chart:</strong> Dealer performance over time
            </div>
            <div id="dealerDossierTrend" class="chart" style="height: 300px; margin-top: 12px;"></div>
            <div style="margin-top: 16px;">
              <strong>Context-Switching Penalty:</strong> Average time on single-game vs multi-game days
            </div>
            <div id="dealerContextSwitchChart" class="chart" style="height: 200px; margin-top: 12px;"></div>
            <div style="margin-top: 24px;">
              <strong>High-Variance Shifts:</strong> Days where this dealer's STD_TIMEDIFF exceeded 200% of their 30-day moving average
            </div>
            <div id="dealerHighVarianceChart" class="chart" style="height: 200px; margin-top: 12px;"></div>
            <div id="dealerHighVarianceNote" style="margin-top: 6px; color: #94a3b8; font-size: 11px;"></div>
          </div>
        </div>
      </section>
    <section class="card chart-card wide section" id="forensicsSection" aria-labelledby="forensicsTitle">
      <h3 id="forensicsTitle">Forensics Table</h3>
      <div class="muted">Full telemetry for the selected game, with search and pagination</div>
      <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 12px 0;">
        <label for="forensicsSearch" class="muted">Search records</label>
        <input id="forensicsSearch" type="search" placeholder="Date, dealer, or table"
          style="padding: 8px 10px; border: 1px solid #344258; border-radius: 6px; background: #111b2d; color: #e2e8f0;">
        <span id="forensicsPageInfo" class="muted" aria-live="polite"></span>
        <button id="forensicsPrevPage" type="button">&larr; Prev</button>
        <button id="forensicsNextPage" type="button">Next &rarr;</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Billing Date</th><th>Game Type</th><th>Dealer</th><th>Table No</th><th>Avg Time (s)</th><th>Std Dev (s)</th></tr>
          </thead>
          <tbody id="forensicsTable"></tbody>
        </table>
      </div>
    </section>
    <footer>Source: combined daily dealer and table pace snapshots. Change the game selector to isolate all KPIs, charts, and tables to another game.</footer>
  </main>
  <script id="pace-console-data" type="application/json">__PAYLOAD__</script>
  <script>
    // Python precomputes every metric and series; this code only renders them.
    const DATA = JSON.parse(document.getElementById('pace-console-data').textContent);
    const ROWS = Array.isArray(DATA.rows) ? DATA.rows : [];
    const games = Array.isArray(DATA.game_order) ? DATA.game_order : [];
    const PAGE_SIZE = 100;
    const WATCHLIST_PAGE_SIZE = 20;
    const CARD_PAGE_SIZE = 48;
    let selectedGame = games[0] || '';
    let currentPage = 0;
    let dealerCardLimit = CARD_PAGE_SIZE;
    let selectedDealer = null;

    const getChartTheme = () => ({
      text: '#94a3b8', grid: '#253247', tooltipBg: '#0f172a',
      tooltipBorder: '#334155', tooltipText: '#f8fafc'
    });
    const theme = getChartTheme();
    const palette = ['#38bdf8', '#34d399', '#fbbf24', '#c084fc', '#fb7185',
      '#2dd4bf', '#a3e635', '#f97316', '#818cf8', '#f472b6'];
    const axisStyle = {
      axisLabel: { color: theme.text },
      axisLine: { lineStyle: { color: '#334155' } },
      splitLine: { lineStyle: { color: theme.grid, type: 'dashed' } }
    };
    const tooltipStyle = {
      backgroundColor: theme.tooltipBg, borderColor: theme.tooltipBorder,
      textStyle: { color: theme.tooltipText, fontSize: 12 }, confine: true
    };
    const chartIds = ['dowVolatilityChart', 'watchlistChart', 'tableWatchlistChart',
      'efficiencyMatrix', 'dealerTrend', 'paceExtremes', 'dealerDossierTrend',
      'dealerContextSwitchChart', 'highVarianceChart', 'dealerHighVarianceChart'];
    const charts = {};
    if (typeof window.echarts !== 'undefined') {
      chartIds.forEach(id => {
        const element = document.getElementById(id);
        if (element) charts[id] = window.echarts.init(element);
      });
    } else {
      chartIds.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
          element.textContent = 'Charts could not load because ECharts is unavailable. Check the network connection and reload.';
          element.style.cssText += ';display:grid;place-items:center;color:#94a3b8;text-align:center;padding:20px';
        }
      });
    }
    const allCharts = Object.values(charts);
    const escapeHtml = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
    const numeric = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
    const fmt2 = value => numeric(value) == null ? 'N/A' : Number(value).toFixed(2);
    const currentData = () => DATA.games && DATA.games[selectedGame] ? DATA.games[selectedGame] : null;
    const setChart = (id, option) => { if (charts[id]) charts[id].setOption(option, true); };
    function showEmpty(id, message) {
      if (!charts[id]) return;
      charts[id].clear();
      charts[id].setOption({ graphic: [{ type: 'text', left: 'center', top: 'middle',
        style: { text: message, fill: theme.text, fontSize: 13, textAlign: 'center' } }] });
    }

    function renderKpis(game) {
      const k = game.kpis || {};
      const tiles = [
        ['Global Average Pace', fmt2(k.globalAvg) + ' s', selectedGame + ' only'],
        ['Selected Game Baseline', fmt2(k.gameBaseline) + ' s', 'Average dealer time for this game'],
        ['Average Std Dev', fmt2(k.stdBaseline) + ' s', 'Consistency baseline for this game'],
        ['Active Fleet', (k.dealerCount || 0) + ' / ' + (k.tableCount || 0),
          (k.dealerCount || 0) + ' dealers ? ' + (k.tableCount || 0) + ' tables']
      ];
      document.getElementById('kpis').innerHTML = tiles.map(tile =>
        '<div class="card kpi"><label>' + escapeHtml(tile[0]) + '</label><strong>' +
        escapeHtml(tile[1]) + '</strong><span class="sub">' + escapeHtml(tile[2]) + '</span></div>'
      ).join('');
      const latestDate = ROWS.length ? [...ROWS].map(r => r.BILLING_DATE).filter(Boolean).sort().pop() : null;
      document.getElementById('feedStatus').textContent = selectedGame + ' · ' + (latestDate ? 'Latest: ' + latestDate : 'No date') + ' · Python-prepared pace telemetry';
    }

    function renderDowVolatility(game) {
      const rows = Array.isArray(game.dowVolatility) ? game.dowVolatility : [];
      if (!rows.length) return showEmpty('dowVolatilityChart', 'No day-of-week data');
      const avgs = rows.map(row => row.avgAVG ?? 0);
      const stds = rows.map(row => row.avgSTD ?? 0);
      const maxAvg = Math.max(...avgs), minAvg = Math.min(...avgs);
      const maxStd = Math.max(...stds), minStd = Math.min(...stds);
      const hiColor = '#fb7185';
      const loColor = '#34d399';
      const avgItemStyle = avgs.map(v => {
        if (v === maxAvg) return { color: hiColor };
        if (v === minAvg) return { color: loColor };
        return { color: palette[0] };
      });
      const stdItemStyle = stds.map(v => {
        if (v === maxStd) return { color: hiColor };
        if (v === minStd) return { color: loColor };
        return { color: palette[2] };
      });
      setChart('dowVolatilityChart', {
        color: [palette[0], palette[2]], tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis' }),
        legend: { top: 0, textStyle: { color: theme.text } },
        grid: { left: 56, right: 20, top: 42, bottom: 38 },
        xAxis: { type: 'category', data: rows.map(row => row.dayName), ...axisStyle },
        yAxis: { type: 'value', name: 'Seconds', ...axisStyle },
        series: [
          { name: 'Mean AVG_TIMEDIFF', type: 'bar', data: avgs.map((v, i) => ({ value: v, itemStyle: avgItemStyle[i] })), barMaxWidth: 28 },
          { name: 'Mean STD_TIMEDIFF', type: 'bar', data: stds.map((v, i) => ({ value: v, itemStyle: stdItemStyle[i] })), barMaxWidth: 28 }
        ]
      });
      const legend = document.getElementById('dowVolatilityLegend');
      if (legend) {
        const hiAvg = rows[avgs.indexOf(maxAvg)].dayName;
        const loAvg = rows[avgs.indexOf(minAvg)].dayName;
        const hiStd = rows[stds.indexOf(maxStd)].dayName;
        const loStd = rows[stds.indexOf(minStd)].dayName;
        legend.innerHTML =
          '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;background:' + hiColor + ';border-radius:2px;display:inline-block"></span>Highest: ' + escapeHtml(hiAvg) + ' (' + fmt2(maxAvg) + 's)</span>' +
          '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;background:' + loColor + ';border-radius:2px;display:inline-block"></span>Lowest: ' + escapeHtml(loAvg) + ' (' + fmt2(minAvg) + 's)</span>' +
          '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;background:' + hiColor + ';border-radius:2px;display:inline-block"></span>Highest STD: ' + escapeHtml(hiStd) + ' (' + fmt2(maxStd) + 's)</span>' +
          '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;background:' + loColor + ';border-radius:2px;display:inline-block"></span>Lowest STD: ' + escapeHtml(loStd) + ' (' + fmt2(minStd) + 's)</span>';
      }
    }
function renderWatchlist(game) {
      const rows = Array.isArray(game.watchlistDealers) ? game.watchlistDealers : [];
      
      document.getElementById('watchlistPageInfo').textContent = rows.length.toLocaleString() + ' slow dealer(s)';
      
      if (!rows.length) return showEmpty('watchlistChart', 'No dealers meet the selected-game thresholds');
      
      setChart('watchlistChart', {
        color: ['#fb7185'],
        tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: params => {
            const row = rows[params[0].dataIndex];
            return '<strong>' + escapeHtml(row.dealer) + '</strong><br>Average: ' + fmt2(row.avg) +
              ' s<br>Slower than baseline: ' + fmt2(row.delta) + ' s';
          }
        }),
        grid: { left: 120, right: 70, top: 16, bottom: 12, containLabel: true },
        xAxis: { type: 'value', name: 'AVG_TIMEDIFF (s)', ...axisStyle },
        yAxis: { type: 'category', inverse: true, data: rows.map(row => row.dealer), ...axisStyle,
          axisLabel: { color: theme.text, width: 180, overflow: 'break' } },
        series: [{
          type: 'bar', data: rows.map(row => row.avg), barMaxWidth: 18,
          itemStyle: { color: '#fb7185', borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: theme.text, formatter: p => fmt2(p.value) }
        }],
        markLine: {
          symbol: ['none', 'none'],
          lineStyle: { color: '#38bdf8', type: 'dashed', width: 2 },
          label: { 
            formatter: 'Baseline ' + fmt2((game.kpis || {}).gameBaseline) + ' s', 
            color: '#f8fafc', backgroundColor: '#38bdf8', padding: [4, 8], borderRadius: 4, 
            position: 'insideEndTop', fontWeight: 600, fontSize: 11
          },
          data: [{ xAxis: numeric((game.kpis || {}).gameBaseline) }]
        }
      });
      if (charts.watchlistChart) {
        charts.watchlistChart.off('click');
        charts.watchlistChart.on('click', params => {
          if (params.dataIndex != null && rows[params.dataIndex]) {
            renderDealerDossier(game, rows[params.dataIndex].dealer);
          }
        });
      }
    }
    function renderTableWatchlist(game) {
      const rows = Array.isArray(game.watchlistTables) ? game.watchlistTables : [];
      
      document.getElementById('tableWatchlistPageInfo').textContent = rows.length.toLocaleString() + ' slow table(s)';
      
      if (!rows.length) return showEmpty('tableWatchlistChart', 'No tables meet the selected-game thresholds');
      
      setChart('tableWatchlistChart', {
        color: ['#fbbf24'],
        tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: params => {
            const row = rows[params[0].dataIndex];
            return '<strong>Table ' + escapeHtml(row.table) + '</strong><br>Average: ' + fmt2(row.avg) +
              ' s<br>Slower than baseline: ' + fmt2(row.delta) + ' s';
          }
        }),
        grid: { left: 60, right: 70, top: 16, bottom: 12, containLabel: true },
        xAxis: { type: 'value', name: 'AVG_TIMEDIFF (s)', ...axisStyle },
        yAxis: { type: 'category', inverse: true, data: rows.map(row => row.table), ...axisStyle },
        series: [{ type: 'bar', data: rows.map(row => row.avg), barMaxWidth: 18,
          itemStyle: { color: '#fbbf24', borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: theme.text, formatter: p => fmt2(p.value) } }],
        markLine: {
          symbol: ['none', 'none'],
          lineStyle: { color: '#38bdf8', type: 'dashed', width: 2 },
          label: { 
            formatter: 'Baseline ' + fmt2((game.kpis || {}).gameBaseline) + ' s', 
            color: '#f8fafc', backgroundColor: '#38bdf8', padding: [4, 8], borderRadius: 4, 
            position: 'insideEndTop', fontWeight: 600, fontSize: 11
          },
          data: [{ xAxis: numeric((game.kpis || {}).gameBaseline) }]
        }
      });
    }

    function renderEfficiencyMatrix(game) {
      const matrix = game.efficiencyMatrix || {};
      const dealers = Array.isArray(matrix.dealers) ? matrix.dealers : [];
      const tables = Array.isArray(matrix.tables) ? matrix.tables : [];
      if (!dealers.length && !tables.length) return showEmpty('efficiencyMatrix', 'No dealer or table profiles');
      setChart('efficiencyMatrix', {
        color: [palette[0], palette[2]],
        tooltip: Object.assign({}, tooltipStyle, { trigger: 'item', formatter: p =>
          '<strong>' + escapeHtml(p.data.name) + '</strong><br>' + p.seriesName +
          '<br>Average time: ' + fmt2(p.data.value[0]) + ' s<br>Std dev: ' + fmt2(p.data.value[1]) + ' s' }),
        legend: { top: 0, textStyle: { color: theme.text } },
        grid: { left: 70, right: 22, top: 42, bottom: 56 },
        xAxis: { type: 'value', name: 'AVG_TIMEDIFF ? Speed (s)', nameLocation: 'middle', nameGap: 30,
          nameTextStyle: { color: theme.text }, ...axisStyle },
        yAxis: { type: 'value', name: 'STD_TIMEDIFF ? Consistency (s)', nameTextStyle: { color: theme.text }, ...axisStyle },
        series: [
          { name: 'Dealers', type: 'scatter', symbolSize: 10,
            data: dealers.map(row => ({ name: row.name, value: [row.avg, row.std] })) },
          { name: 'Tables', type: 'scatter', symbol: 'diamond', symbolSize: 11,
            data: tables.map(row => ({ name: row.name, value: [row.avg, row.std] })) }
        ]
      });
      if (charts.efficiencyMatrix) {
        charts.efficiencyMatrix.off('click');
        charts.efficiencyMatrix.on('click', params => {
          if (params.seriesName === 'Dealers' && params.data && params.data.name) {
            renderDealerDossier(game, params.data.name);
          }
        });
      }
    }

    function renderDealerTrend(game) {
      const trend = game.dealerTrend || {};
      const dates = Array.isArray(trend.dates) ? trend.dates : [];
      if (!dates.length) return showEmpty('dealerTrend', 'No dealer trend data');
      const baseline = Array.isArray(trend.baseline) ? trend.baseline : [];
      const baselineAvg = baseline.length
        ? baseline.reduce((s, v) => s + (numeric(v) || 0), 0) / baseline.length
        : null;
      const series = [{ name: selectedGame + ' baseline', type: 'line',
        data: baseline, showSymbol: false,
        lineStyle: { color: '#f8fafc', width: 3 } }];
      (Array.isArray(trend.dealers) ? trend.dealers : []).forEach((dealer, i) => series.push({
        name: dealer.name, type: 'line', data: dealer.data, showSymbol: false, connectNulls: false,
        lineStyle: { color: palette[i % palette.length], width: 1.6 }
      }));
      setChart('dealerTrend', {
        color: palette, tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis', axisPointer: { type: 'line' } }),
        legend: { type: 'scroll', top: 0, textStyle: { color: theme.text, fontSize: 10 },
          selected: Object.fromEntries(series.map(row => [row.name, row.name === selectedGame + ' baseline'])) },
        grid: { left: 58, right: 20, top: 54, bottom: 62 },
        xAxis: { type: 'category', boundaryGap: false, data: dates, ...axisStyle,
          axisLabel: { color: theme.text, rotate: dates.length > 20 ? 35 : 0 } },
        yAxis: { type: 'value', name: 'AVG_TIMEDIFF (s)', nameTextStyle: { color: theme.text }, ...axisStyle },
        dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 10 }], series: series,
        markLine: baselineAvg != null ? {
          symbol: ['none', 'none'],
          lineStyle: { color: '#fbbf24', type: 'dashed', width: 2 },
          label: {
            formatter: 'Baseline Avg: ' + fmt2(baselineAvg) + ' s',
            color: '#fbbf24', backgroundColor: '#1e293b', padding: [5, 10], borderRadius: 4,
            fontWeight: 600, fontSize: 11
          },
          data: [{ yAxis: baselineAvg }]
        } : null
      });
      if (charts.dealerTrend) {
        charts.dealerTrend.off('click');
        charts.dealerTrend.on('click', params => {
          if (params.seriesName && params.seriesName !== selectedGame + ' baseline') {
            renderDealerDossier(game, params.seriesName);
          }
        });
      }
    }

    function renderPaceExtremes(game) {
      const extremes = game.paceExtremes || {};
      const fastest = Array.isArray(extremes.fastest) ? extremes.fastest : [];
      const slowest = Array.isArray(extremes.slowest) ? extremes.slowest : [];
      const rows = fastest.map(row => ({ entity: row.entity, avg: row.avg, kind: 'Fastest' }))
        .concat(slowest.map(row => ({ entity: row.entity, avg: row.avg, kind: 'Slowest' })));
      if (!rows.length) return showEmpty('paceExtremes', 'No profile rankings');
      setChart('paceExtremes', {
        tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: params => {
            const row = rows[params[0].dataIndex];
            return '<strong>' + escapeHtml(row.entity) + '</strong><br>' + row.kind +
              '<br>Average time: ' + fmt2(row.avg) + ' s';
          }
        }),
        grid: { left: 14, right: 66, top: 16, bottom: 12, containLabel: true },
        xAxis: { type: 'value', name: 'AVG_TIMEDIFF (s)', ...axisStyle },
        yAxis: { type: 'category', inverse: true, data: rows.map(row => row.entity), ...axisStyle,
          axisLabel: { color: theme.text, width: 160, overflow: 'truncate' } },
        series: [{ name: 'Average time', type: 'bar', barMaxWidth: 17,
          data: rows.map(row => ({ value: row.avg, itemStyle: { color: row.kind === 'Fastest' ? '#34d399' : '#fb7185' } })),
          label: { show: true, position: 'right', color: theme.text, formatter: p => fmt2(p.value) } }]
      });
      if (charts.paceExtremes) {
        charts.paceExtremes.off('click');
        charts.paceExtremes.on('click', params => {
          if (params.dataIndex != null && rows[params.dataIndex]) {
            renderDealerDossier(game, rows[params.dataIndex].entity);
          }
        });
      }
    }

    function renderHighVariance(game) {
      const rows = Array.isArray(game.microAlerts) ? game.microAlerts : [];
      const host = document.getElementById('highVarianceChart');
      // Remove any stale note from a previous game
      const oldNote = host.nextElementSibling;
      if (oldNote && oldNote.classList.contains('muted') && oldNote.textContent && oldNote.textContent.includes('high-variance shifts')) {
        oldNote.remove();
      }
      if (!rows.length) return showEmpty('highVarianceChart', 'No high-variance shifts in this game.');
      const sorted = rows.slice().sort((a, b) => (b.ratio || 0) - (a.ratio || 0));
      const MAX_SHOW = 30;
      const shown = sorted.slice(0, MAX_SHOW);
      const hidden = sorted.length - MAX_SHOW;
      setChart('highVarianceChart', {
        color: ['#fb7185'],
        tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: params => {
            const row = shown[params[0].dataIndex];
            return '<strong>' + escapeHtml(row.dealer) + '</strong><br>' +
              escapeHtml(row.date) + '<br>Current std dev: ' + fmt2(row.currentStd) +
              ' s<br>30-day average: ' + fmt2(row.movingAvg) + ' s<br>Ratio: ' + fmt2(row.ratio) + 'x';
          }
        }),
        grid: { left: 200, right: 40, top: 42, bottom: 38, containLabel: true },
        xAxis: { type: 'value', name: 'Ratio (current / 30-day avg)', ...axisStyle },
        yAxis: { type: 'category', inverse: true, data: shown.map(row => escapeHtml(row.dealer) + ' · ' + escapeHtml(row.date)), ...axisStyle,
          axisLabel: { color: theme.text, width: 220, overflow: 'truncate' } },
        series: [{
          type: 'bar', data: shown.map(row => row.ratio), barMaxWidth: 18,
          itemStyle: { color: '#fb7185', borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: theme.text, formatter: p => fmt2(p.value) + 'x' }
        }],
        markLine: {
          symbol: ['none', 'none'],
          lineStyle: { color: '#38bdf8', type: 'dashed', width: 2 },
          label: { formatter: '2.0x threshold', color: '#f8fafc', backgroundColor: '#38bdf8', padding: [4, 8], borderRadius: 4, position: 'insideEndTop', fontWeight: 600, fontSize: 11 },
          data: [{ xAxis: 2 }]
        },
        dataZoom: [{ type: 'inside' }, { type: 'slider', height: 14, bottom: 8 }]
      });
      if (charts.highVarianceChart) {
        charts.highVarianceChart.off('click');
        charts.highVarianceChart.on('click', params => {
          if (params.dataIndex != null && shown[params.dataIndex]) {
            renderDealerDossier(game, shown[params.dataIndex].dealer);
          }
        });
      }
      if (hidden > 0) {
        const note = document.createElement('div');
        note.className = 'muted';
        note.style.textAlign = 'right';
        note.style.marginTop = '6px';
        note.style.fontSize = '11px';
        note.textContent = 'Showing top ' + MAX_SHOW.toLocaleString() + ' of ' + sorted.length.toLocaleString() + ' high-variance shifts (' + hidden.toLocaleString() + ' more)';
        host.parentNode.insertBefore(note, host.nextSibling);
      }
    }

    function filteredDealerCards(game) {
      const cards = Array.isArray(game.dealerCards) ? game.dealerCards : [];
      const baselineFilter = document.getElementById('filterBaseline').value;
      const minDays = Number(document.getElementById('filterMinDays').value || 0);
      const wowFilter = document.getElementById('filterWow').value;
      const hvFilter = document.getElementById('filterHighVariance').value;
      const baseline = numeric((game.kpis || {}).gameBaseline);
      return cards.filter(card => {
        if (Number(card.days || 0) < minDays) return false;
        if (baselineFilter === 'above' && (baseline == null || Number(card.avgTime) <= baseline)) return false;
        if (baselineFilter === 'below' && (baseline == null || Number(card.avgTime) >= baseline)) return false;
        if (wowFilter === 'no-data' && card.wow) return false;
        if (wowFilter === 'faster' && (!card.wow || card.wow.isWorse !== false)) return false;
        if (wowFilter === 'slower' && (!card.wow || card.wow.isWorse !== true)) return false;
        if (hvFilter === 'yes' && !card.hasHighVariance) return false;
        if (hvFilter === 'no' && card.hasHighVariance) return false;
        return true;
      });
    }

    function renderDealerCards(game) {
      const rows = filteredDealerCards(game);
      const visible = rows.slice(0, dealerCardLimit);
      const grid = document.getElementById('dealerCardGrid');
      grid.innerHTML = visible.length ? visible.map(card => {
        const wowHtml = card.wow
          ? '<div class="muted" style="margin-top:8px;padding-top:8px;border-top:1px solid #253247;color:' + (card.wow.isWorse ? '#fb7185' : '#34d399') + ';font-size:10px;">WoW: ' + (card.wow.isWorse ? 'Slower' : 'Faster') + ' by ' + Math.abs(card.wow.pct).toFixed(1) + '% (' + fmt2(card.wow.recentAvg) + 's vs ' + fmt2(card.wow.prevWeekAvg) + 's)</div>'
          : '<div class="muted" style="margin-top:8px;padding-top:8px;border-top:1px solid #253247;font-size:10px;color:#64748b;">WoW: Insufficient data</div>';
        return '<button type="button" class="card" data-dealer="' + escapeHtml(card.dealer) +
          '" style="padding:12px;text-align:left;color:inherit;cursor:pointer;min-width:0"><strong>' +
          escapeHtml(card.dealer) + '</strong><div class="muted">' + fmt2(card.avgTime) + ' s average \u00b7 ' +
          Number(card.days || 0).toLocaleString() + ' days</div><div class="muted">Std dev ' + fmt2(card.stdTime) +
          ' s \u00b7 ' + Number(card.records || 0).toLocaleString() + ' records</div>' + wowHtml + '</button>';
      }).join('') : '<div class="table-empty" style="grid-column:1/-1;text-align:center;padding:20px">No dealers match these filters.</div>';
      const more = document.getElementById('loadMoreBtn');
      more.style.display = rows.length > visible.length ? 'block' : 'none';
      more.textContent = 'Showing ' + visible.length.toLocaleString() + ' of ' + rows.length.toLocaleString() + ' dealers \u00bb Load More \u00bb';
    }

    function renderDealerDossier(game, dealer) {
      const profile = (game.dealerProfiles || {})[dealer];
      const section = document.getElementById('dealerDossierSection');
      if (!profile) { section.style.display = 'none'; return; }
      selectedDealer = dealer;
      section.style.display = 'block';
      document.getElementById('dealerDossierKpis').innerHTML =
        '<div style="margin-bottom:12px"><strong style="font-size:18px;color:#f8fafc">' + escapeHtml(dealer) + '</strong></div>' +
        '<div class="kpis" style="grid-template-columns:repeat(3,minmax(0,1fr))">' +
        '<div class="card kpi"><label>Average Pace</label><strong>' + fmt2(profile.avg) + ' s</strong><span class="sub">' +
        Number(profile.days || 0).toLocaleString() + ' days</span></div>' +
        '<div class="card kpi"><label>Consistency</label><strong>' + fmt2(profile.std) +
        ' s</strong><span class="sub">Average standard deviation</span></div>' +
        '<div class="card kpi"><label>Records</label><strong>' + Number(profile.records || 0).toLocaleString() +
        '</strong><span class="sub"></span></div></div>';
      // Scroll to dossier section
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const dealerGames = games.filter(gameType => DATA.games[gameType] &&
        DATA.games[gameType].dealerProfiles && DATA.games[gameType].dealerProfiles[dealer]);
      document.getElementById('dealerGameSwitcher').innerHTML = dealerGames.map(gameType =>
        '<button type="button" data-dossier-game="' + escapeHtml(gameType) + '"' +
        (gameType === selectedGame ? ' class="active"' : '') + '>' + escapeHtml(gameType) + '</button>'
      ).join('');
      const daily = Array.isArray(profile.daily) ? profile.daily : [];
      if (!daily.length) showEmpty('dealerDossierTrend', 'No daily trend data for this dealer');
      else setChart('dealerDossierTrend', {
        color: [palette[0]], tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis' }),
        grid: { left: 56, right: 20, top: 20, bottom: 46 },
        xAxis: { type: 'category', boundaryGap: false, data: daily.map(point => point[0]), ...axisStyle,
          axisLabel: { color: theme.text, rotate: daily.length > 20 ? 35 : 0 } },
        yAxis: { type: 'value', name: 'AVG_TIMEDIFF (s)', ...axisStyle },
        dataZoom: [{ type: 'inside' }, { type: 'slider', height: 14, bottom: 4 }],
        series: [{ name: dealer, type: 'line', data: daily.map(point => point[1]), showSymbol: false,
          connectNulls: false, lineStyle: { width: 2, color: palette[0] },
          markLine: numeric((game.kpis || {}).gameBaseline) == null ? undefined : {
            symbol: ['none', 'none'], lineStyle: { color: palette[2], type: 'dashed' },
            label: { formatter: 'Game baseline', color: theme.text }, data: [{ yAxis: game.kpis.gameBaseline }]
          }
        }]
      });
      const context = profile.context || {};
      const contextRows = [
        { name: 'Single-game days', value: context.singleAvg },
        { name: 'Multi-game days', value: context.multiAvg }
      ].filter(row => numeric(row.value) != null);
      if (!contextRows.length) showEmpty('dealerContextSwitchChart', 'No context-switching comparison');
      else setChart('dealerContextSwitchChart', {
        color: [palette[3]], tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis' }),
        grid: { left: 110, right: 24, top: 12, bottom: 28 },
        xAxis: { type: 'value', name: 'AVG_TIMEDIFF (s)', ...axisStyle },
        yAxis: { type: 'category', data: contextRows.map(row => row.name), ...axisStyle },
        series: [{ type: 'bar', data: contextRows.map(row => row.value), barMaxWidth: 24,
          label: { show: true, position: 'right', color: theme.text, formatter: p => fmt2(p.value) } }]
      });

      // Dealer-specific high-variance shifts
      const dealerAlerts = Array.isArray(game.microAlerts) ? game.microAlerts.filter(r => r.dealer === dealer) : [];
      const hvHost = document.getElementById('dealerHighVarianceChart');
      const hvNote = document.getElementById('dealerHighVarianceNote');
      if (!dealerAlerts.length) {
        showEmpty('dealerHighVarianceChart', 'No high-variance shifts for this dealer.');
        hvNote.textContent = '';
      } else {
        const sorted = dealerAlerts.slice().sort((a, b) => (b.ratio || 0) - (a.ratio || 0));
        const MAX_SHOW = 20;
        const shown = sorted.slice(0, MAX_SHOW);
        const hidden = sorted.length - MAX_SHOW;
        setChart('dealerHighVarianceChart', {
          color: ['#fb7185'],
          tooltip: Object.assign({}, tooltipStyle, { trigger: 'axis', axisPointer: { type: 'shadow' },
            formatter: params => {
              const row = shown[params[0].dataIndex];
              return '<strong>' + escapeHtml(row.dealer) + '</strong><br>' +
                escapeHtml(row.date) + '<br>Current std dev: ' + fmt2(row.currentStd) +
                ' s<br>30-day average: ' + fmt2(row.movingAvg) + ' s<br>Ratio: ' + fmt2(row.ratio) + 'x';
            }
          }),
          grid: { left: 120, right: 30, top: 32, bottom: 30, containLabel: true },
          xAxis: { type: 'value', name: 'Ratio (current / 30-day avg)', ...axisStyle },
          yAxis: { type: 'category', inverse: true, data: shown.map(row => escapeHtml(row.date)), ...axisStyle },
          series: [{
            type: 'bar', data: shown.map(row => row.ratio), barMaxWidth: 16,
            itemStyle: { color: '#fb7185', borderRadius: [0, 4, 4, 0] },
            label: { show: true, position: 'right', color: theme.text, formatter: p => fmt2(p.value) + 'x' }
          }],
          markLine: {
            symbol: ['none', 'none'],
            lineStyle: { color: '#38bdf8', type: 'dashed', width: 2 },
            label: { formatter: '2.0x threshold', color: '#f8fafc', backgroundColor: '#38bdf8', padding: [4, 8], borderRadius: 4, position: 'insideEndTop', fontWeight: 600, fontSize: 10 },
            data: [{ xAxis: 2 }]
          },
          dataZoom: [{ type: 'inside' }, { type: 'slider', height: 10, bottom: 6 }]
        });
        hvNote.textContent = shown.length + ' shift(s)' + (hidden > 0 ? ' (top ' + MAX_SHOW + ' of ' + sorted.length + ')' : '');
      }
      requestAnimationFrame(() => {
        if (charts.dealerDossierTrend) charts.dealerDossierTrend.resize();
        if (charts.dealerContextSwitchChart) charts.dealerContextSwitchChart.resize();
        if (charts.dealerHighVarianceChart) charts.dealerHighVarianceChart.resize();
      });
    }

    function renderForensics() {
      const query = document.getElementById('forensicsSearch').value.trim().toLowerCase();
      const rows = ROWS.filter(row => row.GAME_TYPE === selectedGame &&
        (!query || [row.BILLING_DATE, row.GAME_TYPE, row.DEALER, row.TABLE_NO]
          .some(value => String(value || '').toLowerCase().includes(query))));
      const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
      currentPage = Math.min(currentPage, pages - 1);
      const body = document.getElementById('forensicsTable');
      body.replaceChildren();
      if (!rows.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 6; cell.className = 'table-empty';
        cell.textContent = 'No telemetry records are available for this game.';
        row.appendChild(cell); body.appendChild(row);
      } else {
        rows.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).forEach(record => {
          const row = document.createElement('tr');
          [record.BILLING_DATE, record.GAME_TYPE, record.DEALER, record.TABLE_NO,
            record.AVG_TIMEDIFF, record.STD_TIMEDIFF].forEach((value, index) => {
            const cell = document.createElement('td');
            cell.textContent = value == null || value === '' ? '?' :
              index >= 4 && Number.isFinite(Number(value)) ? Number(value).toFixed(2) : String(value);
            row.appendChild(cell);
          });
          body.appendChild(row);
        });
      }
      document.getElementById('forensicsPageInfo').textContent = rows.length.toLocaleString() +
        ' records ? Page ' + (currentPage + 1) + ' of ' + pages;
      document.getElementById('forensicsPrevPage').disabled = currentPage === 0;
      document.getElementById('forensicsNextPage').disabled = currentPage >= pages - 1;
      document.querySelectorAll('#gameTags button').forEach(button => {
        button.classList.toggle('active', button.dataset.gameType === selectedGame);
        button.setAttribute('aria-pressed', button.dataset.gameType === selectedGame);
      });
    }

    function buildPaceQuickNav() {
      const nav = document.getElementById('paceQuickNav');
      if (!nav) return;
      const links = [
        { href: '#kpis', label: 'KPIs' },
        { href: '#dowVolatilitySection', label: 'Day-of-Week Volatility' },
        { href: '#slowDealersSection', label: 'Watchlist: Slow Dealers' },
        { href: '#highVarianceWatchlistSection', label: 'Watchlist: High-Variance Shifts' },
        { href: '#slowTablesSection', label: 'Watchlist: Slow Tables' },
        { href: '#dealerTrendSection', label: 'Dealer Speed Over Time' },
        { href: '#efficiencyMatrixSection', label: 'Efficiency Matrix' },
        { href: '#paceExtremesSection', label: 'Top / Bottom 10 Profiles' },
        { href: '#dealerDossierCardsSection', label: 'Individualized Dealer Dossier' },
        { href: '#forensicsSection', label: 'Forensics Table' }
      ];
      nav.innerHTML = '<span class="quick-nav-label">Jump to</span>' + links.map(link =>
        `<a class="section-link" href="${link.href}">${escapeHtml(link.label)}</a>`
      ).join('');
    }

    function renderGame() {
      const game = currentData();
      if (!game) return;
      renderKpis(game);
      renderDowVolatility(game);
      renderWatchlist(game);
      renderTableWatchlist(game);
      renderEfficiencyMatrix(game);
      renderDealerTrend(game);
      renderPaceExtremes(game);
      renderHighVariance(game);
      renderDealerCards(game);
      renderForensics();
    }
    function selectGame(gameType) {
      if (!DATA.games || !DATA.games[gameType]) return;
      selectedGame = gameType;
      currentPage = 0;
      dealerCardLimit = CARD_PAGE_SIZE; selectedDealer = null;
      document.getElementById('dealerDossierSection').style.display = 'none';
      renderGame();
    }

    document.getElementById('gameTags').addEventListener('click', event => {
      const button = event.target.closest('button[data-game-type]');
      if (button) selectGame(button.dataset.gameType);
    });
    document.getElementById('forensicsSearch').addEventListener('input', () => {
      currentPage = 0; renderForensics();
    });
    document.getElementById('forensicsPrevPage').addEventListener('click', () => {
      currentPage -= 1; renderForensics();
    });
    document.getElementById('forensicsNextPage').addEventListener('click', () => {
      currentPage += 1; renderForensics();
    });
    ['filterBaseline', 'filterMinDays', 'filterWow', 'filterHighVariance'].forEach(id =>
      document.getElementById(id).addEventListener('change', () => {
        dealerCardLimit = CARD_PAGE_SIZE; renderDealerCards(currentData());
      })
    );
    document.getElementById('clearFilters').addEventListener('click', () => {
      document.getElementById('filterBaseline').value = '';
      document.getElementById('filterMinDays').value = '';
      document.getElementById('filterWow').value = '';
      document.getElementById('filterHighVariance').value = '';
      dealerCardLimit = CARD_PAGE_SIZE; renderDealerCards(currentData());
    });
    document.getElementById('loadMoreBtn').addEventListener('click', () => {
      dealerCardLimit += CARD_PAGE_SIZE; renderDealerCards(currentData());
    });
    document.getElementById('dealerCardGrid').addEventListener('click', event => {
      const button = event.target.closest('button[data-dealer]');
      if (button) renderDealerDossier(currentData(), button.dataset.dealer);
    });
    document.getElementById('dealerGameSwitcher').addEventListener('click', event => {
      const button = event.target.closest('button[data-dossier-game]');
      if (!button) return;
      const dealer = selectedDealer;
      selectGame(button.dataset.dossierGame);
      if (dealer) renderDealerDossier(currentData(), dealer);
    });

    renderGame();
    buildPaceQuickNav();
    let resizePending = false;
    function resizeCharts() {
      if (resizePending) return;
      resizePending = true;
      requestAnimationFrame(() => {
        allCharts.forEach(chart => chart.resize());
        resizePending = false;
      });
    }
    window.addEventListener('resize', resizeCharts);
    if ('ResizeObserver' in window) {
      const layoutObserver = new ResizeObserver(resizeCharts);
      layoutObserver.observe(document.querySelector('main'));
    }
  </script>
</body>
</html>"""


def build_dashboard():
    # Ensure JSONL exists; bootstrap from legacy JSON if needed
    _ensure_jsonl()

    # Read JSONL via Polars scan_ndjson (lazy/streaming)
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"JSONL telemetry feed not found: {DATA_FILE}. "
                                 "Generate it via the ingest pipeline first.")

    lazy_df = pl.scan_ndjson(DATA_FILE, infer_schema_length=None)
    df = lazy_df.collect()

    # Aggregate all metrics in Python using Polars
    payload = _aggregate(df)
    payload["rows"] = _forensics_rows(df)

    # Render HTML with pre-computed payload
    template = TEMPLATE_START

    # Inject game buttons from game_order
    game_order = payload.get("game_order", [])
    game_buttons = []
    for gt in game_order:
        game_buttons.append(
            f'<button type="button" data-game-type="{html.escape(gt, quote=True)}">'
            f'{html.escape(gt)}</button>'
        )
    game_buttons_html = "\n".join(game_buttons)

    # Populate KPIs for the initially selected game
    initial_game = game_order[0] if game_order else None
    kpi_html = ""
    if initial_game and initial_game in payload.get("games", {}):
        g = payload["games"][initial_game]
        kpis = g.get("kpis", {})
        kpi_tiles = []
        if "globalAvg" in kpis:
            kpi_tiles.append(
                f'<div class="card kpi"><label>Global Average Pace</label>'
                f'<strong>{_r2(kpis["globalAvg"])} s</strong>'
                f'<span class="sub">{initial_game} only</span></div>'
            )
        if "gameBaseline" in kpis:
            kpi_tiles.append(
                f'<div class="card kpi"><label>Selected Game Baseline</label>'
                f'<strong>{_r2(kpis["gameBaseline"])} s</strong>'
                f'<span class="sub">Average dealer time for this game</span></div>'
            )
        if "stdBaseline" in kpis:
            kpi_tiles.append(
                f'<div class="card kpi"><label>Average Std Dev</label>'
                f'<strong>{_r2(kpis["stdBaseline"])} s</strong>'
                f'<span class="sub">Consistency baseline for this game</span></div>'
            )
        if "dealerCount" in kpis and "tableCount" in kpis:
            kpi_tiles.append(
                f'<div class="card kpi"><label>Active Fleet</label>'
                f'<strong>{kpis["dealerCount"]} / {kpis["tableCount"]}</strong>'
                f'<span class="sub">{kpis["dealerCount"]} dealers · {kpis["tableCount"]} games</span></div>'
            )
        kpi_html = "".join(kpi_tiles)

    # Replace __PAYLOAD__ placeholder
    html_output = template.replace(
        "__PAYLOAD__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"),
    )
    html_output = html_output.replace(
        '<div id="gameTags" class="game-tags" style="display: flex; flex-wrap: wrap; gap: 6px;"></div>',
        '<div id="gameTags" class="game-tags" style="display: flex; flex-wrap: wrap; gap: 6px;">'
        + game_buttons_html
        + '</div>',
    )

    # Write output
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as output:
        output.write(html_output)
    print(f"Generated {OUT_FILE} ({len(html_output):,} characters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_dashboard())
