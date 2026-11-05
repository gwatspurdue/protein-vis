import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from protein_vis.pipeline import cached_manifest, file_digest, render_key
from protein_vis.spec import SpecError, load_spec
from test_spec import SPEC


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "figure.toml"
        self.path.write_text(SPEC)
        (self.root / "model.pdb").write_text("END\n")
        self.spec = load_spec(self.path)
        self.spec.output.mkdir(parents=True)
        artifacts = {}
        for name in ("frames/overview.png", "sessions/overview.pse", "contacts.json"):
            artifact = self.spec.output / name
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"fixture")
            artifacts[name] = file_digest(artifact)
        self.manifest = {"render_key": render_key(self.spec), "artifacts": artifacts}
        self.manifest_path = self.spec.output / "manifest.json"
        self.manifest_path.write_text(json.dumps(self.manifest))

    def test_cache_is_usable_without_importing_pymol(self):
        with patch.dict(sys.modules, {"pymol": None, "pymol2": None}):
            self.assertEqual(cached_manifest(self.spec), self.manifest)

    def test_missing_or_modified_artifacts_reject_reuse(self):
        frame = self.spec.output / "frames/overview.png"
        frame.write_bytes(b"modified")
        with self.assertRaisesRegex(SpecError, "changed"):
            cached_manifest(self.spec)
        frame.unlink()
        with self.assertRaisesRegex(SpecError, "complete"):
            cached_manifest(self.spec)

    def test_stale_inputs_and_incomplete_manifest_reject_reuse(self):
        (self.root / "model.pdb").write_text("REMARK modified\n")
        with self.assertRaisesRegex(SpecError, "stale"):
            cached_manifest(self.spec)
        (self.root / "model.pdb").write_text("END\n")
        self.manifest["artifacts"].clear()
        self.manifest_path.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(SpecError, "incomplete"):
            cached_manifest(self.spec)


class RenderTests(unittest.TestCase):
    def test_alignment_rejects_different_or_partial_targets(self):
        from types import SimpleNamespace
        from protein_vis.render import validate_target_correspondence

        def atoms(sequence):
            return [SimpleNamespace(resn=resn, chain="A", segi="") for resn in sequence]

        reference = atoms(["ALA", "GLY", "LYS"])
        self.assertEqual(validate_target_correspondence(reference, reference, "panel"), 3)
        with self.assertRaisesRegex(SpecError, "same target"):
            validate_target_correspondence(atoms(["ALA", "GLY", "TYR"]), reference, "panel")
        with self.assertRaisesRegex(SpecError, "same target"):
            validate_target_correspondence(atoms(["ALA", "GLY"]), reference, "panel")

    def test_contact_pairs_preserve_original_chain_residue_and_insertion_code(self):
        from types import SimpleNamespace
        from protein_vis.render import residue_contacts

        atom = lambda chain, resi, name, xyz: SimpleNamespace(
            chain=chain, resi=resi, resn=name, segi="", coord=xyz)
        target = [atom("A", "10A", "ALA", (0, 0, 0)),
                  atom("A", "10A", "ALA", (1, 0, 0)),
                  atom("A", "10B", "GLY", (50, 0, 0))]
        partner = [atom("B", "2", "GLY", (0, 3, 0))]
        contacts = residue_contacts([(target[0], partner[0]), (target[1], partner[0])])
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["target"]["resi"], "10A")
        self.assertEqual(contacts[0]["target"]["chain"], "A")
        self.assertEqual(contacts[0]["min_distance_A"], 3.0)

    def test_missing_pymol_has_setup_instructions(self):
        from protein_vis.render import render_panels
        with patch.dict(sys.modules, {"pymol2": None}):
            with self.assertRaisesRegex(SpecError, "uv sync --extra render"):
                render_panels(None)


if __name__ == "__main__":
    unittest.main()
