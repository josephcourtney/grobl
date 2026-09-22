# Usage guide

The `grobl` command groups functionality into subcommands. When invoked without a subcommand, `grobl` behaves as if `grobl scan` was called.

## Common workflows

### Copy the current directory to your clipboard

```bash
grobl
```

With default options and an interactive terminal, grobl writes the payload to the clipboard and prints a human-readable summary to stderr (the default summary destination).

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

Bootstrap a `.grobl.toml` configuration file using the bundled defaults. Without `--force`, grobl refuses to overwrite an existing configuration file.

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

Use `--ignore-policy auto|all|none|defaults|config|cli` to choose which rule sources participate. `--no-ignore` disables all inclusion-policy rules.

## Global CLI options

All subcommands share the following options:

* `-v, --verbose` – increase log verbosity (`-v` → INFO, `-vv` or higher → DEBUG)
* `--log-level {CRITICAL,ERROR,WARNING,INFO,DEBUG}` – set an explicit log level
* `-V, --version` – print the installed version
* `-h, --help` – display help for the command or subcommand

Examples:

```bash
grobl -vv scan --summary table .
grobl --log-level=DEBUG scan .
```
