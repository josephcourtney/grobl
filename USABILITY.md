# Usability Review for grobl

This report summarizes hands-on testing of grobl's command-line interface. All observations were made in a clean environment using the project's default configuration unless otherwise noted.

## Successful behaviours

- **Generating summaries and writing to a file** – `grobl --output path` scanned the repository, produced a concise summary, and wrote the full tree and file contents to the specified file without flooding the terminal【8a796b†L1-L29】.
- **Respecting `.groblignore` patterns** – adding a `.groblignore` with `README.md` removed that file from the summary, while `--no-groblignore` restored it【591b40†L1-L28】【7bd02a†L1-L28】.
- **Temporarily adjusting ignore rules** – `--add-ignore tests/test_cli.py` excluded the test module, and `--remove-ignore AGENTS.md` brought a previously ignored file back into the summary【8504e7†L1-L30】【7b69f3†L1-L30】.
- **Handling binary files** – non‑text files are listed with a character count and a `*` marker showing they were skipped in the copied output【613c14†L1-L29】.

## Pain points and issues

- **Default clipboard behaviour is noisy** – when no system clipboard is available the entire output is printed to the terminal, even without `--no-clipboard`, producing thousands of lines of content【f48008†L1-L95】.
- **`--no-clipboard` still emits massive output** – without `--output` the command dumps the entire tree and file bodies to stdout, which can overwhelm terminals【a2c4d6†L1-L58】.
- **Interactive editor lacks numbering and filtering** – `grobl edit-config` prints every file including `.venv` and shows no indices, making it impossible to know which number corresponds to a file and leading to excessive, slow output【18923a†L1-L140】.
- **`migrate-config --stdout` prompts for deletion** – the supposed preview mode still asks whether to delete the old JSON file, interrupting non-interactive use【054415†L1-L8】【231346†L1-L3】.
- **`--output` to a missing directory raises a stack trace** – pointing `--output` at a non-existent path crashes with a Python traceback instead of a helpful message【0a7072†L1-L17】.

## Suggestions

- Fix argument parsing so positional paths are accepted alongside subcommands.
- Detect clipboard failures early and warn rather than dumping full output to stdout; consider a `--summary-only` option.
- When `--no-clipboard` is used, default to writing to a temporary file or require `--output` to avoid terminal spam.
- In interactive modes, respect existing ignore patterns, show numbered entries, and confirm before writing new config files.
- Allow `migrate-config --stdout` to run without deletion prompts and clearly separate preview vs. migration modes.
- Validate `--output` paths and surface friendly errors; optionally create missing directories.
- Improve error messages for invalid config files to point to the offending file and line.

