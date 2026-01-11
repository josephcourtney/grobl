## Ignore UX overhaul (tree vs content)

- [ ] define the user-facing model: “tree visibility” vs “content capture”; document invariants and intended defaults in SPEC.md
- [ ] add a new internal “ignore decision” data model that can explain *why* a path is excluded
  - [ ] introduce a `LayerSource` enum (defaults | config | explicit_config | cli_runtime) and a `MatchDecision`/`ExclusionReason` dataclass
  - [ ] preserve raw patterns during compilation (store raw text + negated/core) so the winning rule can be reported
  - [ ] extend compiled layers to carry provenance (base_dir + source + config file path if applicable)
  - [ ] implement `LayeredIgnoreMatcher.explain_tree(path, is_dir)` and `.explain_content(path, is_dir)` returning decision + provenance
  - [ ] keep existing boolean methods (`excluded_from_tree/print`) delegating to the new decision engine for compatibility

- [ ] make CLI runtime edits apply to content-capture rules as well as tree rules
  - [ ] extend `apply_runtime_ignore_edits(...)` (or add a sibling helper) to support edits for `exclude_print` (“content”) in addition to `exclude_tree`
  - [ ] thread `runtime_print_patterns` from CLI through `_assemble_layered_ignores(...)` into `build_layered_ignores(...)`

## New CLI flags (intuitive include/exclude)

- [ ] implement intuitive flags for common intent (affect both tree + content)
  - [ ] add `--exclude PATTERN` (applies to tree + content)
  - [ ] add `--include PATTERN` (negated include; applies to tree + content)
  - [ ] add `--exclude-file PATH` / `--include-file PATH` (optional convenience for exact files; expands to pattern safely)

- [ ] implement scoped flags (tree-only vs content-only)
  - [ ] add `--exclude-tree PATTERN` / `--include-tree PATTERN`
  - [ ] add `--exclude-content PATTERN` / `--include-content PATTERN`
  - [ ] ensure scoped flags compose deterministically (“last match wins”, consistent ordering across sources)

- [ ] deprecate the confusing legacy flags without breaking existing scripts
  - [ ] keep `--add-ignore/--unignore/--remove-ignore/--ignore-file` working, but emit a deprecation warning pointing to the new equivalents
  - [ ] redefine naming in help/README so “ignore” is no longer overloaded
  - [ ] add a removal timeline policy (e.g., remove legacy flags in next major version)

## Explain/diagnostics (“why is this excluded?”)

- [ ] add `grobl explain [PATHS...]` subcommand (preferred) OR `grobl scan --explain [PATHS...]` (alias)
  - [ ] for each provided path, report:
    - [ ] tree decision: included/excluded + winning pattern + source + base_dir (+ config path if any)
    - [ ] content decision: included/excluded + winning pattern + source + base_dir (+ config path if any)
    - [ ] text detection: text vs binary (and why), if content is omitted due to detection
  - [ ] support `--format {human,json}` for explain output with stable schema and ordering
  - [ ] ensure explain does not require or produce payload output; keep stdout/stderr behavior deterministic

## Summary JSON improvements (optional but high-value)

- [ ] enrich `--summary json` output with reasons for `included=false`
  - [ ] add optional fields like `content_reason` (winning pattern + source + base_dir) when content is omitted
  - [ ] avoid breaking existing consumers: only add new keys; keep existing keys unchanged
  - [ ] ensure JSON key ordering remains stable and a trailing newline is preserved

## Defaults and configuration naming

- [ ] decide on default handling for `docs/` (policy)
  - [ ] option A: remove `docs` from default `exclude_print` to match common expectations
  - [ ] option B: keep current default, but ensure `--include-content 'docs/**'` is prominently documented and demonstrated

- [ ] make config naming clearer (non-breaking)
  - [ ] optionally support `exclude_content` as an alias for `exclude_print` when loading config (keep writing canonical key)

## Tests and spec conformance

- [ ] add unit tests for ignore decision provenance
  - [ ] verify “last match wins” with negations across layers and bases
  - [ ] verify tree vs content decisions differ as expected (tree included, content excluded, etc.)
  - [ ] verify provenance reports correct base_dir + config origin

- [ ] add component/system tests for CLI behavior
  - [ ] `--include-content docs/**` overrides default `exclude_print` and includes doc contents
  - [ ] legacy flags still behave the same and emit deprecation warnings
  - [ ] `grobl explain` reports correct winning rule for both tree and content

- [ ] update SPEC.md with normative behavior for the new flags and explain output
  - [ ] specify precedence/ordering when multiple flags and sources apply
  - [ ] specify explain JSON schema and determinism requirements

## Docs and help text

- [ ] update README.md:
  - [ ] replace “ignore” language with “exclude/include” and “tree/content” terminology
  - [ ] add a troubleshooting section: “in tree but no contents”, “docs contents missing”, “binary detection”
  - [ ] add examples for the new flags and for `grobl explain`

- [ ] update CLI help/epilog strings to feature the new flags and the explain workflow
