import json
from pathlib import Path
import tempfile
import unittest

from scripts.linters.normalize_sources import normalize


class NormalizeSourcesTest(unittest.TestCase):
    def test_citations_and_unrelated_text(self):
        original = {
            "source": ["D Nr. 456, Verweisung", "Generallandesarchiv Karlsruhe {D Nr. 456}",
                       "Generallandesarchiv Karlsruhe D Nr. 456", "Other archive"],
            "german": "{D Nr. 456, Verweisung}",
            "nested": {"source": "Archive {B 1, Verweisung}"},
            "trailing": {"source": ["Archive B 2 Verweisung", "Archive B 3 Verweisung 1"]},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.json"
            path.write_text(json.dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.assertTrue(normalize(path))
            result = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(result["source"], ["Generallandesarchiv Karlsruhe D Nr. 456", "Other archive"])
            self.assertEqual(result["german"], original["german"])
            self.assertEqual(result["nested"]["source"], "Archive B 1")
            self.assertEqual(result["trailing"]["source"], ["Archive B 2", "Archive B 3 Verweisung 1"])
            self.assertFalse(normalize(path))


if __name__ == "__main__":
    unittest.main()
