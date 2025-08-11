# Usability Review of `grobl`

Date: 2025-08-10

This document records a hands-on usability review of the `grobl` command line
tool. All examples were executed in a Linux shell using `uv run grobl`.

---

## Successful Behaviors

- **Basic directory scan** – Running `grobl` on a small project correctly emits
  the tree, file contents, and a summary table【b09272†L1-L19】.
- **Temporary ignore patterns** – `--add-ignore` excludes files for the current
  run without needing a config file【6d8f72†L1-L19】.
- **File output** – `--output` writes the LLM-ready content to a file while the
  summary remains on stdout【5838e9†L1-L10】.
- **Model listing** – `--list-token-models` shows available tokenizers and
  associated models【778620†L1-L10】.

## Issues and Sharp Corners

- **Token counting is hard to use** – Without `tiktoken` installed, `grobl`
  fails with a message referencing `pip install grobl[tokens]`【a69cd3†L1-L3】.
  Even after installing `tiktoken`, the default tokenizer fails to load because
  it attempts to download data from the network and reports an incorrect
  “Unknown tokenizer” error【7f894a†L1-L3】.
- **Interactive editing lacks context** – The `--interactive` mode prompts the
  user to “enter numbers” but the tree view contains no numbers, leaving the
  user guessing which index corresponds to which file【55d6f4†L1-L23】.
- **`init-config` ignores negative response** – Invoking `init-config` and
  pressing Enter (default “N”) still writes `.grobl.config.toml`【d266ef†L1-L2】【24f93c†L1-L3】.
- **`edit-config` is overwhelming** – Running `edit-config` with no existing
  configuration dumps the entire project (including the virtual environment) and
  saves a config file without explicit confirmation【783a54†L1-L20】【b0bbae†L1-L3】.
- **No `--version` flag** – Requesting the version via `--version` results in an
  “unrecognized arguments” error【facc1c†L1-L6】.
- **Nonexistent paths crash** – Supplying a missing directory raises an
  unhandled `FileNotFoundError` stack trace【86e3c3†L1-L16】.
- **Invalid output target** – Providing a directory to `--output` causes an
  unhandled `IsADirectoryError`【7a9245†L1-L16】.
- **Totals omit binary files** – When only a binary file is present, the summary
  reports zero total characters even though the file size is nonzero【5758b0†L1-L16】.
- **`--ignore-defaults` prompt cannot be bypassed** – Scans that may traverse
  large directories prompt the user, which makes automation difficult【4fe3f0†L1-L2】.

## Missing Features and Confusing Options

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

