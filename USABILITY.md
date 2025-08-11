# Usability Review of `grobl`

## Successful Behaviors

- **Basic directory scan** – Running `grobl` on a small project correctly emits
  the tree, file contents, and a summary table
- **Temporary ignore patterns** – `--add-ignore` excludes files for the current
  run without needing a config file
- **File output** – `--output` writes the LLM-ready content to a file while the
  summary remains on stdout
- **Model listing** – `--list-token-models` shows available tokenizers and
  associated models

## Issues and Sharp Corners

- **No `--version` flag** – Requesting the version via `--version` results in an
  “unrecognized arguments” error
- **Token counting is hard to use** – Without `tiktoken` installed, `grobl`
  fails with a message referencing `pip install grobl[tokens]`
  Even after installing `tiktoken`, the default tokenizer fails to load because
  it attempts to download data from the network and reports an incorrect
  “Unknown tokenizer” error
- **`init-config` ignores negative response** – Invoking `init-config` and
  pressing Enter (default “N”) still writes `.grobl.config.toml`
- **Interactive File Selection is Confusing** – The `--interactive` mode should have an interface similar to a check list file tree, like dropbox uses for selective sync.
  - normal arrow (or hjkl) movement should manipulate file tree
  - space should toggle item selection
  - toggling a directory should mark all its contents to match the directory
- **Edit config should be merged with Interactive File Selection**
  - it should just allow the new config to be written without invoking the main grobl command
- **Nonexistent paths crash** – Supplying a missing directory raises an
  unhandled `FileNotFoundError` stack trace
- **Invalid output target** – Providing a directory to `--output` causes an
  unhandled `IsADirectoryError`
- **Totals omit binary files** – When only a binary file is present, the summary
  reports zero total characters even though the file size is nonzero
- **`--ignore-defaults` prompt cannot be bypassed** – Scans that may traverse
  large directories prompt the user, which makes automation difficult
- A `--version` option is expected but absent.
- There is no way to choose a configuration file path or to include/exclude
  patterns for file *contents* from the CLI.
- Option names such as `--tokens-for` and `--force-tokens` are uncommon and may
  confuse new users.
- The tool always outputs full file contents; a mode to show only the summary or
  only the tree would aid quick inspections.

## Recommendations

1. Provide explicit numbering in interactive mode and respect default responses
   before writing configuration files.
2. Improve error handling for missing paths, invalid `--output` targets, and
   failed tokenization (e.g., distinguish network failures from unknown
   tokenizer names).
3. Add a `--version` flag and an option to suppress confirmation prompts.
4. Include CLI options for managing `exclude_print` patterns and for showing
   only summaries or only trees.
5. Consider counting bytes from binary files in the overall totals or clarifying
   that they are omitted.

