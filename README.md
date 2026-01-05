# grobl

grobl is a command-line utility that condenses a directory into a concise context payload for LLMs. It scans input paths, builds a directory tree, collects text file contents (with metadata), and emits a well-structured payload while respecting ignore patterns.

## Documentation

Project documentation is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/). To work on the docs locally, install the development dependencies and launch the preview server:

```bash
uv sync --group dev
uv run mkdocs serve
```

Build the static site with:

```bash
uv run mkdocs build
```

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

  With default options, when run interactively (stdout is a TTY):

  * The **payload** (tree + file contents, LLM-oriented) goes to the **clipboard**.
  * A human **summary** is printed to **stderr** (the default summary destination).

* Save payload to a file:

  ```bash
  grobl --output context.txt
  ```

  This is equivalent to:

  ```bash
  grobl scan . --output context.txt
  ```

  The payload goes to `context.txt`; the human summary is still printed to stdout.

* Show only a summary table (no payload):

  ```bash
grobl scan --format none --summary table
  ```

* Emit only a JSON summary (no LLM payload):

  ```bash
grobl scan --format none --summary json
  ```

* Emit a JSON payload and no summary (machine-only):

  ```bash
grobl scan --format json --summary none --output -
  ```

## Commands

The `grobl` entry point behaves like `grobl scan` when no subcommand is given.

### `grobl scan [OPTIONS] [PATHS...]`

Main command: traverse paths and build LLM/MARKDOWN/JSON-friendly output.

* If `PATHS` is omitted, the current directory is used.
* If you pass only a single file, grobl treats its **parent directory** as the tree root (the file is still included).

### `grobl init [--path DIR] [--force]`

Bootstrap a default `.grobl.toml` in the target directory:

```bash
grobl init --path .           # write ./.grobl.toml (if not present)
grobl init --path . --force   # overwrite if it exists
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

Examples:

```bash
grobl -vv scan --summary table .
grobl --log-level=DEBUG scan .
```

## Scan options

The `scan` command controls four orthogonal concerns:

1. **Scope** – what to collect (tree, files, or both)
2. **Payload** – heavy output format (LLM XML-like, JSON, or none)
3. **Summary** – light metadata output (human, JSON, or none)
4. **Sink** – where the payload is sent (clipboard, stdout, file)

### Scope: what to collect

```bash
--scope {all,tree,files}
```

* `all` (default): collect both directory tree and file contents
* `tree`: collect only the directory tree (no file contents)
* `files`: collect only file contents/payload; the tree is used internally but not emitted in the payload

Scope affects:

* What goes into the payload (tree, files, or both)
* Which files contribute to line/character totals in the summary

### Payload: heavy output

```bash
--format {llm,markdown,json,ndjson,none}
```

* `llm` (default): emit an XML-like, LLM-oriented payload (see **LLM payload format** below)
* `markdown`: emit a Markdown payload containing a directory tree and per-file blocks with metadata headers and fenced contents
* `json`: emit a structured JSON payload (see **JSON formats** below)
* `ndjson`: emit the same summary data as JSON but as newline-delimited records with stable key ordering
* `none`: do not emit any payload; only build a summary (if enabled)

The payload is always written to a clipboard or file destination (see below), not to stderr. If you choose `--format none` and also disable the summary (`--summary none`), grobl exits with a usage error (there would be nothing to do).

### Summary: light metadata output

```bash
--summary {auto,none,table,json}
--summary-style {auto,full,compact}
--summary-to {stderr,stdout,file}
--summary-output PATH
```

* `--summary auto` (default): behave like `table` when stdout is a TTY and like `none` otherwise.
* `--summary table`: print a human-readable summary to the selected destination.
  * `--summary-style auto` (default) chooses `full` on TTYs and `compact` otherwise.
  * `--summary-style full` renders the directory tree plus totals.
  * `--summary-style compact` prints just the totals (`Total lines: ...`).
* `--summary json`: print a JSON summary; the emitted object still records the requested table style in the `"style"` field.
* `--summary none`: omit any summary output.

Summary routing uses `--summary-to`. The default destination is `stderr`, keeping the summary separate from payload streams.
`--summary-to stdout` routes the summary into stdout (useful for simple scripts) and `--summary-to file` requires `--summary-output PATH` to write the summary to disk.
When the payload already writes to stdout (for example via `--output -`), the summary remains on stderr unless you explicitly route it elsewhere.

The summary is independent of the payload:

* You can have a summary without a payload (`--format none --summary table`).
* You can have a payload without a summary (`--format json --summary none`).

There is no separate `--quiet` flag; `--summary none` is the explicit way to suppress summary printing.

### Payload destination: clipboard or file

```bash
--copy
--output PATH
```

* When neither `--copy` nor `--output` is provided, the payload is written to the clipboard (the default).
* `--copy` forces clipboard delivery and cannot be combined with `--output`.
* `--output -` writes the payload to stdout.
* `--output PATH` writes the payload to the specified file.

The **summary** is always printed to stdout (unless `--summary none`) regardless of the payload destination. This makes it easy to both pipe or capture payloads while still seeing a quick human or JSON summary.

Examples:

```bash
# Default interactive workflow: payload to clipboard, human summary to stdout
grobl scan .

