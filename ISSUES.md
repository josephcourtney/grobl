## Markdown payload builder mixes schema and layout

**Problem**

`renderers.build_markdown_payload` is responsible for both:

* **Schema-level decisions**

  * What metadata keys exist and how they’re encoded (e.g., `%%%% BEGIN_FILE path="…" ... %%%%`).
  * The grammar for `BEGIN_FILE` headers (path, language, line/char counts, inclusion markers).
  * Inclusion semantics markers (e.g., `INCLUDED`, line ranges).

* **Layout decisions**

  * Markdown section structure (`# Project Snapshot`, `## Directory`, `## Files`).
  * Where to place headers and blank lines.
  * When/where to emit the “## Files” header (currently guarded by an `any(line.startswith("## Files")...)` check on `parts`, even though `parts` is fresh per call).

Combining these concerns makes it harder to evolve the schema (for tools) independently from the human-readable layout, and the defensive “## Files” header check obscures a simple invariant.

**Suggested approach**

* Introduce a “Markdown schema” or “snapshot builder” layer responsible for schema only:

  * `MarkdownSnapshotSchema` or `MarkdownPayloadSchema` that knows:

    * What a `BEGIN_FILE` header looks like.
    * How inclusion markers, line/char metadata, and other annotations are encoded.
    * What JSON-like structures back each section.

* Separate “schema → Markdown layout” from “raw data → schema”:

  * One object (or set of helpers) builds schema objects from `DirectoryTreeBuilder` / `SummaryContext`.
  * Another is responsible for turning those schema objects into Markdown text (headings, ordering, blank lines).

* Centralize `BEGIN_FILE` formatting in one helper:

  ```python
  def format_begin_file_header(
      path: str,
      language: str | None,
      line_range: str,
      chars: int,
  ) -> str:
      ...
  ```

  Use this everywhere (including tests) instead of open-coding the header.

* Simplify “## Files” header logic:

  * Because `parts` is newly created per call and `build_markdown_payload` is the only function that adds “## Files”, drop the defensive `any(...)` and always add “## Files” exactly once when there are files.

This makes it easier to:

* Change schema rules (e.g. add fields or tweak header grammar).
* Tweak layout (section titles, ordering) without touching schema code.

---

## Totals and inclusion semantics are spread across modules

**Problem**

Totals and inclusion semantics are maintained in `DirectoryTreeBuilder`, but reasoning about them is spread across:

* `summary.py`
* `formatter.py`
* `renderers.DirectoryRenderer.tree_lines_for_markdown`
* `services.ScanExecutor`

`DirectoryTreeBuilder` also has:

```python
def record_metadata(self, rel: Path, lines: int, chars: int) -> None:
    self.files.record_metadata(rel, lines, chars)
    self.all_total_lines += lines
    self.all_total_characters += chars

def add_file(self, file_path: Path, rel: Path, lines: int, chars: int, content: str) -> None:
    self.files.add_file(file_path, rel, lines, chars, content)
    self.total_lines += lines
    self.total_characters += chars
```

The distinction between “all files” totals (`all_total_*`) and “included files” totals (`total_*`) is correct but non-obvious, and callers risk re-implementing inclusion semantics.

**Suggested approach**

* Design a single source of truth for totals and inclusion semantics:

  * Either a small helper (`SummaryTotals`) or extended `SummaryContext` API.
  * It should answer:

    * Global totals for “all files seen”.
    * Totals for “files whose contents were included”.
    * Per-file inclusion status (included vs not included).

* Update modules to query this API instead of re-deriving or duplicating logic:

  * `DirectoryRenderer` should use it when annotating tree lines and Markdown markers.
  * `summary.py` and `formatter.py` should rely on it for their tables and JSON.
  * `ScanExecutor` should treat it as authoritative when building summaries.

* Make `DirectoryTreeBuilder`’s API reflect intent more explicitly:

  * Rename methods, e.g.:

    ```python
    def record_metadata_for_any_file(...): ...
    def record_included_file(...): ...
    ```

  * Or have `add_file` call `record_metadata` internally so `all_total_*` and `total_*` remain coupled:

    ```python
    def add_file(...):
        self.record_metadata(rel, lines, chars)
        self.files.add_file(...)
        self.total_lines += lines
        self.total_characters += chars
    ```

* Add tests that check totals and inclusion semantics via the central API, not internal counters, to reduce the chance of divergence.

