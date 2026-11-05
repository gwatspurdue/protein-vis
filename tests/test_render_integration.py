"""Real headless rendering checks, enabled by `uv sync --extra render`."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from protein_vis.pipeline import build, cached_manifest, render
from protein_vis.spec import SpecError, load_spec


HAS_RENDER = importlib.util.find_spec("pymol2") is not None
HAS_COMPOSE = importlib.util.find_spec("matplotlib") is not None
EXAMPLE = Path(__file__).resolve().parents[1] / "examples/interaction.toml"


@unittest.skipUnless(HAS_RENDER and HAS_COMPOSE, "Install rendering dependencies with uv sync --extra render")
class HeadlessRenderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "figure.toml"
        self.content = EXAMPLE.read_text().replace(
            '"data/9cht-ac.pdb"', json.dumps(str(EXAMPLE.parent / "data/9cht-ac.pdb"))
        ).replace('"../figures/interaction"', '"output"').replace(
            'width = 1400', 'width = 320'
        ).replace('height = 1100', 'height = 260')
        self.path.write_text(self.content)

    def test_actual_scene_output_contacts_and_recomposition_without_pymol(self):
        from PIL import Image
        spec = load_spec(self.path)
        paths, reused = build(spec)
        self.assertFalse(reused)
        self.assertEqual(len(paths), 2)
        manifest = cached_manifest(spec)
        self.assertEqual(set(manifest["views"]), {"context", "interface"})
        self.assertEqual(len(manifest["views"]["context"]), 18)
        contacts = json.loads((spec.output / "contacts.json").read_text())
        self.assertTrue(contacts["panels"]["context"])
        self.assertTrue(any(c["target"]["resi"] == "406" for c in contacts["panels"]["context"]))
        with Image.open(spec.output / "frames/context.png") as image:
            self.assertEqual(image.size, (320, 260))
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
        self.path.write_text(self.content.replace('title = "E6 in context"', 'title = "Updated caption"'))
        with patch.dict("sys.modules", {"pymol2": None, "pymol": None}):
            _, reused = build(load_spec(self.path))
        self.assertTrue(reused)

    def test_empty_and_overlapping_selections_are_errors(self):
        for old, new, message in (
            ('target = "chain A"', 'target = "chain Z"', "no heavy atoms"),
            ('partner = "chain C"', 'partner = "chain A"', "overlap"),
            ('resi 468-472"', 'resi 403-424"', "overlap"),
        ):
            with self.subTest(message=message):
                self.path.write_text(self.content.replace(old, new))
                with self.assertRaisesRegex(SpecError, message):
                    render(load_spec(self.path))
                self.assertFalse((self.root / "output/manifest.json").exists())

    def test_optional_labels_are_saved_and_empty_label_selections_fail(self):
        import pymol2
        literal = 'Pocket "A"'
        content = self.content + ('\n[[panels.labels]]\nselection = "chain A and resi 406+470"\n'
                                  '\n[[panels.labels]]\nselection = "chain C and resi 50"\n'
                                  f'text = {json.dumps(literal)}\nsize = 20\noffset = [1, 0, 2]\n')
        self.path.write_text(content)
        spec = load_spec(self.path)
        manifest = render(spec)
        self.assertEqual(manifest["annotations"]["context"], [])
        labels = manifest["annotations"]["interface"]
        self.assertEqual(len(labels), 3)
        self.assertEqual(labels[-1]["text"], literal)
        with pymol2.PyMOL() as session:
            session.cmd.load(str(spec.output / "sessions/interface.pse"))
            self.assertEqual(session.cmd.count_atoms("pv_residue_annotation_*"), 3)
            visible_labels = []
            session.cmd.iterate("pv_residue_annotation_*", "observed.append(label)", space={"observed": visible_labels})
            self.assertIn(literal, visible_labels)
        self.path.write_text(content.replace('chain A and resi 406+470', 'chain Z'))
        with self.assertRaisesRegex(SpecError, "no heavy atoms"):
            render(load_spec(self.path))

    def test_distance_indicator_matches_report_and_is_optional(self):
        import math
        import pymol2
        content = self.content + ('\n[[panels.distances]]\nstart = "chain A and resi 406"\n'
                                  'end = "chain A and resi 470"\nmode = "centroid"\nname = "Site spacing"\n')
        self.path.write_text(content)
        spec = load_spec(self.path)
        manifest = render(spec)
        self.assertEqual(manifest["distances"]["context"], [])
        distance = manifest["distances"]["interface"][0]
        self.assertAlmostEqual(distance["distance_A"], math.dist(distance["start_xyz_A"], distance["end_xyz_A"]))
        with pymol2.PyMOL() as session:
            session.cmd.load(str(spec.output / "sessions/interface.pse"))
            self.assertIn("pv_distance_interface_0", session.cmd.get_names("objects"))
            labels = []
            session.cmd.iterate("pv_annotation_distance_interface_0", "observed.append(label)", space={"observed": labels})
            self.assertIn(f'Site spacing: {distance["distance_A"]:.2f} Å', labels)
        self.path.write_text(content.replace('chain A and resi 470', 'chain A and resi 406'))
        with self.assertRaisesRegex(SpecError, "overlap"):
            render(load_spec(self.path))


if __name__ == "__main__":
    unittest.main()
