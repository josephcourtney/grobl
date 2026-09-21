# grobl

grobl is a command-line utility that condenses a directory into a concise context payload for LLMs. It scans input paths, builds a directory tree, collects text file contents (with metadata), and emits a well-structured payload while respecting ignore patterns.

## Principles

grobl optimizes for three things:

* prompt-ready output for humans and LLM tooling
* deterministic machine-readable payloads and summaries
* explainable exclusions via `grobl explain`

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
  grobl scan --output context.txt
  ```

  The payload goes to `context.txt`; the human summary is still printed to stderr.

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
  grobl scan --json
  ```

* Emit a payload to stdout while keeping the human summary on stderr:

  ```bash
  grobl scan --stdout --summary table
  ```

## Commands

The `grobl` entry point behaves like `grobl scan` when no subcommand is given, but `grobl --help` shows the real top-level command list.

### `grobl scan [OPTIONS] [PATHS...]`

Main command: traverse paths and build LLM/MARKDOWN/JSON-friendly output.

* If `PATHS` is omitted, the current directory is used.
* If you pass only a single file, grobl treats its **parent directory** as the tree root (the file is still included).

### `grobl explain [OPTIONS] [PATHS...]`

Report the effective inclusion state for provided paths without emitting a payload.

* `--format {human,markdown,json}` selects the explain renderer (`human` is an alias for `markdown`).
* The output reports the effective `full`, `tree_only`, or `omit` state plus the winning rule and source.
* JSON retains derived `tree` and `content` booleans for compatibility and reports `text_detection` when a `full` file is omitted because it is non-text.
* Use `--include PATTERN` to override a lower-precedence `exclude` or `tree_only` rule for the current invocation.

Examples:

```bash
grobl explain README.md --format json
grobl explain --include 'docs/architecture.md' docs/architecture.md
grobl explain src/grobl --format human
```

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
--stdout
--json
```

* `llm` (default): emit an XML-like, LLM-oriented payload (see **LLM payload format** below)
* `markdown`: emit a Markdown payload containing a directory tree and per-file blocks with metadata headers and fenced contents
* `json`: emit a structured JSON payload (see **JSON formats** below)
* `ndjson`: emit the same summary data as JSON but as newline-delimited records with stable key ordering
* `none`: do not emit any payload; only build a summary (if enabled)
* `--stdout`: shorthand for `--output -`
* `--json`: shorthand for `--format json --summary none --output -`

The payload is always written to a clipboard or file destination (see below), not to stderr. If you choose `--format none` and also disable the summary (`--summary none`), grobl exits with a usage error (there would be nothing to do).

### Summary: light metadata output

```bash
--summary {auto,none,table,json}
--summary-style {auto,full,compact}
--summary-to {stderr,stdout,file}
--summary-output PATH
--lines/--no-lines
--characters/--no-characters
--tokens/--no-tokens
--inclusion-status/--no-inclusion-status
```

* `--summary auto` (default): behave like `table` when stdout is a TTY and like `none` otherwise.
* `--summary table`: print a human-readable summary to the selected destination.
  * `--summary-style auto` (default) chooses `full` on TTYs and `compact` otherwise.
  * `--summary-style full` renders the directory tree plus totals.
  * `--summary-style compact` prints just the totals (`Total lines: ...`).
* `--summary json`: print a JSON summary; the emitted object still records the requested table style in the `"style"` field.
  * When a file’s contents are omitted, the corresponding entry includes a `content_reason` object describing the winning pattern (or the `<non-text>` detector) so scripts can trace the exclusion.
* `--summary none`: omit any summary output.

Summary routing uses `--summary-to`. The default destination is `stderr`, keeping the summary separate from payload streams.
`--summary-to stdout` routes the summary into stdout (useful for simple scripts) and `--summary-to file` requires `--summary-output PATH` to write the summary to disk.
When the payload already writes to stdout (for example via `--output -`), the summary remains on stderr unless you explicitly route it elsewhere.
When files are present in the tree but their contents are omitted, the human table summary adds a short note pointing to `grobl explain`.

The summary is independent of the payload:

* You can have a summary without a payload (`--format none --summary table`).
* You can have a payload without a summary (`--format json --summary none`).

There is no separate `--quiet` flag; `--summary none` is the explicit way to suppress summary printing.

### Metadata fields: what per-file details to emit

```bash
--lines/--no-lines
--characters/--no-characters
--tokens/--no-tokens
--inclusion-status/--no-inclusion-status
```

These flags control whether scan outputs include line counts, character counts, token counts, and inclusion markers.

They apply consistently across:

* human table summaries
* JSON payload and summary file entries
* `<file:content ...>` attributes in LLM payloads
* `%%%% BEGIN_FILE ...` metadata in Markdown payloads

Example:

```bash
grobl scan --format json --summary none --output payload.json --no-tokens --no-inclusion-status
```

That run still emits paths and content, but omits token metadata and inclusion booleans from the machine-readable output.

### Payload destination: clipboard or file

```bash
--copy
--output PATH
--stdout
```

* When neither `--copy` nor `--output` is provided, the payload is written to the clipboard (the default).
* `--copy` forces clipboard delivery and cannot be combined with `--output` or `--stdout`.
* `--output -` writes the payload to stdout.
* `--stdout` writes the payload to stdout.
* `--output PATH` writes the payload to the specified file.

The **summary** defaults to `stderr`, not stdout. This keeps operator feedback separate from payload streams.

Examples:

```bash
# Default interactive workflow: payload to clipboard, human summary to stderr
grobl scan .

