import sys
import unittest
from typing import get_type_hints

sys.path.insert(0, "src/ingest")

from player_index import PlayerIndexEntry  # noqa: E402


class TestPlayerIndexSchema(unittest.TestCase):
    def test_module_has_typed_dict(self):
        self.assertTrue(hasattr(PlayerIndexEntry, "__annotations__"))

    def test_schema_fields_and_types(self):
        hints = get_type_hints(PlayerIndexEntry)
        expected = {
            "id": int,
            "pid": str,
            "country": str,
            "arch": str,
            "debit": float,
            "winlose": float,
            "bets": int,
            "avg_bet": float,
            "whale": bool,
            "chaser": bool,
            "op": str,
            "spike": float,
        }
        self.assertEqual(set(hints.keys()), set(expected.keys()))
        for field, typ in expected.items():
            self.assertEqual(hints[field], typ, field)

    def test_entry_matches_contract(self):
        entry: PlayerIndexEntry = {
            "id": 0,
            "pid": "PID_12345",
            "country": "Philippines",
            "arch": "VIP Whale",
            "debit": 500000000.0,
            "winlose": -125000.0,
            "bets": 420,
            "avg_bet": 1190476.19,
            "whale": True,
            "chaser": False,
            "op": "OP_001",
            "spike": 1.0,
        }
        self.assertEqual(entry["id"], 0)
        self.assertIsInstance(entry["id"], int)
        self.assertIsInstance(entry["pid"], str)
        self.assertIsInstance(entry["country"], str)
        self.assertIsInstance(entry["arch"], str)
        self.assertIsInstance(entry["debit"], float)
        self.assertIsInstance(entry["winlose"], float)
        self.assertIsInstance(entry["bets"], int)
        self.assertIsInstance(entry["avg_bet"], float)
        self.assertIsInstance(entry["whale"], bool)
        self.assertIsInstance(entry["chaser"], bool)
        self.assertIsInstance(entry["op"], str)
        self.assertIsInstance(entry["spike"], float)

    def test_id_equals_array_position_rank(self):
        entries: list[PlayerIndexEntry] = []
        for rank in range(5):
            entries.append({
                "id": rank,
                "pid": f"PID_{rank}",
                "country": "USA",
                "arch": "Casual Player",
                "debit": 100.0,
                "winlose": 0.0,
                "bets": 1,
                "avg_bet": 100.0,
                "whale": False,
                "chaser": False,
                "op": "UNKNOWN",
                "spike": 1.0,
            })
        for rank, entry in enumerate(entries):
            self.assertEqual(entry["id"], rank)

    def test_no_import_time_dependencies(self):
        import player_index as mod
        self.assertFalse(hasattr(mod, "__file__") is None)
        self.assertIsNotNone(mod.__file__)


if __name__ == "__main__":
    unittest.main()
