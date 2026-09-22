# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-22

## Current focus

Prepare the 2.4.0 release from `critique-cleanup` and complete the final post-metadata validation and manual smoke checks.

## Recently completed

- Made scan/explain read-only with respect to configuration; migration and pruning are explicit maintenance commands.
- Added canonical config pruning, `inherit_defaults`, persistent scan settings, finite content budgets, and stronger sensitive-path defaults.
- Simplified implicit scan dispatch, output/error handling, and internal module boundaries while preserving the enforced CLI → application/configuration → core dependency direction.
- Added explicit clipboard-success feedback and bounded-memory text detection.
- `just check` and `just release-check` passed before the 2.4.0 version/documentation update.
- Prepared the 2.4.0 changelog and release metadata.

## Known gaps and limitations

- Sensitive-file protection is path-based and does not attempt content-level secret scanning.
- Aggregate byte/token omissions depend on deterministic scan order. `explain` shares the budget across its explicit file targets but cannot reconstruct budget consumed by files outside that invocation.
- Legacy inclusion keys remain supported as ingress compatibility syntax until a future explicit removal.

## Risks / blockers

No known implementation blocker. The release metadata/documentation edits still require the post-edit validation and manual smoke checks listed in `TODO.md`.

## Resume notes

Run the remaining `TODO.md` checks from a local checkout before tagging or publishing 2.4.0.
