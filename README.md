# grobl

grobl is a command-line utility that condenses a directory into a concise context payload for LLMs. It scans input paths, builds a directory tree, collects text file contents (with metadata), and emits a well-structured payload while respecting ignore patterns.

## Installation

```bash
uv tool install grobl
```


## Quick Start

Common workflows:

* Scan current directory and copy payload to clipboard (on a TTY):

  ```bash
  grobl
  ```

  This is equivalent to:

  ```bash
  grobl scan .
  ```

  When run interactively (stdout is a TTY) and without overrides:

  * The **payload** (tree + file contents) goes to the clipboard.
  * A **summary** is printed to stdout.

* Save payload to a file:

  ```bash
  grobl --output context.txt
  ```

* Show only a summary table (no file payload):

  ```bash
  grobl --mode summary
  ```

* Suppress human summary (emit payload only):

  ```bash
  grobl --quiet
  ```

## Commands

The `grobl` entry point behaves like `grobl scan` when no subcommand is given.

### `grobl scan [OPTIONS] [PATHS...]`

Main command: traverse paths and build LLM/JSON-friendly output.

* If `PATHS` is omitted, the current directory is used.
* If you pass only a single file, grobl treats its parent directory as the tree root.

Key options:

* Output modes:

  * `--mode all` (default): directory tree + file payload
  * `--mode tree`: directory tree only
  * `--mode files`: file payload only
  * `--mode summary`: no LLM payload; summary only

* Summary format:

  * `--format human` (default): human-readable summary table
  * `--format json`: machine-readable JSON summary (and, in some modes, JSON payload)

* Summary table style:

  * `--table auto` (default): `full` if stdout is a TTY, otherwise `compact`
  * `--table full`: tree with a framed “Project Summary” table
  * `--table compact`: totals only (`Total lines: ...`)
  * `--table none`: no summary text

* Output destination:

  * `--output PATH`: write payload to a file (highest precedence)
  * `--no-clipboard`: disable clipboard even on a TTY
  * `--quiet`: suppress summary output (payload still emitted as configured)

* Ignore and config controls:

  * `-I, --ignore-defaults`: ignore bundled default exclude patterns
  * `--no-ignore`: disable *all* ignore patterns (built-in + config + CLI)
  * `--ignore-file PATH`: read extra ignore patterns (one per line)
  * `--add-ignore PATTERN`: add an extra exclude-tree pattern for this run
  * `--remove-ignore PATTERN`: remove a pattern from the exclude list
  * `--config PATH`: explicit config file path (highest precedence in config chain)

### `grobl init [--path DIR] [--force]`

Bootstrap a default `.grobl.toml` in the target directory:

```bash
grobl init --path .      # write ./.grobl.toml (if not present)
grobl init --path . --force  # overwrite if it exists
```

Behavior:

* Writes the bundled `default_config.toml` to `.grobl.toml` **verbatim**, preserving:

  * One-item-per-line arrays
  * Comments
  * Spacing

* If the target `.grobl.toml` already exists and `--force` is **not** given, the command exits with an error.

### `grobl version`

Print the installed grobl version (derived from the package metadata):

```bash
grobl version
```

### `grobl completions --shell (bash|zsh|fish)`

Print a completion script for the requested shell:

```bash
grobl completions --shell bash
grobl completions --shell zsh
grobl completions --shell fish
```

Typical installation:

* Bash:

  ```bash
  grobl completions --shell bash > /usr/local/etc/bash_completion.d/grobl
  ```

* Zsh:

  ```bash
  grobl completions --shell zsh > ~/.zfunc/_grobl
  fpath+=(~/.zfunc)
  autoload -U compinit && compinit
  eval "$(env _GROBL_COMPLETE=zsh_source grobl)"
  ```

* Fish:

  ```bash
  grobl completions --shell fish > ~/.config/fish/completions/grobl.fish
  ```

## Global CLI options

All subcommands share a top-level CLI group:

* `-v, --verbose`: increase log verbosity

  * `-v` → `INFO`
  * `-vv` or higher → `DEBUG`

