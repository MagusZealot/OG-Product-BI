#!/usr/bin/env python3
"""
Round Table Time Ingest.

Fetches the daily snapshot CSVs published at
    https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_round_table_time_daily_YYYYMMDD.csv
caches them locally, and aggregates them into a single JSON payload that powers
the standalone Round Table Time dashboard.

CSV format (verified 2026-10-12):
  BILLING_DATE, GAME_TYPE, TABLE, AVG_TIMEDIFF, STD_TIMEDIFF

Key design:
  - Each row = one table + game_type combination for one billing date
  - (billing_date, game_type, table) is unique inside a file, and overlapping
    keys across files are republished with identical metrics (idempotent union).
  - AVG_TIMEDIFF = average round duration (hours) for that table on that date/game
  - STD_TIMEDIFF = standard deviation of round durations
  - New: per-table trajectory tracked across dates and game types
"""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent.parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break


import csv
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(WORKSPACE)
CACHE_DIR = WORKSPACE / "data" / "round_table_time"
REPORT_DIR = WORKSPACE / "output"
MANIFEST_FILE = CACHE_DIR / "_manifest.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_round_table_time_daily_{}.csv"
OUT_FILE = REPORT_DIR / "round_table_time_data.json"

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


def _url_for(d):
    return BASE_URL.format(d.strftime("%Y%m%d"))


def _cache_path(d):
    return CACHE_DIR / f"mnt_round_table_time_daily_{d.strftime('%Y%m%d')}.csv"


def fetch_snapshot(d, force=False):
    """Download one daily snapshot CSV into the cache. Returns True when a
    non-empty file is present afterwards, False when the source has no file
    for that date (404)."""
    path = _cache_path(d)
    if path.exists() and path.stat().st_size > 0 and not force:
        return True

    last_err = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(_url_for(d), timeout=FETCH_TIMEOUT) as resp:
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

    print(f"    [WARN] {d.isoformat()} fetch failed after {FETCH_RETRIES} tries: {last_err}")
    return False


def load_manifest():
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    return {"scanned_through": None, "missing": [], "first_file_date": None, "last_file_date": None}


def save_manifest(m):
    try:
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
    except OSError:
        pass


def discover_latest_file_date():
    """The newest published snapshot. Files for a given business date appear on
    that date, so probe backwards from today until one is found."""
    for back in range(0, LATEST_PROBE_BACK_DAYS + 1):
        d = TODAY - timedelta(days=back)
        if fetch_snapshot(d):
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


