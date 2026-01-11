# grobl CLI Specification

This document defines the normative, observable behavior of the `grobl` command-line interface.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as described in RFC 2119.

---

## 1. Command Structure and Argument Parsing

### 1.1 Commands and Subcommands

* Commands **MUST** consist solely of alphabetic characters (`[A-Za-z]+`).
* Subcommands **MAY** be chained (e.g. `grobl scan foo`), and each segment **MUST** be alphabetic.
* Unknown commands **MUST** result in a usage error, subject to default-scan injection rules (§2).

The CLI **MUST** support at minimum the following commands:

* `scan`
* `explain`

### 1.2 Global Options

The following options are **global** and **MUST** be recognized regardless of position:

* `-h`, `--help`
* `-v`, `--verbose`
* `--log-level`
* `--config`
* All output format flags and output routing flags that are not specific to a particular subcommand’s semantics

Global options **MUST** be recognized before or after the command token.

### 1.3 Option Parsing Model

* Options (global and command-specific) **MAY** appear in any order.
* `--` **MUST** terminate option parsing.
* All tokens following `--` **MUST** be treated as positional arguments, even if they begin with `-`.

### 1.4 Positional Arguments

After command resolution (§2), all remaining non-option tokens **MUST** be interpreted as positional arguments to the resolved command.

For the `scan` command, positional arguments **MUST** be interpreted as scan paths (§3.1).

For the `explain` command, positional arguments **MUST** be interpreted as explain target paths (§7.6).

---

## 2. Default Command and Scan Injection

### 2.1 Default Command

* The default command is `scan`.
* Default command injection **MAY** occur according to §2.2.
* If injection does not occur and no valid command is present, the CLI **MUST** terminate with a usage error indicating an unknown command.

### 2.2 Injectable Tokens

Let *T* be the **first non-option token** after parsing global options (ignoring `--help` for the purpose of command resolution).

*T* is considered injectable if **any** of the following are true after user expansion (§3.3):

* *T* begins with `-`
* *T* resolves to an existing filesystem path (§3.4)

Path-like syntax alone (e.g. `.`, `~`, `/`) **MUST NOT** trigger injection unless the path exists.

### 2.3 Injection Conditions

The CLI **MUST** inject the `scan` command if **any** injectable condition in §2.2 holds for *T*.

### 2.4 Non-Injection Conditions

The CLI **MUST NOT** inject the `scan` command if:

* *T* matches a valid command name, or
* *T* does not begin with `-` and does not resolve to an existing path

In this case, the CLI **MUST** terminate with a usage error indicating an unknown command and **SHOULD** explain why injection did not occur.

### 2.5 Injection Scope

Only *T*, the first non-option token, participates in default-scan injection.
Subsequent tokens **MUST** be treated as positional arguments to the resolved command.

---

## 3. Scan Paths and Repository Root Resolution

### 3.1 Scan Paths

For the `scan` command:

* All positional arguments **MUST** be treated as scan paths.
* If no scan paths are provided, the CLI **MUST** default to the current working directory.

### 3.2 Files vs Directories

* Scan paths **MAY** refer to files or directories.
* For repository root resolution and configuration discovery, file scan paths **MUST** be normalized to their parent directories.
* Files **MUST** still be scanned as explicit targets.

### 3.3 User Path Expansion

User expansion **MUST** include:

* Tilde expansion (`~`)
* Environment variable expansion:

  * POSIX: `$VAR`, `${VAR}`
  * Windows: `%VAR%`

The CLI **MUST NOT** perform wildcard (glob) expansion.

Undefined environment variables **MUST** be left unexpanded.

### 3.4 Existing Filesystem Paths

A token resolves to an existing filesystem path if, after user expansion:

* It refers to a filesystem entry for which `stat`/`lstat` succeeds
* Symlinks **MUST** be treated as existing even if their targets are missing
* Readability or traversal permissions **MUST NOT** affect existence checks

### 3.5 Repository Root Resolution

The repository root **MUST** be resolved using the following precedence:

1. The Git repository root, if the current working directory is inside a Git worktree

   * Git submodules and worktrees **MUST** be treated according to standard Git semantics
2. The common ancestor directory of all scan paths
3. The current working directory

If scan paths reside on different filesystem volumes with no common ancestor, the CLI **MUST** fall back to the current working directory.

