#!/usr/bin/env python3
"""
Game Probability / House-Edge (HE) Ingest.

Fetches the daily snapshot CSVs published at
    https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_game_probability_he_YYYYMMDD.csv
caches them locally, and aggregates them into a single JSON payload that powers
the standalone Game Probability & House Edge dashboard.

Source format observations (verified 2026-10-12):
  * Each file YYYYMMDD is a rolling 7-business-day window snapshot: it carries
    billing_date values from YYYYMMDD-6 .. YYYYMMDD (created_at runs one day
    ahead of billing_date).
  * (billing_date, game_type, bet_place) is unique inside a file, and every
    overlapping key across files is republished with identical metrics, so the
    union of all files is a clean, idempotent daily time series.
  * expected_he / actual_he may be the literal string "null" (no HE model for
    that bet place) and a handful of bonus side bets carry degenerate
    expected_he values (e.g. -854%) which are excluded from HE averages.
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
import io
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(WORKSPACE)
CACHE_DIR = WORKSPACE / "data" / "probability"
REPORT_DIR = WORKSPACE / "output"
MANIFEST_FILE = CACHE_DIR / "_manifest.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_game_probability_he_{}.csv"
OUT_FILE = REPORT_DIR / "game_probability_he_data.json"

START_DATE = date(2025, 1, 1)
TODAY = date.today()

LATEST_PROBE_BACK_DAYS = 14
FETCH_TIMEOUT = 45
FETCH_RETRIES = 3

HE_SIGNIFICANT_DELTA = 5.0
DEGENERATE_HE_LIMIT = 100.0
PROB_BREACH_BUFFER = 0.0

METRIC_FIELDS = ("actual_he", "expected_he", "actual_probability", "expected_probability", "threshold")


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
    return CACHE_DIR / f"mnt_game_probability_he_{d.strftime('%Y%m%d')}.csv"


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
    """'12.3400%' -> 12.34 ; 'null'/'' -> None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", "nan", "-"):
        return None
    try:
        return float(s.rstrip("%").strip())
    except ValueError:
        return None


def parse_snapshot(path):
    """Parse a cached snapshot CSV into normalized row dicts."""
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for raw in csv.DictReader(f):
            bd = (raw.get("billing_date") or "").strip()
            gt = (raw.get("game_type") or "").strip()
            bp = (raw.get("bet_place") or "").strip()
            if not bd or not gt or not bp:
                continue
            rec = {
                "date": bd,
                "game_type": gt,
                "bet_place": bp,
                "updated_at": (raw.get("updated_at") or "").strip(),
            }
            for field in METRIC_FIELDS:
                rec[field] = to_float(raw.get(field))
            rows.append(rec)
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


def is_prob_breach(row):
    ap, th = row["actual_probability"], row["threshold"]
    if ap is None or th is None:
        return False
    return ap > (th + PROB_BREACH_BUFFER)


