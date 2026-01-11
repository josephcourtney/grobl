## Explain/diagnostics (“why is this excluded?”)

- [x] add `grobl explain [PATHS...]` subcommand (preferred) OR `grobl scan --explain [PATHS...]` (alias)
  - [x] for each provided path, report:
    - [x] tree decision: included/excluded + winning pattern + source + base_dir (+ config path if any)
    - [x] content decision: included/excluded + winning pattern + source + base_dir (+ config path if any)
    - [x] text detection: text vs binary (and why), if content is omitted due to detection
  - [x] support `--format {human,json}` for explain output with stable schema and ordering
  - [x] ensure explain does not require or produce payload output; keep stdout/stderr behavior deterministic

## Summary JSON improvements (optional but high-value)

- [x] enrich `--summary json` output with reasons for `included=false`
  - [x] add optional fields like `content_reason` (winning pattern + source + base_dir) when content is omitted
  - [x] avoid breaking existing consumers: only add new keys; keep existing keys unchanged
  - [x] ensure JSON key ordering remains stable and a trailing newline is preserved

## Defaults and configuration naming

- [x] decide on default handling for `docs/` (policy)
  - [x] option B: keep current default, but ensure `--include-content 'docs/**'` is prominently documented and demonstrated

- [x] make config naming clearer (non-breaking)
  - [x] optionally support `exclude_content` as an alias for `exclude_print` when loading config (keep writing canonical key)

## Tests and spec conformance

- [x] add unit tests for ignore decision provenance
  - [x] verify “last match wins” with negations across layers and bases
  - [x] verify tree vs content decisions differ as expected (tree included, content excluded, etc.)
  - [x] verify provenance reports correct base_dir + config origin

- [x] add component/system tests for CLI behavior
  - [x] `--include-content docs/**` overrides default `exclude_print` and includes doc contents
  - [x] legacy flags still behave the same and emit deprecation warnings
  - [x] `grobl explain` reports correct winning rule for both tree and content

- [x] update SPEC.md with normative behavior for the new flags and explain output
  - [x] specify precedence/ordering when multiple flags and sources apply
  - [x] specify explain JSON schema and determinism requirements

## Docs and help text

- [x] update README.md:
  - [x] replace “ignore” language with “exclude/include” and “tree/content” terminology
  - [x] add a troubleshooting section: “in tree but no contents”, “docs contents missing”, “binary detection”
  - [x] add examples for the new flags and for `grobl explain`

- [x] update CLI help/epilog strings to feature the new flags and the explain workflow