# Payload to stdout, no summary (ideal for tools)
grobl scan --json

# Human summary only (no payload)
grobl scan --format none --summary table

# JSON summary only
grobl scan --format none --summary json

# Payload to a file, human summary to stderr
grobl scan --output context.txt

# Payload to a file in a specific format
grobl scan --format json --output context.txt
```

### Inclusion and config controls

Every path has exactly one inclusion state:

| State | In hierarchy | Contents captured |
| --- | --- | --- |
| `full` | yes | yes, for text files |
| `tree_only` | yes | no |
| `omit` | no | no |

The canonical CLI maps directly to those states:

```bash
--exclude PATTERN          # assign omit
--tree-only PATTERN        # assign tree_only
--include PATTERN          # assign full
--exclude-file PATH
--tree-only-file PATH
--include-file PATH
--config PATH
--ignore-policy {auto,all,none,defaults,config,cli}
```

Unmatched paths are `full`. Because `omit` already implies no content, an excluded path never needs to be repeated in a second content-exclusion list.

The former scoped flags (`--exclude-tree`, `--include-tree`, `--exclude-content`, `--include-content`) are still accepted as compatibility inputs but are hidden from normal help. They compile immediately into `omit`, `tree_only`, or `full`; the core policy does not maintain independent tree/content decisions.

### Inclusion-policy precedence

From lowest to highest precedence:

1. bundled defaults
2. hierarchical `.grobl.toml` files from the repository root toward the scanned path
3. an explicit `--config PATH`
4. CLI inclusion rules

Patterns contributed by each `.grobl.toml` are relative to that file's directory. Default and CLI patterns are relative to the resolved repository root. A later layer supersedes an earlier layer when both match.

Within one canonical TOML source, the shorthand lists are evaluated in this order:

```text
exclude < tree_only < include
```

This makes the common exception pattern direct:

```toml
exclude = [
  ".git/",
  ".venv/",
]

tree_only = [
  "docs/",
  "*.png",
]

