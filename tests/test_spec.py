import tempfile
import unittest
from pathlib import Path

from protein_vis.spec import SpecError, load_spec
from protein_vis.pipeline import render_key


SPEC = '''version = 1
title = "A complex"
output = "figures/demo"

[[panels]]
id = "overview"
structure = "model.pdb"
target = "chain A"
partner = "chain B"
partner_representation = "sticks"
title = "Partner in context"

[[panels.sites]]
name = "Pocket"
selection = "chain A and resi 10+11"
color = "#eda100"
'''


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "figure.toml"
        self.path.write_text(SPEC)
        (self.root / "model.pdb").write_text("END\n")

    def test_paths_are_relative_to_spec_and_site_is_preserved(self):
        spec = load_spec(self.path)
        self.assertEqual(spec.panels[0].structure, self.root / "model.pdb")
        self.assertEqual(spec.output, self.root / "figures/demo")
        self.assertEqual(spec.panels[0].sites[0].name, "Pocket")

    def test_rejects_ambiguous_or_mistyped_specifications(self):
        cases = [
            SPEC.replace('target = "chain A"', 'target = ""'),
            SPEC.replace('version = 1', 'version = 2'),
            SPEC.replace('color = "#eda100"', 'color = "golden"'),
            SPEC.replace('partner_representation = "sticks"', 'partner_representation = "oops"'),
            SPEC.replace('title = "A complex"', 'titlle = "A complex"'),
            SPEC + '\n[[panels]]\nid = "overview"\nstructure = "model.pdb"\ntarget = "chain A"\npartner = "chain B"\n',
            SPEC.replace('output = "figures/demo"', 'output = "."'),
            SPEC.replace('version = 1', 'version = 1\ncolumns = 0'),
        ]
        for content in cases:
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(SpecError):
                    load_spec(self.path)

    def test_cache_tracks_structure_and_scene_but_ignores_composition(self):
        original = render_key(load_spec(self.path))
        self.path.write_text(SPEC.replace('title = "A complex"', 'title = "New caption"'))
        self.assertEqual(original, render_key(load_spec(self.path)))
        self.path.write_text(SPEC.replace('name = "Pocket"', 'name = "Site one"'))
        self.assertEqual(original, render_key(load_spec(self.path)))
        self.path.write_text(SPEC.replace('#eda100', '#eb6834'))
        self.assertNotEqual(original, render_key(load_spec(self.path)))
        self.path.write_text(SPEC)
        (self.root / "model.pdb").write_text("REMARK changed\nEND\n")
        self.assertNotEqual(original, render_key(load_spec(self.path)))

    def test_missing_structure_has_actionable_error(self):
        (self.root / "model.pdb").unlink()
        with self.assertRaisesRegex(SpecError, "model.pdb"):
            load_spec(self.path)


if __name__ == "__main__":
    unittest.main()
