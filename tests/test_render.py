import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, "src/dashboard")

from render import render_dashboard  # noqa: E402


class TestRenderDashboardSignature(unittest.TestCase):
    def test_signature_matches_spec(self):
        import inspect
        sig = inspect.signature(render_dashboard)
        self.assertEqual(list(sig.parameters.keys()),
                         ["data_file", "sections_dir", "output_html",
                          "title", "extra_scripts"])

    def test_no_defaults(self):
        import inspect
        sig = inspect.signature(render_dashboard)
        for name, param in sig.parameters.items():
            self.assertIs(param.default, inspect.Parameter.empty, name)


class TestRenderDashboardOutput(unittest.TestCase):
    def setUp(self):
        self.tmp = Path("tests/_render_tmp")
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.data_file = self.tmp / "payload.json"
        payload = {"meta": {"total_players": 3}, "players": []}
        self.data_file.write_text(json.dumps(payload), encoding="utf-8")
        self.sections_dir = self.tmp / "sections"
        self.sections_dir.mkdir()
        (self.sections_dir / "nav_buttons.html").write_text(
            '<button onclick="switchTab(\'players\')">6. Player Dossiers</button>',
            encoding="utf-8")
        (self.sections_dir / "tab_players.html").write_text(
            '<section id="tab-players">players tab</section>', encoding="utf-8")
        (self.sections_dir / "tab_operators.html").write_text(
            '<section id="tab-opdossiers">operators tab</section>',
            encoding="utf-8")
        (self.sections_dir / "slides.html").write_text(
            '<div id="slide-7">slide 7</div>', encoding="utf-8")
        (self.sections_dir / "dossier.js").write_text(
            "let DOSSIER = null;", encoding="utf-8")
        self.output_html = self.tmp / "out.html"

    def test_writes_output_file(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard", "")
        self.assertTrue(self.output_html.exists())

    def test_embeds_json_payload(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard", "")
        html = self.output_html.read_text(encoding="utf-8")
        self.assertIn('<script id="dashboard-raw-data" type="application/json">', html)
        self.assertIn('"total_players": 3', html)

    def test_injects_section_components(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard", "")
        html = self.output_html.read_text(encoding="utf-8")
        self.assertIn('6. Player Dossiers', html)
        self.assertIn('players tab', html)
        self.assertIn('operators tab', html)
        self.assertIn('slide 7', html)
        self.assertIn("let DOSSIER = null;", html)

    def test_title_in_output(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard", "")
        html = self.output_html.read_text(encoding="utf-8")
        self.assertIn("<title>My Dashboard</title>", html)

    def test_get_chart_theme_wired(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard", "")
        html = self.output_html.read_text(encoding="utf-8")
        self.assertIn("function getChartTheme()", html)
        self.assertIn("bg: 'transparent'", html)
        self.assertIn("textColor", html)

    def test_extra_scripts_injected(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard",
                         "<script>console.log('extra');</script>")
        html = self.output_html.read_text(encoding="utf-8")
        self.assertIn("console.log('extra')", html)

    def test_page_initialization(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard", "")
        html = self.output_html.read_text(encoding="utf-8")
        self.assertIn("DOMContentLoaded", html)
        self.assertIn("initCharts()", html)

    def test_echarts_and_tailwind_cdn(self):
        render_dashboard(self.data_file, self.sections_dir, self.output_html,
                         "My Dashboard", "")
        html = self.output_html.read_text(encoding="utf-8")
        self.assertIn("echarts.min.js", html)
        self.assertIn("tailwindcss.com", html)

    def tearDown(self):
        import shutil
        if self.tmp.exists():
            shutil.rmtree(self.tmp)


if __name__ == "__main__":
    unittest.main()
