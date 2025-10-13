# grobl Usability Review

## Environment and Scope
- grobl version 0.7.4 was exercised from a source checkout using `uv run` to drive the `grobl` entrypoint. 【14f4df†L1-L2】
- Help text and option discovery were based on the top-level CLI and the `scan` subcommand. 【eb9486†L5-L18】【9b2aa3†L1-L24】
- Tests focused on scanning temporary sample projects and the repository itself to explore defaults, configuration, JSON output, clipboard behavior, and initialization flows.

## What Works Well
- **Complete payload generation** – Running `grobl scan` against a directory produces both the XML-like payload and a human summary, confirming the core scenario works. 【e1c9e5†L1-L19】
- **JSON summaries and payloads** – `--format json` yields deterministic machine-readable structures for summary mode, and `--mode files --format json` embeds both file contents and the summary metadata. 【6004ca†L1-L23】【2760b1†L1-L43】
- **Ignore controls** – Runtime switches like `--ignore-defaults`, `--add-ignore`, `--remove-ignore`, `--ignore-file`, and `--no-ignore` each adjust coverage as advertised. 【55f116†L1-L3】【eae247†L1-L17】【10221b†L1-L24】【65a188†L1-L19】【46e3ad†L1-L33】
- **Safety prompts for heavy directories** – Disabling default ignores prompts for confirmation and honors both aborting and `--yes`. 【55f116†L1-L3】【d13e83†L1-L2】【119abd†L1-L33】
- **Output redirection** – Supplying `--output` writes the full payload to disk while still presenting the human summary to stdout, which is helpful when capturing context for later use. 【ada57a†L1-L11】【c77a89†L1-L10】
- **Configuration features** – `grobl init` generates a comprehensive `.grobl.toml`, and custom tags from config are reflected in emitted payloads. 【5c7876†L1-L2】【5f58d1†L1-L10】
- **Shell integration** – Completion scripts are available for bash (and other shells via help text). 【e18e4a†L1-L3】
- **Multi-path scans** – Supplying multiple roots produces a merged summary rooted at the common ancestor, making cross-directory scans straightforward. 【abf28c†L1-L17】

## Pain Points and Recommendations

| Severity | Issue | Evidence | Recommendation |
| --- | --- | --- | --- |
| High | **Clipboard failures dominate default UX.** On non-GUI hosts the default run tries to copy to the clipboard, logs warnings/errors, and only then prints payload + summary. 【15b892†L1-L25】 | Detect `pyperclip` backend availability and auto-disable clipboard when unsupported (equivalent to `--no-clipboard`), or downgrade messages to a single concise notice.
| High | **Invalid option values explode with a full traceback.** Because the CLI disables Click's standalone mode, typos like `--mode nope` or `--table wide` produce stack traces instead of friendly messages. 【f503d4†L1-L43】【5370da†L1-L43】【F:src/grobl/cli/root.py†L71-L74】 | Re-enable Click's default exception handling (leave `standalone_mode=True`) or catch `click.BadParameter` explicitly and re-raise as `SystemExit` with the short error.
| High | **Summary mode cannot emit files even when `--output` is supplied.** The command succeeds but the target file never appears, leaving users without a saved payload. 【c44a08†L1-L14】 | Emit the summary table (or at least the JSON summary) to the file sink when `--mode summary` is active, or reject the option combination early with a clear error.
| Medium | **`--quiet` hides machine-readable summaries.** Using `--quiet` with `--mode summary --format json` yields no output at all despite a zero exit status. 【b41362†L1-L3】 | Allow JSON summaries to print regardless of `--quiet` (only suppress the human table), or document the interaction explicitly.
| Medium | **`--mode summary --table none` knowingly produces no output.** The CLI prints a warning but still exits successfully, which is easy to miss in scripts. 【a23e08†L1-L2】【F:src/grobl/cli/scan.py†L136-L153】 | Treat this combination as an error or override `--table` to `compact` when the mode is `summary`.
| Medium | **`grobl init --path` refuses to create the target directory.** Pointing at a non-existent folder fails with an OS error rather than helping the user bootstrap a new project. 【aea66d†L1-L2】 | Create the directory automatically (like `mkdir -p`) or add a flag/clear documentation that the directory must pre-exist.
| Medium | **`grobl init` requires manual reruns to overwrite.** Subsequent invocations only emit a message advising `--force`, forcing users to rerun the command after reading the prompt. 【49d020†L1-L1】 | Prompt interactively to confirm overwrite (respecting `--yes`) rather than forcing another command.
| Medium | **`--quiet` suppresses all summary output (even success confirmation).** Invoking summary mode with `--quiet` returns immediately with no indication of success. 【66555a†L1-L2】 | Print a concise confirmation or write the summary to the requested sink even when `--quiet` is set.
| Low | **`uv run grobl` floods terminals on sizeable projects.** Scanning this repo prints thousands of lines by default, which is overwhelming without an obvious quick-start to limit output. 【e3fa05†L1-L120】 | Default to `--mode summary` when stdout is a TTY, or prompt users to try `--mode summary` after large outputs.
| Low | **`--ignore-defaults` prompt lacks context about bypassing.** Abort confirmation warns but does not mention `--yes` or `--no-ignore`, leaving new users guessing. 【55f116†L1-L3】 | Extend the prompt text to mention the `--yes` escape hatch and how to restore ignores.
| Low | **Summary format option applies only to `--mode summary`.** Other modes ignore `--format json`, which is surprising given the flag description. 【6004ca†L1-L23】【3261e2†L150-L153】 | Clarify the help text (e.g., “Only affects `--mode summary` output to stdout”) or support JSON tables in other modes.
| Low | **`--output` always echoes the human summary.** Even when writing payloads to disk, the table still prints to stdout, which complicates scripting. 【ada57a†L1-L11】 | Add a flag such as `--no-summary` or reuse `--quiet` semantics when `--output` is present.

## Missing Capabilities Experienced Developers Might Expect
- **Payload size controls** – There is no option to cap file sizes, limit total bytes, or trim long files before dumping, which many similar tools provide. The CLI options list shows no such switches. 【9b2aa3†L1-L24】
- **Filtering by glob or language** – Beyond ignore patterns, there is no positive include filter (`--only *.py`, `--max-depth`, etc.), making targeted captures cumbersome. 【9b2aa3†L1-L24】
- **Progress feedback for large scans** – Scanning large directories provides no progress indicators or ETA, which could be problematic during multi-minute runs. 【e3fa05†L1-L120】
- **Config validation** – Configuration accepts values like lists for `include_file_tags` without warning, which can lead to odd XML tag names. 【40628c†L1-L23】

## Option Naming and Organization
- Primary switches (`--mode`, `--table`, `--format`, `--output`) are clear and grouped logically in `--help`. 【9b2aa3†L1-L24】
- Some behaviors (clipboard precedence, JSON availability only for summary mode, quiet suppressing JSON) are implicit rather than encoded in option names. Documenting these relationships in help text or README would reduce surprises.

## Additional Observations
- The tool reports nonexistent paths succinctly (`scan paths do not exist: ...`). 【418a2b†L1-L2】
- Multiple paths yield a merged summary rooted at the common ancestor, which is particularly useful for monorepos. 【abf28c†L1-L17】
- JSON output for non-summary modes includes both payload and summary metadata, which provides a strong foundation for automation workflows. 【1736f3†L1-L47】

