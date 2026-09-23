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

Grobl prunes omitted directories when no restoration rule can possibly match below
them. Narrow restoration patterns therefore preserve fast traversal. Because patterns
use gitignore semantics, a basename-only rule such as `.gitmodules` can match at any
depth and must remain conservative; use a root anchor such as `/.gitmodules` when
only the repository-root file should be restored.

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
follow_symlinks = false
allow_external_symlinks = false
max_file_bytes = 1048576
max_total_bytes = 16777216
max_tokens = 200000
```

A resource-limit value of `0` disables that limit. Budgeted files are omitted as complete units rather than truncated, and the omission reason is available in summaries and `grobl explain`.

The existing `include_tree_tags` and `include_file_tags` settings remain configurable as well. Routing and invocation controls stay CLI-only: `--copy`, `--output`, `--stdout`, `--json`, `--summary-to`, `--summary-output`, `--config`, and logging flags.

General non-policy values use the normal scalar merge precedence (bundled values, XDG/project/pyproject/environment sources, explicit config, then explicit CLI values). Inclusion patterns retain the separate hierarchical root-to-leaf policy layering above because each policy source has its own matching base.

## Symlink policy

Grobl preserves symbolic links as part of the logical tree but does not dereference them by default. A link is rendered as a relationship such as `alias.py -> ../shared/target.py`; broken and external links are marked explicitly. A link itself is not counted as captured file content unless following has been enabled and the target is eligible.

Use either persistent configuration or the corresponding CLI option to follow targets:

```toml
follow_symlinks = true
```

```bash
grobl scan --follow-symlinks .
```

Following remains bounded to the resolved repository root. Crossing that boundary requires a second explicit opt-in:

```toml
follow_symlinks = true
allow_external_symlinks = true
```

```bash
grobl scan --follow-symlinks --allow-external-symlinks .
```

`allow_external_symlinks = true` is invalid unless symlink following is also enabled.

Inclusion patterns are evaluated against the logical path at which a link appears. Traversed descendants continue to use their logical paths beneath the link. Grobl tracks followed directory targets by filesystem identity (`st_dev`, `st_ino`) to prevent cycles and avoids following a link when its physical target is already reachable through a separately selected real path, so the same physical content is not emitted twice merely because it has an alias.

Machine-readable tree output uses `type = "symlink"` and includes the raw target, resolved target when available, target scope, and broken-target state. `grobl explain` reports the same target information together with the reason a link is or is not followed.

macOS Finder aliases are ordinary files from Grobl's perspective. Grobl does not invoke Finder alias-resolution APIs; normal text/binary detection and inclusion policy apply to those files.

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

Normal `scan` and `explain` invocations also detect applicable legacy-schema configuration. They emit a concise migration warning and continue with compatibility parsing, but never migrate, back up, or prune files. Use `grobl config migrate` and `grobl config prune` explicitly for all configuration modifications.

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


## Sensitive-name defaults

The bundled inclusion policy conservatively omits common credential-bearing paths such as `.env.*`, `.npmrc`, `.pypirc`, private-key filename patterns, and common cloud credential locations. These defaults are path-based safeguards, not content-level secret detection. A more specific project `include` rule or CLI `--include` can override them when a sensitive-looking file is intentionally safe to send.
