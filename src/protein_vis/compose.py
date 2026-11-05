"""Compose full molecular frames with labels and site legends, without PyMOL."""

from __future__ import annotations

import json
import math
import textwrap
from dataclasses import asdict
from pathlib import Path

from protein_vis.pipeline import cached_manifest
from protein_vis.spec import FigureSpec, SpecError


def compose(spec: FigureSpec) -> list[Path]:
    cached_manifest(spec)
    try:
        import matplotlib as mpl
        mpl.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
        from PIL import Image
    except ImportError as error:
        raise SpecError("Figure composition needs Matplotlib and Pillow. Run `uv sync`.") from error

    columns = min(spec.columns, len(spec.panels))
    rows = math.ceil(len(spec.panels) / columns)
    legend_rows = max(math.ceil((2 + len(p.sites)) / 2) for p in spec.panels)
    # Leave room for wrapped site names as well as the molecular images.
    longest_name = max((len(s.name) for p in spec.panels for s in p.sites), default=7)
    legend_height = 0.22 * legend_rows * max(1, math.ceil(longest_name / 24)) + 0.1
    height = rows * (spec.panel_height_inches + legend_height) + (0.5 if spec.title else 0.15)
    with mpl.rc_context({"font.family": "DejaVu Sans", "font.size": 8,
                         "pdf.fonttype": 42, "ps.fonttype": 42}):
        fig = plt.figure(figsize=(spec.width_inches, height), facecolor="white")
        try:
            grid = fig.add_gridspec(rows * 2, columns,
                                    height_ratios=[spec.panel_height_inches, legend_height] * rows,
                                    left=0.025, right=0.975, bottom=0.025,
                                    top=1 - (0.5 if spec.title else 0.15) / height,
                                    wspace=0.1, hspace=0.15)
            if spec.title:
                fig.suptitle(textwrap.fill(spec.title, max(30, int(spec.width_inches * 12))),
                             fontsize=12, weight="bold", y=1 - 0.10 / height)
            for index, panel in enumerate(spec.panels):
                row, column = divmod(index, columns)
                ax = fig.add_subplot(grid[2 * row, column])
                # Independent cropping would destroy the shared molecular scale.
                with Image.open(spec.output / "frames" / f"{panel.id}.png") as image:
                    ax.imshow(image.convert("RGBA"))
                ax.set_axis_off()
                label = chr(65 + index) if index < 26 else str(index + 1)
                title = textwrap.fill(panel.title or panel.id, max(16, int(spec.width_inches / columns * 12)))
                ax.set_title(f"{label}   {title}", loc="left", fontsize=9, weight="bold", pad=6)
                legend_ax = fig.add_subplot(grid[2 * row + 1, column])
                legend_ax.set_axis_off()
                entries = [("Target", panel.target_color), ("Interaction partner", panel.partner_color)]
                entries.extend((site.name, site.color) for site in panel.sites)
                legend_ax.legend(handles=[Patch(facecolor=color, edgecolor="none",
                                                label=textwrap.fill(name, 24)) for name, color in entries],
                                 loc="center", ncols=2, frameon=False,
                                 fontsize=7, handlelength=0.9, columnspacing=1)
            written = []
            for suffix in ("png", "pdf"):
                path = spec.output / f"figure.{suffix}"
                fig.savefig(path, dpi=spec.render.dpi)
                written.append(path)
        finally:
            plt.close(fig)
    resolved = asdict(spec)
    resolved["matplotlib_version"] = mpl.__version__
    (spec.output / "resolved-spec.json").write_text(json.dumps(resolved, default=str, indent=2) + "\n")
    return written
