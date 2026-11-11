---
name: protein-vis
description: Use when creating reproducible PyMOL protein, ligand, or peptide interaction figures with highlighted sites, residue labels, or distances.
---

# Protein visualization

Find the protein-vis checkout and read its README for the current specification
and commands. Run commands with `uv run --project <checkout> protein-vis`.
Use `presets` to inspect the available styles. Use `init` to create a TOML
specification from an existing PDB/mmCIF and explicit target and partner PyMOL
selections; add `--site NAME SELECTION COLOR`, `--label-selection SELECTION`,
and `--distance START END` as needed. Run `init --help` for the complete syntax.
The starter refuses to overwrite existing files.

Choose `protein-protein`, `protein-ligand`, or `cyclic-peptide` based on the
partner representation, not a guessed chain identity. Confirm chain/residue
identities from the supplied structure or user context. Never invent binding
sites, residue mappings, or confidence values. Keep the partner prominent and
color each requested site consistently across panels.

Edit the resulting TOML for custom label text, placement, centroid distances,
camera groups, or different site selections. Labels and distances belong to
individual panels. Distances are geometric, in Å, and `closest` and `centroid`
have different meanings; state the method when reporting values. Check that
selections identify the intended atoms and that site selections are disjoint.

Use panel `metrics` and `summary` for user-supplied confidence scores or panel
conclusions, and figure-level `conclusion` for an overall takeaway. Preserve
provided score precision, identify the source, and never imply confidence scores
are experimental binding measurements. These fields only affect composition.

Run `validate`, then `build`. Inspect the PNG and the measured distances in
`manifest.json` for label collisions, clipping, visibility, and interpretation;
adjust the specification and rebuild when needed. Preserve the input structures
and return links to the figure, editable session, and specification. If PyMOL
or dependencies are unavailable, report the failure rather than claiming a
render succeeded. Use cached composition only when render settings are unchanged.
