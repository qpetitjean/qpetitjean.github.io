"""Review-count semantics, aggregation privacy, and remote build fallback."""
import json
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_reviews


class ReviewTests(unittest.TestCase):
    def test_only_submitted_reviews_count_and_private_fields_do_not_escape(self):
        row = {"Journal name": "Journal A", "Date review Submitted": datetime(2025, 3, 1),
               "Article title": "PRIVATE MANUSCRIPT", "Editor": "PRIVATE EDITOR"}
        result = sync_reviews.summarise([row, {**row, "Date review Submitted": None}],
                                       [{**row, "Date review Submitted": datetime(2026, 1, 2)}],
                                       {"Journal A": "https://example.org/"}, "2026-09-28")
        self.assertEqual(result["totals"], {"article": 1, "data": 1, "total": 2})
        self.assertEqual(result["journals"][0]["total"], 2)
        self.assertEqual([r["year"] for r in result["years"]], [2025, 2026])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_absent_default_workbook_uses_saved_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "summary.json"
            saved = {"updated": "2026-09-28", "totals": {"total": 46}}
            cache.write_text(json.dumps(saved), encoding="utf-8")
            with patch.object(sync_reviews, "WORKBOOK", root / "absent.xlsx"), patch.dict(sync_reviews.os.environ, {}, clear=True):
                self.assertEqual(sync_reviews.refresh(cache=cache), saved)
                with self.assertRaises(FileNotFoundError):
                    sync_reviews.refresh(root / "explicit-missing.xlsx", cache)


if __name__ == "__main__":
    unittest.main()
