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
grobl --output context.txt
```

Equivalent to `grobl scan . --output context.txt`. The payload is written to `context.txt` and the summary remains on stdout.

### Emit only a summary

```bash
grobl scan --format none --summary table
```

Skips payload generation and prints only the human summary.

Use `--summary-to stdout` to combine the summary with stdout or `--summary-to file --summary-output PATH` to persist it elsewhere.

### Machine-oriented output

```bash
grobl scan --format json --summary none --output -
```

Produces a JSON payload with no human summary and writes it directly to stdout.

## Subcommands

### `grobl scan [OPTIONS] [PATHS...]`

Traverse one or more paths, apply ignore rules, and emit payloads plus optional summaries. If `PATHS` is omitted, the current directory is scanned. Supplying a single file causes grobl to treat the parent directory as the root while still including the file.

### `grobl init [--path DIR] [--force]`

Bootstrap a `.grobl.toml` configuration file using the bundled defaults. Without `--force`, grobl refuses to overwrite an existing configuration file.

### `grobl version`

Print the installed grobl version.

### `grobl completions --shell (bash|zsh|fish)`

Emit shell completion scripts for the requested shell. For example, generate completions for Bash with:

```bash
grobl completions --shell bash > /usr/local/etc/bash_completion.d/grobl
```

Refer to the README for shell-specific installation guidance.

### Ignore controls

The `scan` command exposes `--exclude` / `--include` for tree+content rules; `--include` is emitted as a gitignore-style negation (`!PATTERN`). Use scoped variants (`--exclude-tree`, `--include-tree`, `--exclude-content`, `--include-content`) when you only want to affect tree visibility or content capture. `--exclude-file` / `--include-file` normalize the provided path into a repository-root-relative pattern that matches the exact file or directory (directories append `/` automatically). Legacy ignore flags (`--add-ignore`, `--remove-ignore`, `--unignore`, `--ignore-file`) still function but emit a deprecation warning and will be removed in a future major release. `--no-ignore` disables every ignore rule (tree + content).

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
