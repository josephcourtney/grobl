# grobl

grobl is a command-line utility that condenses a directory into a concise context payload for LLMs. It scans input paths, builds a directory tree, collects text file contents (with metadata), and emits a well-structured payload while respecting ignore patterns.

## Installation

- uv: `uv tool install grobl` or add to a project and `uv run grobl`.
- pip: `pip install grobl` (when distributed on PyPI).

## Quick Start

- Scan current directory and copy payload to clipboard (TTY): `grobl`
- Save payload to a file: `grobl --output context.txt`
- Show only a summary table: `grobl --mode summary`
- Suppress human summary (payload only): `grobl --quiet`

## Command Synopsis

- `grobl scan [OPTIONS] [PATHS...]` (default subcommand if omitted)
- `grobl init [--path DIR] [--force] [--yes]`
- `grobl version`
- `grobl completions --shell (bash|zsh|fish)`

Key options:
- `--mode {all,tree,files,summary}`: choose payload parts to emit
- `--table {auto,full,compact,none}`: summary table style (auto uses TTY)
- `--output PATH`: write payload to a file (preferred over clipboard/stdout)
- `--no-clipboard`: bypass clipboard and print to stdout
- `-I/--ignore-defaults`: ignore bundled defaults
- `--ignore-file PATH`: read extra ignore patterns (one per line)
- `--add-ignore PATTERN`/`--remove-ignore PATTERN`
- `--config PATH`: explicit config
- `--quiet`: suppress human summary (payload still emitted as configured)
- `--format {human,json}`: choose human-readable or JSON summary output

## Configuration Precedence

Low → high precedence:
1) bundled defaults (unless `-I`)
2) XDG: `$XDG_CONFIG_HOME/grobl/config.toml` (or `~/.config/grobl/config.toml`)
3) project files at common ancestor: `.grobl.toml` or legacy `.grobl.config.toml`
4) `[tool.grobl]` in `pyproject.toml`
5) env: `GROBL_CONFIG_PATH`
6) explicit `--config PATH`

Supports `extends` in TOML (string or list): later files override earlier ones.

Tag customization:
- Configure tag names via TOML: `include_tree_tags = "directory"`, `include_file_tags = "file"`.

## Heavy Directory Warnings

If default ignores are disabled or you explicitly target known heavy directories (e.g., `node_modules`, `.venv`), grobl will warn and ask to continue unless `--yes` is passed.

## Logging and Streams

- Primary/structured outputs (payload, summaries) go to stdout.
- Logs and diagnostics go to stderr.
- Clipboard is auto-disabled when stdout is not a TTY. Output precedence: file → clipboard → stdout.

## Shell Completions

Generate and install completion scripts per shell:
- Bash: `grobl completions --shell bash > /usr/local/etc/bash_completion.d/grobl`
- Zsh: `grobl completions --shell zsh > ~/.zfunc/_grobl` then add `fpath+=(~/.zfunc)` and `autoload -U compinit && compinit` in your `.zshrc`.
- Fish: `grobl completions --shell fish > ~/.config/fish/completions/grobl.fish`

## Exit Codes

- 0: success (including clean BrokenPipe/SIGPIPE during stdout)
- 2: usage error (invalid flags/values)
- 3: configuration load error
- 4: invalid paths/no common ancestor
- 130: interrupted by user (Ctrl-C)

## LLM Payload Format

Two XML-like blocks (when `--mode all`):
- Directory tree: `<directory name="ROOT" path="/path">..</directory>`
- File contents: `<file root="ROOT"> <file:content name="rel/path" lines="N" chars="M">..</file:content> ... </file>`

Markdown code fences in `.md` files are escaped to avoid breaking formatting.

## JSON Summary

When `--format json` is used, grobl prints a machine-readable summary to stdout.
Schema (stable keys, deterministic ordering):

- root: absolute path to the common ancestor directory
- mode: the `--mode` selected (all/tree/files/summary)
- table: the summary table style used (auto/full/compact/none)
- totals: { total_lines, total_characters, all_total_lines, all_total_characters }
- files: list of file entries with keys:
  - path: path relative to `root`
  - lines: number of lines for included text files (0 for binaries)
  - chars: number of characters for included text files (size in bytes for binaries)
  - included: whether the file’s contents are included in the payload
  - binary: present and true for detected binary files
  - binary_details: present for binary files; includes size_bytes and, for common images, width/height and format

Example:

```
{
  "root": "/path/to/project",
  "mode": "summary",
  "table": "compact",
  "totals": {
    "total_lines": 10,
    "total_characters": 120,
    "all_total_lines": 10,
    "all_total_characters": 1234
  },
  "files": [
    {"path": "src/app.py", "lines": 10, "chars": 120, "included": true},
    {
      "path": "assets/logo.png",
      "lines": 0,
      "chars": 1110,
      "included": false,
      "binary": true,
      "binary_details": {"size_bytes": 1110, "format": "png", "width": 512, "height": 512}
    }
  ]
}
```

## Large Repos

- Use ignore patterns and modes to limit payload size.
- Prefer `--mode summary` or `--mode tree` to explore structure first.
- Use `--output` for large payloads and inspect with external tools.

## Testing

- Run tests: `pytest` (coverage and branch coverage enabled via config).
- Branch coverage: configured with `--cov-branch`; reports show branch metrics.
- README smoke tests: exercise quick-start, `--output`, `version`, `completions`, and `init` examples.
- Performance tests: skipped by default in CI; enable with env:
  - `GROBL_RUN_PERF=1 pytest` to run perf tests in CI.
  - `GROBL_PERF_BUDGET_SEC=3.0` to adjust the runtime budget threshold.
