# Grobl Usability Review

This document summarizes hands-on testing of the `grobl` CLI utility. It captures successful
workflows, rough edges, and missing capabilities along with suggestions for improvement.

## Installation

- Installing with `pip install -e .` placed the `grobl` entrypoint outside of `$PATH`, producing
  `command not found` until `pyenv rehash` was run.
  - **Suggestion:** Document the need to `pyenv rehash` when using pyenv, or prefer `pipx install grobl`
    in development docs to guarantee an executable on the PATH.

## Basic Execution

- Running `grobl` in a headless environment fails because `pyperclip` cannot access a clipboard
  implementation, aborting the program before any output is produced.
  ```bash
  $ grobl
  PyperclipException: Pyperclip could not find a copy/paste mechanism...
  ```
  - **Suggestion:** Provide a `--no-clipboard` option that prints to stdout or writes to a file when no
    clipboard is available.
- Using the library API with a dummy clipboard shows the tool can generate a directory summary:
  ```python
  from pathlib import Path
  from grobl.main import process_paths
  from grobl.config import read_config
  from grobl.directory import DirectoryTreeBuilder

  class DummyClipboard:
      def copy(self, content):
          print("Copy length", len(content))

  cfg = read_config(Path())
  builder = DirectoryTreeBuilder(base_path=Path(), exclude_patterns=cfg.get("exclude_tree", []))
  process_paths([Path()], cfg, DummyClipboard(), builder)
  ```

## Configuration and Options

- The help output advertises `--no-gitignore`, yet the ignore file is actually named
  `.groblignore`.
  - **Suggestion:** Rename the flag (e.g. `--no-groblignore`) and the internal function
    `merge_gitignore` to avoid confusion.
- Supplying a `.groblignore` file works, but only if `--no-gitignore` is *not* provided. When the
  flag is used, patterns from `.groblignore` are ignored as expected.
- `grobl migrate-config` successfully converts legacy `.grobl.config.json`/`.groblignore` files into a
  new `.grobl.config.toml`, but the command is interactive and cannot run unattended.
  - **Suggestion:** Support a `--yes` flag to auto-accept deletions or write the TOML to stdout for
    scripting.
- Running with `--ignore-defaults` removes the extensive built-in ignore list and causes `grobl` to
  traverse the entire virtual environment, producing multi-million‑line output.
  - **Suggestion:** Warn users before scanning directories that match common virtual environment names
    when defaults are disabled.

## File Handling

- Non-text files are reported with `0` lines and characters, e.g., a three-byte `test.bin` shows
  `0 0`. This can be confusing.
  - **Suggestion:** show byte counts for binary files or explicitly label them as binary.

## Missing or Expected Features

Experienced developers may expect:

- Ability to specify target directories on the command line instead of always using the current
  working directory.
- An option to write the markdown output to a file rather than only the clipboard.
- CLI switches to add or remove ignore patterns without editing config files.
- Progress indicators or logging when large directories are processed.
- A non-interactive mode for `migrate-config`.

## Summary

`grobl` reliably summarizes directories when run with a functional clipboard and sensible
configuration. Enhancements around clipboard handling, naming consistency, non-interactive
operations, and safer defaults would make the tool more approachable for both new and experienced
users.
