#!/usr/bin/env python3
"""
Shared Workspace Module - Centralizes workspace path resolution and progress
tracking for all ingest + dashboard scripts.
"""
from datetime import datetime
from pathlib import Path
import json

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR
if not (WORKSPACE / "workspace_map.txt").exists():
    for _parent in WORKSPACE.parents:
        if (_parent / "workspace_map.txt").exists():
            WORKSPACE = _parent
            break

RAW_DIR = Path(WORKSPACE / "data" / "raw")
OUTPUT_DIR = Path(WORKSPACE / "output")
OUTPUT_DIR.mkdir(exist_ok=True)
PROGRESS_FILE = OUTPUT_DIR / "progress.json"


def update_progress(stage, message, progress=None, details=None):
    data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stage': stage,
        'message': message,
        'progress': progress,
        'details': details or {}
    }
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
