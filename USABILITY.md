# grobl Usability Review

## Environment and Scope
- grobl version 0.7.4 was exercised from a source checkout using `uv run` to drive the `grobl` entrypoint.
- Help text and option discovery were based on the top-level CLI and the `scan` subcommand.
- Tests focused on scanning temporary sample projects and the repository itself to explore defaults, configuration, JSON output, clipboard behavior, and initialization flows.

## What Works Well
- **Complete payload generation** – Running `grobl scan` against a directory produces both the XML-like payload and a human summary, confirming the core scenario works.
- **JSON summaries and payloads** – `--format json` yields deterministic machine-readable structures for summary mode, and `--mode files --format json` embeds both file contents and the summary metadata.
- **Ignore controls** – Runtime switches like `--ignore-defaults`, `--add-ignore`, `--remove-ignore`, `--ignore-file`, and `--no-ignore` each adjust coverage as advertised.
- **Safety prompts for heavy directories** – Disabling default ignores prompts for confirmation and honors both aborting and `--yes`.
- **Output redirection** – Supplying `--output` writes the full payload to disk while still presenting the human summary to stdout, which is helpful when capturing context for later use.
- **Configuration features** – `grobl init` generates a comprehensive `.grobl.toml`, and custom tags from config are reflected in emitted payloads.
- **Shell integration** – Completion scripts are available for bash (and other shells via help text).
- **Multi-path scans** – Supplying multiple roots produces a merged summary rooted at the common ancestor, making cross-directory scans straightforward.

## Pain Points and Recommendations

| Severity | Issue | Evidence | Recommendation |
| --- | --- | --- | --- |
| High | **Clipboard failures dominate default UX.** | On non-GUI hosts the default run tries to copy to the clipboard, logs warnings/errors, and only then prints payload + summary.  | Detect `pyperclip` backend availability and auto-disable clipboard when unsupported (equivalent to `--no-clipboard`), or downgrade messages to a single concise notice. |
| High | **Invalid option values explode with a full traceback.** | Because the CLI disables Click's standalone mode, typos like `--mode nope` or `--table wide` produce stack traces instead of friendly messages.  | Re-enable Click's default exception handling (leave `standalone_mode=True`) or catch `click.BadParameter` explicitly and re-raise as `SystemExit` with the short error. |
| High | **Summary mode cannot emit files even when `--output` is supplied.** | The command succeeds but the target file never appears, leaving users without a saved payload.  | Emit the summary table (or at least the JSON summary) to the file sink when `--mode summary` is active, or reject the option combination early with a clear error. |
| Medium | **`--quiet` hides machine-readable summaries.** | Using `--quiet` with `--mode summary --format json` yields no output at all despite a zero exit status.  | Allow JSON summaries to print regardless of `--quiet` (only suppress the human table), or document the interaction explicitly. |
| Medium | **`--mode summary --table none` knowingly produces no output.** | The CLI prints a warning but still exits successfully, which is easy to miss in scripts.  | Treat this combination as an error or override `--table` to `compact` when the mode is `summary`. |
| Medium | **`grobl init --path` refuses to create the target directory.** | Pointing at a non-existent folder fails with an OS error rather than helping the user bootstrap a new project.  | Create the directory automatically (like `mkdir -p`) or add a flag/clear documentation that the directory must pre-exist. |
| Medium | **`grobl init` requires manual reruns to overwrite.** | Subsequent invocations only emit a message advising `--force`, forcing users to rerun the command after reading the prompt.  | Prompt interactively to confirm overwrite (respecting `--yes`) rather than forcing another command. |
| Medium | **`--quiet` suppresses all summary output (even success confirmation).** | Invoking summary mode with `--quiet` returns immediately with no indication of success.  | Print a concise confirmation or write the summary to the requested sink even when `--quiet` is set. |
| Low | **`uv run grobl` floods terminals on sizeable projects.** | Scanning this repo prints thousands of lines by default, which is overwhelming without an obvious quick-start to limit output.  | Default to `--mode summary` when stdout is a TTY, or prompt users to try `--mode summary` after large outputs. |
| Low | **`--ignore-defaults` prompt lacks context about bypassing.** | Abort confirmation warns but does not mention `--yes` or `--no-ignore`, leaving new users guessing.  | Extend the prompt text to mention the `--yes` escape hatch and how to restore ignores. |
| Low | **Summary format option applies only to `--mode summary`.** | Other modes ignore `--format json`, which is surprising given the flag description.  | Clarify the help text (e.g., “Only affects `--mode summary` output to stdout”) or support JSON tables in other modes. |
| Low | **`--output` always echoes the human summary.** | Even when writing payloads to disk, the table still prints to stdout, which complicates scripting.  | Add a flag such as `--no-summary` or reuse `--quiet` semantics when `--output` is present. |


## Missing Capabilities Experienced Developers Might Expect
- **Payload size controls** – There is no option to cap file sizes, limit total bytes, or trim long files before dumping, which many similar tools provide. The CLI options list shows no such switches.
- **Filtering by glob or language** – Beyond ignore patterns, there is no positive include filter (`--only *.py`, `--max-depth`, etc.), making targeted captures cumbersome.
- **Progress feedback for large scans** – Scanning large directories provides no progress indicators or ETA, which could be problematic during multi-minute runs.
- **Config validation** – Configuration accepts values like lists for `include_file_tags` without warning, which can lead to odd XML tag names.

## Option Naming and Organization
- Primary switches (`--mode`, `--table`, `--format`, `--output`) are clear and grouped logically in `--help`.
- Some behaviors (clipboard precedence, JSON availability only for summary mode, quiet suppressing JSON) are implicit rather than encoded in option names. Documenting these relationships in help text or README would reduce surprises.

## Additional Observations
- The tool reports nonexistent paths succinctly (`scan paths do not exist: ...`).
- Multiple paths yield a merged summary rooted at the common ancestor, which is particularly useful for monorepos.
- JSON output for non-summary modes includes both payload and summary metadata, which provides a strong foundation for automation workflows.