def parse_snapshot(path):
    """Parse a cached snapshot CSV into normalized row dicts.
    
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
            rows.append({
                "date": bd,
                "game_type": gt,
                "table": tb,
                "actual_duration": av,        # AVG_TIMEDIFF = actual mean round duration
                "std_actual_duration": sv,    # STD_TIMEDIFF = standard deviation of round durations
                "updated_at": (raw.get("updated_at") or "").strip(),
            })
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
# Per-table trajectory builder
# ---------------------------------------------------------------------------
def build_table_trajectories(records):
    """Build per-table trajectory across all dates and game types.
    
    Returns:
      table_entries: dict table_id -> list of {date, game_type, actual_duration, expected_duration, std_actual_duration, duration_delta, is_breach}
      game_table_map: dict game_type -> dict table_id -> [records...]
    """
    table_game_keys = defaultdict(list)
    for r in records:
        table_game_keys[(r["table"], r["game_type"])].append(r)

    table_entries = defaultdict(list)
    game_table_map = defaultdict(lambda: defaultdict(list))

    for (table, game_type), sublist in table_game_keys.items():
        sublist.sort(key=lambda r: r["date"])
        for r in sublist:
            table_entries[table].append({
                "date": r["date"],
                "game_type": game_type,
                "actual_duration": rnd(r["actual_duration"]),
                "expected_duration": rnd(r.get("expected_duration")),
                "std_actual_duration": rnd(r["std_actual_duration"]),
                "duration_delta": rnd(r.get("duration_delta")),
                "is_breach": r.get("is_breach", False),
            })

    for table_id, entries in table_entries.items():
        entries.sort(key=lambda e: (e["date"], e["game_type"]))
        for i in range(1, len(entries)):
            prev = entries[i - 1]
            cur = entries[i]
            if cur["actual_duration"] is not None and prev["actual_duration"] is not None:
                cur["cross_game_delta"] = rnd(cur["actual_duration"] - prev["actual_duration"], 4)
            else:
                cur["cross_game_delta"] = None

    return dict(table_entries)


def build_data_quality(rows, dates, game_types, meta):
    """Surface the source-feed quirks the dashboard must disclose."""
    alias_groups = defaultdict(set)
    for gt in game_types:
        alias_groups[gt.upper()].add(gt)
    duplicate_feeds = []
    for up, variants in sorted(alias_groups.items()):
        if len(variants) < 2:
            continue
        detail = {}
        for v in sorted(variants):
            sub = [r for r in rows if r["game_type"] == v]
            detail[v] = {
                "rows": len(sub),
                "days": len({r["date"] for r in sub}),
                "first_date": min(r["date"] for r in sub),
                "last_date": max(r["date"] for r in sub),
                "null_actual_duration": sum(1 for r in sub if r["actual_duration"] is None),
                "null_std_duration": sum(1 for r in sub if r["std_actual_duration"] is None),
            }
        duplicate_feeds.append({
            "normalized": up,
            "variants": detail,
            "note": "Same table-game combos published under two spellings; both retained.",
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


def build_payload(records, meta_extra):
    """Aggregate the deduplicated record set into the dashboard payload."""
    by_key = {}
    for r in records:
        k = (r["date"], r["game_type"], r["table"])
        prev = by_key.get(k)
        if prev is None or r.get("updated_at", "") > prev.get("updated_at", ""):
            by_key[k] = r
    rows = list(by_key.values())
    rows.sort(key=lambda r: (r["date"], r["game_type"], r["table"]))

    dates = sorted({r["date"] for r in rows})
    game_types = sorted({r["game_type"] for r in rows})
    tables = sorted({r["table"] for r in rows})

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

    # Build per-table trajectories using deduplicated rows
    table_entries = build_table_trajectories(rows)

    meta_extra["unique_keys"] = len(rows)

    # Per-game summaries
    gt_summary = []
    for gt in game_types:
        sub = [r for r in rows if r["game_type"] == gt]
        sub_dates = sorted({r["date"] for r in sub})
        adur = [r["actual_duration"] for r in sub if r["actual_duration"] is not None]
        sdur = [r["std_actual_duration"] for r in sub if r["std_actual_duration"] is not None]
        deltas = [r["duration_delta"] for r in sub if r["duration_delta"] is not None]
        breaches = sum(1 for r in sub if r["is_breach"])
        bm = game_benchmarks[gt]

        table_stats = []
        for tid in {r["table"] for r in sub}:
            t_sub = [r for r in sub if r["table"] == tid]
            t_adur = [r["actual_duration"] for r in t_sub if r["actual_duration"] is not None]
            t_sdur = [r["std_actual_duration"] for r in t_sub if r["std_actual_duration"] is not None]
            t_breaches = sum(1 for r in t_sub if r["is_breach"])
            table_stats.append({
                "table_id": tid,
                "mean_actual": rnd(mean(t_adur)),
                "mean_expected": bm["expected_duration"],
                "mean_std": rnd(mean(t_sdur)),
                "breach_pct": rnd(t_breaches / len(t_sub) * 100, 2) if t_sub else 0.0,
                "rows": len(t_sub),
            })
        table_stats.sort(key=lambda t: (t["mean_actual"] or 0), reverse=True)

        gt_summary.append({
            "game_type": gt,
            "rows": len(sub),
            "days": len(sub_dates),
            "first_date": sub_dates[0] if sub_dates else None,
            "last_date": sub_dates[-1] if sub_dates else None,
            "tables": len({r["table"] for r in sub}),
            "mean_actual_duration": mean(adur),
            "mean_expected_duration": bm["expected_duration"],
            "mean_std_duration": mean(sdur),
            "mean_duration_delta": mean(deltas),
            "threshold": bm["threshold"],
            "breaches": breaches,
            "breach_pct": round(breaches / len(sub) * 100, 2) if sub else 0.0,
            "top_tables": table_stats[:10],
        })
    gt_summary.sort(key=lambda g: (-g["rows"], g["game_type"]))

    # Per-table summaries (across all games)
    table_summaries = []
    for table_id in tables:
        t_entries = table_entries.get(table_id, [])
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

    # Series data per game type
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

        entry = {
            "date": d,
            "samples": len(day_rows),
            "breaches": day_breaches,
            "mean_actual_duration": mean(day_actuals),
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
        for r in sorted([r for r in rows if r["date"] == latest_date], key=lambda r: (r["game_type"], r["table"])):
            latest_rows.append({
                "game_type": r["game_type"],
                "table": r["table"],
                "actual_duration": rnd(r["actual_duration"]),
                "expected_duration": rnd(r["expected_duration"]),
                "std_actual_duration": rnd(r["std_actual_duration"]),
                "duration_delta": rnd(r["duration_delta"]),
                "threshold": rnd(r["threshold"]),
                "is_breach": r["is_breach"],
            })

    data_quality = build_data_quality(rows, dates, game_types, meta_extra)

    payload = {
        "meta": meta_extra,
        "game_types": gt_summary,
        "tables": table_summaries,
        "series_duration": series_duration,
        "series_expected_duration": series_expected_duration,
        "series_breach": series_breach,
        "daily": daily,
        "latest_day": {"billing_date": latest_date, "rows": latest_rows},
        "table_entries": table_entries,
        "data_quality": data_quality,
        "missing_dates": meta_extra.get("files_missing", []),
    }
    return payload


def main():
    update_progress("round_table_time", "Locating newest published snapshot", 2)

    manifest = load_manifest()

    scan_start = START_DATE
    if manifest.get("first_file_date"):
        scan_start = date.fromisoformat(manifest["first_file_date"])

    latest = discover_latest_file_date()
    if latest is None:
        print("[FAIL] No published snapshot found within the probe window.")
        return 1

    print(f"Snapshot range: {scan_start.isoformat()} -> {latest.isoformat()}")
    update_progress("round_table_time", f"Fetching snapshots {scan_start.isoformat()} .. {latest.isoformat()}", 5)

    available, missing, fetched, reused = [], [], 0, 0
    d = scan_start
    total_days = (latest - scan_start).days + 1
    idx = 0
    while d <= latest:
        was_cached = _cache_path(d).exists() and _cache_path(d).stat().st_size > 0
        ok = fetch_snapshot(d)
        if ok:
            available.append(d)
            if was_cached:
                reused += 1
            else:
                fetched += 1
        else:
            missing.append(d.isoformat())
        idx += 1
        if idx % 50 == 0 or idx == total_days:
            update_progress(
                "round_table_time",
                f"Fetched {idx}/{total_days} snapshot days ({fetched} new, {reused} cached)",
                round(5 + (idx / total_days) * 65, 1),
                {"fetched": fetched, "cached": reused, "missing": len(missing)},
            )
        d += timedelta(days=1)

    if not available:
        print("[FAIL] No snapshots could be retrieved.")
        return 1

    first_file_date = manifest.get("first_file_date") or available[0].isoformat()

    available_dates = {snapshot.isoformat() for snapshot in available}
    if manifest.get("missing"):
        prior_missing = [
            m for m in manifest["missing"]
            if m not in missing and m not in available_dates and m > first_file_date
        ]
        missing = sorted(set(prior_missing) | set(missing))
    missing = [m for m in missing if m > first_file_date]

    save_manifest({
        "scanned_through": latest.isoformat(),
        "missing": missing,
        "first_file_date": first_file_date,
        "last_file_date": latest.isoformat(),
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    update_progress("round_table_time", "Parsing and aggregating snapshots", 75)
    print(f"Parsing {len(available)} snapshots ({fetched} newly fetched, {reused} from cache)...")

    records = []
    for i, d in enumerate(available):
        records.extend(parse_snapshot(_cache_path(d)))
        if (i + 1) % 100 == 0:
            update_progress("round_table_time", f"Parsed {i + 1}/{len(available)} snapshots", round(75 + (i / len(available)) * 15, 1))

    unique_dates = sorted({r["date"] for r in records})
    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generator": "round_table_time_ingest.py",
        "source_url": "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_round_table_time_daily_YYYYMMDD.csv",
        "cache_dir": "data/round_table_time",
        "latest_file_date": latest.isoformat(),
        "first_file_date": first_file_date,
        "files_available": len(available),
        "files_fetched_now": fetched,
        "files_reused_cache": reused,
        "files_missing_count": len(missing),
        "files_missing": missing,
        "billing_date_min": unique_dates[0] if unique_dates else None,
        "billing_date_max": unique_dates[-1] if unique_dates else None,
        "days_with_data": len(unique_dates),
        "rows_raw": len(records),
        "game_types": sorted({r["game_type"] for r in records}),
        "tables_tracked": len({r["table"] for r in records}),
        "null_duration_rows": sum(1 for r in records if r["actual_duration"] is None or r["std_actual_duration"] is None),
        "table_entries_count": len({r["table"] for r in records}),
        "he_significant_delta": 5.0,
        "prob_breach_rule": "actual_duration > threshold (mean + 1 std)",
    }

    payload = build_payload(records, meta)
    meta["rows_raw"] = payload["meta"]["unique_keys"]

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT_FILE)
    print(f"""
Round Table Time ingest complete
  snapshots available : {len(available)}  ({first_file_date} .. {latest.isoformat()})
  gaps after start    : {len(missing)}
  business days       : {len(unique_dates)}
  raw rows (windowed) : {len(records)}
  unique keys         : {payload['meta']['unique_keys']}
  game types          : {len(meta['game_types'])}
  tables tracked      : {meta['tables_tracked']}
  null duration rows  : {meta['null_duration_rows']}
  table entries       : {meta['table_entries_count']}
  payload             : {OUT_FILE.name} ({size:,} bytes)""")

    update_progress("round_table_time", "Aggregation complete", 100, {"payload": OUT_FILE.name, "bytes": size})
    return 0


if __name__ == "__main__":
    sys.exit(main())