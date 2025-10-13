## P2 — UX Simplifications (routing & defaults)

* [ ] **Unify routing model (one writer)**

  * **Files**: CLI modules
  * **Change**: Remove remaining direct `print` paths for summaries; use the same sink chain everywhere.

* [ ] **Validate “no output” combos as usage errors**

  * **Files**: `src/grobl/cli/scan.py`
  * **Change**: Treat `--mode summary --table none` (legacy) and future `--payload none --emit none` as usage errors with hints.

* [ ] **Safer defaults**

  * **Files**: `src/grobl/cli/root.py` or `scan.py`
  * **Change**: On TTY with no flags, default to summary-only output (human). Keep current non-TTY behavior compact.

* [ ] **Heavy-dir prompt text improvement**

  * **Files**: `src/grobl/cli/common.py`
  * **Change**: Mention `--yes`, keeping default ignores, and support `GROBL_ASSUME_YES=1`.

*(Deferred interface renames kept for later: `--emit` / `--payload`.)*

---

## P3 — Tests (add/extend to lock behavior)

* [ ] **Summary→file regression**

  * Ensure `scan --mode summary --output out.txt` writes a non-empty file; stdout stays empty unless stdout is the chosen sink.

* [ ] **`--quiet` + JSON**

  * Ensure `scan --mode summary --format json --quiet` still emits JSON (stdout or file).

* [ ] **Friendly errors**

  * Invalid mode exits with code `2` and shows short Click message; assert no Python traceback text.

* [ ] **Version source detection**

  * Simulate `PackageNotFoundError` → `(pyproject)`; normal dist → `(distribution)`.

* [ ] **Config precedence (legacy+modern)**

  * With both files present, modern overrides legacy; capture a single warning with `caplog`.

* [ ] **No-output combos**

  * Asserting `EXIT_USAGE` and helpful message for forbidden combinations.

---

## P4 — Docs & Release Hygiene

* [ ] **README updates**

  * Document sink routing (file → clipboard → stdout), `--quiet` affecting human output only, and sample `grobl version` output with source.
  * Note error behavior: usage errors exit with code `2` and show a short message (no tracebacks).

* [ ] **Changelog & version bump**

  * Bump `pyproject.toml` version to `0.7.5`.
  * Add `## [0.7.5] - YYYY-MM-DD` with:

    * **Fixed**: sink routing for summaries; JSON not muted by `--quiet`; friendly Click errors; config precedence warning.
    * **Added**: version source annotation + `pyproject.toml` fallback.

---

## P5 — Nice-to-haves (defer until after P0–P4)

* [ ] **(Optional) Preserve exact stdout newline semantics**

  * **Files**: `src/grobl/output.py`
  * **Change**: Use `sys.stdout.write(content)` instead of `print(content)` inside `StdoutOutput.write` to avoid extra newline.

* [ ] **Clipboard robustness**

  * Detect clipboard backend at startup; set `allow_clipboard=False` and log a single INFO line if unavailable; reduce retry logs to a single concise message.

* [ ] **CLI switches (future)**

  * Add `--emit {human,json,none}` and `--payload {all,tree,files,none}` (keep old names as hidden aliases); update help grouping accordingly.

* [ ] **Discovery/perf controls (future)**

  * `--include <glob>` (gitwildmatch); `--max-depth N`; payload governors in `TextFileHandler` (`--max-file-lines`, `--max-file-bytes`, `--max-total-bytes`) with `"truncated"` metadata.

* [ ] **ND-JSON stream mode (future)**

  * `--emit ndjson` that streams entries + final summary.

* [ ] **Architecture polish (future)**

  * Require precompiled `PathSpec` in `filter_items()` (update call sites).
  * Authoritative `binary=True` flag set by `BinaryFileHandler`; drop heuristic in `summary._file_entries()`.
  * Add `scan_id` and `root` to every `StructuredLogEvent.context`.

* [ ] **Documentation extras (future)**

  * JSON Schemas: `resources/summary.schema.json`, `resources/payload.schema.json`; link from README.

---

### Notes on deduplication

* “Route summaries through the sink”, “Do not suppress machine output with `--quiet`”, “Implement sink routing for summaries”, and “Prevent `--quiet` from muting JSON” overlapped—kept once under **P0**.
* Click error handling items merged into a single **P0** task.
* Version labeling + CLI printing merged into one **P1** task.
* Config precedence (legacy+modern) appears once under **P1**.
* The optional stdout newline tweak is isolated under **P5**.

