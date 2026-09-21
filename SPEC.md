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

When `--summary json` is selected, each file entry with `included=false` **MUST** include a `content_reason` object describing the winning rule for that scope. The reason object **MUST** contain the keys `pattern`, `negated`, `source`, `base_dir`, `config_path`, and `detail`, with `base_dir` and `config_path` rendered as strings (or `null` if unavailable). Binary exclusions derived from non-text detection **MUST** use the sentinel `pattern` `<non-text>` and `source` `text-detection`, and `detail` should summarize the detection outcome. Summary JSON **MUST** remain deterministic: sort file entries consistently (e.g., lexicographically by path), ensure nested dictionaries use stable key ordering (such as `json.dumps(..., sort_keys=True)`), and include a trailing newline.

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

## 7. Configuration and Inclusion Policy

### 7.1 Configuration files

* Project policy files are named `.grobl.toml`.
* Applicable `.grobl.toml` files **MUST** be discovered from the repository root toward each scanned path.
* Rules from a configuration file **MUST** be interpreted relative to the directory containing that file.

### 7.2 Three inclusion states

Every path **MUST** resolve to exactly one policy state:

* `full`: the path is visible in the hierarchy and, for text files, its contents are eligible for capture.
* `tree_only`: the path is visible in the hierarchy but its file contents are not captured.
* `omit`: the path is absent from the hierarchy and its contents are not captured.

Normative invariants:

* Content capture **MUST NOT** occur for `tree_only` or `omit` paths.
* A path whose contents are captured **MUST** be represented in the hierarchy.
* The policy engine **MUST NOT** represent an independent state equivalent to "content included, hierarchy omitted".
* Unmatched paths **MUST** default to `full`.

Text/binary detection is downstream of policy. A `full` file may still omit contents because deterministic text detection classifies it as non-text; this does not change its policy state.

### 7.3 Canonical configuration keys

Canonical `.grobl.toml` policy uses:

* `exclude`: patterns assigning `omit`.
* `tree_only`: patterns assigning `tree_only`.
* `include`: patterns assigning `full`.

Within one canonical configuration source, these shorthand groups **MUST** be normalized in the following order:

```text
exclude < tree_only < include
```

If several normalized rules match a path, the last matching rule wins. Therefore a matching `include` rule in the same source supersedes matching `tree_only` and `exclude` rules.

### 7.4 Rule sources and precedence

Policy layers **MUST** be evaluated from lowest to highest precedence:

1. bundled defaults
2. discovered `.grobl.toml` files in root-to-leaf order
3. an explicit `--config` file
4. CLI runtime rules

A later layer supersedes an earlier layer when both contain matching rules. Within each normalized layer, the last matching rule wins.

Base directories:

* bundled defaults: repository root
* each discovered config: directory containing that config
* explicit config: directory containing that config
* CLI rules: repository root

### 7.5 Rule-source selection

The CLI **MUST** support:

```text
--ignore-policy auto|all|none|defaults|config|cli
```

Semantics:

* `auto`: defaults + discovered/explicit config + CLI
* `all`: all rule sources
* `none`: no policy rules; unmatched `full` therefore applies everywhere
* `defaults`: bundled defaults only
* `config`: configuration rules only
* `cli`: CLI rules only

The existing `--no-ignore`, `--ignore-defaults`, and `--no-ignore-config` convenience controls **MAY** remain as aliases for selecting sources.

### 7.6 CLI state assignment

The canonical runtime flags are:

* `--exclude PATTERN`: assign `omit`.
* `--tree-only PATTERN`: assign `tree_only`.
* `--include PATTERN`: assign `full`.
* `--exclude-file PATH`, `--tree-only-file PATH`, and `--include-file PATH`: path-targeted equivalents.

CLI shorthand groups **MUST** normalize in the same state order as canonical TOML:

```text
exclude < tree_only < include
```

Thus option type, rather than argv interleaving, defines precedence among canonical state groups. Within a group, patterns retain their supplied order and the last matching pattern wins.

Path-target flags **MUST** normalize the path to a repository-root-relative POSIX pattern. A directory target **MUST** cover its subtree.

### 7.7 Compatibility with the former two-scope model

Implementations **MUST** continue to accept the following legacy configuration keys for compatibility:

* `exclude_tree` -> `omit`
* `exclude_print` -> `tree_only`
* `exclude_content` -> `tree_only`

When a legacy source excludes the same path from both tree and content, `omit` **MUST** win.

The former scoped CLI flags MAY remain accepted as hidden compatibility aliases and **MUST** compile into the three valid states. Compatibility inputs **MUST NOT** reintroduce independent tree/content decisions internally.

When any canonical policy key (`exclude`, `tree_only`, or `include`) is present in a configuration source, that source **SHOULD** be interpreted as canonical rather than combining both models.

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

The `explain` command reports the effective inclusion state and its provenance.

### 11.1 Invocation

* `grobl explain [PATH ...]` **MUST** accept zero or more paths.
* If no paths are provided, the command **MUST** default to the current working directory.
* Explain output **MUST NOT** emit a scan payload.

### 11.2 Output format and routing

Explain output **MUST** default to stdout and support `json` and `markdown`; `human` MAY be accepted as an alias for `markdown`.

JSON output **MUST** be deterministic, sorted by absolute path, serialized with stable key ordering, and terminated by a newline.

### 11.3 Reported decision

For each target, explain output **MUST** report:

* `state`: `full`, `tree_only`, or `omit`.
* the winning policy reason when a rule matched.
* compatibility tree/content projections showing the consequences of that state.
* text-detection information when a `full` file is omitted from content because it is non-text.

The compatibility projections **MUST** obey:

```text
state       tree included   content eligible
full        true            true
tree_only   true            false
omit        false           false
```

### 11.4 Provenance

A winning policy reason **MUST** include:

* pattern
* resulting state
* rule source
* base directory
* config path when applicable
* whether the source pattern used negation

Binary-detection reasons **MUST** remain distinguishable from policy reasons and use the sentinel pattern `<non-text>` with source `text-detection`.

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
