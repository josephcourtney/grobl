# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-21

## Current focus

Finish smoke testing and release validation for the new project-delta configuration model and interactive legacy-maintenance flow.

## Recently completed

- Changed `grobl init` to generate a minimal commented project config rather than materializing bundled policy.
- Added `inherit_defaults` as a policy-only switch; explicit CLI source selection remains higher precedence.
- Added persistent config equivalents for stable scan behavior while keeping routing/actions invocation-specific.
- Added automatic legacy-schema detection for scan/explain with interactive migration/pruning offers and noninteractive warn-only behavior.
- Extended current-tree pruning so disabling inherited defaults is respected during counterfactual analysis.
- Added regression coverage for config-vs-CLI precedence, disabled defaults, invalid configured behavior, migration acceptance/decline, and config-backup omission.
- Fixed the new component-test repository-root setup and kept the SMALL broken-pipe test hermetic by mocking config maintenance.
- `just check` passes after the config revision and fixture fixes, covering syntax, formatting, lint, typing, import contracts, the full test suite, and coverage.

## Known gaps and limitations

- Structural pruning intentionally does not attempt arbitrary gitignore-glob subsumption.
- `--current-tree` remains repository-state dependent and therefore requires explicit confirmation in the interactive flow.
- Persistent scan-wide settings use the general config merge; nested path-specific configs remain policy layers rather than per-subtree payload-format/scope settings.

## Risks / blockers

No known implementation blocker. Manual smoke checks and `just release-check` remain pending.

## Resume notes

Run the remaining smoke tests and release validation in [TODO.md](TODO.md). These changes remain Unreleased.
