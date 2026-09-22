# Configuration

grobl reads hierarchical `.grobl.toml` files. The bundled defaults ship with the package, and `grobl init` writes the current default configuration to a target directory.

## Creating a configuration file

```bash
grobl init --path .
```

Add `--force` to replace an existing file.

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
