"""Generate ordinary TOML files; never overwrite an existing specification."""

from __future__ import annotations

import json
from pathlib import Path

from protein_vis.spec import FigureSpec, load_spec


def write_starter(path: Path, *, preset: str, structure: Path, target: str,
                  partner: str, output: str | None = None, sites=(), labels=(), distances=()) -> FigureSpec:
    path = path.expanduser().resolve()
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    lines = ["version = 1", f"preset = {quote(preset)}",
             f"output = {quote(output or f'figures/{path.stem}')}", "columns = 2"]
    for scene in ("context", "interface"):
        lines.extend(["", "[[panels]]", f"id = {quote(scene)}", f"scene = {quote(scene)}",
                      f"title = {quote(scene.title())}", f"structure = {quote(structure.expanduser().resolve())}",
                      f"target = {quote(target)}", f"partner = {quote(partner)}"])
        for name, selection, color in sites:
            lines.extend(["", "[[panels.sites]]", f"name = {quote(name)}",
                          f"selection = {quote(selection)}", f"color = {quote(color)}"])
        if scene == "interface":
            for selection in labels:
                lines.extend(["", "[[panels.labels]]", f"selection = {quote(selection)}"])
            for start, end in distances:
                lines.extend(["", "[[panels.distances]]", f"start = {quote(start)}", f"end = {quote(end)}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        handle.write("\n".join(lines) + "\n")
    try:
        return load_spec(path)
    except Exception:
        path.unlink()
        raise
