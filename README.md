# protein-vis

Make repeatable PyMOL research figures by editing a TOML file. Keep the
interacting ligand or protein prominent, highlight several named interaction
sites, and export the same complex in context and in detail.

The initial implementation extracts the useful rendering/composition separation
from `~/binders200/plots`; it accepts PDB and mmCIF files directly.

## Setup and first figure

Use Python 3.10+ and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --extra render
uv run protein-vis validate examples/interaction.toml
uv run protein-vis build examples/interaction.toml
```

The `render` extra selects open-source PyMOL 3.2.0a0. Check the
[published wheels](https://pypi.org/project/pymol-open-source/3.2.0a0/#files)
for platform compatibility; the Linux x86-64 wheel requires glibc 2.35+.
PyMOL may also need system OpenGL libraries even when used headlessly.
`uv sync` alone installs composition dependencies; validation and cached
composition do not import PyMOL.

The example includes chains A/C of 9CHT, preserving input numbering. It shows
E6 in blue against E6AP in grey, with two E6AP regions highlighted in yellow
and green. See [structure provenance](examples/data/README.md). To use your own
complex, copy the TOML, point `structure` to its PDB/mmCIF file, and change the
target, partner, and site selections.

## Presets and annotations

Add optional figure text and user-supplied scores directly to the TOML:

```toml
conclusion = "The predicted complex places the binder near the target site."

[[panels]]
id = "interface"
summary = "Candidate 1: predicted interface"
metrics = { iPTM = 0.82, pLDDT = "91.0" }
# Also specify structure, target, and partner for this panel.
```

`conclusion` appears below the figure; `summary` and `metrics` appear beneath
their panel. Values can be finite numbers or nonempty strings; quote a value to
preserve formatting such as trailing zeros. Supply the actual scores and their
source yourself: they are displayed verbatim and are not inferred from the
structure. Confidence scores describe model confidence, not measured binding.
These fields affect composition only, so edit them and run `compose` or `build`
to reuse matching frames without PyMOL ray tracing.

Run `uv run protein-vis presets` for the JSON catalog. Set `preset` at the top
level or within a panel: `protein-protein` draws the partner as a cartoon;
`protein-ligand` uses sticks and a more transparent target; `cyclic-peptide`
uses thick sticks. Explicit panel settings override preset defaults, and
omitting a preset preserves the original defaults. Override
`partner_stick_radius` in Å when needed.

Add optional annotation tables after the panel's site tables:

```toml
[[panels.labels]]
selection = "chain A and resi 406+470"
size = 20
offset = [0, 0, 2]

[[panels.labels]]
selection = "chain A and resi 406"
text = "Active site"
color = "#0b0b0b"

[[panels.distances]]
name = "Site spacing"
start = "chain A and resi 406"
end = "chain A and resi 470"
mode = "centroid"
```

Without `text`, labels show residue name, chain, and original residue ID, one
per residue; custom text creates one label at the selection centroid. Color,
point size, and PyMOL label-position offset are configurable. Use small,
specific selections to avoid clutter. Labels are absent by default.

Distance mode `closest` (default) uses the closest heavy-atom pair; `centroid`
uses the geometric centers of the heavy atoms in the two selections. Both
endpoints must be disjoint and belong to the selected target or partner. The
line is dashed and its label shows Å; `label = false` hides the number. `name`,
`color`, `size`, and `offset` are optional. Distances and their coordinates are recorded
in `manifest.json`; they indicate geometry, not evidence of a bond. An annotated
example is available at `examples/annotated.toml`.

Create a starter with `uv run protein-vis init --help`. For example:

```sh
uv run protein-vis init my-figure.toml --preset protein-protein \
  --structure examples/data/9cht-ac.pdb --target 'chain A' --partner 'chain C' \
  --site 'Region 1' 'chain A and resi 403-424' '#eda100' \
  --label-selection 'chain A and resi 406' \
  --distance 'chain A and resi 406' 'chain C'
uv run protein-vis build my-figure.toml
```

`init` creates context and interface panels, with labels and distances on the
interface panel. It never overwrites an existing specification. Edit its TOML
to change the distance mode or add more detailed selections.

## Agent skill

The portable [protein-vis skill](skills/protein-vis/SKILL.md) guides agents
through presets, selections, annotations, builds, and visual inspection. To make
it discoverable by Codex from any project, link it into your user skills folder
from this checkout and start a new session:

```sh
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/protein-vis" ~/.agents/skills/protein-vis
```

The skill remains in this repository; the sandbox's `.agents` directory is
read-only, so it cannot be installed there during this session.

## Specify partners and sites

```toml
version = 1
title = "Ligand binding sites"
output = "figures/ligand"
columns = 1
width_inches = 3.6

[[panels]]
id = "pocket"
title = "Ligand and two contact regions"
structure = "complex.cif"
target = "chain A and polymer.protein"
partner = "resn LIG and chain A"
partner_representation = "sticks"
scene = "interface"

[[panels.sites]]
name = "Site one"
selection = "chain A and resi 42+45+46"
color = "#eda100"
representation = "sticks"

