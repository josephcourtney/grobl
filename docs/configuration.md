# Configuration

grobl reads hierarchical `.grobl.toml` files. Bundled defaults remain package-owned; `grobl init` writes a small commented project-delta configuration rather than copying the bundled policy into the repository.

## Creating a configuration file

```bash
grobl init --path .
```

Add `--force` to replace an existing file. The generated file contains one explicit `inherit_defaults = true` setting plus commented examples for project policy and persistent scan behavior. It does not materialize Grobl's bundled exclusion lists.

A new project inherits the bundled inclusion policy by default. To define inclusion policy entirely in configuration, set:

```toml
inherit_defaults = false
```

This switch affects only the bundled `exclude` / `tree_only` / `include` policy layer. It does not erase ordinary program defaults such as the default payload format.

## Inclusion policy

Every path resolves to exactly one inclusion state:

| State | In hierarchy | Contents captured |
| --- | --- | --- |
| `full` | yes | yes, when the file is text |
| `tree_only` | yes | no |
| `omit` | no | no |

The canonical configuration uses three lists:

```toml
exclude = [
  ".git/",
  ".venv/",
  "dist/",
]

tree_only = [
  "LICENSE*",
  "docs/",
  "*.png",
]

include = [
  "docs/architecture.md",
]
```

Unmatched paths default to `full`. `exclude` assigns `omit`, `tree_only` assigns `tree_only`, and `include` restores `full`.

A path in `exclude` does not also need to appear in `tree_only`; omission always implies that contents are omitted. This is the main difference from the former independent tree/content configuration.

Within one configuration file the shorthand lists are applied in this order:

```text
exclude < tree_only < include
```

Thus a more permissive list can intentionally override a less permissive one for a more specific pattern.

## Hierarchical precedence

Rules are applied from broadest to most specific source:

```text
bundled defaults
< repository-root .grobl.toml
< deeper .grobl.toml files, root to leaf
< explicit --config
< CLI rules
```

Patterns in a `.grobl.toml` are relative to the directory containing that file. Bundled defaults and CLI patterns are relative to the resolved repository root.

Later layers supersede earlier layers. This allows a repository default such as `tree_only = ["docs/"]` to be overridden by a deeper configuration or by `--include docs/architecture.md`.

With `ignore_policy = "auto"`, `inherit_defaults = false` removes only layer 1 from that sequence. An explicit CLI source-selection choice such as `--ignore-policy defaults` or `--ignore-policy all` has higher precedence and can re-enable the bundled layer.

## Persistent scan behavior

Stable scan-wide CLI behavior can be stored in general configuration. Explicit CLI options always win:

```toml
scope = "all"
format = "llm"
summary = "auto"
summary_style = "compact" # only when summary resolves to table
lines = true
characters = true
tokens = true
inclusion_status = true
ignore_policy = "auto"
```

The existing `include_tree_tags` and `include_file_tags` settings remain configurable as well. Routing and invocation controls stay CLI-only: `--copy`, `--output`, `--stdout`, `--json`, `--summary-to`, `--summary-output`, `--config`, logging flags, and `--interactive/--no-interactive`.

General non-policy values use the normal scalar merge precedence (bundled values, XDG/project/pyproject/environment sources, explicit config, then explicit CLI values). Inclusion patterns retain the separate hierarchical root-to-leaf policy layering above because each policy source has its own matching base.

## Pattern semantics

Patterns use gitignore-style matching, including `**` and negation. A negated restrictive rule restores `full` inclusion. Prefer the explicit `include` list for new configuration because it states the resulting policy directly.

## Compatibility keys

Existing configurations remain readable:

- `exclude_tree` maps to `omit`.
- `exclude_print` and `exclude_content` map to `tree_only`.
- If the same path appears in both legacy tree and content exclusion lists, `omit` wins.

When any canonical inclusion key (`exclude`, `tree_only`, or `include`) is present in a configuration source, that source is interpreted using the canonical model. New configurations should not mix canonical and legacy keys.

### Migrating legacy files

Use the migration command to convert a legacy-only file to the canonical lists:

```bash
grobl config migrate .grobl.toml
```

In-place migration keeps the original as `.grobl.toml.bak` by default. Use `--no-backup` to suppress the backup, `--stdout` to preview the translated TOML without writing it, or `--check` to exit nonzero when legacy keys are still present.

The migration removes exact content-exclusion duplicates that are already dominated by an `exclude_tree` rule. When both legacy tree and content scopes contain patterns, grobl emits a warning because different overlapping glob patterns cannot always be proven equivalent under the canonical grouped precedence. Mixed canonical/legacy files are rejected rather than guessed.

Normal `scan` and `explain` invocations also detect applicable legacy-schema `.grobl.toml` files. In an interactive terminal Grobl offers to migrate each one, preserving a `.bak` file, then offers structural pruning and separately offers current-tree pruning with its repository-state warning. Noninteractive invocations never block or modify configuration; they emit a concise migration warning and continue with compatibility parsing. Use `--interactive` or `--no-interactive` to override TTY auto-detection explicitly.

## Pruning redundant canonical rules

Use `grobl config prune [PATH]` after migration when a canonical file has accumulated redundant rules:

```bash
grobl config prune .grobl.toml --stdout
```

Default pruning is tree-independent structural cleanup. It removes rules shadowed by later identical matchers in the same source, empty canonical policy keys whose removal leaves the source policy unchanged, and non-policy settings that exactly repeat the value inherited from lower-precedence configuration. When removals empty a comment-labelled subsection of a policy array, that orphaned comment group is removed as well.

In-place pruning creates `PATH.bak` by default; `--check` exits nonzero when pruning is available, and `--stdout` previews without writing.

To consider exact repetitions of inherited same-base policy, opt into repository-state analysis:

```bash
grobl config prune .grobl.toml --current-tree --stdout
```

For each exact inherited same-base policy duplicate candidate, grobl removes the rule only when a counterfactual matcher produces the same effective states for the currently traversable tree rooted at the config directory. Unique rules are not candidates merely because no path currently matches them. This mode is deliberately repository-state dependent, so future paths can make a previously redundant inherited rule useful again.

A non-policy setting is pruned only when its value equals the value actually inherited from earlier general-config sources. For example, a project setting that resets an XDG override is retained even when it happens to equal the bundled default.

Legacy policy files are rejected by `config prune`; run `grobl config migrate` first.

## Tag settings

The LLM payload wrapper names remain configurable:

```toml
include_tree_tags = "directory"
include_file_tags = "files"
```
