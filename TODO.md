# TODO

## CLI and UX

- [ ] add `--config <path>` CLI flag to explicitly select a config file
- [ ] load config from the scan’s common ancestor directory instead of `cwd` (fallback to `cwd` only when appropriate)
- [ ] implement `--quiet` to suppress the human summary (retain LLM payload emission rules)
- [ ] warn or error when `--mode summary --table none` would produce no output; document intended behavior
- [ ] generate shell completions (bash/zsh/fish) using Click and document installation
- [ ] auto-select table style: use `full` when stdout is a TTY, `compact` otherwise (override via `--table`)

## Configuration & Ignore Behavior

- [ ] support `--gitignore` (opt-in) to merge patterns from `.gitignore`/`.ignore` files
- [ ] add `--ignore-file <path>` and `--no-ignore` flags for custom ignore sources and disabling ignores
- [ ] expand heavy-directory warnings to trigger when user paths explicitly include known heavy dirs (even with defaults enabled)
- [ ] add `GROBL_CONFIG_PATH` env var and XDG support (`$XDG_CONFIG_HOME/grobl/config.toml`) to config precedence (document order)

## Output & Formats

- [ ] add `--format json` for machine-readable summary output (define and document a stable schema)
- [ ] consider JSON formats for `tree`/`files` modes (investigate feasibility and size/streaming considerations)
- [ ] auto-disable clipboard when stdout is not a TTY or when running non-interactively; prefer stdout in such cases (document precedence)
- [ ] ensure logs/diagnostics go to `stderr` while structured or primary outputs go to `stdout` (audit and adjust as needed)

## Safety & Robustness

- [ ] do not follow directory symlinks by default; guard against symlink cycles (add detection and tests)
- [ ] handle `BrokenPipeError`/SIGPIPE gracefully (no traceback; clean exit code suitable for pipelines)
- [ ] refine exit codes and document them (usage/config/path errors vs interrupt 130)

## Documentation

- [ ] expand README with: installation (uv/pip), quick start, command synopsis, subcommands, examples for `scan`, `init`, `--mode`, `--table`, `--output`, `--no-clipboard`, configuration precedence, heavy-dir warnings, exit codes
- [ ] document LLM payload format (tree/files tags, `<file:content>` wrapper), tag customization, and escaping rules
- [ ] add guidance on large repos and performance expectations; suggest using ignores and modes
- [ ] create `CHANGELOG.md` (Keep a Changelog format) and keep it updated with version bumps

## Testing

- [ ] add tests for config loading precedence: `.grobl.toml`, legacy `.grobl.config.toml`, `[tool.grobl]` in `pyproject.toml`, `--config`, env var/XDG (when implemented)
- [ ] test reading config from common ancestor vs `cwd` with multiple input paths
- [ ] test directory traversal ordering, exclusion rules (`exclude_tree`), and `exclude_print`
- [ ] test file content collection and metadata accounting (lines/chars, included markers)
- [ ] test CLI flags matrix: `--mode`, `--table`, `--output`, `--no-clipboard`, `-I`, `--add-ignore`, `--remove-ignore`, `--quiet`
- [ ] test legacy migration prompts and reference scanning for `.grobl.config.toml`
- [ ] test interrupt path: partial state diagnostics and exit code 130
- [ ] test output sink precedence (file → clipboard → stdout) and clipboard failure handling
- [ ] test symlink skipping and cycle protection
- [ ] test non-TTY behavior for table auto-selection and clipboard auto-disable

## Internal/Refactoring

- [ ] refactor CLI to pass the computed common-ancestor path into config load routines
- [ ] centralize TTY detection and output-mode decisions in a small helper module
- [ ] audit stderr/stdout usage and add a minimal logging policy in docs

