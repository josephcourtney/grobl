# Reimplement CLI – Task Breakdown
* [x] Replace single parser with subparsers: `scan` (default), `init`, `config`, `models`, `migrate`, `version`.
  * **Done when:** `grobl -h` shows subcommands and `grobl scan` is default when omitted.
* [x] Add global `-h/--help` and `-V/--version` available everywhere.
  * **Done when:** `grobl --version` prints version and exits 0.
* [x] Implement `-v/--verbose` (stackable) and `--log-level` (advanced).
  * **Done when:** `-v` → INFO, `-vv` → DEBUG; `--log-level` overrides.
* [ ] Reimplement CLI with click
* [ ] Implement `--mode [all|tree|summary|files]`.
  * **Done when:** each mode suppresses the others.
* [ ] Implement `--table [full|compact|none]`.
  * **Done when:** summary header/columns reflect choice.
* [ ] Preserve clipboard default; add `--no-clipboard` and `--clipboard-too` (when `--output` is used).
  * **Done when:** combinations behave as specified.
* [ ] Support `--output FILE` and `--output -` (stdout).
  * **Done when:** writing to file/stdout works; errors map to exit codes.
* [ ] Add `--json` (NDJSON stream) and `--output=json` (single JSON document).
  * **Done when:** schema with `schema_version: "1"` is emitted; logs go to stderr.
* [ ] Add `--pretty` and `--indent N` for document JSON.
  * **Done when:** pretty formatting toggles correctly.
* [ ] Write and commit a JSON Schema (`resources/json-schema/grobl.v1.json`).
  * **Done when:** tests validate emitted JSON against schema.
* [ ] Implement `--tokens`, `--tokenizer NAME`, `--model NAME[:TIER]`, `--tokens-for [printed|all]`, `--budget INT`, `--force-tokens`.
  * **Done when:** model implies tokens + budget; printed/all respected.
* [ ] Handle missing `tiktoken` with actionable error.
  * **Done when:** exit with proper code; message suggests `pip install grobl[tokens]`.
* [ ] Large-file guard with override.
  * **Done when:** skip note appears unless `--force-tokens`; totals reflect behavior.
* [ ] Honor `.gitignore`/`.ignore` by default (search parents).
  * **Done when:** files ignored by git are excluded from scan unless overridden.
* [ ] Add `--no-ignore` and `--ignore-file PATH` (repeatable).
  * **Done when:** precedence is CLI > explicit ignore files > project ignores > built-ins.
* [ ] Keep/merge existing `exclude_tree` / `exclude_print` behavior.
  * **Done when:** combined filtering yields expected results (tests).
* [ ] Implement config precedence:
  1. `--config PATH` / `--config none`
  2. `$GROBL_CONFIG_PATH`
  3. `$XDG_CONFIG_HOME/grobl/config.toml` or `~/.config/grobl/config.toml`
  4. `.grobl.config.toml` in CWD or project root
  5. `~/.groblrc` (optional)
  * **Done when:** unit tests cover each layer.
* [ ] Parse `$GROBL_OPTS` before CLI for default flags.
  * **Done when:** env defaults can be overridden by explicit CLI flags.
* [ ] Add `$GROBL_COLORS` and `$NO_COLOR` support.
  * **Done when:** env affects color unless `--color` overrides.
* [ ] Make Rich a core dependency; replace manual ANSI formatting with Rich styles for tables, warnings, errors, and headers.
  * **Done when:** all non-JSON output uses Rich’s `Console`.
* [ ] Auto-disable color when not a TTY; respect `--color=always|auto|never`.
  * **Done when:** piping disables color unless `always`.
* [ ] Implement clean fallback to plain text if Rich console color disabled.
  * **Done when:** no ANSI codes appear in non-TTY plain mode.
* [ ] Implement `--progress` using Rich’s `Progress` for TTY; emit parseable lines in non-TTY or `--json` mode.
  * **Done when:** progress output format is stable.
