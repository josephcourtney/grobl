# TODO

Immediate execution-level work only. Completed items are removed before commit; completed history belongs in git and, when user-visible, in the changelog.

- [ ] Run `just check`. Acceptance: syntax, format, lint, typing, import contracts, tests, and coverage all pass after removing the init-time legacy-reference scan.
- [ ] Smoke-test `grobl init` and inspect the generated `.grobl.toml`. Acceptance: it writes the minimal/commented project-delta config and returns immediately without a repository-wide pause.
- [ ] Smoke-test legacy scan behavior interactively and with `--no-interactive`. Acceptance: interactive runs offer migrate then prune; noninteractive runs warn without writing.
- [ ] Run `just release-check`. Acceptance: repository validation passes and source/wheel distributions build without local source overrides.
