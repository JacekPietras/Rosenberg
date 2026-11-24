import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/linters/normalize_document_filenames.py"
spec = importlib.util.spec_from_file_location("document_filenames", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DocumentFilenameTests(unittest.TestCase):
    def test_groups_are_renumbered_without_losing_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            names = ["1580.json", "1580_2.json", "1580_3.json", "1580_4.json",
                     "1580_5.json", "1580_6.json", "1580_99.json", "1600_4.json",
                     "1601.json", "1601-02.json", "1601-02-03.json", "bad.json"]
            for name in names:
                (directory / name).write_text(name)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual((1, True), module.normalize(directory))
            self.assertIn("bad.json: warning", output.getvalue())
            for index, original in enumerate(names[:7], 1):
                self.assertEqual(original, (directory / f"1580_{index}.json").read_text())
            self.assertEqual("1600_4.json", (directory / "1600_1.json").read_text())
            for name in names[8:]:
                self.assertTrue((directory / name).exists())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual((1, True), module.normalize(directory))
            self.assertNotIn("Renamed", output.getvalue())

    def test_colliding_suffix_spellings_keep_both_files(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ("1500_01.json", "1500_1.json"):
                (directory / name).write_text(name)
            with contextlib.redirect_stdout(io.StringIO()):
                module.normalize(directory)
            self.assertEqual({"1500_01.json", "1500_1.json"},
                             {p.read_text() for p in directory.iterdir()})
            self.assertEqual({"1500_1.json", "1500_2.json"},
                             {p.name for p in directory.iterdir()})


if __name__ == "__main__":
    unittest.main()