* `--log-level {CRITICAL,ERROR,WARNING,INFO,DEBUG}`: explicit log level

* `-V, --version`: same as `grobl version`

* `-h, --help`: help for the group or a subcommand

Example:

```bash
grobl -vv scan --mode summary .
grobl --log-level=DEBUG scan .
```

## Configuration

grobl merges configuration from several sources using a well-defined precedence.

### Configuration precedence

From lowest to highest precedence:

1. **Bundled defaults** (unless `-I/--ignore-defaults` is passed)

2. **XDG config**:

   * `$XDG_CONFIG_HOME/grobl/config.toml`, or
   * `~/.config/grobl/config.toml`

3. **Project config** in the common ancestor directory:

   * `.grobl.toml`

4. **`pyproject.toml`** at the common ancestor:

   * `[tool.grobl]` table

5. **Environment override**:

   * `GROBL_CONFIG_PATH=/path/to/config.toml`

6. **Explicit `--config PATH`** on the CLI

Later sources override earlier ones (`dict`-style merge).

### `extends` in TOML

Config files loaded via grobl can use an `extends` key to reference base configs:

```toml
extends = ["../base.toml", "shared/settings.toml"]

[tool]
# local overrides...
```

Rules:

* Value may be a string or a list of strings.
* Relative paths are resolved relative to the config file’s directory.
* Later files override earlier ones in the `extends` chain.
* Cycles are detected and stop the inheritance chain rather than recursing indefinitely.

### Ignore patterns

Configuration keys (also available to CLI overrides):

* `exclude_tree` (list of patterns)
* `exclude_print` (list of patterns)

Patterns are interpreted with **gitignore-style semantics** using `pathspec`:

* `**` matches multiple directory levels.
* Directories are matched with a trailing `/` in the internal representation.
* Matching works on paths relative to the scan root, using POSIX separators.

At runtime:

* `exclude_tree` controls which files/directories are **hidden from the tree traversal**.
* `exclude_print` controls which files have metadata only (no content captured).

CLI overrides are applied on top of the merged config:

* `--add-ignore PATTERN`: append a pattern to `exclude_tree` (if not already present).
* `--remove-ignore PATTERN`: remove a pattern from `exclude_tree` if present.
* `--ignore-file PATH`: add patterns from files (one pattern per non-comment line).
* `--no-ignore`: force `exclude_tree = []`, disabling **all** tree-level ignores.

### Tag customization

Two config keys control the XML-like tag names for the payload:

* `include_tree_tags` (default: `"directory"`)
* `include_file_tags` (default: `"file"`)

Example in TOML:

```toml
include_tree_tags = "project"
include_file_tags = "snippet"
```

This will emit:

```xml
<project name="..." path="...">
  ...
</project>
<snippet root="...">
  ...
</snippet>
```

instead of `<directory>` / `<file>`.

## How grobl processes a project

1. **Input discovery**

   * CLI paths are resolved.
   * grobl validates that all paths exist; missing paths produce an error.
   * A common ancestor directory is computed. If only a single file is passed, the ancestor is its parent directory.
   * If no real common ancestor (e.g., `/` and `/tmp` only share filesystem root on POSIX), the scan fails with a path error.

2. **Apply ignore rules**

   * The merged config is read based on the common ancestor.
   * `exclude_tree` and `exclude_print` are applied using gitignore-style pattern matching.

3. **Directory traversal**

   * grobl walks the tree depth-first from the common ancestor, respecting `exclude_tree`.
   * It records:

     * A textual tree with ASCII connectors and trailing `/` for directories.
     * File visit order and positions within the tree output.

