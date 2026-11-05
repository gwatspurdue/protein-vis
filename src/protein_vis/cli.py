"""Small staged CLI for reproducible molecular figures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from protein_vis.spec import SpecError, load_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build PyMOL research figures from a TOML specification.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("presets", help="print the built-in preset catalog as JSON")
    initializer = subparsers.add_parser("init", help="create a TOML starter with context and interface panels")
    initializer.add_argument("spec", type=Path, help="new TOML file; existing files are never overwritten")
    from protein_vis.presets import PRESETS
    initializer.add_argument("--preset", choices=PRESETS, required=True)
    initializer.add_argument("--structure", type=Path, required=True)
    initializer.add_argument("--target", required=True, help="explicit PyMOL target selection")
    initializer.add_argument("--partner", required=True, help="explicit PyMOL partner selection")
    initializer.add_argument("--output", help="artifact directory relative to the new specification")
    initializer.add_argument("--site", nargs=3, action="append", default=[], metavar=("NAME", "SELECTION", "COLOR"))
    initializer.add_argument("--label-selection", action="append", default=[], help="label residues in the interface panel; repeatable")
    initializer.add_argument("--distance", nargs=2, action="append", default=[], metavar=("START", "END"),
                             help="closest heavy-atom distance in the interface panel; repeatable")
    for name, help_text in (
        ("validate", "validate specification and input paths without importing PyMOL"),
        ("render", "validate atom selections, measure contacts, and ray trace frames"),
        ("compose", "compose cached frames into figures without importing PyMOL"),
        ("build", "render when needed and compose figures"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("spec", type=Path, help="TOML figure specification")
        if name == "build":
            command.add_argument("--force", action="store_true", help="rerender even when the cache matches")
    args = parser.parse_args(argv)
    try:
        if args.command == "presets":
            print(json.dumps(PRESETS, indent=2))
            return 0
        if args.command == "init":
            from protein_vis.starter import write_starter
            spec = write_starter(args.spec, preset=args.preset, structure=args.structure,
                                 target=args.target, partner=args.partner, output=args.output,
                                 sites=args.site, labels=args.label_selection, distances=args.distance)
            print(f"Wrote {spec.source}; output: {spec.output}")
            print("Atom selections are checked at render time.")
            return 0
        spec = load_spec(args.spec)
        if args.command == "validate":
            print(f"Valid specification: {len(spec.panels)} panel(s); output: {spec.output}")
            print("Atom selections are checked at render time.")
        elif args.command == "render":
            from protein_vis.pipeline import render
            render(spec)
            print(f"Rendered frames, sessions and contacts: {spec.output}")
        else:
            if args.command == "build":
                from protein_vis.pipeline import build
                paths, reused = build(spec, force=args.force)
                print("Reused validated frames." if reused else "Rendered new frames.")
            else:
                from protein_vis.compose import compose
                paths = compose(spec)
            for path in paths:
                print(f"Wrote {path}")
    except (SpecError, OSError) as error:
        print(f"protein-vis: {error}", file=sys.stderr)
        return 2
    return 0
