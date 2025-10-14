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

