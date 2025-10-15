# grobl Usability Review

## Environment and Scope
- Tests were executed from the source checkout using the bundled virtual environment (`.venv/bin/grobl`).
- `pyproject.toml` reports grobl version 0.7.4, but the `grobl version` command in this build advertises 0.7.1, so findings call out both the declared and reported versions when relevant.
- Scenarios covered: full repository scans, targeted temporary project scans, and human output modes, clipboard fallbacks, ignore toggles, configuration initialization, heavy-directory warnings, completions, and multi-root scans.

## Successful Workflows
- **Default scan captures tree and payload** – Running `grobl scan --no-clipboard` against the repository produced the expected directory tree followed by file payload blocks, demonstrating that the end-to-end collection path works.
- **Summary tables are informative** – The full summary enumerates every included path with totals, which makes it easy to gauge repository size at a glance.
- **Ignore controls behave predictably** – Flags such as `--ignore-defaults`, `--add-ignore`, `--remove-ignore`, `--ignore-file`, and `--no-ignore` all adjusted coverage as expected, and heavy-directory confirmation respected both aborts and the `--yes` override.
- **Configuration bootstrap** – `grobl init --path <dir>` generates a comprehensive `.grobl.toml` template ready for editing.
- **Shell integration and multi-root support** – Completion scripts generate successfully, and scanning two disjoint directories merged them under the correct `/tmp` common ancestor.

## Usability Friction and Recommendations
| Severity | Issue | Evidence | Recommendation |
| --- | --- | --- | --- |
| High | Clipboard failures dominate the default UX on headless systems. | The first scan attempt logs repeated clipboard failures before emitting output. | Auto-detect missing clipboard backends and silently fall back to stdout (or issue a single concise notice) when `pyperclip` is unavailable. |
| High | `--mode summary --output <file>` silently produces an empty file while still flooding stdout. | The written file remained zero bytes even though the human summary printed, leaving the caller without a saved summary. | Either emit the summary payload to the file sink for summary mode or reject the combination with a clear error. |
| High | Invalid option values surface full Python tracebacks. | Passing `--mode nope` triggers a long Click traceback rather than a short validation message. | Restore Click’s default error handling (`standalone_mode=True`) or wrap `BadParameter` exceptions to exit cleanly with friendly text. |
| High | Reported version disagrees with declared project version. | `pyproject.toml` lists 0.7.4, but `grobl version` prints 0.7.1. | Align the runtime version constant with the package metadata so diagnostics and bug reports reference the same version number. |
| Medium | `--mode summary --table none` warns yet exits successfully, leaving scripts with no payload. | The CLI prints “produces no output” and exits 0. | Treat this combination as an error or automatically choose a minimal table style. |
| Medium | `grobl init --path <missing-dir>` fails instead of helping the user create the directory. | Attempting to initialize a non-existent folder raises `No such file or directory`. | Either create the directory (akin to `mkdir -p`) or provide an explicit flag/error message that explains the prerequisite. |
| Medium | Re-running `grobl init` requires a second invocation with `--force`. | The command merely prints “Use --force to overwrite.” without offering an inline confirmation, and the message points at the wrong path in this build. | Prompt for overwrite confirmation (respecting `--yes`) instead of forcing the operator to retype the command. |
| Low | Heavy-directory warning doesn’t hint at bypass options. | The prompt only says “Continue? (y/N)” with no mention of `--yes` or `--no-ignore`. | Extend the prompt text to highlight the available escape hatches so users learn the flags in-context. |
| Low | Default scans emit thousands of lines of payload, overwhelming terminals. | The summary alone reports 4,582 lines / 155k characters for this repo, indicating a very large default payload. | Consider defaulting to `--mode summary` on TTYs or printing guidance for first-time users about the quieter modes. |
| Low | Writing payloads with `--output` still echoes the human summary to stdout. | `--mode files --output <file>` writes the XML payload but continues to print the summary table, complicating scripting. | Add a `--no-summary` flag or reuse `--quiet` semantics automatically when an output file is provided. |

## Missing Capabilities Seasoned Developers Might Expect
- **Positive include filters or depth limits** – Help text lists ignore-focused switches but lacks a way to include only certain glob patterns or cap traversal depth. This makes targeted captures cumbersome on large trees.
- **Payload size controls** – There is no CLI option to trim long files or cap total payload bytes, so runaway outputs cannot be contained without editing ignore lists.
- **Progress feedback for long scans** – Large directories show no progress bar or ETA, leaving users guessing during multi-minute runs.

## Option Naming and Organization
- Primary toggles (`--mode`, `--table`, `--format`, `--output`) are grouped cleanly in `scan --help`, aiding discovery.
- Several side effects (clipboard precedence) are implicit rather than spelled out, so help text could better spell out these interactions for new users.

## Additional Observations
- `--remove-ignore` immediately resurrects default-excluded entries such as `.venv`, making it straightforward to override bundled rules.
- Heavy-directory prompts respect `--yes` and `--add-ignore`, so experienced users can automate potentially expensive scans once they understand the flags.
- Generating Bash completions works out of the box, and multi-root output cleanly merges disjoint directories under their shared ancestor.

