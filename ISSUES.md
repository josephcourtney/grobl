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

