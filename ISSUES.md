## `ScanExecutor` centralizes too many concerns

**Problem**

`ScanExecutor` currently owns several independent policies:

- How to invoke the scanner and construct `SummaryContext`.
- How to decide which payload to build (JSON vs LLM vs Markdown vs none).
- How `summary_format` affects the resulting structures.
- When and how to write to the sink.
- It returns `(human_summary_text, summary_dict)` while also mutating external state (emitting payloads).

`ScanExecutor.execute` also has a growing `if/elif` ladder keyed on `PayloadFormat` and separate branching for `SummaryFormat`, making it the de-facto dumping ground when adding new output types.

**Suggested approach**

- Introduce a small `PayloadStrategy` interface that encapsulates the “emit payload” policy:

  ```python
  class PayloadStrategy(Protocol):
      def emit(
          self,
          builder: DirectoryTreeBuilder,
          context: SummaryContext,
          result: ScanResult,
          sink: Callable[[str], None],
      ) -> None: ...
  ```

* Provide implementations:

  * `JsonPayloadStrategy`
  * `MarkdownPayloadStrategy`
  * `LlmPayloadStrategy`
  * `NoopPayloadStrategy`

* Maintain a mapping from `PayloadFormat` to strategy:

  ```python
  _PAYLOAD_STRATEGIES: dict[PayloadFormat, PayloadStrategy] = {
      PayloadFormat.JSON: JsonPayloadStrategy(...),
      PayloadFormat.MARKDOWN: MarkdownPayloadStrategy(...),
      PayloadFormat.LLM: LlmPayloadStrategy(...),
      PayloadFormat.NONE: NoopPayloadStrategy(),
  }
  ```

* Let `ScanExecutor.execute`:

  * Pick the strategy from the mapping.
  * Delegate `emit(...)` to it.
  * Focus only on scanning and building `SummaryContext` / `ScanResult`.

* Similarly, centralize summary behaviour in a small helper:

  ```python
  def build_summary_for_format(
      base_summary: dict[str, Any],
      fmt: SummaryFormat,
  ) -> tuple[str, dict[str, Any]]:
      if fmt is SummaryFormat.NONE:
          return "", {
              "root": base_summary["root"],
              "scope": base_summary["scope"],
              "style": base_summary["style"],
              "totals": base_summary["totals"],
              "files": [],
          }
      if fmt is SummaryFormat.JSON:
          return "", base_summary
      # HUMAN
      return "<human text produced separately>", base_summary
  ```

* After that, `execute` should mainly orchestrate:

  * Scan
  * Build context/result
  * Delegate payload/summary handling to small, testable helpers

instead of encoding every output policy inline.

---

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

---

## Directory traversal configuration uses overloaded tuples

**Problem**

`traverse_dir` takes a tuple `config` with two different shapes:

* Without precomputed `PathSpec`:

  ```python
  traverse_dir(base, ([base], [], base), cb)
  ```

* With precomputed `PathSpec`:

  ```python
  traverse_dir(common, (resolved, excl_tree, common, tree_spec), collect)
  ```

The implementation branches on `len(config)`, with casts based on tuple length. This:

* Obscures what the configuration means.
* Makes the signature harder to understand and type-check.
* Encourages “magic” constants like `CONFIG_WITHOUT_SPEC_LENGTH`.

**Suggested approach**

* Introduce an explicit configuration object:

  ```python
  @dataclass(frozen=True)
  class TraverseConfig:
      paths: list[Path]
      patterns: list[str]
      base: Path
      spec: PathSpec | None = None
  ```

* Update `traverse_dir` to take `TraverseConfig`:

  ```python
  def traverse_dir(
      path: Path,
      config: TraverseConfig,
      callback: TreeCallback,
      prefix: str = "",
  ) -> None:
      spec = config.spec or PathSpec.from_lines("gitwildmatch", config.patterns)
      items = filter_items(
          list(path.iterdir()),
          config.paths,
          config.patterns,
          config.base,
          spec,
      )
      ...
  ```

* Update call sites:

  ```python
  cfg = TraverseConfig(paths=[base], patterns=[], base=base)
  traverse_dir(base, cfg, cb)

  cfg = TraverseConfig(paths=resolved, patterns=excl_tree, base=common, spec=tree_spec)
  traverse_dir(common, cfg, collect)
  ```

* Optionally simplify `filter_items` to accept `TraverseConfig` rather than multiple parallel arguments.

This removes tuple shape logic, makes the code more self-documenting, and improves static checking.

---

## Directory tree rendering duplicates annotation logic

**Problem**

`DirectoryRenderer` has at least two methods that annotate the directory tree:

* `tree_lines(include_metadata: bool = False) -> list[str]`
* `tree_lines_for_markdown() -> list[str]`

Both:

* Start from `builder.tree_output()`.
* Prepend `f"{b.base_path.name}/"` as the root line.
* Walk over indices / entries to attach file metadata.

However, they:

* Re-implement similar loops over tree indices and metadata.
* Use different internal representations to compute padding / markers.
* Risk drifting behaviour over time (e.g., different handling for missing metadata).

**Suggested approach**

* Factor out a single “annotated tree” helper that operates on `tree_output` plus metadata:

  ```python
  def _annotated_tree(
      self,
      annotate: Callable[[Path, tuple[int, int, bool] | None], str | None],
  ) -> list[str]:
      b = self.builder
      raw = b.tree_output()
      if not raw:
          return [f"{b.base_path.name}/"]

      entry_map = dict(b.file_tree_entries())
      lines: list[str] = []
      for idx, text in enumerate(raw):
          rel = entry_map.get(idx)
          meta = b.get_metadata(str(rel)) if rel is not None else None
          label = annotate(rel, meta) if rel is not None else None
          lines.append(text if not label else f"{text} {label}")

      return [f"{b.base_path.name}/", *lines]
  ```

* Implement `tree_lines` via `_annotated_tree` with an annotator that:

  * Computes column widths once (for lines/chars/included) across all files.
  * Returns well-aligned column strings when `include_metadata=True`.
  * Returns `None` when `include_metadata=False`.

* Implement `tree_lines_for_markdown` via `_annotated_tree` with an annotator that:

  * Returns markers like `[INCLUDED:FULL]` / `[NOT_INCLUDED]` based on metadata and totals.
  * Uses the same source of truth for inclusion semantics as in Issue 3.

This removes duplicated traversal logic and makes the difference between the two views purely a function of the chosen annotator.

---


