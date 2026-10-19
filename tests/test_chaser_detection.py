import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
SRC_INGEST = REPO_ROOT / "src" / "ingest"
for p in (str(SRC), str(SRC_INGEST)):
    if p not in sys.path:
        sys.path.insert(0, p)

import workspace  # noqa: E402
import chaser_detection  # noqa: E402


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


HEADER = [
    "player_id", "currency", "formatted_debit_at",
    "debit_amount", "credit_amount", "winlose_amount",
    "game_name", "operator_name",
]


class TestChaserDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw_dir = Path(self.tmp.name) / "raw"
        self.raw_dir.mkdir()
        self.out_dir = Path(self.tmp.name) / "output"
        self.out_dir.mkdir()
        self.progress_file = self.out_dir / "progress.json"
        workspace.RAW_DIR = self.raw_dir
        workspace.OUTPUT_DIR = self.out_dir
        workspace.PROGRESS_FILE = self.progress_file
        chaser_detection.workspace = workspace

    def tearDown(self):
        self.tmp.cleanup()

    def test_imports_shared_modules(self):
        self.assertIs(chaser_detection.workspace, workspace)
        self.assertTrue(hasattr(chaser_detection.workspace, "update_progress"))
        self.assertTrue(callable(chaser_detection.workspace.update_progress))
        from ingest.io import iter_raw_rows  # noqa: F401
        self.assertTrue(callable(iter_raw_rows))

    def test_main_produces_expected_chaser_csv(self):
        _write_csv(
            self.raw_dir / "export_01.csv",
            HEADER,
            [
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:00:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Baccarat", "operator_name": "Alpha"},
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:01:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Baccarat", "operator_name": "Alpha"},
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:02:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Baccarat", "operator_name": "Alpha"},
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:03:00",
                 "debit_amount": "35", "credit_amount": "0", "winlose_amount": "35",
                 "game_name": "Baccarat", "operator_name": "Alpha"},
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:04:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Baccarat", "operator_name": "Alpha"},
                {"player_id": "P2", "currency": "PHP", "formatted_debit_at": "2026-08-15 11:00:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Roulette", "operator_name": "Beta"},
                {"player_id": "P2", "currency": "PHP", "formatted_debit_at": "2026-08-15 11:01:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Roulette", "operator_name": "Beta"},
                {"player_id": "P2", "currency": "PHP", "formatted_debit_at": "2026-08-15 11:02:00",
                 "debit_amount": "35", "credit_amount": "0", "winlose_amount": "35",
                 "game_name": "Roulette", "operator_name": "Beta"},
                {"player_id": "P2", "currency": "PHP", "formatted_debit_at": "2026-08-15 11:03:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Roulette", "operator_name": "Beta"},
                {"player_id": "P2", "currency": "PHP", "formatted_debit_at": "2026-08-15 11:04:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Roulette", "operator_name": "Beta"},
                {"player_id": "P3", "currency": "PHP", "formatted_debit_at": "2026-08-15 12:00:00",
                 "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Slots", "operator_name": "Gamma"},
            ],
        )
        rc = chaser_detection.main()
        self.assertEqual(rc, 0)

        out_file = self.out_dir / "chaser_detection.csv"
        self.assertTrue(out_file.exists())
        lines = out_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines,
            [
                "player_id,total_bets,chase_events,max_consecutive_losses,avg_loss_debit,"
                "spike_debit,spike_multiplier,total_debit,total_winlose",
                "P1,5,1,3,10.0,35.0,3.5,75.0,-5.0",
            ],
        )

    def test_missing_folder_returns_error_code(self):
        workspace.RAW_DIR = Path(self.tmp.name) / "does_not_exist"
        self.assertEqual(chaser_detection.main(), 1)

    def test_no_csv_files_returns_error_code(self):
        self.assertEqual(chaser_detection.main(), 1)

    def test_update_progress_writes_progress_file(self):
        _write_csv(self.raw_dir / "export_01.csv", HEADER, [
            {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:00:00",
             "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
             "game_name": "Baccarat", "operator_name": "Alpha"},
            {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:01:00",
             "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
             "game_name": "Baccarat", "operator_name": "Alpha"},
            {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:02:00",
             "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
             "game_name": "Baccarat", "operator_name": "Alpha"},
            {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:03:00",
             "debit_amount": "35", "credit_amount": "0", "winlose_amount": "35",
             "game_name": "Baccarat", "operator_name": "Alpha"},
            {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:04:00",
             "debit_amount": "10", "credit_amount": "0", "winlose_amount": "-10",
             "game_name": "Baccarat", "operator_name": "Alpha"},
        ])
        chaser_detection.main()
        self.assertTrue(self.progress_file.exists())
        data = json.loads(self.progress_file.read_text(encoding="utf-8"))
        self.assertEqual(data["stage"], "chaser_detection")
        self.assertEqual(data["progress"], 100)


if __name__ == "__main__":
    unittest.main()
