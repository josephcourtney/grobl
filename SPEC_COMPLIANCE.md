This is a section-by-section conformance assessment of the **current code** against **SPEC.md**.

“Compliant” means behavior is implemented as specified (or is a strict subset that does not violate a MUST/MUST NOT).
“Divergent” means there are missing features, different defaults, different routing, or rules that would produce different observable behavior.

---

## 1. Command Structure

### 1.1 Commands

* **Compliant (narrowly):** Existing command names (`scan`, `init`, `version`, `completions`) are alphabetic.
* **Divergent (behavioral):** The CLI currently accepts unknown commands and unknown options in ways that prevent “unknown bare word must error” behavior (see §2 and `CLI_CONTEXT_SETTINGS` in `grobl/cli/root.py`).

### 1.2 Default Command

* **Divergent:** The spec requires defaulting behavior to be governed by injection rules (§2) and unknown commands to error. Current CLI implements *two* fallback mechanisms:

  1. `_DefaultScanGroup.resolve_command()` falls back to `scan` on `click.UsageError` (`grobl/cli/root.py`), and
  2. `_inject_default_scan()` also injects `scan` (`grobl/cli/root.py`), plus
  3. `CLI_CONTEXT_SETTINGS` enables `ignore_unknown_options` and `allow_extra_args` (also `grobl/cli/root.py`), which is incompatible with “unknown command must error.”

---

## 2. Default-Scan Injection Rules

### 2.1 Path-Like Tokens

