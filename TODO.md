# TODO

Immediate execution-level work only. Completed items are removed before commit; completed history belongs in git and, when user-visible, in the changelog.

- [ ] Smoke-test `grobl init` and inspect the generated `.grobl.toml`. Acceptance: it is minimal/commented and does not copy bundled policy.
- [ ] Smoke-test legacy scan behavior interactively and with `--no-interactive`. Acceptance: interactive runs offer migrate then prune; noninteractive runs warn without writing.
- [ ] Run `just release-check`. Acceptance: repository validation passes and source/wheel distributions build without local source overrides.
