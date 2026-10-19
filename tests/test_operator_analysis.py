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
import operator_analysis  # noqa: E402


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


HEADER = [
    "player_id", "currency", "formatted_debit_at",
    "debit_amount", "credit_amount", "winlose_amount", "operator_name",
]


class TestOperatorAnalysis(unittest.TestCase):
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
        operator_analysis.workspace = workspace

    def tearDown(self):
        self.tmp.cleanup()

    def test_imports_shared_modules(self):
        self.assertIs(operator_analysis.workspace, workspace)
        self.assertTrue(hasattr(operator_analysis.workspace, "update_progress"))
        self.assertTrue(callable(operator_analysis.workspace.update_progress))
        from ingest.io import iter_raw_rows  # noqa: F401
        self.assertTrue(callable(iter_raw_rows))

    def test_main_produces_expected_operator_csv(self):
        _write_csv(
            self.raw_dir / "export_01.csv",
            HEADER,
            [
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:00:00",
                 "debit_amount": "100", "credit_amount": "0", "winlose_amount": "-10", "operator_name": "Alpha"},
                {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:01:00",
                 "debit_amount": "200", "credit_amount": "0", "winlose_amount": "30", "operator_name": "Alpha"},
                {"player_id": "P2", "currency": "PHP", "formatted_debit_at": "2026-08-15 11:00:00",
                 "debit_amount": "50", "credit_amount": "0", "winlose_amount": "-5", "operator_name": "Beta"},
                {"player_id": "P3", "currency": "PHP", "formatted_debit_at": "2026-08-15 12:00:00",
                 "debit_amount": "300", "credit_amount": "0", "winlose_amount": "-50", "operator_name": "Alpha"},
            ],
        )
        rc = operator_analysis.main()
        self.assertEqual(rc, 0)

        out_file = self.out_dir / "operator_performance.csv"
        self.assertTrue(out_file.exists())
        lines = out_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            lines,
            [
                "Operator,Total_Bets,Total_Debit,Total_Winlose,Operator_ROI_%,Avg_Bet,Unique_Players,Countries",
                "Alpha,3,600.0,-30.0,95.0,200.0,2,Philippines",
                "Beta,1,50.0,-5.0,90.0,50.0,1,Philippines",
            ],
        )

    def test_missing_folder_returns_error_code(self):
        workspace.RAW_DIR = Path(self.tmp.name) / "does_not_exist"
        self.assertEqual(operator_analysis.main(), 1)

    def test_no_csv_files_returns_error_code(self):
        self.assertEqual(operator_analysis.main(), 1)

    def test_update_progress_writes_progress_file(self):
        _write_csv(self.raw_dir / "export_01.csv", HEADER, [
            {"player_id": "P1", "currency": "PHP", "formatted_debit_at": "2026-08-15 10:00:00",
             "debit_amount": "100", "credit_amount": "0", "winlose_amount": "-10", "operator_name": "Alpha"},
        ])
        operator_analysis.main()
        self.assertTrue(self.progress_file.exists())
        data = json.loads(self.progress_file.read_text(encoding="utf-8"))
        self.assertEqual(data["stage"], "operator_analysis")
        self.assertEqual(data["progress"], 100)


if __name__ == "__main__":
    unittest.main()