* [ ] Add `--line-buffered` / `-u` for streaming modes.
  * **Done when:** `sys.stdout.reconfigure(line_buffering=True)` or equivalent is active.
* [ ] Support `-` in positional `PATH` to read newline-delimited paths from stdin.
  * **Done when:** `printf "a\nb" | grobl -` works.
* [ ] Implement `-0/--null` to output NUL-terminated records where applicable (e.g., `--mode files --list` if added).
  * **Done when:** records end with `\0` under flag.
* [ ] Map exit codes to `<sysexits.h>`:
  * usage → 64, noinput → 66, unavailable → 69, ioerr → 74, software → 70, config → 78; success → 0.
  * **Done when:** all error paths return mapped codes.
* [ ] Graceful `SIGINT/SIGTERM`: clean up, exit 130 (SIGINT) / 143 (SIGTERM), no tracebacks unless `--debug`.
  * **Done when:** Ctrl-C yields clean exit.
* [ ] Respect `SIGPIPE`: suppress BrokenPipe tracebacks.
  * **Done when:** `| head -n1` does not print errors.
* [ ] `version`: print version; support `-V/--version`.
  * **Done when:** implemented and tested.
* [ ] `models`: list encodings, models, budgets, aliases.
  * **Done when:** output matches design; tests cover sample resources.
* [ ] `init`: write default config to project root or CWD (no prompts); support `--yes` to overwrite.
  * **Done when:** file written; idempotent behavior tested.
* [ ] `migrate`: convert legacy config files; map exit codes.
  * **Done when:** legacy → TOML and old files handled per flags.
* [ ] `config show|edit|set|validate`.
  * **Done when:** each subcommand works; `edit` respects `$EDITOR`.
* [ ] Make Textual an optional extra: `pip install grobl[pick]`.
  * **Done when:** missing dependency triggers a friendly error and exit 69.
* [ ] Implement `--pick` using Textual:
  * Tree view for directories/files.
  * Toggles for include/exclude tree (`t`) and include/exclude contents (`c`).
  * Space to toggle selection.
  * Status bar with counts and token/size info if available.
  * `s` to save config, `Enter` to run, `q` to quit, `?` for help.
  * **Done when:** full interaction matches design.
* [ ] Integrate `--pick` with config saving (`--config` path if given).
  * **Done when:** saved config validates with `config validate`.
* [ ] Maintain default copy to clipboard + human summary to stdout.
  * **Done when:** both happen on TTY; suppressed by `--no-clipboard`.
* [ ] On pyperclip failure, fallback to stdout and emit one-line stderr note (respect `--quiet`).
  * **Done when:** simulated failure covered by tests.
* [ ] Use Rich `Table` for the summary, aligning header `lines chars [tokens] included`.
  * **Done when:** table formatting is deterministic and tested.
* [ ] Append footer when any files skipped: `Note: N files skipped (reason).`
  * **Done when:** shown conditionally.
* [ ] Update `--help` for root & each subcommand with concise examples.
  * **Done when:** `grobl scan -h` shows examples.
* [ ] Add man pages: `grobl(1)` and `grobl-config(1)` (SYNOPSIS/OPTIONS/EXAMPLES).
  * **Done when:** installed via package; `man grobl` works in dev env.
* [ ] Document JSON Schema and stability policy.
  * **Done when:** `README` section links to schema file and shows sample JSON.

## Tests
* [ ] Parser & help snapshots per subcommand.
* [ ] Exit code mapping tests for each failure path.
* [ ] Tokenization paths (present/missing tiktoken, large files, model inference).
* [ ] Ignore precedence tests (gitignore, explicit ignore file, built-ins).
* [ ] Config precedence & env (`$GROBL_CONFIG_PATH`, `$GROBL_OPTS`, XDG).
* [ ] Progress/line-buffering behavior (smoke).
* [ ] Signals (simulate SIGINT/SIGPIPE).
* [ ] TUI smoke tests with Textual behind a flag (skip on CI without TTY).
  * **Done when:** all tests pass locally and in CI.

