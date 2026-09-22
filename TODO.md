# TODO

Immediate execution-level work only. Completed items are removed before commit; completed history belongs in git and, when user-visible, in the changelog.

- [ ] Re-run `just check` after the 2.4.0 metadata/documentation update. Acceptance: syntax, format, lint, typing, import contracts, tests, and coverage all pass.
- [ ] Re-run `just release-check`. Acceptance: repository validation passes and source/wheel distributions build as 2.4.0 without local source overrides.
- [ ] Smoke-test `grobl init`. Acceptance: it writes the minimal commented project-delta config and returns immediately.
- [ ] Smoke-test a legacy-schema scan and explain. Acceptance: both warn without modifying configuration; `grobl config migrate` and `grobl config prune` remain the only maintenance write paths.
- [ ] Smoke-test default interactive and non-interactive output. Acceptance: an interactive run copies the payload and emits the clipboard receipt on stderr; a non-TTY run writes the payload to stdout without touching the clipboard.
