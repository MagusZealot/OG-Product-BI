import json
import os
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

import importlib.util

SPEC = importlib.util.spec_from_file_location("assemble_index", REPO_ROOT / "assemble_index.py")
ASSEMBLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSEMBLE)


def _write_index(path, players, source_file="export", total_rows=None, chunk_size=1000):
    path.parent.mkdir(parents=True, exist_ok=True)
    if total_rows is None:
        total_rows = sum(p.get("bets", 0) for p in players)
    meta = {
        "total_players": len(players),
        "total_rows": total_rows,
        "source_file": source_file,
        "generated": "2026-01-01 00:00:00",
        "chunk_size": chunk_size,
        "total_chunks": (len(players) + chunk_size - 1) // chunk_size,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "players": players}, f, ensure_ascii=False)


class TestAssembleIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        ASSEMBLE.WORKSPACE = self.root
        ASSEMBLE.INDEX_DIR = self.root / "output" / "data"
        ASSEMBLE.CHUNK_SRC_DIR = self.root / "output" / "chunks"
        ASSEMBLE.OUTPUT_INDEX = self.root / "output" / "data" / "all_players_index.json"
        ASSEMBLE.OUTPUT_CHUNK_DIR = self.root / "output" / "chunks" / "dossier_chunks"

    def tearDown(self):
        self.tmp.cleanup()

    def test_merge_concatenates_all_per_export_indexes(self):
        p1 = [
            {"id": 0, "pid": "A", "debit": 100.0, "bets": 1},
            {"id": 1, "pid": "B", "debit": 50.0, "bets": 1},
        ]
        p2 = [{"id": 0, "pid": "C", "debit": 200.0, "bets": 1}]
        _write_index(ASSEMBLE.INDEX_DIR / "all_players_index_00.json", p1, "00")
        _write_index(ASSEMBLE.INDEX_DIR / "all_players_index_01.json", p2, "01")

        ASSEMBLE.assemble()

        with open(ASSEMBLE.OUTPUT_INDEX, encoding="utf-8") as f:
            data = json.load(f)
        pids = [p["pid"] for p in data["players"]]
        self.assertEqual(set(pids), {"A", "B", "C"})
        self.assertEqual(data["meta"]["total_players"], 3)
        self.assertEqual(data["meta"]["total_rows"], 3)
        debits = [p["debit"] for p in data["players"]]
        self.assertEqual(debits, sorted(debits, reverse=True))

    def test_re_ranks_by_total_debit_desc(self):
        players = [
            {"id": 0, "pid": "LOW", "debit": 10.0, "bets": 1},
            {"id": 1, "pid": "HIGH", "debit": 999.0, "bets": 1},
            {"id": 2, "pid": "MID", "debit": 500.0, "bets": 1},
        ]
        _write_index(ASSEMBLE.INDEX_DIR / "all_players_index_00.json", players, "00")

        ASSEMBLE.assemble()

        with open(ASSEMBLE.OUTPUT_INDEX, encoding="utf-8") as f:
            data = json.load(f)
        debits = [p["debit"] for p in data["players"]]
        self.assertEqual(debits, [999.0, 500.0, 10.0])
        self.assertEqual(data["players"][0]["pid"], "HIGH")

    def test_reassigns_id_as_array_position_after_rerank(self):
        players = [
            {"id": 5, "pid": "P5", "debit": 50.0, "bets": 1},
            {"id": 2, "pid": "P2", "debit": 80.0, "bets": 1},
        ]
        _write_index(ASSEMBLE.INDEX_DIR / "all_players_index_00.json", players, "00")

        ASSEMBLE.assemble()

        data = json.load(open(ASSEMBLE.OUTPUT_INDEX, encoding="utf-8"))
        for idx, p in enumerate(data["players"]):
            self.assertEqual(p["id"], idx)
        self.assertEqual(data["players"][0]["pid"], "P2")

    def test_copies_each_per_export_chunk_into_dossier_chunks(self):
        chunk_dir = ASSEMBLE.CHUNK_SRC_DIR / "dossier_chunks_00"
        chunk_dir.mkdir(parents=True)
        (chunk_dir / "chunk_0000.js").write_text("window.DOSSIER_CHUNK_0000 = {};", encoding="utf-8")
        (chunk_dir / "chunk_0001.js").write_text("window.DOSSIER_CHUNK_0001 = {};", encoding="utf-8")
        _write_index(ASSEMBLE.INDEX_DIR / "all_players_index_00.json", [{"id": 0, "pid": "A", "debit": 1.0, "bets": 1}], "00")

        ASSEMBLE.assemble()

        self.assertTrue((ASSEMBLE.OUTPUT_CHUNK_DIR / "chunk_0000.js").exists())
        self.assertTrue((ASSEMBLE.OUTPUT_CHUNK_DIR / "chunk_0001.js").exists())
        self.assertEqual(
            (ASSEMBLE.OUTPUT_CHUNK_DIR / "chunk_0000.js").read_text(encoding="utf-8"),
            "window.DOSSIER_CHUNK_0000 = {};",
        )

    def test_skip_guard_skips_when_output_newer_than_all_sources(self):
        players = [{"id": 0, "pid": "A", "debit": 1.0, "bets": 1}]
        _write_index(ASSEMBLE.INDEX_DIR / "all_players_index_00.json", players, "00")
        out_dir = ASSEMBLE.OUTPUT_INDEX.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        ASSEMBLE.OUTPUT_INDEX.write_text("PRE-EXISTING", encoding="utf-8")
        os.utime(ASSEMBLE.OUTPUT_INDEX, None)
        source = ASSEMBLE.INDEX_DIR / "all_players_index_00.json"
        os.utime(source, (1, 1))

        self.assertTrue(ASSEMBLE.should_skip())
        ASSEMBLE.assemble()
        self.assertEqual(ASSEMBLE.OUTPUT_INDEX.read_text(encoding="utf-8"), "PRE-EXISTING")

    def test_not_skip_when_source_newer_than_output(self):
        players = [{"id": 0, "pid": "A", "debit": 1.0, "bets": 1}]
        _write_index(ASSEMBLE.INDEX_DIR / "all_players_index_00.json", players, "00")
        out_dir = ASSEMBLE.OUTPUT_INDEX.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        ASSEMBLE.OUTPUT_INDEX.write_text("{}", encoding="utf-8")
        os.utime(ASSEMBLE.OUTPUT_INDEX, (1, 1))

        self.assertFalse(ASSEMBLE.should_skip())

    def test_not_skip_when_no_per_export_indexes(self):
        self.assertFalse(ASSEMBLE.should_skip())


if __name__ == "__main__":
    unittest.main()
