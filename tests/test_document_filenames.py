import contextlib
import importlib.util
import io
import subprocess
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
            subprocess.run(['git', 'init', '-q', str(directory)], check=True)
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

    def test_renames_stage_only_affected_tracked_and_untracked_files(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            subprocess.run(['git', 'init', '-q', str(directory)], check=True)
            (directory / '1500_4.json').write_text('tracked')
            subprocess.run(['git', 'add', '1500_4.json'], cwd=directory, check=True)
            subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                            'commit', '-qm', 'initial'], cwd=directory, check=True)
            (directory / '1600_4.json').write_text('untracked')
            (directory / 'unrelated.json').write_text('unrelated')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual((1, True), module.normalize(directory))
            staged = subprocess.run(['git', 'diff', '--cached', '--no-renames', '--name-only'],
                                    cwd=directory, capture_output=True, text=True, check=True)
            self.assertEqual(['1500_1.json', '1500_4.json', '1600_1.json'], staged.stdout.splitlines())

    def test_colliding_suffix_spellings_keep_both_files(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            subprocess.run(['git', 'init', '-q', str(directory)], check=True)
            for name in ("1500_01.json", "1500_1.json"):
                (directory / name).write_text(name)
            with contextlib.redirect_stdout(io.StringIO()):
                module.normalize(directory)
            self.assertEqual({"1500_01.json", "1500_1.json"},
                             {p.read_text() for p in directory.glob("*.json")})
            self.assertEqual({"1500_1.json", "1500_2.json"},
                             {p.name for p in directory.glob("*.json")})

    def test_renumbering_preserves_filenames_reserved_by_deleted_documents(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            subprocess.run(['git', 'init', '-q', str(directory)], check=True)
            deleted = directory / "deleted"
            deleted.mkdir()
            (deleted / "1500_1.json").write_text("deleted")
            (directory / "1500_4.json").write_text("active")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual((0, True), module.normalize(directory))
            self.assertEqual("active", (directory / "1500_2.json").read_text())
            self.assertEqual("deleted", (deleted / "1500_1.json").read_text())


if __name__ == "__main__":
    unittest.main()
