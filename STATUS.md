# Status

Last updated: 2026-09-21

## Highlights

- Replaced the independent tree/content ignore model with one three-state inclusion policy: `full`, `tree_only`, and `omit`.
- Canonical configuration now uses `exclude`, `tree_only`, and `include`; an omitted path no longer needs to be repeated in a second content-exclusion list.
- Preserved layered precedence: bundled defaults < root-to-leaf `.grobl.toml` files < explicit `--config` < CLI rules.
- Added `--tree-only` and `--tree-only-file`; the former scoped tree/content flags remain hidden compatibility inputs.
- `tree_only` files are represented in the hierarchy without text detection or content reads.
- `grobl explain` reports the effective inclusion state, winning rule provenance, compatibility tree/content projections, and downstream binary detection.
- Added `grobl config migrate` with in-place backup, `--stdout`, and `--check` modes for legacy-only configuration files.
- Bundled and project configuration, specification, README, usage/configuration docs, changelog, and targeted regression tests use the three-state model.
- Retained the 2.2.1 tokenizer special-token fix and the current main development-tool configuration.
