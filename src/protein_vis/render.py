"""PyMOL scenes with explicit partners and independently highlighted sites."""

from __future__ import annotations

import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path

from protein_vis.spec import FigureSpec, SpecError


def _centroid(points) -> list[float]:
    return [math.fsum(point[axis] for point in points) / len(points) for axis in range(3)]


def label_anchors(atoms, text: str | None = None) -> list[dict]:
    """One anchor per original residue, or one literal annotation per selection."""
    if text is not None:
        return [{"text": text, "position": _centroid([a.coord for a in atoms])}]
    residues = {}
    for atom in atoms:
        residues.setdefault((atom.segi, atom.chain, atom.resi, atom.resn), []).append(atom.coord)
    anchors = []
    for (segment, chain, resi, resn), points in residues.items():
        prefix = "/".join(part for part in (segment, chain) if part)
        identifier = f"{prefix}:{resi}" if prefix else resi
        anchors.append({"text": f"{resn} {identifier}", "position": _centroid(points)})
    return anchors


def distance_endpoints(start, end, mode: str) -> tuple[list, list, float]:
    if mode == "centroid":
        left, right = _centroid(start), _centroid(end)
    else:
        # ponytail: O(N*M) time, constant extra space; use a spatial index if full-protein distances become routine.
        left, right = min(((a, b) for a in start for b in end), key=lambda pair: math.dist(*pair))
    return list(left), list(right), math.dist(left, right)


def validate_target_correspondence(moving_atoms, reference_atoms, context: str) -> int:
    """Conservatively require matching protein sequences and chain boundaries."""
    def signature(atoms):
        chains = {}
        for atom in atoms:
            chains.setdefault((atom.segi, atom.chain), []).append(atom.resn)
        return tuple(tuple(residues) for residues in chains.values())

    if signature(moving_atoms) != signature(reference_atoms):
        raise SpecError(f"{context}: alignment requires the same target sequence and chain boundaries. "
                        "Supply matching targets, or set render.align = false for already aligned structures.")
    if len(moving_atoms) < 3:
        raise SpecError(f"{context}: alignment needs at least three protein C-alpha atoms")
    return len(moving_atoms)


def residue_contacts(atom_pairs) -> list[dict]:
    """Reduce heavy-atom pairs to closest residue pairs without renumbering."""
    contacts = {}
    for left, right in atom_pairs:
        def identity(atom):
            return {"segi": atom.segi, "chain": atom.chain,
                    "resi": atom.resi, "resn": atom.resn}

        target, partner = identity(left), identity(right)
        key = (*target.values(), *partner.values())
        distance = math.dist(left.coord, right.coord)
        if key not in contacts or distance < contacts[key]["min_distance_A"]:
            contacts[key] = {"target": target, "partner": partner,
                             "min_distance_A": distance}
    return sorted(contacts.values(), key=lambda row: (
        row["target"]["chain"], row["target"]["resi"],
        row["partner"]["chain"], row["partner"]["resi"]))


def _selection(cmd, name: str, expression: str, context: str) -> str:
    try:
        count = cmd.select(name, expression, quiet=1)
    except Exception as error:
        raise SpecError(f"{context}: invalid selection {expression!r}: {error}") from error
    if count <= 0:
        raise SpecError(f"{context}: selection matches no heavy atoms: {expression}")
    return name


def _color(cmd, name: str, hex_color: str, selection: str):
    cmd.set_color(name, [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)])
    cmd.color(name, selection)


def _style(cmd, panel, target: str, partner: str, sites: list[str]):
    cmd.hide("everything", "all")
    cmd.show(panel.target_representation, target)
    cmd.set("transparency", panel.target_transparency, target)
    cmd.set("cartoon_transparency", panel.target_transparency, target)
    _color(cmd, "pv_target_color", panel.target_color, target)
    cmd.show(panel.partner_representation, partner)
    cmd.set("stick_radius", panel.partner_stick_radius, partner)
    _color(cmd, "pv_partner_color", panel.partner_color, partner)
    # Site colors deliberately apply to every element so each site reads as a unit.
    for index, (site, selection) in enumerate(zip(panel.sites, sites)):
        cmd.show(site.representation, selection)
        cmd.set("transparency", 0, selection)
        cmd.set("cartoon_transparency", 0, selection)
        _color(cmd, f"pv_site_color_{index}", site.color, selection)


