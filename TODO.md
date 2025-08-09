# Token Counting Feature

Add optional token counting to `grobl` using `tiktoken` (or `cntkn` wrapper).

## Core Implementation

- [x] **Add CLI flags**
  - [x] `--tokens` → enable token counting and show in summary.
  - [x] `--tokenizer <name>` → choose tokenizer (default: `cl100k_base`).
  - [x] `--tokens-for printed|all` → choose which files get counted.
  - [x] `--budget <n>` → display prompt budget usage (% of total).
  - [x] Print chosen tokenizer in Project Summary header.

- [x] **Make dependency optional**
  - [x] Add `tiktoken` (or `cntkn`) under an extra in `pyproject.toml` (`tokens` extra).
  - [x] Lazy import in code; fail gracefully if missing.

- [x] **Integrate into pipeline**
  - [x] After `read_text(...)`, compute token count for text files.
  - [x] Skip counting for binary files and excluded-from-print files (configurable).
  - [x] Store tokens in `DirectoryTreeBuilder` along with lines/chars.
  - [x] Track `total_tokens`.

- [x] **Update output**
  - [x] Add Tokens column to `human_summary(...)` table if present.
  - [x] Optionally add `tokens="N"` attribute in `<file:content>` tags.
  - [x] Show total tokens in summary footer.


## Performance & Safety

- [x] **Optimize counting**
  - [x] Cache counts keyed by `(path, size, mtime)`.
  - [x] Warn or skip tokenization for very large files unless `--force-tokens`.
  - [x] Store token counts in `.grobl.tokens.json` cache for faster repeat runs.

- [x] **Error handling**
  - [x] If `--tokens` used but no tokenizer found, print friendly error and exit non-zero.

## Testing
- [x] Unit tests:
  - [x] Mock token counter → assert correct column, per-file counts, and totals.
- [x] CLI tests:
  - [x] Run with `--tokens` and monkeypatched counter; check summary output.
  - [x] Run with `--tokens` without tokenizer installed → expect clear error.
- [x] Performance tests:
  - [x] Ensure large directories don’t become unusably slow with token counting.

# Enhancements
- [ ] allow the definition of "groups" of paths in the config file so that they can be included or excluded as a group
- [ ] add a column header for the "contents included" indicator in the stdout summary output 
- [ ] change the xml tag for directories to "directory", add appropriate attributes like the full path