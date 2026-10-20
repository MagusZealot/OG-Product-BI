import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


class TestWorkspaceModule(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self._sys_path_removed = []
        for p in list(sys.path):
            if str(WORKSPACE_ROOT / "src") == p or str((WORKSPACE_ROOT / "src").resolve()) == p:
                sys.path.remove(p)
                self._sys_path_removed.append(p)

    def tearDown(self):
        os.chdir(self._old_cwd)
        for p in self._sys_path_removed:
            sys.path.append(p)

    def _import_workspace_from(self, subdir):
        target = WORKSPACE_ROOT / "src" / subdir
        os.chdir(str(target))
        if str(WORKSPACE_ROOT / "src") not in sys.path:
            sys.path.insert(0, str(WORKSPACE_ROOT / "src"))
        if "workspace" in sys.modules:
            del sys.modules["workspace"]
        import workspace
        return workspace

    def test_exports_exist(self):
        ws = self._import_workspace_from("ingest")
        for name in ("WORKSPACE", "RAW_DIR", "OUTPUT_DIR", "PROGRESS_FILE", "update_progress"):
            self.assertTrue(hasattr(ws, name), f"missing export: {name}")

    def test_paths_resolve_to_workspace_root(self):
        ws = self._import_workspace_from("ingest")
        self.assertEqual(ws.WORKSPACE, WORKSPACE_ROOT)
        self.assertTrue((ws.WORKSPACE / "workspace_map.md").exists())
        self.assertEqual(ws.RAW_DIR, WORKSPACE_ROOT / "data" / "raw")
        self.assertEqual(ws.OUTPUT_DIR, WORKSPACE_ROOT / "output")
        self.assertEqual(ws.PROGRESS_FILE, WORKSPACE_ROOT / "output" / "progress.json")

    def test_importable_from_every_src_subdirectory(self):
        for subdir in ("ingest", "dashboard", "verify"):
            ws = self._import_workspace_from(subdir)
            self.assertEqual(ws.WORKSPACE, WORKSPACE_ROOT)
            self.assertTrue(callable(ws.update_progress))

    def test_update_progress_writes_progress_json(self):
        ws = self._import_workspace_from("ingest")
        with tempfile.TemporaryDirectory() as tmp:
            progress_file = Path(tmp) / "progress.json"
            ws.OUTPUT_DIR = Path(tmp)
            ws.PROGRESS_FILE = progress_file
            ws.update_progress("ingest", "loading exports", 42, {"file": "a.csv"})
            data = json.loads(progress_file.read_text(encoding="utf-8"))
            self.assertEqual(data["stage"], "ingest")
            self.assertEqual(data["message"], "loading exports")
            self.assertEqual(data["progress"], 42)
            self.assertEqual(data["details"], {"file": "a.csv"})
            self.assertIn("timestamp", data)

    def test_update_progress_defaults_details_to_empty_dict(self):
        ws = self._import_workspace_from("ingest")
        with tempfile.TemporaryDirectory() as tmp:
            progress_file = Path(tmp) / "progress.json"
            ws.OUTPUT_DIR = Path(tmp)
            ws.PROGRESS_FILE = progress_file
            ws.update_progress("stage", "msg", None)
            data = json.loads(progress_file.read_text(encoding="utf-8"))
            self.assertEqual(data["details"], {})


if __name__ == "__main__":
    unittest.main()