def _draw_label(cmd, name, text, position, color, size, offset=(0, 0, 2)):
    # pseudoatom's label parameter is literal; never evaluate user text with cmd.label.
    cmd.pseudoatom(name, pos=position, label=text)
    cmd.hide("everything", name)
    _color(cmd, f"{name}_color", color, name)
    cmd.set("label_color", f"{name}_color", name)
    cmd.set("label_outline_color", "white", name)
    cmd.set("label_font_id", 7, name)
    cmd.set("label_size", size, name)
    cmd.set("label_position", list(offset), name)
    cmd.show("labels", name)


def _annotations(cmd, panel, obj, target, partner) -> tuple[list, list]:
    labels, distances = [], []

    def select(name, expression, context):
        selection = _selection(cmd, name, f"model {obj} and ({expression})", context)
        if cmd.count_atoms(f"{selection} and not ({target} or {partner})"):
            raise SpecError(f"{context}: annotations must belong to target or partner")
        return selection

    for number, label in enumerate(panel.labels):
        selection = select(f"pv_label_sele_{panel.id}_{number}", label.selection, f"{panel.id}.labels[{number}]")
        for anchor in label_anchors(cmd.get_model(selection).atom, label.text):
            _draw_label(cmd, f"pv_residue_annotation_{panel.id}_{len(labels)}", anchor["text"],
                        anchor["position"], label.color, label.size, label.offset)
            labels.append(anchor)
    for number, distance in enumerate(panel.distances):
        prefix = f"pv_distance_{panel.id}_{number}"
        start = select(f"{prefix}_start", distance.start, f"{panel.id}.distances[{number}].start")
        end = select(f"{prefix}_end", distance.end, f"{panel.id}.distances[{number}].end")
        if cmd.count_atoms(f"{start} and {end}"):
            raise SpecError(f"{panel.id}.distances[{number}]: start and end selections overlap")
        left, right, value = distance_endpoints(
            [a.coord for a in cmd.get_model(start).atom],
            [a.coord for a in cmd.get_model(end).atom], distance.mode)
        for suffix, position in (("left", left), ("right", right)):
            cmd.pseudoatom(f"{prefix}_{suffix}", pos=position)
            cmd.hide("everything", f"{prefix}_{suffix}")
        cmd.distance(prefix, f"{prefix}_left", f"{prefix}_right", cutoff=value + 1, quiet=1)
        cmd.hide("labels", prefix)
        cmd.set_color(f"{prefix}_color", [int(distance.color[i:i + 2], 16) / 255 for i in (1, 3, 5)])
        cmd.set("dash_color", f"{prefix}_color", prefix)
        cmd.set("dash_width", 2.5, prefix)
        cmd.set("dash_gap", 0.25, prefix)
        if distance.label:
            text = (f"{distance.name}: " if distance.name else "") + f"{value:.2f} Å"
            _draw_label(cmd, f"pv_annotation_distance_{panel.id}_{number}", text,
                        _centroid([left, right]), distance.color, distance.size, distance.offset)
        distances.append({"name": distance.name, "mode": distance.mode, "start": distance.start,
                          "end": distance.end, "start_xyz_A": left, "end_xyz_A": right, "distance_A": value})
    return labels, distances


