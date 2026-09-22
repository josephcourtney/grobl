# TODO

Immediate execution-level work only. Completed items are removed before commit; completed history belongs in git and, when user-visible, in the changelog.

- [ ] Run `grobl config prune --current-tree --stdout` against the project `.grobl.toml` and review the proposed removals before applying them.
- [ ] Run `just release-check`. Acceptance: repository validation passes and source/wheel distributions build without local source overrides.
- [ ] Spot-check `grobl -V` and `grobl --version`. Acceptance: each prints only `2.3.1` followed by a newline.
