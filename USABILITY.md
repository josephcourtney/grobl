# Grobl Usability Review

This document summarizes hands-on testing of the `grobl` CLI utility. It captures successful
workflows, rough edges, and missing capabilities along with suggestions for improvement.

## Basic Execution

- Running `grobl` in a headless environment previously failed because `pyperclip` could not access a
  clipboard implementation. The tool now supports `--no-clipboard` and `--output <file>` flags, and
  automatically falls back to stdout when the clipboard is unavailable.
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

- The CLI now includes a `--no-groblignore` flag to skip loading patterns from `.groblignore`.
  Previously, the help output referenced `--no-gitignore`, which was misleading given the file
  name.
- Supplying a `.groblignore` file works, and patterns are merged unless `--no-groblignore` is used.
  - `grobl migrate-config` now supports `--yes` and `--stdout` flags for non-interactive migrations.
  - When running with `--ignore-defaults`, the tool warns before traversing common virtual environment
    directories.

## File Handling

  - Non-text files are reported with their byte counts rather than `0 0`, clarifying binary sizes.

## Missing or Expected Features

Experienced developers may expect:

  - Ability to specify target directories on the command line instead of always using the current
    working directory.
  - Options to write the markdown output to a file or print to stdout.
  - CLI switches to add or remove ignore patterns without editing config files.
  - Progress logs when large directories are processed.
  - A non-interactive mode for `migrate-config`.

## Summary

`grobl` reliably summarizes directories when run with a functional clipboard and sensible
configuration. Enhancements around clipboard handling, naming consistency, non-interactive
operations, and safer defaults would make the tool more approachable for both new and experienced
users.
