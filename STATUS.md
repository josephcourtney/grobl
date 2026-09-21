# Status

This file is the short-horizon project snapshot for continuity and handoff. It is intentionally compact; durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-21

## Current focus

Prepare the 2.3.1 maintenance release after integrating the three-state inclusion policy, test-isolation fixes, and documentation-policy cleanup.

## Recently completed

- Integrated the `full | tree_only | omit` policy and canonical `exclude` / `tree_only` / `include` configuration.
- Added `grobl config migrate`, explain provenance, compatibility adapters, and regression coverage.
- Corrected test-size/isolation failures and the TTY fixture mismatch found by the full test run.
- Merged the three-state feature history into `main` and aligned project records with `POLICY.md`.

## Known gaps and limitations

- Legacy policy keys and hidden scoped CLI flags remain intentionally supported at ingress.
- Migration can only warn about overlapping non-identical legacy globs whose equivalence cannot be proven mechanically.
- A fresh `just check` and `just release-check` are still required after the 2.3.1 metadata/documentation update.

## Risks / blockers

No known behavioral blocker. Release readiness depends on the pending full validation gates.

## Resume notes

Run the items in [TODO.md](TODO.md). If both validation gates pass, the repository is ready for the 2.3.1 release step.
