# TODO

Immediate execution-level work only. Completed items are removed before commit; completed history belongs in git and, when user-visible, in the changelog.

- [ ] Run `just check` on `feature/symlink-policy`. Acceptance: syntax, Ruff formatting/lint, typing, import contracts, tests, and coverage all pass.
- [ ] Run `just release-check`. Acceptance: repository validation and distribution builds pass without local source overrides.
- [ ] Smoke-test symlink behavior from the CLI. Acceptance: default scans show links without reading targets; `--follow-symlinks` follows eligible internal targets under logical paths; external targets require the second opt-in; broken links remain visible; `grobl explain` reports the same disposition.
