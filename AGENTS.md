# Protein visualization and research figures

## Purpose

Build a small, reproducible PyMOL pipeline for research figures. A new figure
should normally require a declarative figure specification and input structures,
not another standalone Python script. Support reusable molecular scenes, shared
visual styles, and publication figure composition.

Use **uv** for Python project setup, dependencies, locking, and commands. Maintain
`pyproject.toml` and `uv.lock` once the Python project is initialized. Prefer
`uv sync`, `uv run ...`, and `uv add ...` over pip or bespoke environment scripts.
Keep the PyMOL installation requirements explicit: verify a working installation
in the chosen environment rather than assuming uv alone supplies PyMOL.

## Current state

The initial Python package now lives under `src/protein_vis/`, with a uv project
in `pyproject.toml`. It uses TOML specifications and exposes
`protein-vis validate|render|compose|build SPEC`. See `README.md` and the bundled
`examples/interaction.toml` for actual setup and configuration.

Current modules are `spec.py` (dataclasses and strict validation), `render.py`
(PyMOL scenes, explicit target/partner and named site selections, proximity
measurements), `pipeline.py` (content hashes, artifact validation and build
stages), `compose.py` (Matplotlib figure layout), and `cli.py`.

Keep the interaction partner prominent and several interaction sites separately
highlighted; this is the user's main visual priority. Context and interface views
support explicit focus selections and camera groups. Automatic comparison fits
require identical target protein sequences and full C-alpha correspondence;
more general mappings are not implemented.

The environment now includes PyMOL, Matplotlib, and `uv.lock`. PyMOL and
Matplotlib tests skip when unavailable; do not report skipped tests as passing
or output as visually verified. `.git` is an empty read-only harness mount,
so git/worktree commands do not work in this workspace.

The initial reference is `/home/gavin/binders200/plots` (`~/binders200/plots`).
Treat that project and its research inputs as read-only reference material.
Extract useful behavior into this repo; avoid a runtime dependency on that
absolute path or the surrounding binders200 repository.

## Source analysis

The baseline already has useful separation of responsibilities:

| Source file under `~/binders200/plots/` | Responsibility and reuse potential |
| --- | --- |
| `make_plots.py` | Thin entry point with a local import-path shim; replace the shim with normal package installation. |
| `binderplots/runs.py` | Stdlib dataclasses, state/artifact loading, ranking, discovery, and pooling. Keep the loader as an optional binders200 adapter. |
| `binderplots/geometry.py` | Contact measurements, hotspot mapping, confidence tracks, buried surface area, and JSON reports. Separate report types/serialization from PyMOL execution. |
| `binderplots/render.py` | Shared PyMOL session, target alignment, camera, lighting, representations, transparent PNGs, and `.pse` export. Reuse these rendering primitives. |
| `binderplots/scenes.py` | Gallery, backbone, interface, and epitope scene recipes. Parameterize and reuse recipes. |
| `binderplots/figures.py` | Matplotlib composition, labels, metrics, TSV export, PDF and 300 dpi PNG output. Generalize fixed layouts and campaign-specific text. |
| `binderplots/style.py` | Shared structural colors, confidence bands, typography, and chart defaults. Keep one consistent style source. |
| `binderplots/cli.py` | Loads runs, measures, renders, composes, and reuses outputs. Replace hardcoded run paths and fixed figure sets with specification-driven orchestration. |
| `tests/test_runs.py` | Ten stdlib unittest tests for run loading, ranking, pooling, and discovery; no rendering or geometry coverage. |

The original pipeline produces campaign, gallery, interface, epitope, and optional
backbone figures, along with frames, measurements, summary tables, and editable
PyMOL sessions. Preserve the separation between expensive rendering and cheap
composition so changing labels or layout does not require ray tracing again.

### Assumptions to address during extraction

- Input loading is tied to binders200 `state.json`, AlphaFast metrics, and
  RFdiffusion/ProteinMPNN stages. Plain PDB/mmCIF structures must be usable
  without a binder-design campaign or confidence scores.
- Binder and target chains are guessed when metadata is missing. Make molecular
  roles/selections explicit and validate that they resolve to the intended atoms.
  Do not silently choose the last chain or the first non-binder chain.
