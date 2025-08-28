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

## Large Repos

- Use ignore patterns and modes to limit payload size.
- Prefer `--mode summary` or `--mode tree` to explore structure first.
- Use `--output` for large payloads and inspect with external tools.
