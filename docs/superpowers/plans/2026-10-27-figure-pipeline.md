# Figure pipeline implementation plan

**Goal:** A uv-managed CLI renders reusable protein/ligand figures from TOML,
keeping the interacting partner prominent and multiple interaction sites distinct.

**Architecture:** Ordinary dataclasses and functions separate specification,
PyMOL rendering/measurements, cache provenance, and Matplotlib composition.
Only rendering imports PyMOL. Inputs remain read-only.

**Tech stack:** Python 3.10+, uv, TOML (tomli on Python 3.10), Matplotlib,
Pillow, optional open-source PyMOL.

**Basis:** `AGENTS.md` and the user's interaction-partner/site priorities.

## Decisions

- Use TOML and explicit target/partner PyMOL selections; no guessed chains.
- Each panel names its structure, scene (`context` or `interface`), target,
  partner, representations, and zero or more named colored sites.
- Keep residue IDs from input files, including chain and insertion code.
- Align targets to the first panel; share cameras within each scene type.
- Export transparent frames, per-panel editable sessions, contact reports,
  exact camera views, a provenance manifest, and composed PNG/PDF figures.
- Cache rendered outputs using input content and resolved render settings.
  Labels/layout can change without importing PyMOL or rerendering.
- Begin with heavy-atom residue-pair proximity measurements; defer confidence,
  buried area, binders200 import, and campaign statistics until needed.

## Review focus

Missing/overlapping selections; duplicate panel/site IDs; missing or modified
cached files; insertion-code identity; layout edits that should reuse frames.

## Tasks

- [x] Write failing stdlib unittest checks for TOML validation, paths, cache
  compatibility, and label-only changes. Initialize uv package and implement
  `load_spec(path)` and `render_key(spec)`; run those checks.
- [x] Write a render smoke test using the bundled two-chain 9CHT excerpt.
  Implement context/interface scenes, explicit site highlights, shared views,
  contact reports, and output provenance. Run with optional PyMOL if installable.
- [x] Implement `protein-vis validate|render|compose|build SPEC`, caching and
  composition. Verify end-to-end output and reuse after changing labels.
- [x] Add a standalone example and README, update AGENTS.md, and run the
  available suite and CLI checks with uv.
- [ ] Install dependencies and generate `uv.lock`, run rendering/composition
  checks, and inspect the actual figure. Blocked by PyPI DNS/network access.

Execution is in this workspace: `.git` is an empty, read-only harness mount,
so git branch/worktree operations are unavailable. No source tests exist here
yet; the reference loader's 10 tests passed during initialization.

## Execution record

- Core/schema/cache/contact tests were written and run failing before their
  implementation, then run passing. An alignment review finding added another
  failing-then-passing regression check.
- Final core suite: 14 discovered, 11 passed, 3 skipped (Matplotlib/PyMOL absent).
- `validate examples/interaction.toml` passes via offline uv/Python 3.11.
- `build examples/interaction.toml` exits with actionable missing-PyMOL setup
  instructions. No molecular figure has been generated or visually verified.
- `uv sync --extra render` failed because PyPI DNS resolution is unavailable;
  `uv lock --offline` confirms the dependencies are not cached. No lockfile has
  been fabricated.
- Ruling: require identical target residue sequences/chain boundaries and full
  C-alpha matching for automatic alignment; arbitrary target correspondence,
  mutations and truncations remain outside this first implementation.
