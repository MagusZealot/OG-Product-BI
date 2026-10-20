#!/usr/bin/env python3
"""
Round Dealer & Table Time Ingest — unified dashboard with both dealer and table data.

Fetches daily snapshot CSVs for both dealers and tables, caches them locally,
and aggregates them into a single JSON payload that powers the unified dashboard.

CSV formats (verified 2026-10-12):
  Dealers: BILLING_DATE, GAME_TYPE, DEALER, AVG_TIMEDIFF, STD_TIMEDIFF
  Tables: BILLING_DATE, GAME_TYPE, TABLE, AVG_TIMEDIFF, STD_TIMEDIFF

Key design:
  - Unified composite key: (billing_date, game_type) 
  - Two data sources joined: dealer data (actual/expected/std for dealers)
    and table data (actual/expected/std for tables)
  - STD_TIMEDIFF preserved as std_actual_duration for both dealers and tables
  - Per-dealer and per-table trajectories tracked across dates and game types
"""

from pathlib import Path
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

WORKSPACE = Path(WORKSPACE)
DEALER_CACHE_DIR = WORKSPACE / "data" / "round_dealer_time"
TABLE_CACHE_DIR = WORKSPACE / "data" / "round_table_time"
REPORT_DIR = WORKSPACE / "output"
DEALER_MANIFEST_FILE = DEALER_CACHE_DIR / "_manifest.json"
TABLE_MANIFEST_FILE = TABLE_CACHE_DIR / "_manifest.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
DEALER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TABLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEALER_BASE_URL = "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_round_dealer_time_daily_{}.csv"
TABLE_BASE_URL = "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_round_table_time_daily_{}.csv"
OUT_FILE = REPORT_DIR / "round_dealer_table_time_data.json"

START_DATE = date(2025, 1, 1)
TODAY = date.today()

LATEST_PROBE_BACK_DAYS = 14
FETCH_TIMEOUT = 45
FETCH_RETRIES = 3

def update_progress(stage, message, progress=None, details=None):
    data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stage': stage,
        'message': message,
        'progress': progress,
        'details': details or {}
    }
    try:
        with open(REPORT_DIR / "progress.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass

def dealer_url_for(d):
    return DEALER_BASE_URL.format(d.strftime("%Y%m%d"))

def table_url_for(d):
    return TABLE_BASE_URL.format(d.strftime("%Y%m%d"))

def dealer_cache_path(d):
    return DEALER_CACHE_DIR / f"mnt_round_dealer_time_daily_{d.strftime('%Y%m%d')}.csv"

def table_cache_path(d):
    return TABLE_CACHE_DIR / f"mnt_round_table_time_daily_{d.strftime('%Y%m%d')}.csv"

def fetch_dealer_snapshot(d, force=False):
    """Download one daily snapshot CSV for dealers into the cache. Returns True when a
    non-empty file is present afterwards, False when the source has no file for that date (404)."""
    path = dealer_cache_path(d)
    if path.exists() and path.stat().st_size > 0 and not force:
        return True

    last_err = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(dealer_url_for(d), timeout=FETCH_TIMEOUT) as resp:
                body = resp.read()
            if not body:
                return False
            tmp = path.with_suffix(".csv.part")
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, path)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            last_err = e
        except Exception as e:
            last_err = e
        if attempt < FETCH_RETRIES:
            import time
            time.sleep(1.5 * attempt)

    print(f"    [WARN] Dealer {d.isoformat()} fetch failed after {FETCH_RETRIES} tries: {last_err}")
    return False

def fetch_table_snapshot(d, force=False):
    """Download one daily snapshot CSV for tables into the cache. Returns True when a
    non-empty file is present afterwards, False when the source has no file for that date (404)."""
    path = table_cache_path(d)
    if path.exists() and path.stat().st_size > 0 and not force:
        return True

    last_err = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(table_url_for(d), timeout=FETCH_TIMEOUT) as resp:
                body = resp.read()
            if not body:
                return False
            tmp = path.with_suffix(".csv.part")
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, path)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            last_err = e
        except Exception as e:
            last_err = e
        if attempt < FETCH_RETRIES:
            import time
            time.sleep(1.5 * attempt)

    print(f"    [WARN] Table {d.isoformat()} fetch failed after {FETCH_RETRIES} tries: {last_err}")
    return False

