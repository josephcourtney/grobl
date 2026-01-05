This document provides a section-by-section assessment of the **current grobl codebase**
against **SPEC.md**.

**Definitions**

- **Compliant**: Behavior is implemented as specified, or is a strict subset that does not
  violate any MUST / MUST NOT requirement.
- **Partially compliant**: Core behavior exists but differs in defaults, ordering,
  anchoring, or edge cases.
- **Divergent**: Required behavior is missing or produces observably different results.

---

## 1. Command Structure

### 1.1 Commands

**Compliant**

- All top-level command names (`scan`, `init`, `version`, `completions`) are lowercase,
  alphabetic, and explicitly registered.

### 1.2 Default Command and Unknown Commands

**Compliant**

- Path-like bare arguments invoke the default `scan` command.
- Unknown non-path-like bare tokens now error rather than silently routing to `scan`.
- Multiple fallback mechanisms and permissive Click settings have been removed.
- Behavior is covered by regression tests.

---

## 2. Default-Scan Injection Rules

### 2.1 Path-Like Tokens

**Compliant**

- Tokens containing `. ~ / \` are treated as path-like and trigger default-scan injection.

### 2.2 Injection / Non-Injection Conditions

**Compliant**

- Injection only occurs when all spec conditions are met.
- Filesystem existence is validated before injection.
- Invalid invocations error with usage diagnostics instead of deferring to scan-time errors.

---

## 3. Repository Root Resolution

**Partially compliant**

- Git-root detection is implemented and used as the primary anchor when available.
- Fallback to common ancestor or CWD is supported when not in a git repository.
- Repo-root anchoring is used for traversal bases and some ordering logic.

**Remaining gaps**

- Repo-root anchoring is not yet applied uniformly across:
  - hierarchical config discovery,
  - ignore pattern interpretation,
  - deterministic ordering in all payloads.

---

## 4. Payload Output

### 4.1 Payload Formats

**Compliant**

- `--format` exposes `llm`, `markdown`, `json`, `ndjson`, and `none`.
- Each format has a dedicated emission strategy.

### 4.2 Payload Destination

**Compliant**

- Payloads are routed to exactly one destination:
  - clipboard (default),
  - file path,
  - stdout (`--output -`).
- `--copy` and `--output` are mutually exclusive and validated early.

### 4.3 Stream Separation

**Compliant**

- Payload and summary streams are fully separated.
- Summaries default to stderr unless explicitly redirected.
- Regression tests cover all routing combinations.

---

## 5. Summary Output

### 5.1 Summary Modes

**Compliant**

- `--summary {auto,table,json,none}` is fully supported.
- `auto` resolves based on TTY detection.

### 5.2 Summary Style

**Compliant**

- `--summary-style {auto,full,compact}` is supported.
- Style flags are gated to `--summary table`.

### 5.3 Summary Destination

**Compliant**

- `--summary-to {stderr,stdout,file}` and `--summary-output` behave as specified.
- Invalid combinations error early.

---

## 6. Output Determinism

### 6.1 JSON Output

**Partially compliant**

- JSON payloads and summaries use stable key ordering and indentation.
- **Missing**: required trailing newline for JSON outputs.

### 6.2 NDJSON Output

**Partially compliant**

- NDJSON format exists and emits one object per record.
- **Remaining gaps**:
  - trailing newline guarantees,
  - explicit stability guarantees for record ordering.

---

## 7. Configuration and Ignore Discovery

### 7.1 Hierarchical `.grobl.toml` Discovery

**Divergent**

- Configuration loading is not hierarchical.
- Only a single config base is selected rather than accumulating from repo root
  down to the scan directory.
- Legacy and auxiliary config sources are merged, but not in the spec-required manner.

### 7.2 Relative Interpretation of Ignore Patterns

**Divergent**

- Ignore patterns are interpreted relative to a single config base.
- Patterns are **not** interpreted relative to the directory containing each
  `.grobl.toml` file.

---

## 8. Ignore Semantics

### 8.1 Pattern Language and Negation

**Partially compliant**

- Gitignore-style matching is implemented via `pathspec` (`gitwildmatch`).
- Negation patterns (`!`) are supported syntactically.

### 8.2 Layering and Precedence

**Divergent**

- Ignore lists are overwritten during config merges instead of appended.
- Bundled defaults, config-derived rules, and CLI rules do not form a single
  ordered rule stream.
- Last-match-wins semantics across layers are not guaranteed.

### 8.3 Traversal and Negation Re-Inclusion

**Divergent**

- Traversal prunes directories matched by exclude rules.
- This prevents later negation rules from re-including descendants as required.

---

## 9. Ignore Control Flags

**Divergent**

- Spec-required flags are missing:
  - `--no-ignore-defaults`
  - `--no-ignore-config`
- Existing flags (`--ignore-defaults`, `--no-ignore`) do not map cleanly to spec semantics.

---

## 10. Deterministic Ordering

**Divergent**

- Ordering is currently:
  - per-directory,
  - name-based,
  - case-sensitive,
  - anchored to traversal base rather than repo root.
- Spec requires global ordering by repo-root-relative POSIX path using `casefold()`.

---

## 11. Version Reporting

**Compliant**

- `-V / --version` emits only the semantic version string.
- `grobl version` subcommand remains available.
- Behavior is covered by regression tests.

---

## 12. Help Behavior

**Compliant**

- Root help does not enumerate subcommand options.
- Help output is rendered exactly once per invocation.
- Users are directed to `grobl scan --help` for scan options.

---

## 13. Error Handling

**Compliant**

- Usage, configuration, path, and interrupt errors exit with distinct non-zero codes.
- Unknown commands error correctly.
- Errors surface at the appropriate parsing or validation phase.

---

## 14. Non-Goals

**Compliant**

- Additional features not mentioned in SPEC.md (e.g., shell completions)
  are present but do not conflict with required behavior.

---

# High-Level Summary

### Fully compliant areas
- CLI command structure and injection rules
- Payload formats, destinations, and stream separation
- Summary modes, styles, and routing
- Version and help behavior
- Error handling discipline

### Remaining spec gaps
- Hierarchical config discovery
- Additive, layered ignore semantics
- Negation-safe traversal
- Repo-root-anchored deterministic ordering
- Trailing newline guarantees for JSON / NDJSON

These gaps are tracked explicitly in `TODO.md`.