* **Divergent:** The spec defines path-like tokens as those containing any of `. ~ / \` and uses that in injection decisions. Current `_inject_default_scan()` does **not** implement this rule at all; it injects based primarily on “first token is not a flag and not a known command” (see §2.2).

### 2.2 Injection Conditions / 2.3 Non-Injection Conditions

* **Divergent (major):**

  * Current `_inject_default_scan()` injects `scan` for essentially any invocation where the first non-global token is not a known command and is not a help/version flag. It does **not** check filesystem existence and does **not** check path-likeness. (`grobl/cli/root.py::_inject_default_scan`)
  * Example divergence: `grobl foo` (where `foo` does not exist)

    * **Spec:** MUST NOT inject; MUST error unknown command.
    * **Current:** injects `scan`, then `run_scan()` errors “scan paths do not exist” (raised as `ValueError`) rather than “unknown command.”
  * Additionally, `_DefaultScanGroup.resolve_command()` will route unknown commands to scan anyway (independent of injection). (`grobl/cli/root.py::_DefaultScanGroup.resolve_command`)
  * `ignore_unknown_options=True` and `allow_extra_args=True` further allow ambiguous parsing instead of unknown-command errors. (`grobl/cli/root.py::CLI_CONTEXT_SETTINGS`)

---

## 3. Repository Root Resolution

* **Divergent:** There is no “repo root” resolution per spec (git root → common ancestor → CWD).

  * Current behavior:

    * Scanning “common base” is computed as the common ancestor of the *resolved scan paths* (`grobl/core.py::run_scan`).
    * “config base” is computed by searching upward for `.grobl.toml` / legacy / `pyproject.toml` (`grobl/config.py::resolve_config_base`).
  * There is **no git-root detection** anywhere in the provided code.
  * Deterministic ordering and hierarchical config discovery therefore cannot be anchored to repo root as required by §3 and §10.

---

## 4. Payload Output

### 4.1 Payload Formats

* **Divergent:**

  * Spec requires `--format {llm|markdown|json|ndjson|none}`.
  * Current CLI uses `--payload` and supports only `llm|markdown|json|none` (`grobl/constants.py::PayloadFormat`; `grobl/cli/scan.py`).
  * `ndjson` is missing entirely (enum, CLI, and rendering/emit strategy).

### 4.2 Payload Destination (default + selection)

* **Divergent:**

  * Spec requires a single selected destination with defaults:

    * default: clipboard
    * `--output -` => stdout
    * `--output PATH` => file
    * `--copy` forces clipboard
  * Current behavior is driven by `--sink` plus an output-chain fallback model (`grobl/output.py`):

    * `PayloadSink.AUTO` writes to **clipboard (suppressed errors) then stdout** when stdout is a TTY; otherwise stdout only.
    * `PayloadSink.CLIPBOARD` writes to **clipboard (suppressed errors) then stdout**.
    * This violates spec §4.2 (“Exactly one payload destination MUST be selected”) and also violates the default behavior you specified (clipboard-only by default).

### 4.3 Mutual Exclusivity (`--copy` vs `--output`)

* **Divergent:** Neither `--copy` nor mutual exclusivity exists in current CLI. Instead, `--sink` + `--output` combinations are allowed.

---

## 5. Summary Output

### 5.1 Summary Modes / 5.2 Auto Summary

* **Divergent:**

  * Spec requires `--summary {auto|none|table|json}` with `auto` based on stdout TTY.
  * Current CLI uses `--summary {human|json|none}` (via `SummaryFormat`) and defaults to `human` unconditionally (`grobl/constants.py::SummaryFormat`; `grobl/cli/scan.py`).
  * No `auto` mode exists.

### 5.3 Summary Style

* **Divergent:**

  * Spec: `--summary-style {auto|full|compact}` only valid when `--summary table`.
  * Current CLI: `--summary-style {auto|full|compact|none}` is always accepted regardless of `--summary` mode; there is **no validation** that ties it to human/table summary only (`grobl/constants.py::TableStyle`; `grobl/cli/scan.py`).

### 5.4 Summary Destination (`--summary-to`, `--summary-output`)

* **Divergent:** These flags and behaviors do not exist in current code.

---

## 6. Output Stream Separation

* **Divergent (major):**

  * Spec requires payload and summary to be independently routable, and summary MUST NOT contaminate payload unless explicitly routed together.
  * Current CLI prints summary to **stdout** (both human and summary-json) after payload emission (`grobl/cli/scan.py`).
  * Meanwhile payload may also go to stdout depending on sink selection (AUTO fallback, STDOUT sink, CLIPBOARD fallback). This contaminates pipelines.

---

## 7. Configuration and Ignore Discovery

### 7.1 Hierarchical `.grobl.toml` discovery (repo root down)

* **Divergent:** Current config loading is *not hierarchical*.

  * `read_config()` merges: defaults → XDG → base_path local `.grobl.toml`/legacy → pyproject tool table → env → explicit (`grobl/config.py::read_config`).
  * `resolve_config_base()` selects a single base directory by searching upward for one config file, then loads from *that base only* (`grobl/config.py::resolve_config_base`, `grobl/cli/scan.py`).
  * There is no “repo root down to each directory” accumulation of `.grobl.toml` files.

### 7.2 Relative interpretation to the `.grobl.toml` directory

* **Divergent:** Ignore patterns are effectively interpreted relative to a single `match_base` / config base, not per-config-file directory.

  * In traversal, matches are evaluated on `item.relative_to(config.base)` where `config.base` is `match_base` passed into `TraverseConfig` (`grobl/directory.py::filter_items`).
  * `match_base` is set to `options.pattern_base` which CLI sets to `config_base` (`grobl/cli/scan.py` → `ScanOptions(pattern_base=config_base)`).

---

## 8. Ignore Semantics

### 8.1 Pattern language + `!`

* **Partially compliant:**

  * You already use `PathSpec.from_lines("gitwildmatch", patterns)` for traversal filtering (`grobl/core.py`, `grobl/directory.py`), so “gitwildmatch semantics” are present.
  * Runtime “unignore” is implemented by appending `!pattern` to the ignore list (`grobl/config.py::_append_unignore_patterns`), which is directionally aligned with supporting `!`.

### 8.2 Layering and precedence (additive, last match wins across ordered rule stream)

* **Divergent:**

  * Config layering is not additive: `cfg |= load_toml_config(p)` overwrites keys like `exclude_tree` rather than appending patterns (`grobl/config.py::read_config`).
  * Therefore patterns from defaults and `.grobl.toml` do not form a single additive rule stream as required by the spec.

### 8.3 Directory traversal MUST allow negations to re-include beneath excluded parents

* **Divergent:** Current traversal prunes excluded directories before descending.

  * `filter_items()` skips any path matched by the exclude spec; `traverse_dir()` only recurses into directories that survived filtering (`grobl/directory.py::filter_items`, `grobl/directory.py::traverse_dir`).
  * This means a later `!` rule cannot re-include content under a directory that was excluded at a higher level unless that directory itself is not filtered out at traversal time. The spec requires ensuring negations can re-include even if a parent was excluded.

---

## 9. Ignore Control Flags

* **Divergent:**

  * Spec requires `--no-ignore-defaults` and `--no-ignore-config`.
  * Current CLI has `--ignore-defaults` (inverse name/meaning) and `--no-ignore` (“disable all ignore patterns”) (`grobl/cli/scan.py`).
  * Current implementation of `--no-ignore` sets `exclude_tree` to `[]` after runtime adjustments (`grobl/config.py::apply_runtime_ignores`), which does not match the required semantics.

---

## 10. Deterministic Ordering

* **Divergent:**

  * Spec requires ordering by POSIX-style relative path from repo root using `/` separators and `casefold()`.
  * Current ordering:

    * Traversal sorts within each directory by `x.name` only (`grobl/directory.py::filter_items`), not by full relative path, not case-folded, not repo-root anchored.
    * Builder records entries relative to `base_path=common` (common ancestor) rather than repo root (`grobl/core.py::run_scan` creates `DirectoryTreeBuilder(base_path=common, ...)`).

---

## 11. Output Determinism

### 11.1 JSON output

* **Partially compliant:**

  * JSON emission uses `sort_keys=True, indent=2` (`grobl/services.py::JsonPayloadStrategy.emit`; `grobl/cli/scan.py` for summary JSON).
* **Divergent:**

  * Spec requires a trailing newline. Current JSON emission does **not** append a newline (both payload JSON and summary JSON).

### 11.2 NDJSON output

* **Divergent:** No NDJSON format exists.

---

## 12. Version Reporting

* **Divergent:**

  * Spec requires `-V/--version` to print only `X.Y.Z`.
  * Current `click.version_option(__version__, "-V", "--version")` uses Click’s default message format (typically includes program name and “version”) unless overridden (`grobl/cli/root.py`).
  * There is also a `grobl version` subcommand that prints the raw version string (`grobl/cli/version.py`), but the spec is explicit about `-V/--version`.

---

## 13. Help Behavior

* **Divergent:**

  * Root help currently enumerates scan options directly (`grobl/cli/root.py::_DefaultScanGroup.get_help`), which violates “Root help MUST NOT enumerate subcommand options.”
  * Help is rendered twice in the observed output; the implementation uses `Console(record=True)` and prints to the console while also returning `console.export_text()`, producing duplicate output. This violates “Help output MUST be rendered exactly once per invocation.”

---

## 14. Error Handling

* **Partially compliant:**

  * Usage/config/path errors are generally non-zero exits (`EXIT_USAGE=2`, `EXIT_CONFIG=3`, `EXIT_PATH=4`).
* **Divergent:**

  * Unknown command handling does not match spec due to the fallback-to-scan behavior and permissive Click settings (see §2).

---

## 15. Non-Goals

* No conflicts; current code includes additional behavior not covered by the spec (e.g., completions), which is acceptable because the spec does not prohibit it.

---

# Summary of Compliance vs Divergence (high signal)

## Compliant / mostly aligned

* Uses `gitwildmatch` (`pathspec`) for ignore matching.
* Supports negation patterns in principle (`!` can appear; CLI `--unignore` appends `!`).
* Uses `pyperclip` for clipboard support.
* JSON outputs have stable key ordering and indentation (but not trailing newline).

## Divergent (requires changes to meet spec)

* Default-scan behavior: multiple fallback mechanisms; injection is not “safe”; unknown command does not reliably error.
* Missing `--format`, missing `ndjson`, and old `--payload/--sink` interface remains.
* Payload destination is not “exactly one”; stdout fallback violates the spec.
* Summary routing and separation: summary currently prints to stdout and contaminates payload pipelines.
* Repo root resolution (git root) does not exist; all repo-root-anchored behaviors (hierarchical config, ordering) are absent.
* `.grobl.toml` hierarchy discovery and per-file-directory-relative ignore interpretation are not implemented.
* Additive gitignore layering across `.grobl.toml` + CLI rules is not implemented (current merges overwrite lists).
* Traversal pruning prevents required negation re-inclusion behavior.
* Deterministic ordering is not per spec (name-only sort; not casefold; not repo-root-relative).
* `-V/--version` output format does not match spec.
* Root help violates concision and is printed twice.
