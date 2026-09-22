# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-21

## Current focus

Validate the new canonical-config pruning workflow and the existing 2.3.1 release metadata.

## Recently completed

- Added `grobl config prune` for future-safe removal of same-source rules shadowed by later identical matchers.
- Added optional `--current-tree` pruning for exact inherited same-base duplicates, guarded by counterfactual effective-state comparison.
- Preserved backup, `--stdout`, and `--check` maintenance semantics shared with `config migrate`.
- Added unit/component/CLI regression coverage and import-architecture wiring.

## Known gaps and limitations

- Default pruning intentionally does not attempt arbitrary gitignore-glob subsumption.
- `--current-tree` is repository-state dependent and may retain or remove rules differently after paths change.
- Legacy policy files must be migrated before pruning.

## Risks / blockers

No known implementation blocker. Full repository and release validation remain pending.

## Resume notes

Run the validation items in [TODO.md](TODO.md). Review `grobl config prune --current-tree --stdout` before applying it to the project config.