def render_panels(spec: FigureSpec) -> dict:
    try:
        import pymol2
    except (ImportError, OSError) as error:
        raise SpecError("PyMOL is unavailable. Run `uv sync --extra render` in a supported environment. "
                        f"Import error: {error}") from error
    (spec.output / "frames").mkdir(parents=True, exist_ok=True)
    (spec.output / "sessions").mkdir(parents=True, exist_ok=True)
    reports = {}
    views = {}
    alignments = {}
    annotations, distances = {}, {}
    with pymol2.PyMOL() as pymol:
        cmd = pymol.cmd
        for name, value in {
            "ray_opaque_background": 0, "ray_shadows": 0, "antialias": 2,
            "orthoscopic": 1, "ambient": 0.46, "direct": 0.52,
            "reflect": 0.12, "specular": 0.14, "spec_power": 180,
            "cartoon_fancy_helices": 1, "cartoon_smooth_loops": 1,
            "surface_quality": 1, "transparency_mode": 2,
            "stick_radius": 0.24, "sphere_scale": 0.26,
        }.items():
            cmd.set(name, value)
        cmd.bg_color("white")
        loaded = []
        for index, panel in enumerate(spec.panels):
            obj = f"pv_model_{index}"
            cmd.load(str(panel.structure), obj, quiet=1)
            if cmd.count_states(obj) != 1:
                raise SpecError(f"{panel.id}: supply a single-state structure")
            cmd.remove(f"model {obj} and (hydro or solvent)")
            target = _selection(cmd, f"pv_target_{index}", f"model {obj} and ({panel.target})", f"{panel.id}.target")
            partner = _selection(cmd, f"pv_partner_{index}", f"model {obj} and ({panel.partner})", f"{panel.id}.partner")
            if cmd.count_atoms(f"{target} and {partner}"):
                raise SpecError(f"{panel.id}: target and partner selections overlap")
            sites = []
            for number, site in enumerate(panel.sites):
                selection = _selection(cmd, f"pv_site_{index}_{number}",
                                       f"model {obj} and ({site.selection})", f"{panel.id}.{site.name}")
                if cmd.count_atoms(f"{selection} and not ({target} or {partner})"):
                    raise SpecError(f"{panel.id}.{site.name}: sites must belong to target or partner")
                if sites and cmd.count_atoms(f"{selection} and ({' or '.join(sites)})"):
                    raise SpecError(f"{panel.id}.{site.name}: interaction sites overlap; use distinct selections")
                sites.append(selection)
            if spec.render.align and loaded and panel.structure != spec.panels[0].structure:
                reference = loaded[0][1]
                moving_ca = f"{target} and polymer.protein and name CA"
                reference_ca = f"{reference} and polymer.protein and name CA"
                expected = validate_target_correspondence(cmd.get_model(moving_ca).atom,
                                                         cmd.get_model(reference_ca).atom, panel.id)
                result = cmd.align(moving_ca, reference_ca, cycles=0, quiet=1)
                if result[1] != expected:
                    raise SpecError(f"{panel.id}: alignment did not match every target C-alpha atom")
                alignments[panel.id] = {"reference": spec.panels[0].id,
                                        "rmsd_A": result[0], "aligned_atoms": result[1]}
            atoms = {a.index: a for a in cmd.get_model(obj).atom}
            pairs = cmd.find_pairs(target, partner, cutoff=spec.render.contact_cutoff)
            reports[panel.id] = residue_contacts((atoms[left[1]], atoms[right[1]]) for left, right in pairs)
            focus = f"({partner}) or ({' or '.join(sites)})" if sites else partner
            if panel.scene == "context":
                focus = f"({target}) or ({partner})"
            else:
                focus += f" or (byres ({target} within {spec.render.contact_cutoff} of {partner}))"
            if panel.focus:
                focus = _selection(cmd, f"pv_focus_{index}", f"model {obj} and ({panel.focus})", f"{panel.id}.focus")
            loaded.append((obj, target, partner, sites, focus))
        cmd.hide("everything", "all")
        # Fit each scene group to the union of its panels, preserving common scale.
        group_views = {}
        for group_name in sorted({p.camera_group for p in spec.panels}):
            group = [entry[4] for panel, entry in zip(spec.panels, loaded)
                     if panel.camera_group == group_name and panel.view is None]
            if group:
                cmd.orient(group[0])
                cmd.zoom(" or ".join(f"({focus})" for focus in group), buffer=3, complete=1)
                group_views[group_name] = list(cmd.get_view())
        for panel, (obj, target, partner, sites, _focus) in zip(spec.panels, loaded):
            _style(cmd, panel, target, partner, sites)
            cmd.set_view(panel.view if panel.view is not None else group_views[panel.camera_group])
            annotations[panel.id], distances[panel.id] = _annotations(cmd, panel, obj, target, partner)
            cmd.deselect()
            views[panel.id] = list(cmd.get_view())
            cmd.png(str(spec.output / "frames" / f"{panel.id}.png"),
                    width=spec.render.width, height=spec.render.height,
                    dpi=spec.render.dpi, ray=1, quiet=1)
            cmd.save(str(spec.output / "sessions" / f"{panel.id}.pse"), quiet=1)
        version = str(cmd.get_version()[0])
    (spec.output / "contacts.json").write_text(json.dumps({
        "definition": "Minimum heavy-atom distance per target/partner residue pair; geometric proximity only.",
        "cutoff_A": spec.render.contact_cutoff,
        "residue_numbering": "Input structure numbering, including chain, segment and insertion code.",
        "panels": reports,
    }, indent=2) + "\n")
    return {"created_utc": datetime.now(timezone.utc).isoformat(),
            "python_version": platform.python_version(), "pymol_version": version,
            "views": views, "alignments": alignments, "annotations": annotations,
            "distances": distances}
