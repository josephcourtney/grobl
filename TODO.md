# TODO

Immediate execution-level work only. Completed items are removed before commit; completed history belongs in git and, when user-visible, in the changelog.

- [ ] Run `just check` after the 2.3.1 metadata/documentation update. Acceptance: every strict validation step passes.
- [ ] Run `just release-check`. Acceptance: repository validation passes and source/wheel distributions build without local source overrides.
- [ ] Spot-check `grobl -V` and `grobl --version`. Acceptance: each prints only `2.3.1` followed by a newline.
