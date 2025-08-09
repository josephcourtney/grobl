# Token Counting Feature

Add optional token counting to `grobl` using `tiktoken` (or `cntkn` wrapper).

## Core Implementation

- [ ] **Add CLI flags**
  - `--tokens` → enable token counting and show in summary.
  - `--tokenizer <name>` → choose tokenizer (default: `cl100k_base`).
  - Print chosen tokenizer in Project Summary header.

- [ ] **Make dependency optional**
  - Add `tiktoken` (or `cntkn`) under an extra in `pyproject.toml` (`tokens` extra).
  - Lazy import in code; fail gracefully if missing.

- [ ] **Integrate into pipeline**
  - After `read_text(...)`, compute token count for text files.
  - Skip counting for binary files and excluded-from-print files (configurable).
  - Store tokens in `DirectoryTreeBuilder` along with lines/chars.
  - Track `total_tokens`.

- [ ] **Update output**
  - Add Tokens column to `human_summary(...)` table if present.
  - Optionally add `tokens="N"` attribute in `<file:content>` tags.
  - Show total tokens in summary footer.

## Performance & Safety

- [ ] **Optimize counting**
  - Cache counts keyed by `(path, size, mtime)`.
  - Warn or skip tokenization for very large files unless `--force-tokens`.

- [ ] **Error handling**
  - If `--tokens` used but no tokenizer found, print friendly error and exit non-zero.

## Testing

- [ ] Unit tests:
  - Mock token counter → assert correct column, per-file counts, and totals.
- [ ] CLI tests:
  - Run with `--tokens` and monkeypatched counter; check summary output.
  - Run with `--tokens` without tokenizer installed → expect clear error.
- [ ] Performance tests:
  - Ensure large directories don’t become unusably slow with token counting.

## Optional Enhancements

- [ ] `--tokens-for printed|all` → choose which files get counted.
- [ ] `--budget <n>` → display prompt budget usage (% of total).
- [ ] Store token counts in `.grobl.tokens.json` cache for faster repeat runs.
