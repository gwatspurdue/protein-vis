"""TOML figure specifications; no rendering dependencies."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from protein_vis.presets import PRESETS

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


class SpecError(ValueError):
    """A specification cannot be used safely or unambiguously."""


REPRESENTATIONS = {"cartoon", "sticks", "surface", "spheres", "lines"}


@dataclass(frozen=True)
class Site:
    name: str
    selection: str
    color: str
    representation: str = "sticks"


@dataclass(frozen=True)
class Label:
    selection: str
    text: str | None = None
    color: str = "#0b0b0b"
    size: float = 16
    offset: tuple[float, float, float] = (0, 0, 2)


@dataclass(frozen=True)
class Distance:
    start: str
    end: str
    mode: str = "closest"
    name: str = ""
    color: str = "#52514e"
    label: bool = True
    size: float = 16
    offset: tuple[float, float, float] = (0, 0, 2)


@dataclass(frozen=True)
class Panel:
    id: str
    structure: Path
    target: str
    partner: str
    title: str = ""
    scene: str = "context"
    target_representation: str = "surface"
    partner_representation: str = "sticks"
    target_color: str = "#d8d7d0"
    partner_color: str = "#2a78d6"
    target_transparency: float = 0.35
    sites: tuple[Site, ...] = ()
    view: tuple[float, ...] | None = None
    focus: str | None = None
    camera_group: str = "context"
    preset: str | None = None
    partner_stick_radius: float = 0.24
    labels: tuple[Label, ...] = ()
    distances: tuple[Distance, ...] = ()


@dataclass(frozen=True)
class RenderSettings:
    width: int = 1400
    height: int = 1100
    dpi: int = 300
    contact_cutoff: float = 4.5
    align: bool = True


@dataclass(frozen=True)
class FigureSpec:
    source: Path
    output: Path
    panels: tuple[Panel, ...]
    title: str = ""
    columns: int = 2
    width_inches: float = 7.2
    panel_height_inches: float = 3.2
    render: RenderSettings = RenderSettings()


def _table(value, allowed: set[str], context: str) -> dict:
    if not isinstance(value, dict):
        raise SpecError(f"{context}: expected a table")
    unknown = value.keys() - allowed
    if unknown:
        raise SpecError(f"{context}: unknown fields: {', '.join(sorted(unknown))}")
    return value


def _text(value, context: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise SpecError(f"{context}: expected {'a string' if empty else 'a nonempty string'}")
    return value


def _number(value, context: str, low: float, high: float, *, integer=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not low <= value <= high or (integer and type(value) is not int)):
        raise SpecError(f"{context}: expected {'an integer' if integer else 'a number'} in {low}..{high}")
    return value


def _color(value, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise SpecError(f"{context}: expected a #RRGGBB color")
    return value


def _representation(value, context: str) -> str:
    if not isinstance(value, str) or value not in REPRESENTATIONS:
        raise SpecError(f"{context}: choose from {', '.join(sorted(REPRESENTATIONS))}")
    return value


def _preset(value) -> str | None:
    if value is not None and (not isinstance(value, str) or value not in PRESETS):
        raise SpecError(f"preset: choose from {', '.join(PRESETS)}")
    return value


def _labels(rows, context: str) -> tuple[Label, ...]:
    if not isinstance(rows, list):
        raise SpecError(f"{context}: expected [[panels.labels]] tables")
    labels = []
    for row in rows:
        _table(row, set(Label.__dataclass_fields__), context)
        offset = row.get("offset", [0, 0, 2])
        if not isinstance(offset, list) or len(offset) != 3:
            raise SpecError(f"{context}.offset: expected three numbers")
        labels.append(Label(
            selection=_text(row.get("selection"), f"{context}.selection"),
            text=_text(row["text"], f"{context}.text") if "text" in row else None,
            color=_color(row.get("color", "#0b0b0b"), f"{context}.color"),
            size=_number(row.get("size", 16), f"{context}.size", 6, 72),
            offset=tuple(_number(v, f"{context}.offset", -100, 100) for v in offset),
        ))
    return tuple(labels)


def _distances(rows, context: str) -> tuple[Distance, ...]:
    if not isinstance(rows, list):
        raise SpecError(f"{context}: expected [[panels.distances]] tables")
    distances = []
    for row in rows:
        _table(row, set(Distance.__dataclass_fields__), context)
        mode = row.get("mode", "closest")
        if mode not in ("closest", "centroid"):
            raise SpecError(f"{context}.mode: choose closest or centroid")
        show_label = row.get("label", True)
        if type(show_label) is not bool:
            raise SpecError(f"{context}.label: expected true or false")
        offset = row.get("offset", [0, 0, 2])
        if not isinstance(offset, list) or len(offset) != 3:
            raise SpecError(f"{context}.offset: expected three numbers")
        distances.append(Distance(
            start=_text(row.get("start"), f"{context}.start"),
            end=_text(row.get("end"), f"{context}.end"), mode=mode,
            name=_text(row.get("name", ""), f"{context}.name", empty=True),
            color=_color(row.get("color", "#52514e"), f"{context}.color"),
            label=show_label, size=_number(row.get("size", 16), f"{context}.size", 6, 72),
            offset=tuple(_number(v, f"{context}.offset", -100, 100) for v in offset),
        ))
    return tuple(distances)


def load_spec(path: Path) -> FigureSpec:
    """Load and validate a figure; resolve paths relative to its TOML file."""
    path = Path(path).expanduser().resolve()
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SpecError(f"Cannot read {path}: {error}") from error
    _table(data, {"version", "output", "title", "columns", "width_inches",
                  "panel_height_inches", "render", "panels", "preset"}, "figure")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise SpecError("version must be 1")
    figure_preset = _preset(data.get("preset"))
    output = (path.parent / _text(data.get("output"), "output")).resolve()
    if output == path.parent or output in path.parents:
        raise SpecError("output must be a separate artifact directory, not the specification directory or its parent")
    settings = _table(data.get("render", {}), set(RenderSettings.__dataclass_fields__), "render")
    render = RenderSettings(**settings)
    for name in ("width", "height"):
        _number(getattr(render, name), f"render.{name}", 100, 10000, integer=True)
    _number(render.dpi, "render.dpi", 72, 1200, integer=True)
    _number(render.contact_cutoff, "render.contact_cutoff", 0.1, 20)
    if type(render.align) is not bool:
        raise SpecError("render.align must be true or false")
    raw_panels = data.get("panels")
    if not isinstance(raw_panels, list) or not raw_panels:
        raise SpecError("panels: specify at least one [[panels]] table")
    panels = []
    ids = set()
    for row in raw_panels:
        _table(row, set(Panel.__dataclass_fields__), "panel")
        preset = _preset(row.get("preset", figure_preset))
        row = {**(PRESETS[preset]["defaults"] if preset else {}), **row}
        identifier = _text(row.get("id"), "panel.id")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", identifier) or identifier in ids:
            raise SpecError(f"panel.id: {identifier!r} must be unique and contain only letters, numbers, '_' or '-'")
        ids.add(identifier)
        structure = (path.parent / _text(row.get("structure"), f"{identifier}.structure")).resolve()
        if not structure.is_file() or structure.suffix.lower() not in {".pdb", ".ent", ".cif", ".mmcif"}:
            raise SpecError(f"{identifier}: structure must be an existing PDB/mmCIF file: {structure}")
        if output == structure or output in structure.parents:
            raise SpecError(f"{identifier}: keep input structures outside the output directory")
        scene = row.get("scene", "context")
        if scene not in ("context", "interface"):
            raise SpecError(f"{identifier}.scene: choose context or interface")
        sites = []
        raw_sites = row.get("sites", [])
        if not isinstance(raw_sites, list):
            raise SpecError(f"{identifier}.sites: expected [[panels.sites]] tables")
        for site in raw_sites:
            _table(site, set(Site.__dataclass_fields__), f"{identifier}.site")
            name = _text(site.get("name"), "site.name")
            if name in {s.name for s in sites}:
                raise SpecError(f"{identifier}: duplicate site name {name!r}")
            sites.append(Site(name, _text(site.get("selection"), "site.selection"),
                              _color(site.get("color"), "site.color"),
                              _representation(site.get("representation", "sticks"), "site.representation")))
        view = row.get("view")
        if view is not None:
            if not isinstance(view, list) or len(view) != 18:
                raise SpecError(f"{identifier}.view: expected the 18 numbers from PyMOL get_view")
            view = tuple(_number(v, f"{identifier}.view", -1e9, 1e9) for v in view)
        panels.append(Panel(
            id=identifier, structure=structure,
            target=_text(row.get("target"), f"{identifier}.target"),
            partner=_text(row.get("partner"), f"{identifier}.partner"),
            title=_text(row.get("title", ""), f"{identifier}.title", empty=True),
            scene=scene,
            target_representation=_representation(row.get("target_representation", "cartoon" if scene == "interface" else "surface"), "target_representation"),
            partner_representation=_representation(row.get("partner_representation", "sticks"), "partner_representation"),
            target_color=_color(row.get("target_color", "#d8d7d0"), "target_color"),
            partner_color=_color(row.get("partner_color", "#2a78d6"), "partner_color"),
            target_transparency=_number(row.get("target_transparency", 0.35), "target_transparency", 0, 1),
            sites=tuple(sites), view=view,
            focus=_text(row["focus"], f"{identifier}.focus") if "focus" in row else None,
            camera_group=_text(row.get("camera_group", scene), f"{identifier}.camera_group"),
            preset=preset,
            partner_stick_radius=_number(row.get("partner_stick_radius", 0.24), "partner_stick_radius", 0.05, 2),
            labels=_labels(row.get("labels", []), f"{identifier}.labels"),
            distances=_distances(row.get("distances", []), f"{identifier}.distances"),
        ))
    return FigureSpec(
        source=path, output=output, panels=tuple(panels),
        title=_text(data.get("title", ""), "title", empty=True),
        columns=_number(data.get("columns", 2), "columns", 1, 6, integer=True),
        width_inches=_number(data.get("width_inches", 7.2), "width_inches", 2, 40),
        panel_height_inches=_number(data.get("panel_height_inches", 3.2), "panel_height_inches", 1, 20),
        render=render,
    )
