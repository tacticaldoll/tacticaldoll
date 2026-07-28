import importlib.util
import json
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_dashboard", ROOT / "scripts/generate_dashboard.py"
)
dashboard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(dashboard)


class DashboardTest(unittest.TestCase):
    def test_generated_svg_is_well_formed_and_contains_profile_data(self):
        config = json.loads((ROOT / "profile.json").read_text())
        payload = json.loads((ROOT / "tests/fixtures/github.json").read_text())
        generated = dashboard.build_dashboard(
            config, payload, datetime(2026, 7, 28, tzinfo=timezone.utc)
        )

        ET.fromstring(generated)
        self.assertIn("tacticaldoll", generated)
        self.assertIn("tianheng", generated)
        self.assertIn("PRIMARY STACK", generated)
        self.assertNotIn("tacticaldoll</text>\n        <text x=\"212\"", generated)


if __name__ == "__main__":
    unittest.main()
