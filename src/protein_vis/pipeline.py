"""Artifact identities and staged figure builds; safe to import without PyMOL."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from protein_vis import __version__
from protein_vis.spec import FigureSpec, SpecError


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_inputs(spec: FigureSpec) -> dict:
    panels = []
    for panel in spec.panels:
        row = asdict(panel)
        row.pop("title")
        row["structure"] = str(panel.structure)
        row["structure_sha256"] = file_digest(panel.structure)
        for site in row["sites"]:
            site.pop("name")
        panels.append(row)
    return {"pipeline_version": __version__, "cache_schema": 1,
            "render": asdict(spec.render), "panels": panels}


def render_key(spec: FigureSpec) -> str:
    payload = json.dumps(render_inputs(spec), sort_keys=True, allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def cached_manifest(spec: FigureSpec) -> dict:
    """Require matching settings and complete, unchanged outputs before reuse."""
    try:
        manifest = json.loads((spec.output / "manifest.json").read_text())
        if manifest["render_key"] != render_key(spec):
            raise SpecError("Cached render is stale: structure or render settings changed. Run render or build.")
        expected = {"contacts.json"}
        for panel in spec.panels:
            expected.update({f"frames/{panel.id}.png", f"sessions/{panel.id}.pse"})
        artifacts = manifest["artifacts"]
        if set(artifacts) != expected:
            raise SpecError("Cached render is incomplete. Run render or build.")
        for name, digest in artifacts.items():
            if file_digest(spec.output / name) != digest:
                raise SpecError(f"Cached artifact changed: {name}. Run render or build.")
        return manifest
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SpecError("No complete cached render. Run render or build first.") from error


def render(spec: FigureSpec) -> dict:
    from protein_vis.render import render_panels

    inputs = render_inputs(spec)
    key = render_key(spec)
    spec.output.mkdir(parents=True, exist_ok=True)
    # A failed rerender must not leave a seemingly valid old manifest.
    (spec.output / "manifest.json").unlink(missing_ok=True)
    metadata = render_panels(spec)
    artifacts = ["contacts.json"]
    for panel in spec.panels:
        artifacts.extend((f"frames/{panel.id}.png", f"sessions/{panel.id}.pse"))
    manifest = {"render_key": key, "inputs": inputs, **metadata,
                "artifacts": {name: file_digest(spec.output / name) for name in artifacts}}
    (spec.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def build(spec: FigureSpec, *, force: bool = False) -> tuple[list[Path], bool]:
    reused = False
    if not force:
        try:
            cached_manifest(spec)
            reused = True
        except SpecError:
            pass
    if not reused:
        render(spec)
    from protein_vis.compose import compose

    return compose(spec), reused
