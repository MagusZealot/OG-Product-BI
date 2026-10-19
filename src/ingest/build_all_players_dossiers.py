#!/usr/bin/env python3
"""Build per-export player indexes and lazy-loaded dossier trajectory chunks.

Each export is processed independently. The CSV is streamed once to produce
the compact index and again to construct typed trajectory buffers. The large
merged all_players_dossiers JSON is deliberately opt-in.
"""
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import csv
import io
import json
import os
import time
from array import array
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone

from currency_converter import convert_to_php, CURRENCY_COUNTRY
from workspace import RAW_DIR as FOLDER, OUTPUT_DIR as REPORT_DIR
from player_index import PlayerIndexEntry

CHUNK_SIZE = 1000
MAX_WORKERS = min(max(os.cpu_count() or 2, 2), 4)
WRITE_MONOLITH = os.environ.get("BUILD_DOSSIER_MONOLITH", "0").strip().lower() in {"1", "true", "yes"}

_DEVICE_CACHE = {}


def norm_device(value):
    result = _DEVICE_CACHE.get(value)
    if result is None:
        lowered = value.lower()
        result = "Mobile" if "mobile" in lowered else "Desktop" if "desktop" in lowered else "Other"
        _DEVICE_CACHE[value] = result
    return result


def load_refs():
    whales, chasers = {}, {}
    for row in csv.DictReader(open(REPORT_DIR / "whale_analysis.csv", encoding="utf-8", newline="")):
        whales[row["player_id"]] = {
            "avg_session_hours": float(row["avg_session_hours"]),
        }
    for row in csv.DictReader(open(REPORT_DIR / "chaser_detection.csv", encoding="utf-8", newline="")):
        chasers[row["player_id"]] = {
            "spike_multiplier": float(row["spike_multiplier"]),
        }
    return whales, chasers


def classify(pid, debit, whales, chasers):
    spike = chasers.get(pid, {}).get("spike_multiplier", 0.0)
    if spike >= 1000:
        return "Extreme Chaser"
    if spike >= 100:
        return "Critical Chaser"
    if pid in whales:
        hours = whales[pid]["avg_session_hours"]
        return "Lightning Burst Whale" if hours < .05 else "Sustained Grinder Whale" if hours >= .4 else "VIP Whale"
    if pid in chasers:
        return "High Chaser" if spike >= 20 else "Moderate Chaser" if spike >= 5 else "Low Chaser"
    return "VIP High Roller" if debit >= 100_000_000 else "High Roller" if debit >= 10_000_000 else "Mid Roller" if debit >= 1_000_000 else "Active Player" if debit >= 100_000 else "Casual Player"


def _columns(reader):
    header = next(reader)
    return {name: header.index(name) for name in (
        "player_id", "currency", "debit_amount", "credit_amount", "winlose_amount",
        "devicetype", "operator_name", "game_name", "balance", "debit_at", "formatted_debit_at"
    )}


def _parse_amount(row, idx):
    try:
        return float(row[idx] or 0)
    except (ValueError, IndexError):
        return 0.0


def _iter_rows(path):
    source = open(path, "r", encoding="utf-8-sig", errors="replace", newline="")
    reader = csv.reader(source)
    try:
        cols = _columns(reader)
        for row in reader:
            if len(row) > cols["player_id"] and row[cols["player_id"]].strip():
                yield row, cols
    finally:
        source.close()


