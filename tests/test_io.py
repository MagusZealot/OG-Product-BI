import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_INGEST = REPO_ROOT / "src" / "ingest"
if str(SRC_INGEST) not in sys.path:
    sys.path.insert(0, str(SRC_INGEST))

import importlib.util

REPO_ROOT = Path(__file__).resolve().parent.parent
IO_PATH = REPO_ROOT / "src" / "ingest" / "io.py"
SRC_INGEST = REPO_ROOT / "src" / "ingest"
if str(SRC_INGEST) not in sys.path:
    sys.path.insert(0, str(SRC_INGEST))

_spec = importlib.util.spec_from_file_location("ingest_io", IO_PATH)
ingest_io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ingest_io)
iter_raw_rows = ingest_io.iter_raw_rows


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestIterRawRows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_yields_normalized_rows_with_all_columns(self):
        _write_csv(
            self.folder / "a.csv",
            ["player_id", "currency", "formatted_debit_at",
             "debit_amount", "credit_amount", "winlose_amount",
             "game_name", "operator_name"],
            [
                {"player_id": "P1", "currency": "PHP",
                 "formatted_debit_at": "2026-08-15 10:00:00",
                 "debit_amount": "100", "credit_amount": "50",
                 "winlose_amount": "-25", "game_name": "Baccarat",
                 "operator_name": "OpA"},
                {"player_id": "P2", "currency": "PHP",
                 "formatted_debit_at": "2026-08-15 11:00:00",
                 "debit_amount": "200", "credit_amount": "0",
                 "winlose_amount": "0", "game_name": "Roulette",
                 "operator_name": "OpB"},
            ],
        )
        rows = list(iter_raw_rows(self.folder))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {
            "player_id": "P1",
            "currency": "PHP",
            "formatted_debit_at": "2026-08-15 10:00:00",
            "debit_php": 100.0,
            "credit_php": 50.0,
            "winlose_php": -25.0,
            "game_name": "Baccarat",
            "operator_name": "OpA",
        })
        self.assertEqual(rows[1]["debit_php"], 200.0)

    def test_currency_conversion_uses_shared_converter(self):
        _write_csv(
            self.folder / "a.csv",
            ["player_id", "currency", "formatted_debit_at",
             "debit_amount", "credit_amount", "winlose_amount",
             "game_name", "operator_name"],
            [
                {"player_id": "P1", "currency": "USD",
                 "formatted_debit_at": "", "debit_amount": "100",
                 "credit_amount": "0", "winlose_amount": "0",
                 "game_name": "Baccarat", "operator_name": "OpA"},
            ],
        )
        rows = list(iter_raw_rows(self.folder))
        self.assertEqual(len(rows), 1)
        # Empty date string -> converter falls back to BASE_RATES (USD=56.5),
        # no network call. Independent source of truth: BASE_RATES constant.
        from currency_converter import BASE_RATES  # noqa: E402
        expected_debit = round(100.0 * BASE_RATES["USD"], 2)
        self.assertEqual(rows[0]["debit_php"], expected_debit)
        self.assertNotEqual(rows[0]["debit_php"], 100.0)

    def test_missing_columns_do_not_crash(self):
        _write_csv(
            self.folder / "a.csv",
            ["player_id", "currency"],
            [
                {"player_id": "P1", "currency": "PHP"},
                {"player_id": "P2", "currency": "USD"},
            ],
        )
        rows = list(iter_raw_rows(self.folder))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["player_id"], "P1")
        self.assertEqual(rows[0]["debit_php"], 0.0)
        self.assertEqual(rows[0]["game_name"], "")

    def test_bad_encoding_does_not_crash(self):
        path = self.folder / "bad.csv"
        with open(path, "wb") as f:
            f.write(b"player_id,currency,debit_amount\n")
            f.write(b"P1,PHP,100\n")
            f.write(b"P2,\xff,200\n")
        rows = list(iter_raw_rows(self.folder))
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["player_id"], "P1")

    def test_only_csv_files_are_read(self):
        _write_csv(
            self.folder / "data.csv",
            ["player_id", "currency", "debit_amount"],
            [{"player_id": "P1", "currency": "PHP", "debit_amount": "10"}],
        )
        with open(self.folder / "notes.txt", "w", encoding="utf-8") as f:
            f.write("not a csv\n")
        rows = list(iter_raw_rows(self.folder))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["player_id"], "P1")

    def test_empty_folder_yields_nothing(self):
        self.assertEqual(list(iter_raw_rows(self.folder)), [])

    def test_multiple_files_all_read(self):
        _write_csv(
            self.folder / "a.csv",
            ["player_id", "currency", "debit_amount"],
            [{"player_id": "P1", "currency": "PHP", "debit_amount": "1"}],
        )
        _write_csv(
            self.folder / "b.csv",
            ["player_id", "currency", "debit_amount"],
            [{"player_id": "P2", "currency": "PHP", "debit_amount": "2"}],
        )
        rows = list(iter_raw_rows(self.folder))
        self.assertEqual([r["player_id"] for r in rows], ["P1", "P2"])


if __name__ == "__main__":
    unittest.main()