def load_dealer_manifest():
    if DEALER_MANIFEST_FILE.exists():
        try:
            with open(DEALER_MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {"scanned_through": None, "missing": [], "first_file_date": None, "last_file_date": None}

def load_table_manifest():
    if TABLE_MANIFEST_FILE.exists():
        try:
            with open(TABLE_MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {"scanned_through": None, "missing": [], "first_file_date": None, "last_file_date": None}

def save_dealer_manifest(m):
    try:
        with open(DEALER_MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
    except OSError:
        pass

def save_table_manifest(m):
    try:
        with open(TABLE_MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
    except OSError:
        pass

def discover_latest_file_date():
    """The newest published snapshot. Files for a given business date appear on
    that date, so probe backwards from today until one is found."""
    for back in range(0, LATEST_PROBE_BACK_DAYS + 1):
        d = TODAY - timedelta(days=back)
        if fetch_dealer_snapshot(d) and fetch_table_snapshot(d):
            return d
    return None

def to_float(raw):
    """Numeric string -> float; None on missing/non-numeric."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def parse_dealer_snapshot(path):
    """Parse a cached dealer snapshot CSV into normalized row dicts.
    
    CSV format verified 2026-10-12:
      BILLING_DATE, GAME_TYPE, DEALER, AVG_TIMEDIFF, STD_TIMEDIFF
    """
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for raw in csv.DictReader(f):
            bd = (raw.get("BILLING_DATE") or raw.get("billing_date") or "").strip()
            gt = (raw.get("GAME_TYPE") or raw.get("game_type") or "").strip()
            ds = (raw.get("DEALER") or raw.get("dealer") or "").strip()
            av = to_float(raw.get("AVG_TIMEDIFF") or raw.get("avg_time_diff") or "")
            sv = to_float(raw.get("STD_TIMEDIFF") or raw.get("std_time_diff") or "")
            if not bd or not gt or not ds:
                continue
            row = {
                "date": bd,
                "game_type": gt,
                "source": "dealer",
                "entity_id": ds,
                "entity_name": ds,
                "actual_duration": av,        # AVG_TIMEDIFF = actual mean round duration
                "std_actual_duration": sv,    # STD_TIMEDIFF = standard deviation of round durations
                "updated_at": (raw.get("updated_at") or "").strip(),
            }
            # Calculate duration_delta for compatibility
            row["duration_delta"] = (
                round(row["actual_duration"] - row["std_actual_duration"], 4)
                if row["actual_duration"] is not None and row["std_actual_duration"] is not None
                else None
            )
            rows.append(row)
    return rows

def parse_table_snapshot(path):
    """Parse a cached table snapshot CSV into normalized row dicts.
    
    CSV format verified 2026-10-12:
      BILLING_DATE, GAME_TYPE, TABLE_NO, AVG_TIMEDIFF, STD_TIMEDIFF
    """
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for raw in csv.DictReader(f):
            bd = (raw.get("BILLING_DATE") or raw.get("billing_date") or "").strip()
            gt = (raw.get("GAME_TYPE") or raw.get("game_type") or "").strip()
            tb = (raw.get("TABLE_NO") or raw.get("table_no") or raw.get("TABLE") or raw.get("table") or "").strip()
            av = to_float(raw.get("AVG_TIMEDIFF") or raw.get("avg_time_diff") or "")
            sv = to_float(raw.get("STD_TIMEDIFF") or raw.get("std_time_diff") or "")
            if not bd or not gt or not tb:
                continue
            row = {
                "date": bd,
                "game_type": gt,
                "source": "table",
                "entity_id": tb,
                "entity_name": tb,
                "actual_duration": av,
                "std_actual_duration": sv,
                "updated_at": (raw.get("updated_at") or "").strip(),
            }
            rows.append(row)
    return rows

def mean(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)

def median(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    if n % 2:
        return round(vals[mid], 4)
    return round((vals[mid - 1] + vals[mid]) / 2.0, 4)

def rnd(v, digits=2):
    return None if v is None else round(v, digits)

# ---------------------------------------------------------------------------
# Unified trajectory builder for both dealers and tables
# ---------------------------------------------------------------------------

def build_unified_trajectories(records):
    """Build per-entity trajectory across all dates and game types.
    
    Returns:
      entity_entries: dict entity_id -> list of {date, game_type, source, actual_duration, expected_duration, std_actual_duration, duration_delta, is_breach}
    """
    entity_game_keys = defaultdict(list)
    for r in records:
        entity_game_keys[(r["entity_id"], r["game_type"])].append(r)

    entity_entries = defaultdict(list)

    for (entity_id, game_type), sublist in entity_game_keys.items():
        sublist.sort(key=lambda r: r["date"])
        for r in sublist:
            entity_entries[r["entity_id"]].append({
                "date": r["date"],
                "game_type": game_type,
                "source": r["source"],
                "actual_duration": rnd(r["actual_duration"]),
                "expected_duration": rnd(r.get("expected_duration")),
                "std_actual_duration": rnd(r["std_actual_duration"]),
                "duration_delta": rnd(r.get("duration_delta")),
                "is_breach": r.get("is_breach", False),
            })

    for entity_id, entries in entity_entries.items():
        entries.sort(key=lambda e: (e["date"], e["game_type"]))
        for i in range(1, len(entries)):
            prev = entries[i - 1]
            cur = entries[i]
            if cur["actual_duration"] is not None and prev["actual_duration"] is not None:
                cur["cross_entity_delta"] = rnd(cur["actual_duration"] - prev["actual_duration"], 4)
            else:
                cur["cross_entity_delta"] = None

    return dict(entity_entries)

def build_unified_data_quality(rows, dates, game_types, meta):
    """Surface the source-feed quirks the unified dashboard must disclose."""
    # Separate dealers and tables for data quality analysis
    dealer_rows = [r for r in rows if r["source"] == "dealer"]
    table_rows = [r for r in rows if r["source"] == "table"]
    
    alias_groups = defaultdict(set)
    for gt in game_types:
        alias_groups[gt.upper()].add(gt)
    duplicate_feeds = []
    for up, variants in sorted(alias_groups.items()):
        if len(variants) < 2:
            continue
        detail = {}
        for v in sorted(variants):
            # Check both dealer and table data for this game type
            sub_dealers = [r for r in dealer_rows if r["game_type"] == v]
            sub_tables = [r for r in table_rows if r["game_type"] == v]
            detail[v] = {
                "dealer_rows": len(sub_dealers),
                "table_rows": len(sub_tables),
                "dealer_days": len({r["date"] for r in sub_dealers}),
                "table_days": len({r["date"] for r in sub_tables}),
                "dealer_first_date": min(r["date"] for r in sub_dealers) if sub_dealers else None,
                "dealer_last_date": max(r["date"] for r in sub_dealers) if sub_dealers else None,
                "table_first_date": min(r["date"] for r in sub_tables) if sub_tables else None,
                "table_last_date": max(r["date"] for r in sub_tables) if sub_tables else None,
                "dealer_null_actual": sum(1 for r in sub_dealers if r["actual_duration"] is None),
                "dealer_null_std": sum(1 for r in sub_dealers if r["std_actual_duration"] is None),
                "table_null_actual": sum(1 for r in sub_tables if r["actual_duration"] is None),
                "table_null_std": sum(1 for r in sub_tables if r["std_actual_duration"] is None),
            }
        duplicate_feeds.append({
            "normalized": up,
            "variants": detail,
            "note": "Same entity-game combos published under two spellings; both retained.",
        })

    coverage = []
    total_days = len(dates)
    for gt in game_types:
        sub_days = {r["date"] for r in rows if r["game_type"] == gt}
        first, last = min(sub_days), max(sub_days)
        span = (date.fromisoformat(last) - date.fromisoformat(first)).days + 1
        coverage.append({
            "game_type": gt,
            "days_present": len(sub_days),
            "days_in_span": span,
            "coverage_pct": round(len(sub_days) / span * 100, 1) if span else 0.0,
            "first_date": first,
            "last_date": last,
            "partial": len(sub_days) < total_days,
        })
    coverage.sort(key=lambda c: c["coverage_pct"])

    null_fields = {}
    for field in ("actual_duration", "std_actual_duration"):
        n = sum(1 for r in rows if r[field] is None)
        null_fields[field] = {"rows": n, "pct": round(n / len(rows) * 100, 2) if rows else 0.0}

    return {
        "duplicate_feeds": duplicate_feeds,
        "coverage": coverage,
        "null_fields": null_fields,
    }

def build_unified_payload(records, meta_extra):
    """Aggregate the deduplicated record set into the unified dashboard payload."""
    by_key = {}
    for r in records:
        k = (r["date"], r["game_type"], r["entity_id"], r["source"])
        prev = by_key.get(k)
        if prev is None or r.get("updated_at", "") > prev.get("updated_at", ""):
            by_key[k] = r
    rows = list(by_key.values())
    rows.sort(key=lambda r: (r["date"], r["game_type"], r["entity_id"], r["source"]))

    dates = sorted({r["date"] for r in rows})
    game_types = sorted({r["game_type"] for r in rows})
    dealers = sorted({r["entity_id"] for r in rows if r["source"] == "dealer"})
    tables = sorted({r["entity_id"] for r in rows if r["source"] == "table"})

    # Compute benchmarks per game type
    game_benchmarks = {}
    for gt in game_types:
        sub_act = [r["actual_duration"] for r in rows if r["game_type"] == gt and r["actual_duration"] is not None]
        sub_std = [r["std_actual_duration"] for r in rows if r["game_type"] == gt and r["std_actual_duration"] is not None]
        m_act = mean(sub_act) or 0.0
        m_std = mean(sub_std) or 0.0
        thresh = round(m_act + m_std, 4)
        game_benchmarks[gt] = {
            "expected_duration": m_act,
            "expected_std": m_std,
            "threshold": thresh,
        }

    # Tag rows with expected duration, threshold, delta, and breach
    for r in rows:
        bm = game_benchmarks.get(r["game_type"], {"expected_duration": 0.0, "threshold": 9999.0})
        r["expected_duration"] = bm["expected_duration"]
        r["threshold"] = bm["threshold"]
        r["duration_delta"] = (
            round(r["actual_duration"] - bm["expected_duration"], 4)
            if r["actual_duration"] is not None
            else None
        )
        r["is_breach"] = (
            r["actual_duration"] > bm["threshold"]
            if r["actual_duration"] is not None
            else False
        )

    # Build per-entity trajectories using deduplicated rows
    entity_entries = build_unified_trajectories(rows)

    meta_extra["unique_keys"] = len(rows)

    # Per-game summaries (combined dealer+table data)
    gt_summary = []
    for gt in game_types:
        sub = [r for r in rows if r["game_type"] == gt]
        sub_dates = sorted({r["date"] for r in sub})
        adur = [r["actual_duration"] for r in sub if r["actual_duration"] is not None]
        sdur = [r["std_actual_duration"] for r in sub if r["std_actual_duration"] is not None]
        deltas = [r["duration_delta"] for r in sub if r["duration_delta"] is not None]
        breaches = sum(1 for r in sub if r["is_breach"])
        bm = game_benchmarks[gt]

        entity_stats = []
        for eid in {r["entity_id"] for r in sub}:
            e_sub = [r for r in sub if r["entity_id"] == eid]
            e_adur = [r["actual_duration"] for r in e_sub if r["actual_duration"] is not None]
            e_sdur = [r["std_actual_duration"] for r in e_sub if r["std_actual_duration"] is not None]
            e_breaches = sum(1 for r in e_sub if r["is_breach"])
            src = e_sub[0]["source"]
            entity_stats.append({
                "entity_id": eid,
                "source": src,
                "mean_actual": rnd(mean(e_adur)),
                "mean_expected": bm["expected_duration"],
                "mean_std": rnd(mean(e_sdur)),
                "breach_pct": rnd(e_breaches / len(e_sub) * 100, 2) if e_sub else 0.0,
                "rows": len(e_sub),
            })
        entity_stats.sort(key=lambda e: (e["mean_actual"] or 0), reverse=True)
        top_dealers = [e for e in entity_stats if e["source"] == "dealer"][:5]
        top_tables = [e for e in entity_stats if e["source"] == "table"][:5]

        gt_summary.append({
            "game_type": gt,
            "rows": len(sub),
            "days": len(sub_dates),
            "first_date": sub_dates[0] if sub_dates else None,
            "last_date": sub_dates[-1] if sub_dates else None,
            "dealers": len({r["entity_id"] for r in sub if r["source"] == "dealer"}),
            "tables": len({r["entity_id"] for r in sub if r["source"] == "table"}),
            "mean_actual_duration": mean(adur),
            "mean_expected_duration": bm["expected_duration"],
            "mean_std_duration": mean(sdur),
            "mean_duration_delta": mean(deltas),
            "threshold": bm["threshold"],
            "breaches": breaches,
            "breach_pct": round(breaches / len(sub) * 100, 2) if sub else 0.0,
            "top_entities": entity_stats[:10],
            "top_dealers": top_dealers,
            "top_tables": top_tables,
        })
    gt_summary.sort(key=lambda g: (-g["rows"], g["game_type"]))

    # Per-dealer summaries
    dealer_summaries = []
    for dealer_id in dealers:
        d_entries = entity_entries.get(dealer_id, [])
        if not d_entries:
            continue
        all_adur = [e["actual_duration"] for e in d_entries if e["actual_duration"] is not None]
        all_edur = [e["expected_duration"] for e in d_entries if e["expected_duration"] is not None]
        all_sdur = [e["std_actual_duration"] for e in d_entries if e["std_actual_duration"] is not None]
        total_breaches = sum(1 for e in d_entries if e["is_breach"])
        trend = (
            round(d_entries[-1]["actual_duration"] - d_entries[0]["actual_duration"], 4)
            if len(d_entries) > 1 and d_entries[0]["actual_duration"] is not None and d_entries[-1]["actual_duration"] is not None
            else None
        )
        dealer_summaries.append({
            "dealer_id": dealer_id,
            "source": "dealer",
            "total_rows": len(d_entries),
            "date_range": f"{d_entries[0]['date']} – {d_entries[-1]['date']}",
            "games_count": len({e["game_type"] for e in d_entries}),
            "mean_actual_duration": mean(all_adur),
            "mean_expected_duration": mean(all_edur),
            "mean_std_duration": mean(all_sdur),
            "total_breaches": total_breaches,
            "breach_pct": round(total_breaches / len(d_entries) * 100, 2) if d_entries else 0.0,
            "recent_trend": trend,
        })
    dealer_summaries.sort(key=lambda d: (d["mean_actual_duration"] or 0), reverse=True)

    # Per-table summaries
    table_summaries = []
    for table_id in tables:
        t_entries = entity_entries.get(table_id, [])
        if not t_entries:
            continue
        all_adur = [e["actual_duration"] for e in t_entries if e["actual_duration"] is not None]
        all_edur = [e["expected_duration"] for e in t_entries if e["expected_duration"] is not None]
        all_sdur = [e["std_actual_duration"] for e in t_entries if e["std_actual_duration"] is not None]
        total_breaches = sum(1 for e in t_entries if e["is_breach"])
        trend = (
            round(t_entries[-1]["actual_duration"] - t_entries[0]["actual_duration"], 4)
            if len(t_entries) > 1 and t_entries[0]["actual_duration"] is not None and t_entries[-1]["actual_duration"] is not None
            else None
        )
        table_summaries.append({
            "table_id": table_id,
            "source": "table",
            "total_rows": len(t_entries),
            "date_range": f"{t_entries[0]['date']} – {t_entries[-1]['date']}",
            "games_count": len({e["game_type"] for e in t_entries}),
            "mean_actual_duration": mean(all_adur),
            "mean_expected_duration": mean(all_edur),
            "mean_std_duration": mean(all_sdur),
            "total_breaches": total_breaches,
            "breach_pct": round(total_breaches / len(t_entries) * 100, 2) if t_entries else 0.0,
            "recent_trend": trend,
        })
    table_summaries.sort(key=lambda t: (t["mean_actual_duration"] or 0), reverse=True)

    # Combined entity list for selector
    combined_entities = []
    for d in dealer_summaries:
        combined_entities.append({
            "entity_id": d["dealer_id"],
            "source": "dealer",
            "total_rows": d["total_rows"],
            "games_count": d["games_count"],
            "mean_actual_duration": d["mean_actual_duration"],
            "mean_expected_duration": d["mean_expected_duration"],
            "mean_std_duration": d["mean_std_duration"],
            "breach_pct": d["breach_pct"],
        })
    for t in table_summaries:
        combined_entities.append({
            "entity_id": t["table_id"],
            "source": "table",
            "total_rows": t["total_rows"],
            "games_count": t["games_count"],
            "mean_actual_duration": t["mean_actual_duration"],
            "mean_expected_duration": t["mean_expected_duration"],
            "mean_std_duration": t["mean_std_duration"],
            "breach_pct": t["breach_pct"],
        })

    # Variance Matrix (Speed vs Consistency quadrant data)
    variance_matrix = [
        {
            "name": e["entity_id"],
            "source": e["source"],
            "speed": rnd(e["mean_actual_duration"]),
            "consistency": rnd(e["mean_std_duration"]),
            "expected": rnd(e["mean_expected_duration"]),
            "breach": e["breach_pct"],
            "rows": e["total_rows"],
        }
        for e in combined_entities
        if e["mean_actual_duration"] is not None and e["mean_std_duration"] is not None
    ]

    # Environment vs Personnel Scatter Data (Table AVG vs Dealer AVG per date & game)
    environment_scatter = []
    for d in dates:
        day_rows = [r for r in rows if r["date"] == d]
        for gt in game_types:
            d_sub = [r["actual_duration"] for r in day_rows if r["game_type"] == gt and r["source"] == "dealer" and r["actual_duration"] is not None]
            t_sub = [r["actual_duration"] for r in day_rows if r["game_type"] == gt and r["source"] == "table" and r["actual_duration"] is not None]
            if d_sub and t_sub:
                d_m = mean(d_sub)
                t_m = mean(t_sub)
                environment_scatter.append({
                    "date": d,
                    "game_type": gt,
                    "table_avg": rnd(t_m),
                    "dealer_avg": rnd(d_m),
                    "gap": rnd(d_m - t_m),
                })

    # Series data per game type (for charts)
    series_duration = {gt: [] for gt in game_types}
    series_expected_duration = {gt: [] for gt in game_types}
    series_breach = {gt: [] for gt in game_types}
    daily = []

    for d in dates:
        day_rows = [r for r in rows if r["date"] == d]
        day_actuals = [r["actual_duration"] for r in day_rows if r["actual_duration"] is not None]
        day_expecteds = [r["expected_duration"] for r in day_rows if r["expected_duration"] is not None]
        day_stds = [r["std_actual_duration"] for r in day_rows if r["std_actual_duration"] is not None]
        day_deltas = [r["duration_delta"] for r in day_rows if r["duration_delta"] is not None]
        day_breaches = sum(1 for r in day_rows if r["is_breach"])

        d_acts = [r["actual_duration"] for r in day_rows if r["source"] == "dealer" and r["actual_duration"] is not None]
        t_acts = [r["actual_duration"] for r in day_rows if r["source"] == "table" and r["actual_duration"] is not None]

        entry = {
            "date": d,
            "samples": len(day_rows),
            "breaches": day_breaches,
            "mean_actual_duration": mean(day_actuals),
            "dealer_mean_actual": mean(d_acts),
            "table_mean_actual": mean(t_acts),
            "mean_expected_duration": mean(day_expecteds),
            "mean_std_duration": mean(day_stds),
            "mean_duration_delta": mean(day_deltas),
            "breach_pct": round(day_breaches / len(day_rows) * 100, 2) if day_rows else 0.0,
        }
        daily.append(entry)

        for gt in game_types:
            gt_day = [r for r in day_rows if r["game_type"] == gt]
            if not gt_day:
                continue
            series_duration[gt].append([d, mean([r["actual_duration"] for r in gt_day])])
            series_expected_duration[gt].append([d, mean([r["expected_duration"] for r in gt_day])])
            series_breach[gt].append([d, round(sum(1 for r in gt_day if r["is_breach"]) / len(gt_day) * 100, 2) if gt_day else 0.0])

    latest_date = dates[-1] if dates else None
    latest_rows = []
    if latest_date:
        for r in sorted([r for r in rows if r["date"] == latest_date], key=lambda r: (r["game_type"], r["entity_id"], r["source"])):
            latest_rows.append({
                "game_type": r["game_type"],
                "entity": r["entity_id"],
                "source": r["source"],
                "actual_duration": rnd(r["actual_duration"]),
                "expected_duration": rnd(r["expected_duration"]),
                "std_actual_duration": rnd(r["std_actual_duration"]),
                "duration_delta": rnd(r["duration_delta"]),
                "threshold": rnd(r["threshold"]),
                "is_breach": r["is_breach"],
            })

    data_quality = build_unified_data_quality(rows, dates, game_types, meta_extra)

    payload = {
        "meta": meta_extra,
        "game_types": gt_summary,
        "dealers": dealer_summaries,
        "tables": table_summaries,
        "series_duration": series_duration,
        "series_expected_duration": series_expected_duration,
        "series_breach": series_breach,
        "daily": daily,
        "latest_day": {"billing_date": latest_date, "rows": latest_rows},
        "entity_entries": entity_entries,
        "data_quality": data_quality,
        "missing_dates": meta_extra.get("files_missing", []),
        "combined_entities": combined_entities,
        "variance_matrix": variance_matrix,
        "environment_scatter": environment_scatter,
    }
    return payload

def main():
    update_progress("round_dealer_table_time", "Locating newest published snapshot", 2)

    dealer_manifest = load_dealer_manifest()
    table_manifest = load_table_manifest()

    scan_start = START_DATE
    if dealer_manifest.get("first_file_date"):
        scan_start = date.fromisoformat(dealer_manifest["first_file_date"])
    if table_manifest.get("first_file_date"):
        scan_start = min(scan_start, date.fromisoformat(table_manifest["first_file_date"]))

    latest = discover_latest_file_date()
    if latest is None:
        print("[FAIL] No published snapshot found within the probe window.")
        return 1

    print(f"Snapshot range: {scan_start.isoformat()} -> {latest.isoformat()}")
    update_progress("round_dealer_table_time", f"Fetching snapshots {scan_start.isoformat()} .. {latest.isoformat()}", 5)

    # Fetch both dealer and table snapshots
    dealer_available, table_available = [], []
    dealer_missing, table_missing = [], []
    dealer_fetched, table_fetched = 0, 0
    dealer_reused, table_reused = 0, 0
    d = scan_start
    total_days = (latest - scan_start).days + 1
    idx = 0
    while d <= latest:
        dealer_was_cached = dealer_cache_path(d).exists() and dealer_cache_path(d).stat().st_size > 0
        dealer_ok = fetch_dealer_snapshot(d)
        table_was_cached = table_cache_path(d).exists() and table_cache_path(d).stat().st_size > 0
        table_ok = fetch_table_snapshot(d)
        
        if dealer_ok:
            dealer_available.append(d)
            if dealer_was_cached:
                dealer_reused += 1
            else:
                dealer_fetched += 1
        else:
            dealer_missing.append(d.isoformat())
            
        if table_ok:
            table_available.append(d)
            if table_was_cached:
                table_reused += 1
            else:
                table_fetched += 1
        else:
            table_missing.append(d.isoformat())
        
        idx += 1
        if idx % 50 == 0 or idx == total_days:
            update_progress(
                "round_dealer_table_time",
                f"Fetched {idx}/{total_days} snapshot days ({dealer_fetched} new dealer, {dealer_reused} cached dealer, {table_fetched} new table, {table_reused} cached table)",
                round(5 + (idx / total_days) * 65, 1),
                {"dealer_fetched": dealer_fetched, "dealer_cached": dealer_reused, "dealer_missing": len(dealer_missing),
                 "table_fetched": table_fetched, "table_cached": table_reused, "table_missing": len(table_missing)},
            )
        d += timedelta(days=1)

    if not dealer_available or not table_available:
        print("[FAIL] No snapshots could be retrieved for both dealer and table data.")
        return 1

    # Use the more recent date for manifest tracking
    dealer_first_file_date = dealer_manifest.get("first_file_date") or dealer_available[0].isoformat()
    table_first_file_date = table_manifest.get("first_file_date") or table_available[0].isoformat()
    
    # Update manifests
    save_dealer_manifest({
        "scanned_through": latest.isoformat(),
        "missing": dealer_missing,
        "first_file_date": dealer_first_file_date,
        "last_file_date": latest.isoformat(),
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_table_manifest({
        "scanned_through": latest.isoformat(),
        "missing": table_missing,
        "first_file_date": table_first_file_date,
        "last_file_date": latest.isoformat(),
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    update_progress("round_dealer_table_time", "Parsing and aggregating snapshots", 75)
    print(f"Parsing {len(dealer_available)} dealer snapshots ({dealer_fetched} newly fetched, {dealer_reused} from cache)...")
    print(f"Parsing {len(table_available)} table snapshots ({table_fetched} newly fetched, {table_reused} from cache)...")

    dealer_records = []
    table_records = []
    for i, d in enumerate(dealer_available):
        dealer_records.extend(parse_dealer_snapshot(dealer_cache_path(d)))
        if (i + 1) % 100 == 0:
            update_progress("round_dealer_table_time", f"Parsed {i + 1}/{len(dealer_available)} dealer snapshots", round(75 + (i / len(dealer_available)) * 15, 1))
    
    for i, d in enumerate(table_available):
        table_records.extend(parse_table_snapshot(table_cache_path(d)))
        if (i + 1) % 100 == 0:
            update_progress("round_dealer_table_time", f"Parsed {i + 1}/{len(table_available)} table snapshots", round(75 + (i / len(table_available)) * 15, 1))

    all_records = dealer_records + table_records

    unique_dates = sorted({r["date"] for r in all_records})
    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generator": "round_dealer_table_time_ingest.py",
        "source_urls": {
            "dealer": "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_round_dealer_time_daily_YYYYMMDD.csv",
            "table": "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_round_table_time_daily_YYYYMMDD.csv",
        },
        "cache_dirs": {
            "dealer": "data/round_dealer_time",
            "table": "data/round_table_time",
        },
        "latest_file_date": latest.isoformat(),
        "first_file_date": scan_start.isoformat(),
        "dealer_files_available": len(dealer_available),
        "dealer_files_fetched_now": dealer_fetched,
        "dealer_files_reused_cache": dealer_reused,
        "dealer_files_missing_count": len(dealer_missing),
        "dealer_files_missing": dealer_missing,
        "table_files_available": len(table_available),
        "table_files_fetched_now": table_fetched,
        "table_files_reused_cache": table_reused,
        "table_files_missing_count": len(table_missing),
        "table_files_missing": table_missing,
        "billing_date_min": unique_dates[0] if unique_dates else None,
        "billing_date_max": unique_dates[-1] if unique_dates else None,
        "days_with_data": len(unique_dates),
        "rows_raw": len(all_records),
        "game_types": sorted({r["game_type"] for r in all_records}),
        "dealers_tracked": len({r["entity_id"] for r in dealer_records}),
        "tables_tracked": len({r["entity_id"] for r in table_records}),
        "null_duration_rows": sum(1 for r in all_records if r["actual_duration"] is None or r["std_actual_duration"] is None),
        "entity_entries_count": len({r["entity_id"] for r in all_records}),
        "he_significant_delta": 5.0,
        "prob_breach_rule": "actual_duration > threshold (mean + 1 std)",
    }

    payload = build_unified_payload(all_records, meta)
    meta["rows_raw"] = payload["meta"]["unique_keys"]

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT_FILE)
    print("\nRound Dealer & Table Time ingest complete")
    print(f"  dealer snapshots available : {len(dealer_available)}  ({dealer_first_file_date} .. {latest.isoformat()})")
    print(f"  table snapshots available  : {len(table_available)}  ({table_first_file_date} .. {latest.isoformat()})")
    print(f"  gaps after start           : dealer {len(dealer_missing)} | table {len(table_missing)}")
    print(f"  business days             : {len(unique_dates)}")
    print(f"  raw rows (windowed)       : {len(all_records)}")
    print(f"  dealer rows               : {len(dealer_records)}")
    print(f"  table rows                : {len(table_records)}")
    print(f"  unique keys               : {payload['meta']['unique_keys']}")
    print(f"  game types                : {len(meta['game_types'])}")
    print(f"  dealers tracked           : {meta['dealers_tracked']}")
    print(f"  tables tracked            : {meta['tables_tracked']}")
    print(f"  null duration rows        : {meta['null_duration_rows']}")
    print(f"  entity entries            : {meta['entity_entries_count']}")
    print(f"  payload                   : {OUT_FILE.name} ({size:,} bytes)")

    update_progress("round_dealer_table_time", "Aggregation complete", 100, {"payload": OUT_FILE.name, "bytes": size})
    return 0

if __name__ == "__main__":
    sys.exit(main())