# Payload to stdout, no summary (ideal for tools)
grobl scan --format json --summary none --output -

# Human summary only (no payload)
grobl scan --format none --summary table

# JSON summary only
grobl scan --format none --summary json

# Payload to a file, human summary to stdout
grobl scan --output context.txt

# Payload to a file in a specific format
grobl scan --format json --output context.txt
```

### Ignore and config controls

Configuration and ignore behavior are shared across all scan modes:

```bash
--no-ignore-defaults   # disable bundled default ignore rules
-I, --ignore-defaults  # (alias) disable bundled default ignore rules
--no-ignore-config     # disable ignore rules from all discovered .grobl.toml files
--no-ignore            # disable all ignore patterns (built-in + config + CLI)
--ignore-file PATH     # read extra ignore patterns (one per non-comment line)
--add-ignore PATTERN   # add an extra exclude-tree pattern for this run
--remove-ignore PATTERN # remove a pattern from the exclude list
--unignore PATTERN     # add an exception pattern for this run
--config PATH          # explicit config file path (highest precedence, must exist)
```

Rules:

* `--no-ignore` forces `exclude_tree = []`, disabling **all** tree-level ignores.
* `--no-ignore-defaults` disables bundled defaults, but keeps config/runtime ignores.
* `--no-ignore-config` disables ignores from `.grobl.toml` files, but keeps defaults/runtime ignores.
* `--ignore-file PATH` reads patterns from files; empty lines and lines starting with `#` are ignored.
* `--config PATH` must point to an existing file; if it does not, grobl treats this as a configuration error and exits.

### Configuration precedence

From lowest to highest precedence:

1. **Bundled defaults** (unless `-I/--ignore-defaults` is passed)

2. **XDG config**:

   * `$XDG_CONFIG_HOME/grobl/config.toml`, or
   * `~/.config/grobl/config.toml`

3. **Project config** in the scan root:

   * `.grobl.toml`

4. **`pyproject.toml`** at the scan root:

   * `[tool.grobl]` table

5. **Environment override**:

   * `GROBL_CONFIG_PATH=/path/to/config.toml`

6. **Explicit `--config PATH`**

Later sources override earlier ones (dictionary-style merge).

### `extends` in TOML

Config files loaded by grobl can use an `extends` key to reference base configs:

```toml
extends = ["../base.toml", "shared/settings.toml"]

[tool]
# local overrides...
```

Rules:

* Value may be a string or a list of strings.
* Relative paths are resolved relative to the config file’s directory.
* Later files override earlier ones in the `extends` chain.
* Cycles are detected and break the inheritance chain instead of recursing indefinitely.

### Ignore patterns

Configuration keys (also available to CLI overrides):

* `exclude_tree` (list of patterns)
* `exclude_print` (list of patterns)

Patterns use **gitignore-style semantics** via `pathspec`:

* `**` matches multiple directory levels.
* Directories are matched with a trailing `/` in the internal representation.
* Matching uses separators.

Ignore sources are layered and have different “pattern bases”:

1. **Bundled defaults** (base = repository root)
2. **Hierarchical `.grobl.toml` ignores** discovered from repository root down to the scanned directories
   * Each `.grobl.toml` contributes `exclude_tree` / `exclude_print`
   * Patterns from a given `.grobl.toml` are interpreted **relative to that file’s directory**
3. **Runtime/CLI ignores** (base = repository root)

Within a layer, patterns are evaluated sequentially and **the last matching pattern wins**.
Negation (`!pattern`) is supported.

At runtime:

* `exclude_tree` controls which files/directories are **hidden from the rendered tree and payload**.
  * Note: traversal does not prune excluded directories, so a later negation can re-include descendants.
* `exclude_print` controls which files have metadata only (no content captured).

CLI overrides:

* `--add-ignore PATTERN`: append a pattern to `exclude_tree` (if not already present).
* `--remove-ignore PATTERN`: remove a pattern from `exclude_tree` if present.
* `--unignore PATTERN`: append a negated pattern to `exclude_tree` (e.g. `!tests/fixtures/**/.gitignore`).
* `--ignore-file PATH`: add patterns from files (one pattern per non-comment line).
* `--no-ignore`: force `exclude_tree = []`, disabling **all** tree-level ignores.

Example:

```bash
# Re-include only .gitignore files under tests/fixtures
grobl scan --unignore "tests/fixtures/**/.gitignore" .
```

Use `--no-ignore` cautiously: it disables all tree-level ignores and can make scans significantly slower and payloads very large.

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
   * If the only shared ancestor is the filesystem root (e.g., `/` and `/tmp` on POSIX), the scan fails with a path error.

2. **Apply ignore rules**

   * The merged config is read based on the scan root (common ancestor).
   * `exclude_tree` and `exclude_print` are applied using gitignore-style pattern matching.

