# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-21

## Current focus

Review the pruning result for the project config and finish 2.3.1 release validation.

## Recently completed

- Added `grobl config prune` with conservative structural pruning and optional current-tree counterfactual pruning.
- Added unit/component/CLI regression coverage, documentation, and import-architecture wiring.
- `just check` passes on the pruning implementation, covering syntax, formatting, lint, typing, import architecture, the full test suite, and coverage reporting.

## Known gaps and limitations

- Default pruning intentionally does not attempt arbitrary gitignore-glob subsumption.
- `--current-tree` is repository-state dependent and may retain or remove rules differently after paths change.
- Legacy policy files must be migrated before pruning.

## Risks / blockers

No known implementation blocker. Release artifact validation with `just release-check` remains pending.

## Resume notes

Preview `grobl config prune --current-tree --stdout` against the project config before applying it, then run the remaining release items in [TODO.md](TODO.md).