---

## 4. Payload Output (scan)

### 4.1 Payload Formats

For the `scan` command, the CLI **MUST** support the following payload formats:

```
llm | markdown | json | ndjson | none
```

The format **MUST** be selected using `--format`.

If `--format none` is specified, no payload **MUST** be emitted.

### 4.2 Payload Destination

Exactly one payload destination **MUST** be selected.

Destination selection rules:

1. If `--copy` is specified, the payload **MUST** be written to the system clipboard.
2. Else if `--output PATH` is specified:

   * If `PATH` is `-`, the payload **MUST** be written to stdout.
   * Otherwise, the payload **MUST** be written to the specified file.
3. Else:

   * If stdout is connected to a TTY, the payload **MUST** be written to the system clipboard.
   * If stdout is not connected to a TTY, the payload **MUST** be written to stdout.

If clipboard output is selected and clipboard access fails, the CLI **MUST** terminate with a usage error explaining the failure and suggesting `--output`.

### 4.3 Mutual Exclusivity

* `--copy` and `--output` **MUST NOT** be used together.
* If both are specified, the CLI **MUST** terminate with a usage error.

---

## 5. Summary Output (scan)

### 5.1 Summary Modes

For the `scan` command, the CLI **MUST** support the following summary modes:

```
auto | none | table | json
```

The mode **MUST** be selected using `--summary`.

### 5.2 Auto Summary Behavior

When `--summary auto` is specified:

* If the CLI determines it is running interactively, the summary mode **MUST** behave as `table`
* Otherwise, the summary mode **MUST** behave as `none`

### 5.3 Summary Style

The CLI **MUST** support the following summary styles:

```
auto | full | compact
```

* `--summary-style` **MUST** be valid **only** when `--summary table` is selected
* Otherwise, the CLI **MUST** terminate with a usage error

### 5.4 Summary Destination

The summary destination **MUST** be selected using `--summary-to`:

```
stderr | stdout | file
```

* If `file` is selected, `--summary-output PATH` **MUST** be provided
* If not specified, the summary destination **MUST** default to `stderr`

### 5.5 Summary JSON Extensibility

When `--summary json` is selected, the CLI **MAY** add new fields over time.
Added fields **MUST NOT** change the meaning of existing fields.

If the summary JSON reports per-path inclusion booleans for either tree visibility or content capture, the implementation **SHOULD** additionally report an exclusion reason object when inclusion is `false`. If present, reason objects **MUST** be stable and machine-readable (§7.5, §7.6).

---

## 6. Output Stream Separation and Compatibility (scan)

### 6.1 Streams and Merge Order

The CLI produces two independent output streams:

* **Payload stream**
* **Summary stream**

If both streams are routed to the same destination, output **MUST** be deterministically concatenated in the following order:

1. Summary stream
2. Payload stream

### 6.2 Merge Compatibility Rules

The CLI **MUST** treat the following as machine-readable formats:

* Payload: `json`, `ndjson`
* Summary: `json`

For any destination:

* If any non-empty stream routed to that destination is machine-readable, **exactly one** non-empty stream **MUST** be routed there
* Otherwise, merging human-readable streams **MAY** occur

Human-readable formats are:

* Payload: `llm`, `markdown`
* Summary: `table`

Invalid merges **MUST** be rejected with a usage error explaining the incompatibility and suggesting:

* Making formats compatible, or
* Routing streams to different destinations

### 6.3 Default Separation

If payload output is written to stdout and no explicit summary destination is specified, summary output **MUST** default to stderr.

---

## 7. Configuration and Include/Exclude Policy

### 7.1 Configuration Files

* Configuration files are named `.grobl.toml`
* `.grobl.toml` files **MUST** be discovered by traversing from the repository root down to each scanned directory

### 7.2 Two Scopes: Tree Visibility vs Content Capture

`grobl` applies include/exclude rules in two distinct scopes:

* **Tree scope**: determines whether a path is visible as part of traversal and (where applicable) in any emitted file-tree representation.
* **Content scope**: determines whether a file’s contents are eligible to be included in the payload.

Normative invariants:

* Content capture for a file **MUST NOT** occur unless that file is included in the tree scope.
* A path **MAY** be included in the tree scope while excluded from the content scope (e.g. “in tree but no contents”).

