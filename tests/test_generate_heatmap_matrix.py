import csv
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
import generate_heatmap_matrix  # noqa: E402


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


class TestGenerateHeatmapMatrix(unittest.TestCase):
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
        generate_heatmap_matrix.workspace = workspace

    def tearDown(self):
        self.tmp.cleanup()

    def test_imports_shared_modules(self):
        self.assertIs(generate_heatmap_matrix.workspace, workspace)
        self.assertTrue(hasattr(generate_heatmap_matrix.workspace, "update_progress"))
        self.assertTrue(callable(generate_heatmap_matrix.workspace.update_progress))
        from ingest.io import iter_raw_rows  # noqa: F401
        self.assertTrue(callable(iter_raw_rows))

    def test_main_produces_expected_heatmap_csv(self):
        _write_csv(
            self.raw_dir / "export_01.csv",
            HEADER,
            [
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:00:00",
                 "debit_amount": "100", "credit_amount": "0", "winlose_amount": "-10",
                 "game_name": "Baccarat", "operator_name": "Alpha"},
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:30:00",
                 "debit_amount": "200", "credit_amount": "0", "winlose_amount": "30",
                 "game_name": "Baccarat", "operator_name": "Alpha"},
                {"player_id": "P2", "currency": "PHP", "formatted_debit_at": "2026-08-15 14:00:00",
                 "debit_amount": "50", "credit_amount": "0", "winlose_amount": "-5",
                 "game_name": "Roulette", "operator_name": "Beta"},
                {"player_id": "P3", "currency": "PHP", "formatted_debit_at": "2026-08-15 14:59:59",
                 "debit_amount": "300", "credit_amount": "0", "winlose_amount": "-50",
                 "game_name": "Roulette", "operator_name": "Alpha"},
                {"player_id": "P4", "currency": "PHP", "formatted_debit_at": "",
                 "debit_amount": "100", "credit_amount": "0", "winlose_amount": "0",
                 "game_name": "Baccarat", "operator_name": "Beta"},
                {"player_id": "P5", "currency": "PHP", "formatted_debit_at": "2026-08-15 23:00:00",
                 "debit_amount": "75", "credit_amount": "0", "winlose_amount": "-75",
                 "game_name": "Slots", "operator_name": "Alpha"},
            ],
        )
        rc = generate_heatmap_matrix.main()
        self.assertEqual(rc, 0)

        out_file = self.out_dir / "country_hourly_heatmap.csv"
        self.assertTrue(out_file.exists())
        lines = out_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines,
            [
                "Country,00:00,01:00,02:00,03:00,04:00,05:00,06:00,07:00,08:00,09:00,"
                "10:00,11:00,12:00,13:00,14:00,15:00,16:00,17:00,18:00,19:00,20:00,"
                "21:00,22:00,23:00,Total",
                "Philippines,0,0,0,0,0,0,0,0,0,0,2,0,0,0,2,0,0,0,0,0,0,0,0,1,5",
            ],
        )

    def test_update_progress_writes_progress_file(self):
        _write_csv(self.raw_dir / "export_01.csv", HEADER, [
            {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:00:00",
             "debit_amount": "100", "credit_amount": "0", "winlose_amount": "-10",
             "game_name": "Baccarat", "operator_name": "Alpha"},
        ])
        generate_heatmap_matrix.main()
        self.assertTrue(self.progress_file.exists())
        import json
        data = json.loads(self.progress_file.read_text(encoding="utf-8"))
        self.assertEqual(data["stage"], "heatmap_matrix")
        self.assertEqual(data["progress"], 100)


if __name__ == "__main__":
    unittest.main()
