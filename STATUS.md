# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-22

## Current focus

Validate the CLI-safety and simplification pass on the `critique-cleanup` branch.

## Recently completed

- Made scan/explain warning-only for legacy configuration; migration and pruning are explicit config commands.
- Simplified implicit scan parsing so unknown first positionals are paths rather than unknown commands.
- Added finite configurable per-file, aggregate-byte, and token budgets with explainable omissions.
- Changed text detection to bounded-memory streaming and strengthened sensitive-filename defaults.
- Normalized config-read, clipboard, and output-write failures and added explicit clipboard-success feedback.
- Removed CLI/config/service compatibility facades, the obsolete runtime-ignore compatibility API, and tests that existed only to preserve those legacy seams.
- Cleaned duplicate, unused, and mutable package metadata.

## Known gaps and limitations

- Sensitive-file protection is path-based and does not attempt content-level secret scanning.
- Aggregate byte/token omissions depend on deterministic scan order; standalone `explain` reports the active budgets and direct per-file violations rather than reconstructing a previous scan.
- Legacy inclusion keys remain supported as ingress compatibility syntax until a future explicit removal.

## Risks / blockers

Repository validation still needs to confirm formatting, typing, import contracts, tests, and coverage after this pass.

## Resume notes

Run the validation items in `TODO.md` from a local checkout. This environment could review and update the repository through GitHub but could not execute the repository because outbound GitHub/DNS access from the code container was unavailable.