For directory traversal:

* The ignore engine **MUST** be evaluated in a way that allows negated patterns to re-include descendants even when an ancestor directory matched an exclude pattern (§8).
* If a file is included in the tree scope, all of its ancestor directories **MUST** be considered included for the purpose of representing a coherent path to that file (even if an ancestor directory matched an exclude pattern earlier).

### 7.3 Ignore Policy Flag

The CLI **MUST** support an ignore policy flag:

```
--ignore-policy auto|all|none|defaults|config|cli
```

Semantics (applies independently to both scopes):

* `auto`: defaults + config + CLI rules
* `all`: all include/exclude sources enabled
* `none`: no include/exclude rules from any source
* `defaults`: bundled default rules only
* `config`: rules from `.grobl.toml` only
* `cli`: rules provided via CLI flags only

### 7.3 Tree visibility vs content capture

grobl treats ignore rules through two lenses: tree visibility (which entries appear in the rendered directory tree) and content capture (which files contribute textual contents to payloads). `exclude_tree` controls the former, hiding files and directories from traversal output. `exclude_print` (also accepted as `exclude_content` in configuration) controls the latter, leaving the file visible but omitting its text and metadata payload. These scopes are evaluated independently so that a file can be hidden in the tree while its contents are still captured, or vice versa, depending on layered rules.

Default behavior applies the bundled `exclude_tree` and `exclude_print` lists unless flags or configuration override them. CLI include/exclude flags (§7.5) append to these same scopes, and negated patterns (`!pattern`) can re-include entries even after a prior exclusion.

### 7.4 Rule Sources, Base Directories, and Precedence

Include/exclude rules originate from the following sources:

1. **Defaults** (bundled)
2. **Config** (`.grobl.toml`)
3. **CLI** (flags)

Rules **MUST** be applied sequentially and the **last matching rule wins** within each scope.

Base directory rules:

* Default rules **MUST** be interpreted as relative to the repository root.
* CLI rules **MUST** be interpreted as relative to the repository root.
* Rules loaded from a `.grobl.toml` **MUST** be interpreted as relative to that `.grobl.toml` file’s directory.

Config discovery order:

* For a given scanned path, applicable `.grobl.toml` files are those encountered from the repository root down to the scanned directory.
* When multiple config files apply, their rules **MUST** be applied in root-to-leaf order.

### 7.5 CLI Include/Exclude Flags

The CLI **MUST** support additive include/exclude flags.

#### 7.5.1 Both-scopes flags

The following flags apply to **both** scopes:

* `--exclude PATTERN` (adds an exclude rule)
* `--include PATTERN` (adds an include rule)

`--include PATTERN` **MUST** be interpreted as a negated gitignore-style pattern (`!PATTERN`) in the rule engine.

#### 7.5.2 Scoped flags

The following flags apply to one scope only:

* Tree scope: `--exclude-tree PATTERN`, `--include-tree PATTERN`
* Content scope: `--exclude-content PATTERN`, `--include-content PATTERN`

`--include-<scope> PATTERN` **MUST** be interpreted as a negated gitignore-style pattern (`!PATTERN`) in that scope’s rule engine.

#### 7.5.3 Path convenience flags

The CLI **MAY** support path convenience flags that expand to anchored patterns:

* `--exclude-file PATH`
* `--include-file PATH`

If supported:

* The CLI **MUST** interpret `PATH` after user expansion (§3.3).
* The CLI **MUST** normalize `PATH` to a repository-root-relative, POSIX-style path for matching.
* The generated pattern **MUST** match that exact file path (not “any file with that basename elsewhere”).
* For directories, the generated pattern **MUST** exclude/include the directory subtree.

#### 7.5.4 Ordering of CLI rules

CLI-provided rules **MUST** be applied in left-to-right order as they appear in the command line (argv), independent of option grouping.

### 7.6 Deprecated Legacy Ignore Flags

If the CLI supports legacy flags using “ignore/unignore” terminology (e.g. `--add-ignore`, `--unignore`, `--remove-ignore`, `--ignore-file`), they **MUST** remain functional for compatibility.

Behavioral requirements:

