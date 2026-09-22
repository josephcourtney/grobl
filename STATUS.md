# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-21

## Current focus

2.3.1 is release-ready; no immediate implementation work remains.

## Recently completed

- Refined `grobl config prune` to remove structural config redundancy while preserving meaningful overrides, XDG resets, `extends` suppression, and explanatory comments.
- Reviewed the project config with `grobl config prune --current-tree --stdout` and applied the accepted minimal result.
- `just check` passes after the pruning refinement.
- `just release-check` passes, including distribution builds.
- `grobl -V` and `grobl --version` both report `2.3.1` exactly.

## Known gaps and limitations

- Structural pruning intentionally does not attempt arbitrary gitignore-glob subsumption.
- `--current-tree` is repository-state dependent and may retain or remove rules differently after paths change.
- Legacy policy files must be migrated before pruning.

## Risks / blockers

No known blocker for the 2.3.1 release.

## Resume notes

The repository has passed the release validation gates. Publishing remains a separate explicit release operation.
