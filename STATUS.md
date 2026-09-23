# Status

This file is the short-horizon project snapshot for continuity and handoff. Durable architecture is in [DESIGN.md](DESIGN.md), execution strategy in [PLAN.md](PLAN.md), and immediate work in [TODO.md](TODO.md).

Last updated: 2026-09-23

## Current focus

Finish validation of bounded, explicit symbolic-link traversal on `feature/symlink-policy` before merging it to `main`.

## Recently completed

- Made POSIX symlinks explicit logical tree entries and stopped dereferencing file links by default.
- Added `--follow-symlinks` / `follow_symlinks` plus a separate `--allow-external-symlinks` / `allow_external_symlinks` boundary override.
- Preserved logical paths for inclusion matching, hierarchical config discovery, emitted content paths, and explain output.
- Added broken-link handling, external-target classification, inode-based directory cycle prevention, and duplicate-target avoidance.
- Added JSON symlink metadata and explain dispositions, including omitted-directory traversal needed to reach explicitly restored descendants.
- Added unit/system regressions and updated DESIGN, SPEC, configuration/usage documentation, starter defaults, and the changelog.

## Known gaps and limitations

- macOS Finder aliases are ordinary files; Grobl does not invoke Finder alias-resolution APIs.
- External symlink traversal is intentionally disabled unless both following and the external-target override are enabled.
- Sensitive-file protection remains path-based and does not attempt content-level secret scanning.

## Risks / blockers

The implementation has received static review, but this execution environment cannot clone GitHub over DNS, so the repository's `just check` and `just release-check` gates have not been run against the branch.

## Resume notes

Run the remaining checks in [TODO.md](TODO.md) from a local checkout. If they pass, the feature branch is ready for normal merge review.