def build_data_quality(rows, dates, game_types, meta):
    """Surface the source-feed quirks the dashboard must disclose rather than
    silently smooth over: casing-aliased duplicate feeds, games whose coverage
    is partial, and rows missing individual metrics."""
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
                "null_actual_probability": sum(1 for r in sub if r["actual_probability"] is None),
                "null_threshold": sum(1 for r in sub if r["threshold"] is None),
                "null_he": sum(1 for r in sub if r["actual_he"] is None or r["expected_he"] is None),
            }
        duplicate_feeds.append({
            "normalized": up,
            "variants": detail,
            "note": "Same bet places published under two spellings with different values; both retained.",
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
    for field in ("actual_he", "expected_he", "actual_probability", "expected_probability", "threshold"):
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
        k = (r["date"], r["game_type"], r["bet_place"])
        prev = by_key.get(k)
        if prev is None or r["updated_at"] > prev["updated_at"]:
            by_key[k] = r
    rows = list(by_key.values())

    for r in rows:
        r["he_delta"] = (
            round(r["actual_he"] - r["expected_he"], 4)
            if r["actual_he"] is not None and r["expected_he"] is not None
            else None
        )
        r["prob_delta"] = (
            round(r["actual_probability"] - r["expected_probability"], 4)
            if r["actual_probability"] is not None and r["expected_probability"] is not None
            else None
        )
        r["he_usable"] = (
            r["actual_he"] is not None
            and r["expected_he"] is not None
            and abs(r["expected_he"]) <= DEGENERATE_HE_LIMIT
        )
        r["prob_breach"] = is_prob_breach(r)
        r["he_significant"] = r["he_usable"] and r["he_delta"] is not None and abs(r["he_delta"]) >= HE_SIGNIFICANT_DELTA

    rows.sort(key=lambda r: (r["date"], r["game_type"], r["bet_place"]))
    dates = sorted({r["date"] for r in rows})
    game_types = sorted({r["game_type"] for r in rows})
    meta_extra["unique_keys"] = len(rows)

    def he_pool(sub):
        return [r["he_delta"] for r in sub if r["he_usable"]]

    def actual_he_pool(sub):
        return [r["actual_he"] for r in sub if r["he_usable"]]

    def expected_he_pool(sub):
        return [r["expected_he"] for r in sub if r["he_usable"]]

    def breaching(sub):
        return sum(1 for r in sub if r["prob_breach"])

    gt_summary = []
    for gt in game_types:
        sub = [r for r in rows if r["game_type"] == gt]
        sub_dates = sorted({r["date"] for r in sub})
        he_deltas = he_pool(sub)
        breaches = breaching(sub)
        ahe = actual_he_pool(sub)
        ehe = expected_he_pool(sub)
        null_prob = sum(1 for r in sub if r["actual_probability"] is None)
        null_thr = sum(1 for r in sub if r["threshold"] is None)
        null_he = sum(1 for r in sub if r["actual_he"] is None or r["expected_he"] is None)
        gt_summary.append({
            "game_type": gt,
            "rows": len(sub),
            "days": len(sub_dates),
            "first_date": sub_dates[0],
            "last_date": sub_dates[-1],
            "bet_places": len({r["bet_place"] for r in sub}),
            "mean_actual_he": mean(ahe),
            "mean_expected_he": mean(ehe),
            "mean_he_delta": mean(he_deltas),
            "median_he_delta": median(he_deltas),
            "mean_abs_he_delta": mean([abs(v) for v in he_deltas]),
            "max_abs_he_delta": rnd(max((abs(v) for v in he_deltas), default=None)),
            "pct_he_above_expected": (
                round(sum(1 for v in he_deltas if v > 0) / len(he_deltas) * 100, 2) if he_deltas else None
            ),
            "mean_actual_probability": mean([r["actual_probability"] for r in sub]),
            "mean_expected_probability": mean([r["expected_probability"] for r in sub]),
            "mean_prob_delta": mean([r["prob_delta"] for r in sub if r["prob_delta"] is not None]),
            "mean_threshold": mean([r["threshold"] for r in sub]),
            "breaches": breaches,
            "breach_pct": round(breaches / len(sub) * 100, 2),
            "he_rows": len(he_deltas),
            "null_he_rows": sum(1 for r in sub if r["actual_he"] is None or r["expected_he"] is None),
            "null_probability_rows": null_prob,
            "null_threshold_rows": null_thr,
            "he_above_expected_days": len({r["date"] for r in sub if r["he_usable"] and r["he_delta"] > 0}),
        })
    gt_summary.sort(key=lambda g: (-g["rows"], g["game_type"]))

    bp_summary = []
    for gt in game_types:
        for bp in sorted({r["bet_place"] for r in rows if r["game_type"] == gt}):
            sub = [r for r in rows if r["game_type"] == gt and r["bet_place"] == bp]
            sub_sorted = sorted(sub, key=lambda r: r["date"])
            he_deltas = he_pool(sub)
            breaches = breaching(sub)
            breach_rows = [r for r in sub if r["prob_breach"]]
            worst = max(breach_rows, key=lambda r: r["actual_probability"] - r["threshold"], default=None)
            latest = sub_sorted[-1]
            bp_summary.append({
                "key": f"{gt}|{bp}",
                "game_type": gt,
                "bet_place": bp,
                "rows": len(sub),
                "days": len({r["date"] for r in sub}),
                "first_date": sub_sorted[0]["date"],
                "last_date": latest["date"],
                "mean_actual_he": mean(actual_he_pool(sub)),
                "mean_expected_he": mean(expected_he_pool(sub)),
                "mean_he_delta": mean(he_deltas),
                "median_he_delta": median(he_deltas),
                "max_abs_he_delta": rnd(max((abs(v) for v in he_deltas), default=None)),
                "mean_actual_probability": mean([r["actual_probability"] for r in sub]),
                "mean_expected_probability": mean([r["expected_probability"] for r in sub]),
                "mean_prob_delta": mean([r["prob_delta"] for r in sub if r["prob_delta"] is not None]),
                "mean_threshold": mean([r["threshold"] for r in sub]),
                "breaches": breaches,
                "breach_pct": round(breaches / len(sub) * 100, 2),
                "max_overage": rnd((worst["actual_probability"] - worst["threshold"]) if worst else None),
                "max_overage_date": worst["date"] if worst else None,
                "has_null_he": any(r["actual_he"] is None or r["expected_he"] is None for r in sub),
                "degenerate_he": any(not r["he_usable"] and r["actual_he"] is not None and r["expected_he"] is not None for r in sub),
                "latest": {
                    "date": latest["date"],
                    "actual_he": rnd(latest["actual_he"]),
                    "expected_he": rnd(latest["expected_he"]),
                    "he_delta": rnd(latest["he_delta"]),
                    "actual_probability": rnd(latest["actual_probability"]),
                    "expected_probability": rnd(latest["expected_probability"]),
                    "prob_delta": rnd(latest["prob_delta"]),
                    "threshold": rnd(latest["threshold"]),
                    "prob_breach": latest["prob_breach"],
                },
            })

    series_he = {gt: [] for gt in game_types}
    series_expected_he = {gt: [] for gt in game_types}
    series_actual_probability = {gt: [] for gt in game_types}
    series_expected_probability = {gt: [] for gt in game_types}
    series_threshold = {gt: [] for gt in game_types}
    series_prob_gap = {gt: [] for gt in game_types}
    series_breach = {gt: [] for gt in game_types}
    series_breach_count = {gt: [] for gt in game_types}
    bet_place_breach_events = defaultdict(list)
    daily = []

    for d in dates:
        day_rows = [r for r in rows if r["date"] == d]
        entry = {
            "date": d,
            "samples": len(day_rows),
            "breaches": breaching(day_rows),
            "mean_actual_he": mean(actual_he_pool(day_rows)),
            "mean_expected_he": mean(expected_he_pool(day_rows)),
            "mean_he_delta": mean(he_pool(day_rows)),
            "mean_actual_probability": mean([r["actual_probability"] for r in day_rows]),
            "mean_expected_probability": mean([r["expected_probability"] for r in day_rows]),
            "mean_threshold": mean([r["threshold"] for r in day_rows]),
            "mean_prob_delta": mean([r["prob_delta"] for r in day_rows if r["prob_delta"] is not None]),
        }
        entry["breach_pct"] = round(entry["breaches"] / len(day_rows) * 100, 2) if day_rows else 0.0
        daily.append(entry)

        for gt in game_types:
            gt_day = [r for r in day_rows if r["game_type"] == gt]
            if not gt_day:
                continue
            series_he[gt].append([d, mean(actual_he_pool(gt_day))])
            series_expected_he[gt].append([d, mean(expected_he_pool(gt_day))])
            series_actual_probability[gt].append([d, mean([r["actual_probability"] for r in gt_day])])
            series_expected_probability[gt].append([d, mean([r["expected_probability"] for r in gt_day])])
            series_threshold[gt].append([d, mean([r["threshold"] for r in gt_day])])
            series_prob_gap[gt].append([d, mean([r["prob_delta"] for r in gt_day if r["prob_delta"] is not None])])
            series_breach[gt].append([d, round(breaching(gt_day) / len(gt_day) * 100, 2)])
            series_breach_count[gt].append([d, breaching(gt_day)])

        for r in day_rows:
            if r["prob_breach"]:
                bet_place_breach_events[(r["game_type"], r["bet_place"])].append(d)

    bet_place_breaches = {
        f"{gt}|{bp}": [[day, count] for day, count in sorted(Counter(days_hit).items())]
        for (gt, bp), days_hit in sorted(bet_place_breach_events.items())
    }

    latest_date = dates[-1] if dates else None
    latest_rows = []
    if latest_date:
        for r in sorted([r for r in rows if r["date"] == latest_date], key=lambda r: (r["game_type"], r["bet_place"])):
            latest_rows.append({
                "game_type": r["game_type"],
                "bet_place": r["bet_place"],
                "actual_he": rnd(r["actual_he"]),
                "expected_he": rnd(r["expected_he"]),
                "he_delta": rnd(r["he_delta"]),
                "actual_probability": rnd(r["actual_probability"]),
                "expected_probability": rnd(r["expected_probability"]),
                "prob_delta": rnd(r["prob_delta"]),
                "threshold": rnd(r["threshold"]),
                "prob_breach": r["prob_breach"],
                "he_significant": r["he_significant"],
            })

    def watch_entry(r):
        return {
            "date": r["date"],
            "game_type": r["game_type"],
            "bet_place": r["bet_place"],
            "actual_he": rnd(r["actual_he"]),
            "expected_he": rnd(r["expected_he"]),
            "he_delta": rnd(r["he_delta"]),
            "actual_probability": rnd(r["actual_probability"]),
            "expected_probability": rnd(r["expected_probability"]),
            "prob_delta": rnd(r["prob_delta"]),
            "threshold": rnd(r["threshold"]),
            "overage": rnd((r["actual_probability"] - r["threshold"]) if r["prob_breach"] else None),
        }

    he_watch = sorted(
        [r for r in rows if r["he_usable"] and r["he_delta"] is not None],
        key=lambda r: abs(r["he_delta"]),
        reverse=True,
    )[:30]
    prob_watch = sorted(
        [r for r in rows if r["prob_breach"]],
        key=lambda r: r["actual_probability"] - r["threshold"],
        reverse=True,
    )[:30]

    bucket_edges = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 5.0, 10.0, 25.0, 50.0, 100.0]
    n_buckets = len(bucket_edges)
    counts = [0] * n_buckets
    for r in rows:
        th = r["threshold"]
        if th is None:
            continue
        idx = n_buckets - 1
        for i in range(n_buckets - 1):
            if th < bucket_edges[i + 1]:
                idx = i
                break
        counts[idx] += 1
    threshold_buckets = [
        {
            "label": (
                f"{bucket_edges[i]:g} - {bucket_edges[i + 1]:g}%"
                if i < n_buckets - 1
                else f">= {bucket_edges[-1]:g}%"
            ),
            "count": counts[i],
        }
        for i in range(n_buckets)
    ]

    data_quality = build_data_quality(rows, dates, game_types, meta_extra)

    payload = {
        "meta": meta_extra,
        "game_types": gt_summary,
        "bet_places": bp_summary,
        "series_he": series_he,
        "series_expected_he": series_expected_he,
        "series_actual_probability": series_actual_probability,
        "series_expected_probability": series_expected_probability,
        "series_threshold": series_threshold,
        "series_prob_gap": series_prob_gap,
        "series_breach": series_breach,
        "series_breach_count": series_breach_count,
        "bet_place_breaches": bet_place_breaches,
        "daily": daily,
        "latest_day": {"billing_date": latest_date, "rows": latest_rows},
        "watchlist": {
            "he": [watch_entry(r) for r in he_watch],
            "prob": [watch_entry(r) for r in prob_watch],
        },
        "threshold_buckets": threshold_buckets,
        "data_quality": data_quality,
        "missing_dates": meta_extra.get("files_missing", []),
    }
    return payload


def main():
    update_progress("probability_he", "Locating newest published snapshot", 2)

    manifest = load_manifest()

    # The scan floor comes from the manifest. Without one we always rescan from
    # START_DATE: fetch_snapshot() short-circuits on cached files, so the only
    # network cost is for dates that are genuinely not cached yet (a handful of
    # 404s plus new snapshots). This must be resolved BEFORE the latest-date
    # probe, otherwise the file just fetched for the probe would be mistaken
    # for the oldest cached snapshot.
    scan_start = START_DATE
    if manifest.get("first_file_date"):
        scan_start = date.fromisoformat(manifest["first_file_date"])

    latest = discover_latest_file_date()
    if latest is None:
        print("[FAIL] No published snapshot found within the probe window.")
        return 1

    print(f"Snapshot range: {scan_start.isoformat()} -> {latest.isoformat()}")
    update_progress("probability_he", f"Fetching snapshots {scan_start.isoformat()} .. {latest.isoformat()}", 5)

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
                "probability_he",
                f"Fetched {idx}/{total_days} snapshot days ({fetched} new, {reused} cached)",
                round(5 + (idx / total_days) * 65, 1),
                {"fetched": fetched, "cached": reused, "missing": len(missing)},
            )
        d += timedelta(days=1)

    if not available:
        print("[FAIL] No snapshots could be retrieved.")
        return 1

    first_file_date = manifest.get("first_file_date") or available[0].isoformat()

    # Only report gaps that fall AFTER the first published snapshot. Dates
    # before it are simply before the feed existed, not missing data.
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

    update_progress("probability_he", "Parsing and aggregating snapshots", 75)
    print(f"Parsing {len(available)} snapshots ({fetched} newly fetched, {reused} from cache)...")

    records = []
    for i, d in enumerate(available):
        records.extend(parse_snapshot(_cache_path(d)))
        if (i + 1) % 100 == 0:
            update_progress("probability_he", f"Parsed {i + 1}/{len(available)} snapshots", round(75 + (i / len(available)) * 15, 1))

    unique_dates = sorted({r["date"] for r in records})
    null_he_rows = sum(1 for r in records if r["actual_he"] is None or r["expected_he"] is None)
    degenerate_rows = sum(
        1 for r in records
        if r["actual_he"] is not None and r["expected_he"] is not None and abs(r["expected_he"]) > DEGENERATE_HE_LIMIT
    )
    null_prob_rows = sum(1 for r in records if r["actual_probability"] is None)
    null_threshold_rows = sum(1 for r in records if r["threshold"] is None)

    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generator": "probability_he_ingest.py",
        "source_url": "https://ogp.oss-ap-southeast-1.aliyuncs.com/share/mnt_game_probability_he_YYYYMMDD.csv",
        "cache_dir": "data/probability",
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
        "bet_places_tracked": len({(r["game_type"], r["bet_place"]) for r in records}),
        "null_he_rows": null_he_rows,
        "null_probability_rows": null_prob_rows,
        "null_threshold_rows": null_threshold_rows,
        "degenerate_he_rows_excluded": degenerate_rows,
        "he_significant_delta": HE_SIGNIFICANT_DELTA,
        "prob_breach_rule": "actual_probability > threshold",
    }

    payload = build_payload(records, meta)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    size = os.path.getsize(OUT_FILE)
    print(f"""
Game Probability / HE ingest complete
  snapshots available : {len(available)}  ({first_file_date} .. {latest.isoformat()})
  gaps after start    : {len(missing)}
  business days       : {len(unique_dates)}
  raw rows (windowed) : {len(records)}
  unique keys         : {payload['meta']['unique_keys']}
  game types          : {len(meta['game_types'])}
  bet places tracked  : {meta['bet_places_tracked']}
  null HE rows        : {null_he_rows}
  null probability    : {null_prob_rows}
  null threshold      : {null_threshold_rows}
  degenerate HE rows  : {degenerate_rows}
  duplicate feeds     : {len(payload['data_quality']['duplicate_feeds'])}
  payload             : {OUT_FILE.name} ({size:,} bytes)""")

    update_progress("probability_he", "Aggregation complete", 100, {"payload": OUT_FILE.name, "bytes": size})
    return 0


if __name__ == "__main__":
    sys.exit(main())
