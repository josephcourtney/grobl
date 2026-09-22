# TODO

Immediate execution-level work only. Completed items are removed before commit; completed history belongs in git and, when user-visible, in the changelog.

- [ ] Run `just check`. Acceptance: syntax, format, lint, typing, import contracts, tests, and coverage all pass on `critique-cleanup`.
- [ ] Smoke-test `grobl init`. Acceptance: it writes the minimal commented project-delta config and returns immediately.
- [ ] Smoke-test a legacy-schema scan and explain. Acceptance: both warn without modifying configuration; `grobl config migrate` and `grobl config prune` remain the only maintenance write paths.
- [ ] Smoke-test default interactive output. Acceptance: the payload is copied to the clipboard and stderr reports the copied file/token/size summary.
- [ ] Run `just release-check`. Acceptance: repository validation passes and source/wheel distributions build without local source overrides.
