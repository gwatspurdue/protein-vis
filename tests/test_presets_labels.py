import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from protein_vis.cli import main
from protein_vis.pipeline import render_key
from protein_vis.spec import load_spec, SpecError
from test_spec import SPEC


class PresetLabelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "figure.toml"
        self.path.write_text(SPEC)
        (self.root / "model.pdb").write_text("END\n")

    def load(self, content):
        self.path.write_text(content)
        return load_spec(self.path)

    def test_preset_defaults_and_explicit_overrides(self):
        content = SPEC.replace('partner_representation = "sticks"\n', '')
        panel = self.load(content.replace('version = 1', 'version = 1\npreset = "protein-protein"')).panels[0]
        self.assertEqual(panel.partner_representation, "cartoon")
        self.assertEqual(panel.target_transparency, 0.18)
        explicit = self.load(SPEC.replace('version = 1', 'version = 1\npreset = "protein-protein"')).panels[0]
        self.assertEqual(explicit.partner_representation, "sticks")
        overridden = self.load(content.replace('version = 1', 'version = 1\npreset = "protein-protein"').replace(
            'id = "overview"', 'id = "overview"\npreset = "cyclic-peptide"')).panels[0]
        self.assertEqual(overridden.partner_representation, "sticks")
        self.assertEqual(overridden.partner_stick_radius, 0.30)
        ligand = self.load(content.replace('id = "overview"', 'id = "overview"\npreset = "protein-ligand"')).panels[0]
        self.assertEqual(ligand.target_transparency, 0.5)

    def test_no_preset_preserves_style_and_labels_are_optional(self):
        panel = load_spec(self.path).panels[0]
        self.assertEqual(panel.target_transparency, 0.35)
        self.assertEqual(panel.partner_representation, "sticks")
        self.assertEqual(panel.partner_stick_radius, 0.24)
        self.assertEqual(panel.labels, ())

    def test_labels_resolve_and_invalidate_render_cache(self):
        original = render_key(load_spec(self.path))
        content = SPEC + '\n[[panels.labels]]\nselection = "chain A and resi 10A"\nsize = 18\noffset = [1, 0, 2]\n'
        spec = self.load(content)
        self.assertIsNone(spec.panels[0].labels[0].text)
        self.assertEqual(spec.panels[0].labels[0].offset, (1, 0, 2))
        self.assertNotEqual(original, render_key(spec))
        changed = self.load(content + 'text = "Pocket"\n')
        self.assertNotEqual(render_key(spec), render_key(changed))

    def test_rejects_unknown_presets_and_invalid_labels(self):
        for suffix in ('\n[[panels.labels]]\nselection = ""',
                       '\n[[panels.labels]]\nselection = "all"\nsize = -1',
                       '\n[[panels.labels]]\nselection = "all"\noffset = [1, 2]',
                       '\n[[panels.labels]]\nselection = "all"\ntext = ""',
                       '\n[[panels.labels]]\nselection = "all"\ncolor = "red"'):
            with self.subTest(suffix=suffix), self.assertRaises(SpecError):
                self.load(SPEC + suffix)
        for value in ('"unknown"', '[]'):
            with self.subTest(value=value), self.assertRaises(SpecError):
                self.load(SPEC.replace('version = 1', f'version = 1\npreset = {value}'))

    def test_preset_catalog_and_init_create_valid_spec_without_clobbering(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["presets"]), 0)
        self.assertEqual(set(json.loads(out.getvalue())), {"protein-protein", "protein-ligand", "cyclic-peptide"})
        destination = self.root / "new folder" / "ligand.toml"
        args = ["init", str(destination), "--preset", "protein-ligand", "--structure", str(self.root / "model.pdb"),
                "--target", "chain A", "--partner", "resn LIG", "--site", 'Pocket "one"', "chain A and resi 10A", "#eda100",
                "--label-selection", "chain A and resi 10A", "--distance", "chain A and resi 10A", "resn LIG"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
        spec = load_spec(destination)
        self.assertEqual(len(spec.panels), 2)
        self.assertEqual(spec.panels[0].sites[0].name, 'Pocket "one"')
        self.assertEqual(spec.panels[0].labels, ())
        self.assertEqual(len(spec.panels[1].labels), 1)
        self.assertEqual(len(spec.panels[1].distances), 1)
        original = destination.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 2)
        self.assertEqual(destination.read_bytes(), original)

    def test_residue_label_anchors_preserve_ids_and_custom_text_is_literal(self):
        from types import SimpleNamespace
        from protein_vis.render import label_anchors
        def atom(resi, x):
            return SimpleNamespace(segi="", chain="A", resi=resi, resn="ALA", coord=(x, 0, 0))
        atoms = [atom("10A", 0), atom("10A", 2), atom("10B", 4)]
        anchors = label_anchors(atoms)
        self.assertEqual([a["text"] for a in anchors], ["ALA A:10A", "ALA A:10B"])
        self.assertEqual(anchors[0]["position"], [1, 0, 0])
        literal = '__import__("os").system("should never run")'
        custom = label_anchors(atoms, literal)
        self.assertEqual(len(custom), 1)
        self.assertEqual(custom[0]["text"], literal)
        self.assertEqual(custom[0]["position"], [2, 0, 0])

    def test_distance_defaults_validation_and_cache(self):
        original = load_spec(self.path)
        self.assertEqual(original.panels[0].distances, ())
        content = SPEC + '\n[[panels.distances]]\nstart = "chain A and resi 10A"\nend = "chain B"\n'
        spec = self.load(content)
        self.assertEqual(spec.panels[0].distances[0].mode, "closest")
        self.assertNotEqual(render_key(original), render_key(spec))
        for invalid in ('mode = "unknown"', 'label = "true"', 'color = "red"', 'size = 0'):
            with self.subTest(invalid=invalid), self.assertRaises(SpecError):
                self.load(content + invalid)

    def test_distance_endpoints_distinguish_closest_and_centroid(self):
        from protein_vis.render import distance_endpoints
        start = [(0, 0, 0), (4, 0, 0)]
        end = [(5, 0, 0), (9, 0, 0)]
        self.assertEqual(distance_endpoints(start, end, "closest"), ([4, 0, 0], [5, 0, 0], 1))
        self.assertEqual(distance_endpoints(start, end, "centroid"), ([2, 0, 0], [7, 0, 0], 5))


if __name__ == "__main__":
    unittest.main()
