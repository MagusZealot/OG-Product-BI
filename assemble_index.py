#!/usr/bin/env python3
"""Assemble aggregate all_players_index.json + dossier_chunks/ from per-export step 6 outputs.

Standalone helper run after pipeline step 6. Merges every per-export
all_players_index_XX.json into a single aggregate index, re-ranks players by
total debit descending, reassigns id as array position, and copies each
per-export chunk into the aggregate dossier_chunks/ layout consumed by the
existing dashboards.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
if not (WORKSPACE / "workspace_map.md").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.md").exists():
            WORKSPACE = _parent
            break

INDEX_DIR = WORKSPACE / "output" / "data"
CHUNK_SRC_DIR = WORKSPACE / "output" / "chunks"
OUTPUT_INDEX = INDEX_DIR / "all_players_index.json"
OUTPUT_CHUNK_DIR = CHUNK_SRC_DIR / "dossier_chunks"

CHUNK_SIZE = 1000
PER_EXPORT_INDEX_GLOB = "all_players_index_*.json"
PER_EXPORT_CHUNK_GLOB = "dossier_chunks_*"
CHUNK_FILE_GLOB = "chunk_*.js"


def _iter_per_export_indexes():
    return sorted(INDEX_DIR.glob(PER_EXPORT_INDEX_GLOB))


def _iter_per_export_chunk_dirs():
    return sorted(CHUNK_SRC_DIR.glob(PER_EXPORT_CHUNK_GLOB))


def _load_index(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def should_skip():
    """True if the aggregate output already exists and is newer than all sources."""
    if not OUTPUT_INDEX.exists() or OUTPUT_INDEX.stat().st_size == 0:
        return False
    index_files = list(_iter_per_export_indexes())
    if not index_files:
        return False
    out_mtime = OUTPUT_INDEX.stat().st_mtime
    for src in index_files:
        if not src.exists() or src.stat().st_mtime > out_mtime:
            return False
    return True


def _atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def _copy_chunks():
    OUTPUT_CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    for src_chunk_dir in _iter_per_export_chunk_dirs():
        if not src_chunk_dir.is_dir():
            continue
        for chunk_file in sorted(src_chunk_dir.glob(CHUNK_FILE_GLOB)):
            shutil.copy2(chunk_file, OUTPUT_CHUNK_DIR / chunk_file.name)


def assemble():
    index_files = list(_iter_per_export_indexes())
    if not index_files:
        print("No per-export indexes found; nothing to assemble")
        return False

    if should_skip():
        print("Aggregate index newer than per-export sources; skipping assemble_index")
        return True

    all_players = []
    total_rows = 0
    for path in index_files:
        data = _load_index(path)
        players = data.get("players", [])
        all_players.extend(players)
        total_rows += data.get("meta", {}).get("total_rows", 0)

    all_players.sort(key=lambda p: p.get("debit", 0), reverse=True)

    for idx, p in enumerate(all_players):
        p["id"] = idx

    meta = {
        "total_players": len(all_players),
        "total_rows": total_rows,
        "source_file": "aggregate",
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chunk_size": CHUNK_SIZE,
        "total_chunks": (len(all_players) + CHUNK_SIZE - 1) // CHUNK_SIZE,
    }
    result = {"meta": meta, "players": all_players}

    OUTPUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    _atomic_json(OUTPUT_INDEX, result)

    _copy_chunks()

    print(f"Assembled {len(all_players)} players -> {OUTPUT_INDEX.name}")
    return True


def main():
    success = assemble()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
