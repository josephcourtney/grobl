### Smells / risks and high-level refactor suggestions

1. **`ScanExecutor` is beginning to centralize too many independent policies**

   Symptoms:

   * Knows about:

     * how to call the scanner,
     * how to build summary contexts,
     * which payload to build,
     * JSON-vs-LLM-vs-Markdown logic,
     * how `summary_format` affects outputs,
     * when to write to the sink.
   * It returns `(human_summary_text, summary_dict)` while also mutating external state (writing payload).

   Possible direction:

   * Introduce a `PayloadStrategy` interface, e.g.:

     ```python
     class PayloadStrategy(Protocol):
         def emit(self, builder: DirectoryTreeBuilder, common: Path, sink: Callable[[str], None]) -> None: ...
     ```

   * Provide implementations:

     * `LLMPayloadStrategy`,
     * `MarkdownPayloadStrategy`,
     * `JsonPayloadStrategy`,
     * `NoopPayloadStrategy`.

   * `ScanExecutor` would then just:

     * pick a strategy from a mapping keyed by `PayloadFormat`,
     * delegate `emit(...)` to it,
     * and focus on scanning + summary-building.

   That keeps `ScanExecutor` from becoming the permanent dumping ground for new output types.

2. **`renderers.build_markdown_payload` mixing layout and schema-level policy**

   Right now it decides both:

   * Markdown structure (# Project Snapshot, `## Directory`, `## Files`),
   * and schema rules (which metadata keys are omitted, inclusion markers, line-range conventions).

   Potential refactor:

   * Extract a “Markdown schema” / “snapshot builder” object:

     * One concern: *what* goes into the Markdown schema (`BEGIN_FILE` line grammar, annotation conventions).
     * Another: *how* it’s laid out as Markdown text (sections, headings, etc.).

   You don’t need this immediately, but if you expect to iterate on the schema vs. layout independently, this will help.

3. **Cross-module knowledge of totals and inclusion semantics**

   * Totals are maintained in `DirectoryTreeBuilder`, but:

     * `summary.py`, `formatter.py`, `renderers.DirectoryRenderer.tree_lines_for_markdown`, and `services.ScanExecutor` all reason about those numbers and/or inclusion across different dimensions.
   * It’s still coherent, but this is a subtle “knowledge spread” smell.

   Possible direction:

   * Allow `SummaryContext` or a small “Totals” helper to be the single source of truth for:

     * included vs all totals,
     * inclusion status per file,
     * reused when building Markdown annotations, JSON summaries, and human tables.
   * That would tighten SRP and reduce duplication of the “what is included?” logic across modules.

4. **CLI error handling is split between `cli.scan`, `cli.common`, and `cli.root`**

   * `scan.py` handles Click `UsageError`s and some validation.
   * `_execute_with_handling` maps core exceptions (`PathNotFoundError`, `ScanInterrupted`) to exit codes.
   * `root.main` has its own `BrokenPipeError` handling.
   * `scan`’s own printing of the summary also has a `BrokenPipeError` handler.

   It works and tests pass, but responsibilities are a bit scattered.

   Potential improvement:

   * Keep `BrokenPipeError` handling in one place (probably `main`), and let CLI commands just raise.
   * Alternatively, standardize a small “top-level error adapter” that wraps command invocation and exits appropriately, so each command doesn’t need its own pipe+exit logic.

## hardening opportunities

  - src/grobl/file_handling.py:78-149 currently asks
    FileHandlerRegistry.handle to run text_detector before
    dispatching, and then TextFileHandler._analyze reopens
    the same file via text_reader to collect the content. That
    means every text file is opened twice (once for detection,
    once for reading). Sharing the detector’s findings (or the
    early chunk it already read) with the handler would avoid
    redundant I/O and speed up large scans.
  - src/grobl/utils.py:15-31 treats any common ancestor equal
    to Path(root.anchor) (typically / or a Windows drive root)
    as “no common ancestor,” and src/grobl/cli/scan.py:124-
    128 silently falls back to the current working directory
    when that happens. Tossing the user’s intended root
    into the current directory is surprising; it would be
    better to allow true root anchors (or at least surface a
    clear error) so grobl / or grobl C:\ genuinely scans the
    requested tree rather than whatever directory the user
    happened to run from.
  - src/grobl/renderers.py:219-255 constructs the Markdown
    payload’s metadata header by interpolating path,
    language, etc. inside unescaped double quotes (e.g.,
    path="foo"bar.md"). Files whose names contain quotes or
    newlines can therefore produce invalid Markdown/metadata
    blocks. Escaping those values (or using a structured
    serializer) would keep the payload valid even for oddly
    named files.


## 1. Centralise “payload format → builder” logic

Right now `ScanExecutor.execute` has a small but growing `if/elif` ladder:

```python
if self._should_emit_json_payload(options):
    payload_json = self._deps.sink_payload_builder(context)
    self._sink(_json.dumps(payload_json, sort_keys=True, indent=2))
elif options.payload_format is PayloadFormat.LLM:
    payload = self._deps.payload_builder(...)
    ...
elif options.payload_format is PayloadFormat.MARKDOWN:
    payload = build_markdown_payload(...)
    ...
```

and the summary handling has its own `if options.summary_format is ...` branching afterwards.

**Dedup idea**

* Introduce small strategy functions or a mapping for payloads:

```python
_PAYLOAD_EMITTERS: dict[PayloadFormat, Callable[[ScanExecutor, SummaryContext, ScanResult], None]] = {
    PayloadFormat.JSON: _emit_json_payload,
    PayloadFormat.LLM: _emit_llm_payload,
    PayloadFormat.MARKDOWN: _emit_markdown_payload,
    PayloadFormat.NONE: _emit_noop_payload,
}
```

Inside `execute`:

```python
emitter = _PAYLOAD_EMITTERS[options.payload_format]
emitter(self, context, result)
```

Each `_emit_*` helper becomes a ~5–10 line function. That:

* Removes the `if/elif` ladder.
* Makes it obvious where to plug in a new format.
* Lets each function have a focused local variable set (no long method with many moving parts).

Same trick works for **summary behaviour**:

```python
def _build_summary_for_format(
    *, base_summary: dict[str, Any], fmt: SummaryFormat
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
    return "<human-text provided separately>", base_summary
```

Then `execute` just calls that once instead of inlining three cases.

---

## 2. Unify `BrokenPipeError` handling

You currently handle `BrokenPipeError` in at least two separate places with very similar code:

* `cli.root.main`:

```python
try:
    cli.main(...)
except BrokenPipeError:
    try:
        sys.stdout.close()
    finally:
        raise SystemExit(0)
```

* `cli.scan` when printing the summary:

```python
try:
    ...
except BrokenPipeError:
    try:
        sys.stdout.close()
    finally:
        raise SystemExit(0)
```

**Dedup idea**

* Standardise this as a tiny helper, e.g. in `tty.py` or a new `cli/errors.py`:

```python
def exit_on_broken_pipe() -> None:
    try:
        sys.stdout.close()
    finally:
        raise SystemExit(0)
```

Then:

```python
except BrokenPipeError:
    exit_on_broken_pipe()
```

in both places. That:

* Removes duplicated control-flow.
* Makes the “broken pipe policy” clearly discoverable in one place.

You could go further and say “only `main` handles broken pipes”, letting `scan` re-raise, but the helper is the minimal change.

---

## 3. Clean up directory traversal config tuple

`traverse_dir` is called with two different tuple “shapes”:

* Without precomputed `PathSpec`:

```python
traverse_dir(base, ([base], [], base), cb)
```

* With precomputed `PathSpec`:

```python
traverse_dir(common, (resolved, excl_tree, common, tree_spec), collect)
```

and the implementation uses length checks:

```python
if len(config) == CONFIG_WITHOUT_SPEC_LENGTH:
    paths, patterns, base = cast(...)
    spec: PathSpec | None = None
else:
    paths, patterns, base, spec = cast(...)
```

This makes the signature harder to read and reason about.

**Dedup / clarity idea**

* Introduce a small config dataclass and let callers construct it once:

```python
@dataclass(frozen=True)
class TraverseConfig:
    paths: list[Path]
    patterns: list[str]
    base: Path
    spec: PathSpec | None = None
```

Then:

```python
def traverse_dir(path: Path, config: TraverseConfig, callback: TreeCallback, prefix: str = "") -> None:
    spec = config.spec or PathSpec.from_lines("gitwildmatch", config.patterns)
    items = filter_items(list(path.iterdir()), config.paths, config.patterns, config.base, spec)
    ...
```

Call sites become:

```python
cfg = TraverseConfig(paths=[base], patterns=[], base=base)
traverse_dir(base, cfg, cb)

cfg = TraverseConfig(paths=resolved, patterns=excl_tree, base=common, spec=tree_spec)
traverse_dir(common, cfg, collect)
```

* No magic `CONFIG_WITHOUT_SPEC_LENGTH`.
* Type checking becomes simpler; no casts on tuple shapes.
* `filter_items` signature can be simplified to just accept a `TraverseConfig` as well if you want to go further.

---

## 4. Reduce duplication between `tree_lines` and `tree_lines_for_markdown`

`DirectoryRenderer` has two methods:

* `tree_lines(include_metadata: bool = False) -> list[str]`
* `tree_lines_for_markdown() -> list[str]`

Both:

* Start from `builder.tree_output()`.
* Prepend `f"{b.base_path.name}/"` as the root line.
* Walk over `file_tree_entries` and metadata to annotate lines.

But the logic is split and partially reimplemented between them (e.g. computing column widths vs computing annotation width).

**Dedup idea**

Factor out a single “annotate file rows” helper that operates on the raw tree:

```python
def _annotated_tree(
    self,
    *,
    annotate: Callable[[Path, tuple[int, int, bool]], str | None],
) -> list[str]:
    b = self.builder
    raw = b.tree_output()
    if not raw:
        return [f"{b.base_path.name}/"]

    entry_map = dict(b.file_tree_entries())
    out: list[str] = []
    for idx, text in enumerate(raw):
        rel = entry_map.get(idx)
        if rel is None:
            out.append(text)
            continue
        meta = b.get_metadata(str(rel))
        label = annotate(rel, meta) if meta is not None else None
        out.append(text if label is None else f"{text} {label}")
    return [f"{b.base_path.name}/", *out]
```

Then:

* `tree_lines(include_metadata=True)` can call `_annotated_tree` with an annotator that returns `"lines chars included"` column text, computing padding once.
* `tree_lines_for_markdown` can call `_annotated_tree` with an annotator that returns `[INCLUDED:FULL]` / `[NOT_INCLUDED]` labels.

That:

* Removes repetition of the “walk raw tree + lookup metadata + choose marker” pattern.
* Makes it obvious that both views are just different annotations over the same tree.

---

## 5. Make `DirectoryTreeBuilder` totals updates more self-documenting

Right now `DirectoryTreeBuilder` has:

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

The distinction between `total_*` and `all_total_*` is correct, but the reader has to mentally reconstruct:

* `record_metadata` → *all* files seen.
* `add_file` → only files whose contents were included.

**Readability tweak**

* Make that explicit via small naming and docstring changes:

```python
def record_metadata_for_any_file(...):
    """Record counts for any file (included or not) and update global totals."""
    ...

def record_included_file(...):
    """Record counts and content for a file whose contents are included."""
    ...
```

and/or:

* Have `add_file` call `record_metadata` internally so that “all files totals” and “included totals” are clearly coupled in one place:

```python
def add_file(...):
    self.record_metadata(rel, lines, chars)
    self.files.add_file(...)
    self.total_lines += lines
    self.total_characters += chars
```

That removes the risk of future handlers forgetting to update `all_total_*`.

---

## 6. Small CLI readability wins

A few small, mechanical changes can make the CLI modules easier to scan:

1. **`ScanParams` vs `ScanOptions`**

   * `ScanParams` (CLI-only) and `ScanOptions` (service-level) are similarly named.
   * Consider renaming `ScanParams` to `CliScanParams` or `ScanCliParams` to make their roles immediately obvious.

2. **Inline `ctx = click.get_current_context()` usage**

   In `scan`, `ctx` is only used for two `click.UsageError`s. You can:

   * Factor the validation into small helpers:

   ```python
   def _validate_payload_and_summary(params: ScanParams, ctx: click.Context) -> None: ...
   def _validate_sink_and_output(params: ScanParams, ctx: click.Context) -> None: ...
   ```

   and call them in order. That makes the main `scan` function read as a flat “parse → build params → validate → run”.

3. **Consistent naming for “stdout summary style”**

   * In `scan` you compute:

     ```python
     actual_table = resolve_table_style(params.summary_style)
     ...
     summary, summary_json = _execute_with_handling(..., summary_style=actual_table)
     ```

   * Meanwhile `ScanOptions.summary_style` already wants the *effective* style, not `AUTO`.

   You can avoid the small mental hop by passing the resolved style into `ScanOptions` directly (instead of both the raw and the resolved ones):

   ```python
   effective_style = resolve_table_style(params.summary_style)
   ...
   options=ScanOptions(..., summary_style=effective_style)
   ```

   and `_execute_with_handling` no longer needs a separate `summary_style` argument; it can use `options.summary_style` via the executor.

This doesn’t change behaviour, it just reduces the number of separate “what is the current table style?” variables floating around.

---

## 7. Simplify Markdown payload “## Files” header logic

In `build_markdown_payload`:

```python
if scope in {ContentScope.ALL, ContentScope.FILES}:
    files = builder.files_json()
    if files:
        # Ensure we only add the "## Files" header once...
        if not any(line.startswith("## Files") for line in parts):
            parts.extend(("", "## Files"))
        for file_info in files:
            ...
```

Because `parts` is freshly created per call and only this block ever adds `## Files`, the defensive `any(...)` is unnecessary and obscures intent a bit.

You can simplify to:

```python
if scope in {ContentScope.ALL, ContentScope.FILES}:
    files = builder.files_json()
    if files:
        parts.extend(("", "## Files"))
        for file_info in files:
            ...
```

If you ever introduce multiple file sections, that’s the time to reintroduce the check—but until then, this is clearer.

---

## 8. Centralise Markdown `BEGIN_FILE` metadata formatting

The block:

```python
meta_parts: list[str] = [f'path="{name}"']
# `kind="full"` is the default and therefore omitted...
if language:
    meta_parts.append(f'language="{language}"')
meta_parts.extend((f'lines="{line_range}"', f'chars="{chars}"'))

header = f"%%%% BEGIN_FILE {' '.join(meta_parts)} %%%%"
```

is the only place that knows the exact schema for `BEGIN_FILE`, but all tests and consumers care about that schema.

You can:

* Extract a helper `format_begin_file_header(name, language, line_range, chars) -> str`.

That:

* Gives the format a single “home” (makes changes safer).
* Lets tests that care about the exact header call the helper directly instead of duplicating string literals or fragile `startswith` patterns.


## bugs

  - XML attributes: _build_tree_payload/_build_files_payload (src/grobl/renderers.py:139-148) interpolate name, path, and root straight into "<ttag …>" without escaping. Any directory or file whose
    name contains ", <, >, or & produces malformed XML/LLM payloads and will break downstream consumers that expect well-formed tags.
  - File contents leaking raw XML: DirectoryRenderer.files_payload() concatenates the chunks coming from FileCollector.add_file (src/grobl/renderers.py:131-134) without escaping them, then wraps them
    in <file:content>…</file:content> tags. If a captured file contains <, &, or </file:content> itself (very common), the resulting payload can no longer be parsed or even recognized as XML, so the
    “XML-like” contract this module advertises is violated.
  - Markdown metadata injection: The %%%% BEGIN_FILE path="…" … header in build_markdown_payload (src/grobl/renderers.py:236-244) also interpolates raw file names. Filenames with embedded quotes, %,
    or other Markdown-sensitive characters will break the header (e.g., path="foo"bar.md"), corrupting the generated Markdown payload.

  Escaping the interpolated values (or encoding them generically) before emitting them would prevent such inputs from breaking the outputs.