3. **Directory traversal**

   * grobl walks the tree depth-first from the scan root, respecting `exclude_tree`.
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
       * If excluded: only metadata is stored; contents are omitted.
   * For binary files:

     * No contents are read.
     * `lines = 0`, `chars = size_in_bytes` are recorded.
     * Contents are never included in the payload.

   Special handling:

   * For `.md` files, Markdown code fences (` ``` `) are escaped as `\\```` so that including a payload in another Markdown document does not break fences.

5. **Formatting and output**

   * A directory tree and file metadata/contents are fed into renderers.
   * A summary object is computed (totals + per-file entries).
   * Depending on `--scope`, `--format`, `--summary`, and the destination flags:

     * The selected payload is emitted to the clipboard or the requested file/stdout.
     * A human or JSON summary is printed to stdout (unless `--summary none`).

## Output destinations and clipboard behavior

grobl copies payloads to the clipboard by default. Use `--copy` to force clipboard delivery, or `--output PATH` (use `-` for stdout) to write directly to a file or the terminal. `--copy` and `--output` cannot be used together; doing so emits a usage error.

When writing to the clipboard fails (e.g., missing backend), grobl logs a structured warning and re-raises the exception so the failure is visible to the caller.

The summary is printed to stdout independently, unless suppressed by `--summary none`.

### Broken pipes

If writing to stdout raises a `BrokenPipeError` (e.g., when piping to `head`), grobl:

* Closes stdout
* Exits with status `0` (treated as success)

This keeps it well-behaved in shell pipelines.

## LLM payload format (payload = llm)

When `--format llm` and scope includes the tree and/or files, grobl emits an XML-like payload suitable for LLM contexts.

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

Markdown code fences in `.md` files are escaped (` ``` ` → `\\````) inside the `content` so that the entire block can be safely embedded in another Markdown document.

Tag name (`file` above) comes from `include_file_tags` in config.

Which blocks appear is controlled by `--scope`:

* `--scope all` → directory block + file block
* `--scope tree` → directory block only
* `--scope files` → file block only

## JSON formats

grobl uses JSON in two ways:

1. **JSON summary** – printed to stdout when `--summary json`
2. **JSON payload** – written to the selected destination when `--format json`

### JSON summary schema

Used when:

```bash
grobl scan --summary json ...
```

Structure:

```json
{
  "root": "/absolute/path/to/PROJECT",
  "scope": "all",
  "style": "compact",
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

* `scope` reflects `--scope`.
* `style` reflects `--summary-style`.
* `totals` report both:

  * totals for files whose contents were included (`total_*`), and
  * totals for all files seen (`all_total_*`).
* Each file entry has:

  * `path`: path relative to the root
  * `lines`: line count (0 for binaries)
  * `chars`: character count (for binaries, the byte size)
  * `included`: `true` if the file’s content is included in the payload
  * `binary`: `true` for files heuristically treated as binary (`lines == 0`, `chars > 0`, `included == false`)

### JSON payload schema (format = json)

Used when:

```bash
grobl scan --format json ...
```

In these cases, grobl writes a structured JSON payload to the selected destination with:

```json
{
  "root": "/absolute/path/to/PROJECT",
  "scope": "all",
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
    "style": "none",
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

* `tree` is present when `--scope` is `all` or `tree`, listing visited entries in traversal order.
* `files` is present when `--scope` is `all` or `files`, listing captured file blobs.
* `summary` matches the summary schema described above, embedded for convenience.
* Whether a separate summary is printed depends on `--summary` and the requested destination (`--summary-to` defaults to stderr):

  * `--summary none` → no extra output
  * `--summary json` → an additional summary JSON is printed to the summary destination (stderr by default)
  * `--summary table` → a human summary is printed to the summary destination (stderr by default)

## Large repositories

For large projects:

* Prefer exploring structure first:

  ```bash
  grobl scan --scope tree --summary table
  grobl scan --format none --summary table
  ```

* Use `--output` when expecting large payloads:

  ```bash
  grobl scan --output context.txt
  ```

* Restrict scope via paths and ignores:

  ```bash
  grobl scan src tests
  grobl scan --add-ignore "examples/**" .
  ```

* Most heavy directories (`node_modules`, `.venv`, build outputs, coverage artifacts, etc.) are excluded from the tree by default via `exclude_tree` in the bundled config. To include them, either:

  * Override the defaults with a project `.grobl.toml`, or
  * Use `-I/--ignore-defaults` and supply your own `exclude_tree`, or
  * Use `--no-ignore` to disable all tree-level ignores.

Use `--no-ignore` cautiously: it disables **all** tree-level ignores and can significantly increase scan time and payload size.

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

  * Invalid flags or option values (e.g., unknown `--scope`, combining `--copy` with `--output`, or `--format none --summary none`).
* `3`: configuration load error

  * Bad TOML in config files or `pyproject.toml`.
  * Explicit `--config PATH` that cannot be loaded.
* `4`: path error

  * Invalid paths (nonexistent) or no meaningful common ancestor between paths.
* `130`: interrupted by user (Ctrl-C)

  * On interruption, grobl captures scan state and may print diagnostics for debugging.

These codes are suitable for use in CI pipelines and shell scripts.
