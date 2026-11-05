# Presets, optional labels, and agent use

**Goal:** Reuse common molecular styles, optionally label selected residues or
sites, and let agents generate/build figures through the existing CLI.

**Design:** Built-in protein-protein, protein-ligand, and cyclic-peptide presets
provide display defaults. A figure-level preset can be overridden per panel;
explicit panel values win. Omitting presets preserves current styling. Labels
are opt-in arrays on panels: selection, optional literal text, color, point size,
and offset. Without custom text, make one label per selected residue preserving
chain and insertion code. With text, annotate the selection centroid once.
Use pseudoatom labels so annotation text is never evaluated as Python.

**Agent interface:** Add `presets` (JSON catalog) and `init` (safe TOML starter,
explicit molecular selections, optional sites and labels). Ship a portable
`skills/protein-vis/SKILL.md` that uses those commands, validates selections,
builds and visually inspects output. `.agents` is read-only in this harness;
document linking the skill into a supported discovery directory outside it.
No MCP server or new runtime dependency is necessary.

## Work

- [x] Add failing tests for preset resolution/override/rejection, label schema,
  default-off behavior and cache invalidation. Implement presets and label types.
- [x] Add safe residue/centroid anchor generation and PyMOL label rendering;
  verify literal text, insertion codes, and labels in real saved sessions.
- [x] Add optional distance indicators for closest heavy atoms or centroids,
  reporting measured endpoints and values in Å.
- [x] Test and implement preset catalog and exclusive-write TOML initialization.
- [x] Create and validate the agent skill. Independent agent evaluation could not
  run because the selected model was at capacity; the CLI was exercised in tests.
- [ ] Update examples and documentation, inspect an actual labeled figure, run
  the full suite, and obtain focused code review.

The existing 14 tests pass with the installed rendering environment. The user
has also inspected and approved the initial rendered figure. Keep that baseline
style and avoid changing existing output unless a preset or label is selected.