include = [
  "docs/architecture.md",
]
```

General non-policy configuration is still loaded through grobl's normal config merge (`XDG`, project config, `pyproject.toml`, environment override, explicit `--config`). Inclusion rules specifically use the hierarchical policy layering above so their pattern bases remain well-defined.

### `extends` in TOML

Config files loaded by grobl can use an `extends` key to reference base configs:

```toml
extends = ["../base.toml", "shared/settings.toml"]
```

Relative paths are resolved relative to the config file containing `extends`. Later files in the chain override earlier values, and cycles are ignored rather than recursed indefinitely.

### Inclusion patterns

Canonical `.grobl.toml` keys are:

* `exclude`: assign `omit`.
* `tree_only`: assign `tree_only`.
* `include`: assign `full`.

Patterns use gitignore-style matching, including `**` and `!pattern`. Negation in a restrictive list restores full inclusion; prefer the explicit `include` list for new configuration.

Legacy configuration remains readable:

* `exclude_tree` maps to `omit`.
* `exclude_print` and `exclude_content` map to `tree_only`.
* if a legacy path is excluded from both tree and content, `omit` wins.

To rewrite a legacy-only file into canonical form:

```bash
grobl config migrate .grobl.toml
```

The command writes in place and creates `.grobl.toml.bak` by default. `--stdout` previews without writing, `--check` reports whether migration is still needed, and `--no-backup` disables the backup. Mixed canonical/legacy files are rejected. If both old tree and content scopes contain patterns, the command warns that overlapping globs should be reviewed after migration.

Example runtime override:

```bash
grobl scan --tree-only "docs/**" --include "docs/architecture.md" .
```

Use `--no-ignore` cautiously: it disables every inclusion-policy rule and can make scans significantly slower and payloads very large.
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

2. **Resolve inclusion policy**

   * grobl assembles bundled defaults, hierarchical `.grobl.toml` files, an optional explicit config, and CLI rules.
   * Gitignore-style patterns resolve every path to one state: `full`, `tree_only`, or `omit`.
   * Later matching layers supersede earlier ones; within canonical shorthand groups, `exclude < tree_only < include`.

3. **Directory traversal**

   * grobl walks the tree depth-first from the scan root.
   * `omit` entries are not rendered. Explicit re-inclusion rules are still allowed to restore descendants.
   * `full` and `tree_only` entries remain visible in the hierarchy.
   * grobl records a textual tree plus deterministic file visit order.

4. **File analysis**

   For each visible file:

   * `tree_only` files are not text-detected or read. grobl records lightweight metadata and the policy reason only.
   * `full` files are text/binary detected.
   * For text files in `full` state:

     * Contents are read as UTF-8.
     * `lines`, `chars`, and token counts are computed.
     * Metadata + contents are stored.
   * For non-text files in `full` state:

     * Contents are not included.
     * `lines = 0`, `chars = size_in_bytes` are recorded.
     * The policy state remains `full`; binary detection is reported separately.

   Special handling:

   * For `.md` files, Markdown code fences (` ``` `) are escaped as `\\```` so that including a payload in another Markdown document does not break fences.

5. **Formatting and output**

   * A directory tree and file metadata/contents are fed into renderers.
   * A summary object is computed (totals + per-file entries).
   * Depending on `--scope`, `--format`, `--summary`, and the destination flags:

     * The selected payload is emitted to the clipboard or the requested file/stdout.
     * A human or JSON summary is printed to the requested summary destination (stderr by default, unless `--summary none`).

## Output destinations and clipboard behavior

grobl copies payloads to the clipboard by default. Use `--copy` to force clipboard delivery, `--output PATH` (use `-` for stdout) to write directly to a file or the terminal, or `--stdout` as a convenience shorthand. `--copy`, `--output`, and `--stdout` are mutually exclusive payload destinations.

When writing to the clipboard fails (e.g., missing backend), grobl logs a structured warning and re-raises the exception so the failure is visible to the caller.

The summary is routed independently and defaults to stderr unless suppressed by `--summary none`.

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
<file:content name="src/main.py" lines="10" chars="120" tokens="31">
def main():
    ...
</file:content>
<file:content name="README.md" lines="42" chars="1024" tokens="221">
# Title
...
</file:content>
</file>
```

Each `<file:content>` element captures:

* `name`: path relative to the root
* `lines`: number of lines in the captured content
* `chars`: number of characters in the captured content
* `tokens`: number of tokens in the captured content using grobl's bundled tokenizer model

These metadata attributes can be suppressed at scan time with `--no-lines`, `--no-characters`, or `--no-tokens`.

Markdown code fences in `.md` files are escaped (` ``` ` → `\\````) inside the `content` so that the entire block can be safely embedded in another Markdown document.

Tag name (`file` above) comes from `include_file_tags` in config.

Which blocks appear is controlled by `--scope`:

* `--scope all` → directory block + file block
* `--scope tree` → directory block only
* `--scope files` → file block only

## JSON formats

grobl uses JSON in two ways:

1. **JSON summary** – printed to the selected summary destination when `--summary json`
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
  * `included`: `true` if the file's content is included in the payload
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

## Troubleshooting

### In tree but no contents

A path in this condition has effective policy state `tree_only`, or is `full` but was rejected by binary detection.

* Run `grobl explain PATH --format json` to distinguish the cases and see the winning rule.
* Use `--include PATTERN` or an `include` entry in `.grobl.toml` to restore `full` policy.

### Docs contents missing

The project configuration can deliberately assign `tree_only` to `docs/` when its structure is useful but its contents are too verbose.

* Add `--include 'docs/**'` for an invocation, or put a more specific pattern in the `include` list.
* Run `grobl explain docs --format json` to inspect the effective state and provenance.

### Binary detection

Binary detection is separate from inclusion policy. A file may have `full` policy while its contents are still omitted because it is not text.

* Summary/explain JSON uses `content_reason.pattern == "<non-text>"` and source `text-detection` for this case.
* Inclusion rules cannot turn binary data into text; `--include` only controls policy eligibility.
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
  grobl scan --exclude "examples/**" .
  ```

* Most heavy directories (`node_modules`, `.venv`, build outputs, coverage artifacts, etc.) are assigned `omit` by the bundled `exclude` list. To include one, either:

  * restore it in a project `.grobl.toml` with `include = ["path/"]`, or
  * use `--include PATH` for one invocation, or
  * disable bundled policy with `-I/--ignore-defaults` and provide your own rules.

Use `--no-ignore` cautiously: it disables every inclusion-policy rule and can significantly increase scan time and payload size.

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
