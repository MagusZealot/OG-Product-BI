#!/usr/bin/env python3
"""
Shared raw-data reader for ingest scripts.

Exposes iter_raw_rows(folder), a generator yielding normalized row dicts
from every .csv export in folder, so each ingest script no longer
re-implements its own csv.DictReader loop.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from currency_converter import convert_to_php  # noqa: E402

_DEBIT_COL = "debit_amount"
_CREDIT_COL = "credit_amount"
_WINLOSE_COL = "winlose_amount"

_AMOUNT_COLUMNS = (
    ("debit_php", _DEBIT_COL),
    ("credit_php", _CREDIT_COL),
    ("winlose_php", _WINLOSE_COL),
)


def _safe_float(val):
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _normalize_row(row):
    currency = (row.get("currency") or "").strip()
    formatted_debit_at = (row.get("formatted_debit_at") or "").strip()

    out = {
        "player_id": (row.get("player_id") or "").strip(),
        "currency": currency,
        "formatted_debit_at": formatted_debit_at,
        "game_name": (row.get("game_name") or "").strip(),
        "operator_name": (row.get("operator_name") or "").strip(),
    }
    for out_col, src_col in _AMOUNT_COLUMNS:
        out[out_col] = convert_to_php(
            _safe_float(row.get(src_col)), currency, formatted_debit_at
        )
    return out


def iter_raw_rows(folder):
    """Yield normalized row dicts from all .csv files in folder."""
    folder = Path(folder)
    for file_path in sorted(folder.glob("*.csv")):
        try:
            with open(
                file_path,
                "r",
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            ) as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    continue
                for row in reader:
                    yield _normalize_row(row)
        except (OSError, csv.Error, UnicodeError):
            continue
