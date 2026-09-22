# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-21

## Current focus

Validate the new project-delta configuration model and interactive legacy-maintenance flow.

## Recently completed

- Changed `grobl init` to generate a minimal commented project config rather than materializing bundled policy.
- Added `inherit_defaults` as a policy-only switch; explicit CLI source selection remains higher precedence.
- Added persistent config equivalents for stable scan behavior while keeping routing/actions invocation-specific.
- Added automatic legacy-schema detection for scan/explain with interactive migration/pruning offers and noninteractive warn-only behavior.
- Extended current-tree pruning so disabling inherited defaults is respected during counterfactual analysis.
- Added regression coverage for config-vs-CLI precedence, disabled defaults, invalid configured behavior, and migration acceptance/decline.

## Known gaps and limitations

- Structural pruning intentionally does not attempt arbitrary gitignore-glob subsumption.
- `--current-tree` remains repository-state dependent and therefore requires explicit confirmation in the interactive flow.
- Persistent scan-wide settings use the general config merge; nested path-specific configs remain policy layers rather than per-subtree payload-format/scope settings.

## Risks / blockers

Repository validation has not yet been rerun after this config revision.

## Resume notes

Run the validation items in [TODO.md](TODO.md). The previously validated 2.3.1 state is the baseline; these changes are currently Unreleased.
