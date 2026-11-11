import importlib.util
import builtins
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from protein_vis.cli import main
from protein_vis.pipeline import file_digest, render_key
from protein_vis.spec import load_spec
from test_spec import SPEC


class CliTests(unittest.TestCase):
    def test_validate_needs_no_pymol_and_reports_bad_specs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "figure.toml"
            path.write_text(SPEC)
            (root / "model.pdb").write_text("END\n")
            with patch.dict("sys.modules", {"pymol": None, "pymol2": None}), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(["validate", str(path)]), 0)
                self.assertIn("1 panel", out.getvalue())
            path.write_text(SPEC.replace('version = 1', 'version = 2'))
            with redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["validate", str(path)]), 2)
                self.assertIn("version", err.getvalue())

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Matplotlib is not installed")
    def test_composition_without_pymol_preserves_full_frame_and_exports(self):
        from PIL import Image
        from matplotlib.figure import Figure
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "figure.toml"
            path.write_text(SPEC.replace('title = "A complex"', 'title = "A complex"\nconclusion = "Predicted binding mode"').replace(
                'title = "Partner in context"', 'title = "Partner in context"\nsummary = "Candidate one"\nmetrics = { iPTM = 0.82 }'))
            (root / "model.pdb").write_text("END\n")
            spec = load_spec(path)
            (spec.output / "frames").mkdir(parents=True)
            (spec.output / "sessions").mkdir()
            Image.new("RGBA", (300, 200), (42, 120, 214, 255)).save(spec.output / "frames/overview.png")
            (spec.output / "sessions/overview.pse").write_bytes(b"fixture")
            (spec.output / "contacts.json").write_text("{}")
            artifacts = {name: file_digest(spec.output / name) for name in
                         ("frames/overview.png", "sessions/overview.pse", "contacts.json")}
            (spec.output / "manifest.json").write_text(json.dumps({"render_key": render_key(spec), "artifacts": artifacts}))
            displayed = []
            savefig = Figure.savefig
            def capture(figure, *args, **kwargs):
                displayed.extend(text.get_text() for text in figure.texts)
                displayed.extend(text.get_text() for axis in figure.axes for text in axis.texts)
                return savefig(figure, *args, **kwargs)
            original_import = builtins.__import__
            def without_pymol(name, *args, **kwargs):
                if name.split(".")[0] in {"pymol", "pymol2"}:
                    raise ImportError(f"unexpected PyMOL import: {name}")
                return original_import(name, *args, **kwargs)
            with patch.object(Figure, "savefig", capture), patch("builtins.__import__", side_effect=without_pymol), redirect_stdout(io.StringIO()):
                self.assertEqual(main(["compose", str(path)]), 0)
            self.assertTrue(any("iPTM: 0.82" in text and "Candidate one" in text for text in displayed))
            self.assertTrue(any("Predicted binding mode" in text for text in displayed))
            self.assertTrue((spec.output / "figure.pdf").read_bytes().startswith(b"%PDF"))
            self.assertEqual(Image.open(spec.output / "figure.png").size[0], 2160)
            self.assertTrue((spec.output / "resolved-spec.json").is_file())
            if shutil.which("pdftotext"):
                pdf_text = subprocess.check_output(["pdftotext", str(spec.output / "figure.pdf"), "-"], text=True)
                self.assertIn("iPTM: 0.82", pdf_text)
                self.assertIn("Candidate one", pdf_text)
                self.assertIn("Predicted binding mode", pdf_text)


if __name__ == "__main__":
    unittest.main()