[[panels.sites]]
name = "Site two"
selection = "chain A and resi 103-108"
color = "#1baf7a"
representation = "surface"
```

Paths are relative to the TOML file, including `output`. Input files must live
outside the output directory. Unknown fields and duplicate panel IDs/site names
are errors. `validate` checks the schema and file paths; `render` additionally
checks actual atoms. Targets and partners must be nonempty and disjoint. Site
selections must be nonempty subsets of those partners and disjoint from other
sites in that panel. A ligand selection should include its residue/chain ID
when several copies share the same name.

Selections use PyMOL syntax scoped to each panel's structure. Site colors apply
to all selected elements, keeping the highlighted region visually consistent.
Colors are `#RRGGBB`; representations are `cartoon`, `sticks`, `surface`,
`spheres`, or `lines`. Use `sticks` for small molecules and `cartoon` for
protein partners. No confidence coloring or chain guessing is applied.

| Panel option | Default / behavior |
| --- | --- |
| `scene` | `"context"` fits both partners; `"interface"` fits the partner, selected sites and nearby target residues. |
| `target_representation` | `"surface"` for context, `"cartoon"` for interface. |
| `partner_representation` | `"sticks"`. |
| `target_color`, `partner_color` | `"#d8d7d0"`, `"#2a78d6"`. |
| `target_transparency` | `0.35`; use a larger value to reveal a buried partner. |
| `focus` | Optional selection to fit a particular pocket or region. |
| `camera_group` | Defaults to the scene name. Panels in the same group share orientation and scale, fitted to the union of their focus selections. Use distinct groups for different site close-ups. |
| `view` | Optional 18-number PyMOL `get_view` list. Overrides automatic framing for that panel. |

Across different input structures, targets are aligned to the first panel's
target using protein C-alpha atoms. Automatic alignment requires identical target
residue sequences and chain boundaries, and matches every C-alpha atom without
outlier rejection. Mutations, truncations and missing target residues are
rejected in this first version. The fit's RMSD and matched atom count are
recorded. Inspect the resulting superposition for your data. For structures
already in a common coordinate frame or nonprotein targets, set `align = false`
under `[render]`. Use single-state structures; multi-state input is rejected.

`[render]` options are `width = 1400`, `height = 1100` (frame pixels),
`dpi = 300`, `contact_cutoff = 4.5` (Å), and `align = true`.
Figure layout uses top-level `columns = 2`, `width_inches = 7.2`, and
`panel_height_inches = 3.2`; space for titles and legends is added to that height.
Panels retain their full frames during composition to preserve shared scale.

## Iterate without ray tracing again

```sh
# Expensive step: molecular frames, measurements and sessions
uv run protein-vis render examples/interaction.toml

# After changing titles, site names or figure layout
uv run protein-vis compose examples/interaction.toml

# Automatically reuse intact compatible renders, or rerender changed settings
uv run protein-vis build examples/interaction.toml

# Force fresh frames, e.g. after changing the PyMOL installation
uv run protein-vis build examples/interaction.toml --force
```

Cache identities include structure contents, selections, site colors and
representations, cameras, alignment, render settings and pipeline version.
Missing or changed artifacts invalidate reuse. `compose` reports a stale cache
instead of silently using unrelated frames. The recorded PyMOL version is
provenance; a PyMOL upgrade alone does not automatically invalidate old frames.

## Outputs

Each specification writes an isolated output directory:

| File | Purpose |
| --- | --- |
| `figure.png`, `figure.pdf` | Composed figure; the PDF has vector text/legends and raster molecular panels. |
| `frames/<panel-id>.png` | Transparent ray-traced molecular image. |
| `sessions/<panel-id>.pse` | Editable scene with that panel visible and its camera restored. |
| `contacts.json` | Minimum heavy-atom distance for each target/partner residue pair within the cutoff. |
| `manifest.json` | Input hashes, rendering settings, versions, exact views, alignment diagnostics and artifact checksums. |
| `resolved-spec.json` | Resolved paths and the composition settings used for the latest figure. |

Contact reports retain input chain/segment IDs and residue IDs, including
insertion codes. They describe geometric proximity, not hydrogen bonds or
experimental evidence of binding. Atom selections omit hydrogens and PyMOL
`solvent`. No residue remapping or interpretation of B-factors as pLDDT occurs.
Generated artifacts under `figures/` are ignored by git.

## Development and current verification

```sh
uv sync --extra render
uv run python -m unittest discover -s tests -v
```

The tests cover schema/path validation, content-sensitive cache reuse,
chain/insertion-code preservation, and dependency-independent CLI behavior.
With rendering dependencies installed they also exercise real headless scenes,
selection errors, transparent frames and composition without PyMOL.

The project includes `uv.lock`. If dependencies cannot be installed, the
dependency-independent checks can be run with an installed Python 3.11:

```sh
UV_CACHE_DIR=/tmp/protein-vis-uv-cache PYTHONPATH=src \
  uv run --no-project --python /usr/bin/python3.11 \
  python -m unittest discover -s tests -v
```
