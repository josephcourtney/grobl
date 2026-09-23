# Usage guide

The `grobl` command groups functionality into subcommands. A first positional token is treated as a subcommand only when it exactly matches a registered command; otherwise Grobl injects `scan`. Thus `grobl src` is equivalent to `grobl scan src`, and nonexistent implicit targets produce path errors rather than unknown-command errors.

## Common workflows

### Copy the current directory to your clipboard

```bash
grobl
```

With default options and an interactive terminal, grobl writes the payload to the clipboard and prints a human-readable summary to stderr (the default summary destination). After a successful copy it also prints a concise stderr receipt with the included file count, token count when enabled, and payload size.

When no payload destination is specified and stdout is not a TTY, grobl writes the payload to stdout instead of touching the clipboard. Summary routing remains independent.

### Save a payload to disk

```bash
grobl scan --output context.txt
```

The payload is written to `context.txt` and the summary remains on stderr.

### Emit only a summary

```bash
grobl scan --format none --summary table
```

Skips payload generation and prints only the human summary.

Use `--summary-to stdout` to combine the summary with stdout or `--summary-to file --summary-output PATH` to persist it elsewhere.

### Machine-oriented output

```bash
grobl scan --json
```

Produces a JSON payload with no human summary and writes it directly to stdout.

### Payload to stdout with operator feedback

```bash
grobl scan --stdout --summary table
```

Writes the payload to stdout while keeping the human summary on stderr.

## Subcommands

### `grobl scan [OPTIONS] [PATHS...]`

Traverse one or more paths, resolve the layered inclusion policy, and emit payloads plus optional summaries. If `PATHS` is omitted, the current directory is scanned. Supplying a single file causes grobl to treat the parent directory as the root while still including the file.

### `grobl init [--path DIR] [--force]`

Bootstrap a minimal commented `.grobl.toml` project-delta configuration. Bundled policy remains package-owned and is inherited implicitly unless `inherit_defaults = false` is set. Without `--force`, grobl refuses to overwrite an existing configuration file.

### `grobl config migrate [PATH]`

Translate a legacy-only `.grobl.toml` inclusion policy to canonical `exclude`, `tree_only`, and `include` keys. In-place migration keeps a `.bak` copy by default; use `--stdout` to preview or `--check` to test whether migration is needed without writing.

### `grobl config prune [PATH]`

Remove redundant entries from a canonical config. Without extra flags, pruning performs tree-independent structural cleanup: shadowed same-source policy rules, semantically empty canonical policy keys, inherited duplicate non-policy settings, and orphaned policy-array comment groups. Add `--current-tree` to counterfactually test exact inherited same-base policy duplicates against the current traversable tree before removing them. `--stdout`, `--check`, and `--backup/--no-backup` mirror the migration command.

### `grobl version`

Print the installed grobl version.

### `grobl completions --shell (bash|zsh|fish)`

Emit shell completion scripts for the requested shell. For example, generate completions for Bash with:

```bash
grobl completions --shell bash > /usr/local/etc/bash_completion.d/grobl
```

Refer to the README for shell-specific installation guidance.

### Inclusion controls

The scan and explain commands expose the three valid path states directly:

```bash
--exclude PATTERN          # omit path from hierarchy and contents
--tree-only PATTERN        # keep hierarchy entry, omit contents
--include PATTERN          # fully include path
--exclude-file PATH
--tree-only-file PATH
--include-file PATH
```

Unmatched paths are fully included by default. `--exclude` therefore does not need a second content-exclusion rule. `--tree-only` is the explicit case for names or hierarchy that are useful even when file contents are not.

CLI rules have higher precedence than bundled defaults and discovered configuration. The legacy scoped flags (`--exclude-tree`, `--include-tree`, `--exclude-content`, and `--include-content`) remain accepted for compatibility but are hidden from normal help and compile into the three-state model.

Use `--ignore-policy auto|all|none|defaults|config|cli` to choose which rule sources participate. `--no-ignore` disables all inclusion-policy rules. In config, `inherit_defaults = false` disables only the bundled policy layer when source selection is automatic.

Persistent config equivalents exist for `scope`, `format`, `summary`, `summary_style`, `lines`, `characters`, `tokens`, `inclusion_status`, `ignore_policy`, `follow_symlinks`, `allow_external_symlinks`, `max_file_bytes`, `max_total_bytes`, and `max_tokens`; explicit CLI values override them. Output destinations, explicit config selection, and logging remain invocation-only.

Content budgets can also be set directly with `--max-file-bytes`, `--max-total-bytes`, and `--max-tokens`. The bundled defaults are 1 MiB per file, 16 MiB total included bytes, and 200,000 included tokens; `0` disables an individual limit. Files that would exceed a budget remain visible but their contents are omitted with an explainable `resource-limit` reason.

The bundled policy conservatively excludes common sensitive filenames and credential locations, including `.env.*`, package-registry credential files, private-key patterns, and common cloud credential paths. This is path-based protection; an explicit `--include` can restore a file when inclusion is intentional.

When scan or explain encounters an applicable legacy inclusion schema, it warns and continues through compatibility parsing without changing configuration. Migration and pruning happen only through the explicit `grobl config migrate` and `grobl config prune` commands.

### Symbolic links

Grobl preserves POSIX symbolic links as relationships in the logical tree and does not dereference them by default. For example, a link may appear as:

```text
alias.py -> ../shared/target.py
```

Use `--follow-symlinks` when the target should be read or traversed. Following remains inside the resolved repository root unless `--allow-external-symlinks` is also supplied:

```bash
grobl scan --follow-symlinks links/
grobl scan --follow-symlinks --allow-external-symlinks links/
```

The same settings can be persisted as `follow_symlinks` and `allow_external_symlinks`. External following cannot be enabled without following itself.

Inclusion rules continue to match the logical link path, not the resolved target pathname. Broken links remain visible but are never followed. Grobl prevents directory-link cycles and avoids duplicate physical traversal when the same target is already selected through its real path. `grobl explain LINK` reports the raw and resolved target, whether it is internal or external, and why it would or would not be followed.

macOS Finder aliases are ordinary files to Grobl; they are not resolved through Finder-specific APIs.

## Global CLI options

All subcommands share the following options:

* `-v, --verbose` – increase log verbosity (`-v` → INFO, `-vv` or higher → DEBUG)
* `--log-level {CRITICAL,ERROR,WARNING,INFO,DEBUG}` – set an explicit log level
* `--debug` – print scan phase timings to stderr without changing payload routing
* `-V, --version` – print the installed version
* `-h, --help` – display help for the command or subcommand

Examples:

```bash
grobl -vv scan --summary table .
grobl --log-level=DEBUG scan .
grobl --debug scan .
```


## Profiling scan performance

Use `--debug` when diagnosing a slow scan:

```bash
grobl --debug
grobl scan --debug .
```

The timing report is written to stderr, independently of payload and summary
destinations. It reports command setup phases plus scan internals such as policy
matching, text detection, file reading, token counting, payload build/write, and
summary generation. Repeated per-file work is accumulated by phase. The
`scan/traversal` line contains its indented file-analysis subphases, so those
child durations should not be added to the parent duration when interpreting the
report.
