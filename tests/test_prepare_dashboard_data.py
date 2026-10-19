import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DASHBOARD = REPO_ROOT / "src" / "dashboard"
SRC_INGEST = REPO_ROOT / "src" / "ingest"
for _p in (str(SRC_DASHBOARD), str(SRC_INGEST)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import prepare_dashboard_data  # noqa: E402
from player_index import PlayerIndexEntry  # noqa: E402


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestPrepareDashboardDataImportsSharedSchema(unittest.TestCase):
    def test_imports_player_index_entry(self):
        import inspect
        source = inspect.getsource(prepare_dashboard_data)
        self.assertIn("PlayerIndexEntry", source)
        self.assertIn("from player_index import", source)

    def test_player_index_entry_is_player_index_type(self):
        self.assertIs(prepare_dashboard_data.PlayerIndexEntry, PlayerIndexEntry)

    def test_chasers_list_typed_as_player_index_entry(self):
        import inspect
        source = inspect.getsource(prepare_dashboard_data)
        self.assertIn("list[PlayerIndexEntry]", source)


class TestPrepareDashboardDataOutput(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tmp.name) / "output"
        self.output_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_inputs(self):
        _write_csv(
            self.output_dir / "whale_analysis.csv",
            ["player_id", "total_debit", "total_bets", "avg_session_hours", "session_count", "countries"],
            [
                {"player_id": "W1", "total_debit": "1000000.0", "total_bets": "500", "avg_session_hours": "2.5", "session_count": "10", "countries": "PH"},
                {"player_id": "W2", "total_debit": "500000.0", "total_bets": "200", "avg_session_hours": "1.5", "session_count": "5", "countries": "US"},
            ],
        )
        _write_csv(
            self.output_dir / "chaser_detection.csv",
            ["player_id", "total_bets", "chase_events", "max_consecutive_losses", "avg_loss_debit", "spike_debit", "spike_multiplier", "total_debit", "total_winlose"],
            [
                {"player_id": "C1", "total_bets": "100", "chase_events": "3", "max_consecutive_losses": "5", "avg_loss_debit": "100.0", "spike_debit": "500.0", "spike_multiplier": "5.0", "total_debit": "10000.0", "total_winlose": "-5000.0"},
                {"player_id": "C2", "total_bets": "200", "chase_events": "1", "max_consecutive_losses": "2", "avg_loss_debit": "50.0", "spike_debit": "200.0", "spike_multiplier": "2.0", "total_debit": "20000.0", "total_winlose": "1000.0"},
            ],
        )
        _write_csv(
            self.output_dir / "hourly_traffic.csv",
            ["Hour", "Total_Bets"],
            [
                {"Hour": "00", "Total_Bets": "100"},
                {"Hour": "01", "Total_Bets": "80"},
            ],
        )
        _write_csv(
            self.output_dir / "time_series_analysis.csv",
            ["Country", "Total_Bets", "Peak_Hour", "Peak_Bets", "Peak_Percentage"],
            [
                {"Country": "PH", "Total_Bets": "5000", "Peak_Hour": "20", "Peak_Bets": "500", "Peak_Percentage": "10.0"},
                {"Country": "US", "Total_Bets": "3000", "Peak_Hour": "15", "Peak_Bets": "400", "Peak_Percentage": "13.3"},
            ],
        )
        heatmap_header = ["Country"] + [f"{h:02d}" for h in range(24)]
        _write_csv(
            self.output_dir / "country_hourly_heatmap.csv",
            heatmap_header,
            [
                {"Country": "PH", **{f"{h:02d}": str(h * 10) for h in range(24)}},
                {"Country": "US", **{f"{h:02d}": str(h * 5) for h in range(24)}},
            ],
        )
        _write_csv(
            self.output_dir / "operator_performance.csv",
            ["Operator", "Total_Bets", "Total_Debit", "Total_Winlose", "Operator_ROI_%", "Avg_Bet", "Unique_Players", "Countries"],
            [
                {"Operator": "OpA", "Total_Bets": "1000", "Total_Debit": "50000000.0", "Total_Winlose": "-5000000.0", "Operator_ROI_%": "90.0", "Avg_Bet": "50000.0", "Unique_Players": "100", "Countries": "PH, US"},
                {"Operator": "OpB", "Total_Bets": "500", "Total_Debit": "30000000.0", "Total_Winlose": "-2000000.0", "Operator_ROI_%": "93.33", "Avg_Bet": "60000.0", "Unique_Players": "80", "Countries": "PH"},
            ],
        )

    def test_output_has_expected_sections(self):
        self._write_inputs()
        result = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        self.assertIn("metadata", result)
        self.assertIn("whales", result)
        self.assertIn("chasers", result)
        self.assertIn("traffic", result)
        self.assertIn("operators", result)

    def test_output_is_deterministic_across_runs(self):
        self._write_inputs()
        result1 = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        result2 = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        self.assertEqual(result1, result2)

    def test_whales_section_values(self):
        self._write_inputs()
        result = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        self.assertEqual(len(result["whales"]["top_20"]), 2)
        self.assertEqual(result["whales"]["top_20"][0]["player_id"], "W1")
        self.assertEqual(result["whales"]["top_20"][0]["total_debit"], 1000000.0)

    def test_chasers_section_values(self):
        self._write_inputs()
        result = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        self.assertEqual(result["chasers"]["total_count"], 2)
        self.assertEqual(result["chasers"]["net_losers"], 1)
        self.assertEqual(result["chasers"]["net_winners"], 1)

    def test_operators_section_values(self):
        self._write_inputs()
        result = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        self.assertEqual(len(result["operators"]["top_50"]), 2)
        self.assertEqual(result["operators"]["top_50"][0]["operator"], "OpA")

    def test_traffic_section_values(self):
        self._write_inputs()
        result = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        self.assertEqual(len(result["traffic"]["hourly_curve"]), 2)
        self.assertEqual(result["traffic"]["hourly_curve"][0]["hour"], "00")
        self.assertEqual(result["traffic"]["hourly_curve"][0]["bets"], 100)

    def test_metadata_values(self):
        self._write_inputs()
        result = prepare_dashboard_data.prepare_dashboard_data(self.output_dir)
        self.assertEqual(result["metadata"]["total_whales"], 20)
        self.assertEqual(result["metadata"]["total_operators"], 2)
        self.assertEqual(result["metadata"]["total_chasers"], 2)


if __name__ == "__main__":
    unittest.main()
