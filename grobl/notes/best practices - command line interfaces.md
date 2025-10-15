---
aliases:
  - Best Practices - Command line Interfaces
created: 2025-04-19|11:13
linter-yaml-title-alias: Best Practices - Command line Interfaces
modified: 2025-07-30|10:16
status: beta
tags: []
title: Best Practices - Command line Interfaces
---

# Best Practices - Command line Interfaces

## Core Guidelines

## CLI Design Fundamentals

### Follow Platform and Shell Conventions
Design CLI tools to align with Unix-like systems and shell idioms. Minimize surprises by adhering to conventions for argument syntax, environment variables, signals, and file/path handling.

### Make the CLI Discoverable
Support both human discoverability (`--help`, man pages) and machine discoverability (stable parsing, predictable exit codes). Avoid dynamic help text unless necessary.

### Command Line Parsing

- Use short (`-x`) and long (`--example`) flags.
- Support `--` to end option parsing.
- Implement `-h`/`--help` and `-V`/`--version` by default.
- Reserve:
  - `-v`/`--verbose` for verbosity when possible. If implementing a filter-style tool (e.g., grep-like), `-v` may instead mean "invert-match".
  - `-q`/`--quiet` to suppress output where feasible. If a legacy meaning exists, document clearly.
  - `-0`/`--null` for NUL-terminated output.
- Document parsing conventions (e.g., `--color`, `--config`).

### Exit Behavior

- Exit codes:
  - `0`: success
  - `1`: success with no result (for filter tools only)
  - `2` or higher: error
  - Where appropriate, align with `<sysexits.h>` or document your own error codes.
- Log errors to `stderr`. Do not suppress unless `--quiet` is set.
- Do not exit silently on failure unless explicitly requested.

## Usability and Documentation

- Include concise examples in `--help` and man pages.
- Ship full man pages with `SYNOPSIS`, `OPTIONS`, `EXAMPLES`.
- Support i18n via gettext or pluggable message files.

### Interface Shape

- Use subcommands (e.g., `git push`) if your tool has clearly separable verbs with distinct arguments.
- Prefer a single-command interface if all functionality centers on a single domain or mode of operation.
- Evaluate subcommands for scalability, tab-completion, and future extensibility.

## Terminal Capabilities

- Use standard ANSI CSI/OSC sequences or query via `terminfo` and `$TERM`.
- For REPLs/prompt tools, support basic line editing:
  - Ctrl‑A / Home: start of line
  - Ctrl‑E / End: end of line
  - Ctrl‑W: delete word
  - Ctrl‑U: delete line
  - Ctrl‑R: reverse search
  - Ctrl‑C: cancel line
  - Ctrl‑L: clear screen
  - Arrow keys: movement
  - If lacking, recommend using `rlwrap`.

## I/O And Interface Behavior

### Input & Output
- Direct regular output to `stdout`, diagnostics to `stderr`.
- Use `-` as a stand-in for stdin/stdout.
- Provide `--line-buffered` or `-u` for line-buffered output where unbuffered streaming is needed.
- Respect `SIGPIPE` failures silently—avoid stack traces on pipe closures.

#### Structured Output
- Output Modes:
  - Document output (e.g., `--output=json`): Emit a single complete JSON/YAML object.
  - Record stream output (e.g., `--json`, `--seq`, ND-JSON): Emit newline-delimited objects or status records.
- Schema Stability:
  - Document the structure for both document and stream modes.
  - Version the format and avoid unannounced breaking changes.
- Type Separation:
  - Logs go to `stderr`; structured data to `stdout`.
- Custom Format Strings:
  - Support a `--format` or `--write-out` option for assembling single-line output reports.
- Pretty vs. Compact:
  - Default to compact when output is redirected or piped.
  - Support `--pretty`, `--indent`, or equivalent for human-readability.
- Formal Schemas:
  - Publish and test against JSON Schema or equivalent.