def extract_player_index(fpath, f_idx, whales, chasers):
    """Step 1: aggregate lightweight telemetry, without trajectory histories."""
    meta = {}
    for row, c in _iter_rows(fpath):
        pid = row[c["player_id"]].strip()
        m = meta.get(pid)
        if m is None:
            m = meta[pid] = {
                "bets": 0, "debit": 0.0, "credit": 0.0, "winlose": 0.0,
                "games": {}, "ops": Counter(), "devices": Counter(), "hourly": [0] * 24,
                "cur_counts": Counter(), "recent": deque(maxlen=10), "first_seen": 0,
                "last_seen": 0, "last_ts": None, "time_order_ok": True,
            }
        currency = row[c["currency"]].strip()
        date = row[c["formatted_debit_at"]]
        debit = convert_to_php(_parse_amount(row, c["debit_amount"]), currency, date)
        credit = convert_to_php(_parse_amount(row, c["credit_amount"]), currency, date)
        winlose = convert_to_php(_parse_amount(row, c["winlose_amount"]), currency, date)
        m["bets"] += 1
        m["debit"] += debit
        m["credit"] += credit
        m["winlose"] += winlose
        m["cur_counts"][currency] += 1
        game = row[c["game_name"]].strip() or "Unknown"
        gm = m["games"].setdefault(game, [0, 0.0, 0.0, 0, 0])
        gm[0] += 1; gm[1] += debit; gm[2] += credit
        if winlose > 0: gm[3] += 1
        elif winlose < 0: gm[4] += 1
        m["ops"][row[c["operator_name"]].strip() or "UNKNOWN"] += 1
        m["devices"][norm_device(row[c["devicetype"]])] += 1
        stamp = row[c["debit_at"]]
        try: ts = int(stamp)
        except (ValueError, TypeError): ts = 0
        if m["last_ts"] is not None and ts < m["last_ts"]:
            m["time_order_ok"] = False
        m["last_ts"] = ts
        if ts:
            m["first_seen"] = min(m["first_seen"], ts) if m["first_seen"] else ts
            m["last_seen"] = max(m["last_seen"], ts)
        ft = row[c["formatted_debit_at"]]
        if len(ft) >= 13:
            try: m["hourly"][int(ft[11:13])] += 1
            except (ValueError, IndexError): pass
        balance = convert_to_php(_parse_amount(row, c["balance"]), currency, date)
        m["recent"].append((ft, game, debit, credit, winlose, balance))

    ordered = sorted(meta, key=lambda pid: meta[pid]["debit"], reverse=True)
    entries: list[PlayerIndexEntry] = []
    for rank, pid in enumerate(ordered):
        m = meta[pid]
        country = CURRENCY_COUNTRY.get(m["cur_counts"].most_common(1)[0][0], "Unknown") if m["cur_counts"] else "Unknown"
        entry: PlayerIndexEntry = {
            "id": rank, "pid": pid, "country": country,
            "arch": classify(pid, m["debit"], whales, chasers),
            "debit": round(m["debit"], 2), "winlose": round(m["winlose"], 2), "bets": m["bets"],
            "avg_bet": round(m["debit"] / m["bets"], 2) if m["bets"] else 0.0,
            "whale": int(pid in whales), "chaser": int(pid in chasers),
            "op": m["ops"].most_common(1)[0][0] if m["ops"] else "UNKNOWN",
            "spike": chasers.get(pid, {}).get("spike_multiplier", 1.0),
        }
        entries.append(entry)
    result = {
        "meta": {"total_players": len(entries), "total_rows": sum(e["bets"] for e in entries),
                 "source_file": fpath.stem, "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "chunk_size": CHUNK_SIZE, "total_chunks": (len(entries) + CHUNK_SIZE - 1) // CHUNK_SIZE},
        "players": entries,
    }
    path = REPORT_DIR / f"all_players_index_{f_idx:02d}.json"
    _atomic_json(path, result)
    print(f"    Step 1 index -> {path.name} ({path.stat().st_size:,} bytes)")
    return meta, entries, result["meta"]


def _atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def build_player_detail(pid, m, timestamps, balances, signs, whales, chasers):
    """Step 2: derive one player's detail from typed trajectory buffers."""
    if not m["time_order_ok"]:
        order = sorted(range(len(timestamps)), key=timestamps.__getitem__)
        timestamps = array("q", (timestamps[i] for i in order))
        balances = array("d", (balances[i] for i in order))
        signs = array("b", (signs[i] for i in order))
    session_count = total_active = 0
    previous = session_start = None
    for ts in timestamps:
        if not ts: continue
        if previous is None:
            session_count += 1; session_start = ts
        elif ts - previous > 1800:
            total_active += previous - session_start
            session_count += 1; session_start = ts
        previous = ts
    if previous is not None: total_active += previous - session_start
    avg_session = total_active / 3600 / session_count if session_count else 0.0
    wins = losses = ties = max_wins = max_losses = cur_wins = cur_losses = 0
    for sign in signs:
        if sign > 0:
            wins += 1; cur_wins += 1; cur_losses = 0; max_wins = max(max_wins, cur_wins)
        elif sign < 0:
            losses += 1; cur_losses += 1; cur_wins = 0; max_losses = max(max_losses, cur_losses)
        else:
            ties += 1; cur_wins = cur_losses = 0
    country = CURRENCY_COUNTRY.get(m["cur_counts"].most_common(1)[0][0], "Unknown") if m["cur_counts"] else "Unknown"
    arch = classify(pid, m["debit"], whales, chasers)
    primary_op = m["ops"].most_common(1)[0][0] if m["ops"] else "UNKNOWN"
    games = [{"game": g, "bets": v[0], "debit": round(v[1], 2), "credit": round(v[2], 2),
              "wins": v[3], "losses": v[4], "win_rate_pct": round(v[3] / v[0] * 100, 2) if v[0] else 0.0}
             for g, v in m["games"].items()]
    games.sort(key=lambda g: g["debit"], reverse=True)
    recent = [{"time": r[0], "game": r[1], "debit": round(r[2], 2), "credit": round(r[3], 2),
               "winlose": round(r[4], 2), "balance": round(r[5], 2)} for r in m["recent"]]
    return {
        "country": country, "arch": arch, "primary_operator": primary_op,
        "total_debit": round(m["debit"], 2), "total_credit": round(m["credit"], 2), "total_winlose": round(m["winlose"], 2),
        "total_bets": m["bets"], "avg_bet": round(m["debit"] / m["bets"], 2) if m["bets"] else 0.0,
        "is_whale": int(pid in whales), "is_chaser": int(pid in chasers),
        "spike_multiplier": chasers.get(pid, {}).get("spike_multiplier", 1.0),
        "max_consecutive_losses": max_losses, "max_consecutive_wins": max_wins,
        "total_wins": wins, "total_losses": losses, "total_ties": ties,
        "session_count": session_count, "avg_session_hours": round(avg_session, 3),
        "first_seen": datetime.fromtimestamp(m["first_seen"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if m["first_seen"] else "",
        "last_seen": datetime.fromtimestamp(m["last_seen"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if m["last_seen"] else "",
        "peak_balance": round(max(balances), 2) if balances else 0.0,
        "min_balance": round(min(balances), 2) if balances else 0.0,
        "avg_balance": round(sum(balances) / len(balances), 2) if balances else 0.0,
        "balance_series": balances.tolist() if hasattr(balances, "tolist") else list(balances),
        "timestamps": timestamps.tolist() if hasattr(timestamps, "tolist") else list(timestamps),
        "games": games, "hours": m["hourly"], "devices": dict(m["devices"]),
        "operators": dict(m["ops"].most_common(10)), "recent_rounds": recent,
    }


def build_trajectories(fpath, f_idx, meta, entries, whales, chasers, index_meta):
    """Step 2: reread rows into typed per-player arrays and write chunks async."""
    trajectories = {pid: (array("q"), array("d"), array("b")) for pid in meta}
    for row, c in _iter_rows(fpath):
        pid = row[c["player_id"]].strip()
        buffers = trajectories.get(pid)
        if buffers is None: continue
        currency = row[c["currency"]].strip()
        date = row[c["formatted_debit_at"]]
        try: ts = int(row[c["debit_at"]])
        except (ValueError, TypeError): ts = 0
        wl = convert_to_php(_parse_amount(row, c["winlose_amount"]), currency, date)
        buffers[0].append(ts)
        buffers[1].append(convert_to_php(_parse_amount(row, c["balance"]), currency, date))
        buffers[2].append(1 if wl > 0 else -1 if wl < 0 else 0)

    chunk_dir = REPORT_DIR / f"dossier_chunks_{f_idx:02d}"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    writers = ThreadPoolExecutor(max_workers=2)
    pending = []
    monolith_players = [] if WRITE_MONOLITH else None
    for start in range(0, len(entries), CHUNK_SIZE):
        chunk_id = start // CHUNK_SIZE
        details = {}
        for entry in entries[start:start + CHUNK_SIZE]:
            pid = entry["pid"]
            ts, bal, signs = trajectories[pid]
            details[pid] = build_player_detail(pid, meta[pid], ts, bal, signs, whales, chasers)
            if monolith_players is not None:
                d = details[pid]
                monolith_players.append({"player_id": pid, "id": entry["id"], "archetype": d["arch"],
                    "country": d["country"], "primary_operator": d["primary_operator"],
                    "total_debit": d["total_debit"], "total_credit": d["total_credit"], "total_winlose": d["total_winlose"],
                    "total_bets": d["total_bets"], "avg_bet": d["avg_bet"], "is_whale": bool(d["is_whale"]),
                    "is_chaser": bool(d["is_chaser"]), "spike_multiplier": d["spike_multiplier"],
                    "max_consecutive_losses": d["max_consecutive_losses"], "max_consecutive_wins": d["max_consecutive_wins"],
                    "total_wins": d["total_wins"], "total_losses": d["total_losses"], "total_ties": d["total_ties"],
                    "session_count": d["session_count"], "avg_session_hours": d["avg_session_hours"],
                    "first_seen": d["first_seen"], "last_seen": d["last_seen"], "peak_balance": d["peak_balance"],
                    "min_balance": d["min_balance"], "avg_balance": d["avg_balance"], "balance_series": d["balance_series"],
                    "timestamps": d["timestamps"],
                    "pnl_series": [round(b - d["balance_series"][0], 2) for b in d["balance_series"]] if d["balance_series"] else [],
                    "games": d["games"], "hours": d["hours"], "devices": d["devices"],
                    "operators": d["operators"], "recent_rounds": d["recent_rounds"]})
        target = chunk_dir / f"chunk_{chunk_id:04d}.js"
        pending.append(writers.submit(_write_chunk, target, chunk_id, details))
        if len(pending) >= 4:
            pending.pop(0).result()
        del details
    for future in pending: future.result()
    writers.shutdown(wait=True)
    if monolith_players is not None:
        _atomic_json(REPORT_DIR / f"all_players_dossiers_{f_idx:02d}.json", {"meta": index_meta, "players": monolith_players})
    print(f"    Step 2 chunks -> {chunk_dir.name} ({index_meta['total_chunks']} files)")


def _write_chunk(path, chunk_id, details):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as out:
        out.write(f"window.DOSSIER_CHUNK_{chunk_id:04d} = ")
        json.dump(details, out, ensure_ascii=False, separators=(",", ":"))
        out.write(";")
    os.replace(tmp, path)


def process_file(task):
    f_idx, fpath = task
    index_path = REPORT_DIR / f"all_players_index_{f_idx:02d}.json"
    chunk_dir = REPORT_DIR / f"dossier_chunks_{f_idx:02d}"
    if index_path.exists():
        try:
            with open(index_path, encoding="utf-8") as source: cached = json.load(source)
            players = cached["players"]
            expected = cached["meta"]["total_chunks"]
            if expected and len(players) and all((chunk_dir / f"chunk_{i:04d}.js").exists() for i in range(expected)):
                print(f"  [{f_idx + 1}] {fpath.name}: index and chunks present; skipping")
                return
        except (OSError, ValueError, KeyError, TypeError):
            pass
    print(f"  [{f_idx + 1}] {fpath.name}...")
    t0 = time.time()
    whales, chasers = load_refs()
    meta, entries, index_meta = extract_player_index(fpath, f_idx, whales, chasers)
    if entries:
        build_trajectories(fpath, f_idx, meta, entries, whales, chasers, index_meta)
    print(f"    Completed in {time.time() - t0:.0f}s")


def main():
    files = sorted(FOLDER.glob("*EXPORT_CSV*.csv"))
    if not files:
        print("No EXPORT_CSV files found")
        return
    print(f"Processing {len(files)} export files (workers={MAX_WORKERS}; monolith={WRITE_MONOLITH})...")
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
        list(pool.map(process_file, enumerate(files)))
    print(f"DONE. Total time: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
