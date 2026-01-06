# grobl CLI Specification

This document defines the normative behavior of the `grobl` command-line interface.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are to be interpreted as described in RFC 2119.

---

## 1. Command Structure

### 1.1 Commands

* Commands **MUST** consist solely of alphabetic characters (`[A-Za-z]+`).
* Subcommands **MAY** be chained (e.g. `grobl scan foo`), and each segment **MUST** be alphabetic.
* Any token that is not a valid command **MUST** be treated according to the default-scan rules (§2).

### 1.2 Default Command

* The default command is `scan`.
* When no explicit command is provided, the CLI **MAY** inject `scan` according to §2.
* If default command injection does not occur, the CLI **MUST** error with an “unknown command” usage error.

---

## 2. Default-Scan Injection Rules

### 2.1 Path-Like Tokens

A token **MUST** be treated as path-like if it contains **any** of the following characters:

```
.  ~  /  \
```

### 2.2 Injection Conditions

Let *T* be the first non-global token after global options.

The CLI **MUST** inject the `scan` command if **any** of the following are true:

1. *T* begins with `-`
2. *T* is path-like (§2.1)
3. *T* resolves to an existing filesystem path after user expansion

### 2.3 Non-Injection Conditions

The CLI **MUST NOT** inject the `scan` command if:

* *T* matches a valid command name
* *T* is not path-like and does not resolve to an existing path

In this case, the CLI **MUST** terminate with a usage error indicating an unknown command.

---

## 3. Repository Root Resolution

The repository root **MUST** be resolved using the following precedence:

1. Git repository root, if the current working directory is inside a Git worktree
2. The common ancestor of all provided scan paths
3. The current working directory

The resolved repository root **MUST** be used as:

* The base for hierarchical configuration discovery (§7)
* The base for deterministic path ordering (§10)

---

## 4. Payload Output

### 4.1 Payload Formats

The CLI **MUST** support the following machine-readable payload formats:

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
3. Else, the payload **MUST** be written to the system clipboard.

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

* If stdout is a TTY, the summary mode **MUST** behave as `table`
* Otherwise, the summary mode **MUST** behave as `none`

### 5.3 Summary Style

The CLI **MUST** support the following summary styles:

```
auto | full | compact
```

* `--summary-style` **MUST** be valid **only** when `--summary table` is selected.
* If `--summary-style` is provided with any other summary mode, the CLI **MUST** terminate with a usage error.

### 5.4 Summary Destination

The summary **MUST** be routed using `--summary-to`:

```
stderr | stdout | file
```

* If `file` is selected, `--summary-output PATH` **MUST** be provided.
* If not specified, the default summary destination **MUST** be `stderr`.

---

## 6. Output Stream Separation

* Payload output and summary output **MUST** be independently routable.
* Summary output **MUST NOT** contaminate payload output unless explicitly routed to the same destination.
* When payload is written to stdout, summary output **SHOULD** default to stderr.

---

## 7. Configuration and Ignore Discovery

### 7.1 Configuration Files

* Configuration files are named `.grobl.toml`.
* `.grobl.toml` files **MUST** be discovered by traversing from the repository root down to each scanned directory.

### 7.2 Relative Interpretation

* Ignore patterns defined in a `.grobl.toml` file **MUST** be interpreted as relative to the directory containing that file.

---

## 8. Ignore Semantics

### 8.1 Pattern Language

* Ignore patterns **MUST** follow gitignore semantics.
* The `!` prefix **MUST** be supported to negate earlier ignore rules.

### 8.2 Layering and Precedence

Ignore rules **MUST** be applied in the following order:

1. Bundled default ignore rules
2. Ignore rules from `.grobl.toml` files, ordered from repository root to deepest directory
3. Ignore rules provided via CLI flags

Rules **MUST** be evaluated sequentially.

* The **last matching rule wins**.
* A negated rule (`!pattern`) **MUST** re-include paths excluded by earlier rules.

### 8.3 Directory Traversal

* The CLI **MUST** ensure that negated rules can re-include paths even if a parent path was previously excluded.

---

## 9. Ignore Control Flags

* The CLI **MUST** support:

  * `--no-ignore-defaults`
  * `--no-ignore-config`
* `--no-ignore-defaults` **MUST** disable bundled default ignore rules.
* `--no-ignore-config` **MUST** disable ignore rules from all `.grobl.toml` files.
* CLI-provided ignore rules **MUST** still apply unless explicitly disabled.

---

## 10. Deterministic Ordering

* All scanned paths **MUST** be ordered deterministically.
* Ordering **MUST** be based on POSIX-style relative paths from the repository root.
* Path separators **MUST** be normalized to `/`.
* Comparisons **MUST** use case-folded ordering.

---

## 11. Output Determinism

### 11.1 JSON Output

* JSON output **MUST** have stable key ordering.
* JSON output **MUST** use consistent indentation and whitespace.
* A trailing newline **MUST** be present.

### 11.2 NDJSON Output

* Each record **MUST** occupy exactly one line.
* Key ordering **MUST** be stable.
* A trailing newline **MUST** be present.

---

## 12. Version Reporting

* `--version` and `-V` **MUST** print only the semantic version string (`X.Y.Z`) and exit successfully.
* No additional text **MUST** be emitted.

---

## 13. Help Behavior

* Root help output **MUST** be concise.
* Help output **MUST** be rendered exactly once per invocation.

---

## 14. Error Handling

* Usage errors **MUST** terminate with a non-zero exit code.
* Unknown commands **MUST** result in a usage error.
* Invalid flag combinations **MUST** result in a usage error.

---

## 15. Non-Goals

This specification does not define:

* Internal implementation structure
* Performance guarantees
* User interface styling
* Editor, IDE, or shell integration behavior

Only observable CLI behavior is in scope.