* Legacy flags **MUST** map onto the include/exclude model described in §7.2–§7.5.
* Legacy flags **SHOULD** emit a deprecation warning that points users to the equivalent `--exclude*` / `--include*` flags.
* Deprecation warnings **MUST** be emitted to the summary stream destination (or stderr if no summary destination applies).

This specification does not require a particular removal timeline; if one exists, it **MUST** be documented in release notes.

### 7.7 Config Keys for Two Scopes

`.grobl.toml` **MUST** be able to express rules for each scope.

At minimum, the implementation **MUST** recognize:

* `exclude_tree` (list of patterns)
* `exclude_content` (list of patterns)

Compatibility requirements:

* If a legacy key `exclude_print` exists, it **MUST** be accepted as an alias for `exclude_content`.
* If both `exclude_content` and `exclude_print` are present, `exclude_content` **MUST** take precedence and the CLI **SHOULD** warn.

This specification does not require the presence of “include” lists in configuration; implementations **MAY** add them.

---

## 8. Pattern Semantics

### 8.1 Gitignore Semantics

* Patterns **MUST** follow gitignore semantics.
* Negated rules (`!pattern`) **MUST** re-include paths even if parent paths were previously excluded.
* The CLI **MUST** allow negated rules to re-include paths during traversal.

### 8.2 Deterministic Matching Context

Within a given scope, the matching context for a path **MUST** be:

* The applicable rule list for that path (§7.4), and
* The correct base directory for each rule source (§7.4)

The rule engine **MUST** be deterministic with respect to:

* The normalized path representation used for matching (§9), and
* The sequential “last match wins” rule.

---

## 9. Deterministic Ordering

* All scanned paths **MUST** be ordered deterministically.
* Ordering **MUST** be based on normalized POSIX-style paths.
* Paths **MUST** be normalized to NFC and compared using Unicode casefolding.

---

## 10. Output Determinism

### 10.1 JSON

* Stable key ordering
* Consistent indentation and whitespace
* Trailing newline required

### 10.2 NDJSON

* One record per line
* Stable key ordering
* Trailing newline required

---

## 11. Explain Command

The `explain` command reports *why* paths are included or excluded in each scope.

### 11.1 Invocation

* `grobl explain [PATH ...]` **MUST** accept zero or more paths.
* If no paths are provided, the CLI **MUST** default to the current working directory.

The CLI **MAY** provide an alias flag on `scan`:

* If `grobl scan --explain [PATH ...]` is supported, it **MUST** behave identically to `grobl explain [PATH ...]` and **MUST NOT** emit a scan payload.

### 11.2 Output Format and Routing

By default, `explain` output **MUST** be written to stdout.

`explain` output **MUST** support:

* `--format json` (machine-readable)
* `--format markdown` (human-readable)

If the token `human` is accepted, it **MUST** be treated as an alias for `markdown` for the `explain` command.

If `--format none` is specified for `explain`, the CLI **MUST** terminate with a usage error.

### 11.3 Reported Decisions

For each target path, the explain report **MUST** include at minimum:

* Tree scope decision: included/excluded
* Content scope decision: included/excluded

If content is excluded due to non-text/binary classification (as opposed to pattern matching), the report **SHOULD** indicate that classification outcome. The classification algorithm is implementation-defined but **MUST** be deterministic.

### 11.4 Reason Objects (Provenance)

When a scope decision is “excluded”, the explain output **MUST** be able to report the winning reason.

A reason object (or equivalent human-readable text) **MUST** include:

* The winning pattern text (or a sentinel indicating “non-text/binary”)
* Whether the pattern was negated
* The rule source: `defaults | config | cli`
* The base directory used for interpreting that pattern
* If the source is `config`, the `.grobl.toml` path that contributed the winning rule **SHOULD** be reported

---

## 12. Version Reporting

* `--version` and `-V` **MUST** print only the semantic version string (`X.Y.Z`) and exit successfully
* No additional output **MUST** be emitted

---

## 13. Help and Errors

* Help output **MUST** be rendered exactly once per invocation
* Root help **MUST** be concise
* All usage errors **MUST**:

  * Exit non-zero
  * Explain why the error occurred
  * Suggest resolutions when possible

---

## 14. Non-Goals

This specification does not define:

* Internal implementation details
* Performance characteristics
* UI styling
* Editor or IDE integrations

Only observable CLI behavior is in scope.