- Target numbering maps residues by C-alpha file order when counts match, then
  silently falls back to raw IDs. Equal counts do not establish correspondence.
  Support validated mappings and preserve chain IDs and insertion codes; report
  missing hotspot mappings instead of silently dropping them.
- Polymer detection uses the presence of atoms named `CA`. Cyclic peptides in
  these source models are single CCD ligand entities; this is input-specific,
  not a property of every cyclic peptide. Preserve atom-level versus residue-level
  reporting where appropriate.
- B-factors are treated as pLDDT. Only apply confidence semantics when the input
  provenance explicitly identifies confidence values.
- `--reuse-frames` checks for directory/report existence and reconstructs frame
  paths by design index. Validate cache compatibility against structures,
  selections, design identities, camera, style, and render settings.
- Composition imports report types from a module importing PyMOL, and CLI imports
  rendering eagerly. Keep specification validation and cached composition usable
  without starting or importing PyMOL.
- Pooling checks binder type and hotspots, but not target identity or residue
  correspondence. Validate a shared target before comparing aligned designs.
- The source README says short binders use surfaces, while rendering uses cartoon
  for polymers and thick sticks for nonpolymers. Follow inspected implementation
  and visual verification when resolving documentation discrepancies.

## Development direction

Keep the flow explicit: **figure specification → validated inputs/selections →
measurements → molecular frames → composed figures**. Use a small Python package
and CLI with ordinary functions and dataclasses. Avoid plugin frameworks, workflow
engines, GUIs, and speculative abstractions.

Use the existing TOML specification format when extending the workflow.
Represent structure paths, molecular roles, selections, alignment reference,
camera, scene recipe, style, output size, and layout as data. Resolve relative
input paths against the specification location. Supply a runnable example;
do not invent commands in documentation before they exist.

Start with one end-to-end structure-to-figure workflow, then add recipes based on
actual figure needs. Keep binders200 adaptation outside generic rendering and
composition. Add reusable capabilities instead of figure-specific script copies.

Keep comparison panels aligned to one reference and camera. Allow saved camera
views for reproducibility. Record resolved settings, input identities, versions,
and measurement definitions beside generated output. Keep source structures
unchanged; treat frames, figures, sessions, and reports as regenerable artifacts.

## Scientific and visual conventions

- Use consistent molecular role colors across scenes and charts; the source uses
  blue binders, grey targets, highlighted hotspots, and green contact side chains.
- Label units and distinguish measurements from predictions. Confidence and
  geometric proximity do not establish experimental binding.
- The source uses 4.5 Å for heavy-atom contacts, 3.5 Å for polar proximity, and
  8 Å for on-epitope classification. These are distinct definitions; make them
  explicit and configurable. Its polar-pair count and displayed PyMOL polar
  contacts use different methods; do not imply they are identical.
- The source buried interface area is `(SASA(binder) + SASA(target) -
  SASA(complex)) / 2`, in Å². State the convention and ensure the measured complex
  contains the intended partners.
- Export transparent molecular frames and editable `.pse` sessions. Composed PDF
  text/charts can be vector while molecular images remain raster; describe this
  accurately. Expose physical dimensions and resolution for publication output.
- Inspect rendered figures for cropping, visibility, label collisions, shared
  scale/camera, and legible text. Code execution alone does not verify a figure.

## Validation

Use `uv run python -m unittest discover -s tests -v` for this repo's checks once
its environment exists. The README also documents the working offline uv command
using the installed Python 3.11 and `PYTHONPATH=src`. Test specification
validation, path resolution, residue mapping, measurement definitions, and cache
invalidation with small fixtures. Keep tests that do not need PyMOL independent
of it. Add a small headless render smoke check when rendering is implemented;
report clearly when the required PyMOL environment is unavailable.

To check the reference loader without modifying the source workspace:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s /home/gavin/binders200/plots/tests -t /home/gavin/binders200/plots
```

At initialization, these 10 reference tests passed. The source README's
`~/anaconda3/envs/binder_viz/bin/python` was absent in this environment; rendering
has not been verified. Update this guide with actual setup and check commands
as the local implementation takes shape.
