## Correctness / Bugs

* [ ] Version source labeling: in `src/grobl/__init__.py`, if `importlib.metadata` lookup fails, parse `[project].version` from `pyproject.toml`; expose `__version_source__ = "distribution"|"pyproject"|"fallback"`.
* [ ] `version` subcommand: print version with source annotation (e.g., `0.7.4 (pyproject)`).
* [ ] Route *all* output through the sink: in `cli/scan.py`, send human/JSON summaries via `write_fn(...)` instead of `print(...)` so `--mode summary --output <file>` writes to the file.
* [ ] `--quiet` must not suppress machine output: allow JSON summaries to print even with `--quiet`.
* [ ] Click errors without tracebacks: wrap `cli.main(...)` with `try/except` for `click.UsageError`/`ClickException`, call `.show()` and exit with `EXIT_USAGE`.
* [ ] Config precedence with legacy: if both `.grobl.config.toml` and `.grobl.toml` exist, load legacy first, modern second; warn once that legacy is present.
* [ ] Improve “No common ancestor” message when only filesystem root is shared.

## UX simplifications

* [ ] Unify routing model: one writer for payload + summaries (done above); remove direct `print` paths.
* [ ] Add `--emit {human,json,none}` (default: `human` on TTY; `json` if `--format json` or non-TTY). Wire to summary emission only.
* [ ] Add `--payload {all,tree,files,none}` (alias of current `--mode`; keep old names as hidden aliases). Use `--payload` to select LLM/JSON sink content.
* [ ] Validate no-output combos: treat `--payload none --emit none` and legacy `--mode summary --table none` as usage errors with actionable hint.
* [ ] Safer defaults: on TTY with no flags, default to summary-only (`--payload none`, `--emit human`).
* [ ] Heavy-dir prompt text: include tip about `--yes` and keeping default ignores; support `GROBL_ASSUME_YES=1`.

## Discovery / Performance controls

* [ ] Add positive filters: `--include <glob>` (repeatable, gitwildmatch). Intersect in `filter_items()`; thread through CLI→core.
* [ ] Add depth limit: `--max-depth N`; stop recursion when depth > N in `traverse_dir`.
* [ ] Add payload governors in `TextFileHandler`: `--max-file-lines`, `--max-file-bytes`, `--max-total-bytes`; annotate truncated entries in JSON (`"truncated": {...}`) and mark in human output.

## Optional emit formats

* [ ] ND-JSON stream mode: `--emit ndjson` to write tree entries, files, and final summary as separate records to stdout/sink.

## Architecture / internal polish

* [ ] Require precompiled `PathSpec` in `filter_items()` to eliminate optional recompute path; update call sites accordingly.
* [ ] Authoritative binary flag: set `binary=True` when `BinaryFileHandler` handles a path; drop heuristic in `summary._file_entries()` and use the recorded flag.
* [ ] Structured logging correlation: add `scan_id` (uuid4) and `root` to all `StructuredLogEvent.context`; pass consistently across services.

## Help / CLI organization

* [ ] Reorder options: group Output (`--payload`, `--emit`, `--format`, `--output`, `--quiet`) before Discovery/Filters (`--include`, `--max-depth`, `--add/remove-ignore`, etc.). Update help text accordingly.

## Tests (new/updated)

* [ ] Summary-to-file regression: `scan --mode summary --output out.txt` writes non-empty file; nothing echoed unless stdout chosen.
* [ ] `--quiet` + JSON: `scan --mode summary --format json --quiet` still prints JSON.
* [ ] No-output combos: assert `EXIT_USAGE` and helpful message.
* [ ] Version fallback: test `grobl version` prints with `(pyproject|distribution)` under source checkout vs installed wheel.
* [ ] Include/depth: tests for `--include` narrowing and `--max-depth` limiting recursion.
* [ ] Truncation flags: property tests that truncated outputs include deterministic `"truncated"` metadata.
* [ ] ND-JSON: smoke test that records are well-formed and end with a summary record.

## Documentation

* [ ] README: clarify defaults (summary-only), show `--payload all` + `--output` for large payloads.
* [ ] README: add matrix table for `payload × emit` with sinks and expected behavior.
* [ ] README: document heavy-dir prompt and escape hatches (`--yes`, keeps ignores).
* [ ] Add JSON Schemas: `resources/summary.schema.json` and `resources/payload.schema.json`; link from README.

## Quick wins (small, high-value)

* [ ] Implement sink routing for summaries (fixes `--output` + summary and “stdout flood”).
* [ ] Prevent `--quiet` from muting JSON.
* [ ] Version fallback to pyproject with annotated source.
* [ ] Catch Click exceptions to avoid stack traces while preserving BrokenPipe handling.

* [ ] Detect clipboard backend availability at startup; if unavailable, set `allow_clipboard=False` and emit one-line notice at `INFO` once.
* [ ] Reduce clipboard retry logs to a single message; drop stack traces; keep bounded timeout.
* [ ] Add `--clipboard {auto,always,never}` (and `GROBL_NO_CLIPBOARD`) wired to `clipboard_allowed()`.

* [ ] `init`: if `--path` is missing, either create it (default) or require `--mkdir`; document behavior.
* [ ] `init`: when config exists, prompt “Overwrite? (y/N)” (respect `--yes`); keep `--force` as non-interactive override.
* [ ] `init`: correct the overwrite message to reference the exact path; add tests.