4. **File analysis**

   For each file:

   * A lightweight text/binary check is applied.
   * For text files:

     * Contents are read (UTF-8, errors ignored).
     * `lines`, `chars` (character count) are computed.
     * The file’s relative path is checked against `exclude_print`:

       * If allowed: metadata + contents are stored.
       * If excluded: only metadata is stored; contents are omitted from the payload.
   * For binary files:

     * No contents are read.
     * `lines = 0`, `chars = size_in_bytes` are recorded.
     * Contents are never included in the payload.

   Special handling:

   * For `.md` files, markdown code fences (` ``` `) are escaped as `\```` so that including a payload in another Markdown document does not break fences.

5. **Formatting and output**

   * A directory tree and file metadata/contents are fed into output renderers.
   * A summary object is computed (totals + per-file entries).
   * Depending on the selected `--mode`, `--format`, and output preferences:

     * An XML-like LLM payload or JSON payload is sent to the output sink.
     * A human or JSON summary is printed (unless suppressed with `--quiet`).

## Output destinations and clipboard behavior

### Output precedence

grobl always routes the **payload** (LLM or JSON) through an output chain with this precedence:

1. **File** (if `--output PATH` is given)
2. **Clipboard** (if allowed)
3. **Stdout**

Clipboard use is controlled by:

* Whether stdout is a TTY (as reported by `sys.stdout.isatty()`), and
* The CLI flag `--no-clipboard`, and
* `no_clipboard = true` in config.

Clipboard is allowed only if:

* stdout is a TTY, and
* `--no-clipboard` is **not** used, and
* `no_clipboard` is **not** set in config.

If clipboard is enabled but copying fails, grobl logs a structured warning and falls back to the next strategy (usually stdout), without aborting the scan.

### Summary output

Summaries are **separate** from the payload:

* For `--format human`:

  * When `--mode summary`, the summary is printed to stdout only (no payload).
  * For other modes, a human summary is printed to stdout (unless `--quiet`, or `--table none`).

* For `--format json`:

  * When `--mode summary`, a JSON summary (see below) is printed to stdout.
  * When `--mode all/tree/files`, a **JSON payload** is written via the output chain; no summary is printed to stdout. This is useful for machine consumption where the payload is the primary output.

The `--quiet` flag always suppresses summary printing (human or JSON), but does **not** affect the payload.

### Broken pipes

If writing to stdout raises a `BrokenPipeError` (e.g., when piping to `head`), grobl:

* Closes stdout,
* Exits with status `0` (treated as success).

This keeps it well-behaved in shell pipelines.

## LLM payload format (human mode)

When `--format human` and `--mode` is **not** `summary`, grobl emits an XML-like payload suitable for LLM contexts.

### Directory tree block

```xml
<directory name="PROJECT" path="/absolute/path/to/PROJECT">
PROJECT/
├── src/
│   └── main.py
└── README.md
</directory>
```

* The first line inside the tag is always `"{root_name}/"`.
* Directories in the tree end with `/`.
* ASCII art connectors (`├──`, `└──`, `│`) indicate structure.

Tag name (`directory` above) comes from `include_tree_tags` in config.

### File contents block

```xml
<file root="PROJECT">
<file:content name="src/main.py" lines="10" chars="120">
def main():
    ...
</file:content>
<file:content name="README.md" lines="42" chars="1024">
# Title
...
</file:content>
</file>
```

Each `<file:content>` element captures:

* `name`: path relative to the root
* `lines`: number of lines in the captured content
* `chars`: number of characters in the captured content

Markdown code fences in `.md` files are escaped (` ``` ` → `\````) inside the `content` so that the entire block can be safely embedded in another Markdown document.

Tag name (`file` above) comes from `include_file_tags` in config.

## JSON formats

grobl uses JSON in two distinct ways:

1. **JSON summary** (printed to stdout when `--format json --mode summary`)
2. **JSON payload** (sent to the sink when `--format json` and `--mode` is `all`, `tree`, or `files`)

### JSON summary schema

Used when:

```bash
grobl scan --mode summary --format json ...
```

Structure:

```json
{
  "root": "/absolute/path/to/PROJECT",
  "mode": "summary",
  "table": "compact",
  "totals": {
    "total_lines": 10,
    "total_characters": 120,
    "all_total_lines": 10,
    "all_total_characters": 1234
  },
  "files": [
    {
      "path": "src/app.py",
      "lines": 10,
      "chars": 120,
      "included": true
    },
    {
      "path": "assets/logo.png",
      "lines": 0,
      "chars": 1110,
      "included": false,
      "binary": true
    }
  ]
}
```

Notes:

* `mode` and `table` reflect the CLI choices.
* `totals` report both:

  * totals for files whose contents were included (`total_*`), and
  * totals for all files seen (`all_total_*`).
* Each file entry has:

  * `path`: path relative to the root
  * `lines`: line count (0 for binaries)
  * `chars`: character count (for binaries, the byte size)
  * `included`: `true` if the file’s content is included in the payload
  * `binary`: `true` for files heuristically treated as binary (`lines == 0`, `chars > 0`, `included == false`)

### JSON payload schema (non-summary modes)

Used when:

```bash
grobl scan --mode all   --format json ...
grobl scan --mode tree  --format json ...
grobl scan --mode files --format json ...
```

In these cases, grobl writes a structured JSON payload to the sink (file/clipboard/stdout) with:

```json
{
  "root": "/absolute/path/to/PROJECT",
  "mode": "all",
  "tree": [
    {"type": "dir",  "path": "."},
    {"type": "dir",  "path": "src"},
    {"type": "file", "path": "src/app.py"}
  ],
  "files": [
    {
      "name": "src/app.py",
      "lines": 10,
      "chars": 120,
      "content": "def main():\n    ..."
    }
  ],
  "summary": {
    "table": "none",
    "totals": {
      "total_lines": 10,
      "total_characters": 120,
      "all_total_lines": 10,
      "all_total_characters": 120
    },
    "files": [
      {
        "path": "src/app.py",
        "lines": 10,
        "chars": 120,
        "included": true
      }
    ]
  }
}
```

* `tree` is present for `mode = all` or `tree`, listing visited entries in traversal order.
* `files` is present for `mode = all` or `files`, listing captured file blobs.
* `summary` matches the summary schema described above, embedded for convenience.

In this JSON mode, **no summary is printed to stdout**; all structured data is routed through the sink.

## Large repositories

For large projects:

* Prefer exploring structure first:

  ```bash
  grobl --mode tree --table compact
  grobl --mode summary
  ```

* Use `--output` when expecting large payloads:

  ```bash
  grobl --output context.txt
  ```

* Restrict scope via paths and ignores:

  ```bash
  grobl scan src tests
  grobl scan --add-ignore "examples/**" .
  ```

* Most heavy directories (`node_modules`, `.venv`, build outputs, coverage artifacts, etc.) are excluded from the tree by default via `exclude_tree` in the bundled config. To include them, either:

  * Override the defaults with a project `.grobl.toml`, or
  * Use `-I/--ignore-defaults` and supply your own `exclude_tree`.

Use `--no-ignore` cautiously: it disables **all** tree-level ignores and can make scans significantly slower and payloads very large.

## Testing

grobl uses `pytest` with coverage:

* Run tests (from the project root):

  ```bash
  uv run pytest
  ```

* Coverage is configured via `pyproject.toml` and `coverage`:

  * Branch coverage enabled (`--cov-branch`)
  * Source limited to `src/grobl`
  * XML report written to `.coverage.xml`

The test suite includes:

* Unit tests for core logic, config, traversal, formatting, logging, and utilities.
* Component tests for CLI behavior (including JSON output and payloads).
* System tests that exercise flows described in this README (quick-start scan, `--output`, `version`, `completions`, `init`).

## Exit codes

grobl uses stable exit codes:

* `0`: success

  * Includes clean `BrokenPipeError` on stdout.
* `2`: usage error

  * Invalid flags or option values (e.g., invalid `--mode`).
* `3`: configuration load error

  * Bad TOML in config files or `pyproject.toml`.
* `4`: path error

  * Invalid paths (nonexistent) or no meaningful common ancestor between paths.
* `130`: interrupted by user (Ctrl-C)

  * On interruption, grobl captures scan state and prints diagnostics for debugging.

These codes are suitable for use in CI pipelines and shell scripts.