### Progress and Runtime Status

- Provide a `--progress` or equivalent option that emits:
  - One-line parseable updates (fixed-width or key-value format).
  - In-place or newline-separated progress.
  - Consistent behavior whether or not stdout is a TTY.
- If applicable, emit structured status lines (e.g., JSON objects or tabular fields) at predictable intervals.
- Support signal-triggered progress dumps (e.g., `SIGINFO`, `SIGUSR1`) if appropriate.
- Ensure progress lines can be captured and parsed by external wrappers.

### Formatting and Colors

- Default to 16-color palette; support 256-color and true color if `$TERM` allows.
- Expose `$TOOL_COLORS` for theming.
- Auto-disable color when not on a TTY (`isatty()` or equivalent).
- Support `--color=always|auto|never` to override.

### Pipeline Support

- Prefer NUL-terminated records (`-0`, `-Z`) for file paths to avoid delimiter issues.

### Interactive Behavior

- Emit progress/stats on stable, parseable lines.
- Non-interactive tools should:
  - Exit cleanly on `SIGINT` (Ctrl‑C).
  - Remove temp files, terminate threads, and close child processes.
- REPLs should exit on Ctrl‑D at empty input.
- TUIs should exit on `q`.
- Trap `SIGTERM` to clean up temporary resources.

## Configuration and Environment

### Configuration
- Search precedence (highest to lowest):

  1. `--config` CLI flag
  2. `$<PROG>_CONFIG_PATH` env var
  3. `$XDG_CONFIG_HOME/<prog>/config`
  4. `.<prog>rc` in working tree
  5. `$HOME/.<prog>rc`
- Support environment configuration:
  - `EDITOR`, `VISUAL` – editor selection
  - `PAGER` – pager command
  - `<PROG>_OPTS` – default flags
- Avoid global state. Parse config into a passed-in object.

### Ignore-File Integration

- Honor `.gitignore`, `.dockerignore`, `.ignore` by default.
- Search parent directories for these files unless disabled.
- Provide overrides:
  - `--no-ignore`
  - `--ignore-file=<path>`

## Operational Safety and Error Handling

### Safety and Destructiveness

- Offer `--dry-run` to simulate actions.
- Require opt-in for destructive actions:
  - Use `--interactive`, `--force`, etc.
- Non-interactive defaults:
  - Never prompt unless `--interactive` is set.
  - Use `--force` to override safeguards.
- Fail safely by default. Emit clear, non-interactive error messages.

### Error Output Behavior
- Help and error output should be:
  - Grammatically consistent
  - Line-wrapped to typical terminal widths
  - Free of stack traces unless in debug mode

## Appendix

### Exit Codes

| Name            | Value | Meaning                            |
| --------------- | ----- | ---------------------------------- |
| EX\_OK          | 0     | successful termination             |
| EX\_\_BASE      | 64    | base value for error messages      |
| EX\_USAGE       | 64    | command line usage error           |
| EX\_DATAERR     | 65    | data format error                  |
| EX\_NOINPUT     | 66    | cannot open input                  |
| EX\_NOUSER      | 67    | addressee unknown                  |
| EX\_NOHOST      | 68    | host name unknown                  |
| EX\_UNAVAILABLE | 69    | service unavailable                |
| EX\_SOFTWARE    | 70    | internal software error            |
| EX\_OSERR       | 71    | system error (e.g., can't fork)    |
| EX\_OSFILE      | 72    | critical OS file missing           |
| EX\_CANTCREAT   | 73    | can't create output file           |
| EX\_IOERR       | 74    | input/output error                 |
| EX\_TEMPFAIL    | 75    | temporary failure; retry suggested |
| EX\_PROTOCOL    | 76    | remote protocol error              |
| EX\_NOPERM      | 77    | permission denied                  |
| EX\_CONFIG      | 78    | configuration error                |
| EX\_\_MAX       | 78    | highest defined code               |
