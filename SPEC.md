# grobl CLI Specification

This document defines the normative, observable behavior of the `grobl` command-line interface.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as described in RFC 2119.

---

## 1. Command Structure and Argument Parsing

### 1.1 Commands and Subcommands

* Commands **MUST** consist solely of alphabetic characters (`[A-Za-z]+`).
* Subcommands **MAY** be chained (e.g. `grobl scan foo`), and each segment **MUST** be alphabetic.
* Unknown commands **MUST** result in a usage error, subject to default-scan injection rules (§2).

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

For the `scan` command, positional arguments **MUST** be interpreted as scan paths (§3.2).

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

## 4. Payload Output

### 4.1 Payload Formats

The CLI **MUST** support the following payload formats:

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

## 5. Summary Output

### 5.1 Summary Modes

The CLI **MUST** support the following summary modes:

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

---

## 6. Output Stream Separation and Compatibility

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

## 7. Configuration and Ignore Policy

### 7.1 Configuration Files

* Configuration files are named `.grobl.toml`
* `.grobl.toml` files **MUST** be discovered by traversing from the repository root down to each scanned directory

### 7.2 Ignore Policy

The CLI **MUST** support an ignore policy flag:

```
--ignore-policy auto|all|none|defaults|config|cli
```

Semantics:

* `auto`: defaults + config + CLI ignore rules
* `all`: all ignore sources enabled
* `none`: no ignore rules from any source
* `defaults`: bundled default ignore rules only
* `config`: ignore rules from `.grobl.toml` only
* `cli`: ignore rules provided via CLI flags only

Ignore rules **MUST** be applied sequentially; the **last matching rule wins**.
Negated rules (`!pattern`) **MUST** re-include paths even if parent paths were previously excluded.

---

## 8. Ignore Semantics

* Ignore patterns **MUST** follow gitignore semantics
* Ignore patterns from `.grobl.toml` **MUST** be interpreted as relative to the file’s directory
* The CLI **MUST** allow negated rules to re-include paths during traversal

---

## 9. Deterministic Ordering

* All scanned paths **MUST** be ordered deterministically
* Ordering **MUST** be based on normalized POSIX-style paths
* Paths **MUST** be normalized to NFC and compared using Unicode casefolding

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

## 11. Version Reporting

* `--version` and `-V` **MUST** print only the semantic version string (`X.Y.Z`) and exit successfully
* No additional output **MUST** be emitted

---

## 12. Help and Errors

* Help output **MUST** be rendered exactly once per invocation
* Root help **MUST** be concise
* All usage errors **MUST**:

  * Exit non-zero
  * Explain why the error occurred
  * Suggest resolutions when possible

---

## 13. Non-Goals

This specification does not define:

* Internal implementation details
* Performance characteristics
* UI styling
* Editor or IDE integrations

Only observable CLI behavior is in scope.

---

If you want, next steps could be:

* A **conformance test matrix** derived directly from this spec
* A **parser-state machine** sketch to validate the option/command resolution
* A **help text contract** that ensures your help output actually enforces the guarantees you’ve now made

