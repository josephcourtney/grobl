# Design

grobl turns a set of filesystem paths into deterministic, prompt-ready context while making every inclusion decision explainable. This file is the canonical record of the intended architecture and the properties that implementation changes must preserve. Observable CLI behavior is specified separately in [SPEC.md](SPEC.md).

## Goals

- Produce compact LLM, Markdown, JSON, and NDJSON representations of repository content.
- Keep path selection deterministic and explainable.
- Separate inclusion policy from text/binary detection and from output formatting.
- Keep payload and summary routing independent so machine-readable output is composable in shell workflows.
- Preserve a narrow CLI layer over reusable application and core logic.
- Retain explicit compatibility paths for supported legacy configuration without carrying the legacy model into the core.

## Non-goals

- A graphical user interface or editor integration.
- A general-purpose backup, synchronization, or archival system.
- Automatic interpretation of binary file contents.
- Exact prediction of downstream model context capacity; Grobl enforces its own configurable content budgets instead.
- Independent hierarchy/content states beyond the three-state inclusion model.

## Architectural structure

The package is layered, and the dependency direction is enforced by `import-linter.toml`.

1. **CLI layer — `grobl.cli`**
   - Defines Click commands, options, help text, and argument normalization.
   - Delegates behavior to the application layer rather than owning scan policy or rendering logic.

2. **Application/configuration layer — `grobl.app`, `grobl.config_*`, migration/pruning modules**
   - Orchestrates scan and explain workflows.
   - Resolves configuration, repository roots, output routing, and compatibility inputs.
   - Translates user-facing inputs into core policy and execution objects.

3. **Core/rendering layer — `grobl.core`, renderers, summaries, formatting, output**
   - Executes scans against an already-resolved inclusion policy.
   - Builds deterministic payload and summary representations.
   - Keeps presentation concerns separate from traversal and matching.

4. **Traversal/policy infrastructure — directory, file handling, inclusion matching, provenance, utilities**
   - Resolves layered rules to one inclusion state per path.
   - Traverses only as far as needed to honor possible descendant restoration.
   - Performs text detection and file reading only when the resolved state allows content capture.

5. **Foundation — constants, errors, version access, resources**
   - Supplies stable shared definitions without depending upward.

Core/infrastructure modules must not depend on the application or CLI layers. Application modules must not depend on CLI modules. CLI subcommands share helpers rather than importing one another.

## Inclusion model

Every path resolves to exactly one `InclusionLevel`:

| State | Hierarchy | Content eligible |
| --- | --- | --- |
| `full` | included | yes |
| `tree_only` | included | no |
| `omit` | excluded | no |

The following are invariants:

- Unmatched paths are `full`.
- Content capture implies hierarchy inclusion.
- `tree_only` and `omit` paths are never read for content.
- The core has no state equivalent to “content included while hierarchy omitted”.
- Traversing through an `omit` directory solely to reach a possible restoration does not reset unmatched descendants to `full`; the omitted ancestor remains effective until a later matching rule restores or changes the state.
- Text/binary detection is downstream of policy. A non-text `full` file remains `full` even when its bytes are not emitted.
- A winning rule retains provenance sufficient to explain its pattern, resulting state, source, base directory, configuration origin, and negation.

The rationale for this model is recorded in [ADR-001](docs/adr/0001-three-state-inclusion-policy.md).

## Rule layering and normalization

Canonical policy inputs are `exclude` → `omit`, `tree_only` → `tree_only`, and `include` → `full`. Within a source they normalize in that order, and the last matching rule wins.

Sources are evaluated from lowest to highest precedence:

1. bundled defaults
2. discovered `.grobl.toml` files from repository root toward the target
3. explicit `--config`
4. CLI runtime rules

Each source retains its own matching base. Compatibility inputs are normalized at the boundary into these same states before the core sees them.

## Configuration ownership and persistent behavior

Bundled policy is implementation-owned data, not project-owned boilerplate. `grobl init` therefore creates a small commented project-delta file instead of copying the bundled policy. A project config records only choices that differ from or intentionally document package behavior.

`inherit_defaults` controls only installation of the bundled inclusion-policy layer. Under automatic source selection, `false` starts policy composition with project/config layers; it does not erase payload, summary, metadata, tag, or other program defaults. Explicit CLI source-selection remains the final authority.

Stable scan-wide behavior can be persisted using config keys corresponding to `scope`, payload `format`, summary mode/style, metadata visibility, `ignore_policy`, and content resource limits. Explicit CLI values override those settings. Routing/actions remain invocation-owned so a repository cannot unexpectedly force clipboard writes, output paths, JSON convenience mode, logging, explicit config selection, or interactivity.

Inclusion policy remains hierarchical because each policy source has a path-relative matching base. Scan-wide scalar behavior is resolved through the general config merge rather than varying by nested path; one scan invocation has one payload format, scope, summary mode, and metadata-visibility policy even when it spans multiple subtrees.

## Compatibility and migration policy

Legacy `exclude_tree`, `exclude_print`, and `exclude_content` inputs remain supported because existing repositories may depend on them. They are compatibility syntax only; they do not define separate internal axes.

`grobl config migrate` is the deterministic explicit path from legacy-only configuration to canonical `exclude`/`tree_only`/`include` configuration. Mixed legacy/canonical policy sources are rejected rather than interpreted ambiguously. Migration preserves the original by default and warns when overlapping legacy globs cannot be proven equivalent.

Scan and explain never modify configuration. When they encounter legacy schema they emit a warning and continue through the compatibility parser. Migration and pruning are explicit maintenance operations performed only by `grobl config migrate` and `grobl config prune`.

Canonical configuration maintenance distinguishes tree-independent structural pruning from repository-state pruning. Structural pruning removes same-source rules shadowed by identical later matchers, semantically empty canonical policy keys, and non-policy settings that simply repeat their effective inherited value; formatting cleanup removes comment-only policy subsections left empty by those edits. Repository-state pruning is explicit: it considers only exact inherited same-base policy duplicates and removes a candidate after counterfactual matching proves that the currently traversable tree keeps the same effective states. Unique dormant rules are never removed merely for having no current matches.

## Scan pipeline

A scan proceeds conceptually through stable boundaries:

- resolve paths and repository root
- assemble the layered inclusion policy
- traverse deterministically while honoring possible reinclusion
- classify visible files by inclusion state
- preflight `full` files against per-file and aggregate byte budgets before reading
- perform streaming text detection and content reads only for budget-eligible `full` files
- enforce aggregate token budget before admitting content to the payload
- build metadata, tree, payload, and summary representations
- route payload and summary streams independently

These are architectural stages, not a requirement that each stage map to one function or module.

## Output model

Payload and summary are independent streams.

- Payload formats may be human-oriented or machine-readable.
- Summary formats may be human-oriented or machine-readable.
- If both streams share a destination, merging is allowed only when the selected formats are compatible.
- Machine-readable JSON/NDJSON output is deterministic, uses stable ordering, and ends with a newline.
- Path ordering is based on normalized POSIX-style representations with the normalization rules defined in SPEC.md.

## Error handling

Expected user errors are translated into stable CLI usage/config/path/I/O exits rather than uncaught tracebacks. Broken stdout pipes are treated as successful pipeline termination. Internal programming errors are not silently converted into user-facing success.

## Quality requirements

- `import-linter` contracts enforce the architectural dependency direction.
- Tests use strict resource-isolation categories: SMALL tests are hermetic; tests requiring real filesystem access are MEDIUM or larger.
- The canonical validation gate is `just check`; release validation is `just release-check`.
- Version reporting derives from installed package metadata and must remain consistent with `pyproject.toml` and the changelog.

## Sensitive-file policy

The bundled inclusion policy conservatively omits common credential-bearing filenames, environment-file variants, and private-key patterns. These are path-based safeguards rather than a claim of content-level secret detection; explicit higher-precedence include rules remain available when the user intentionally wants such a file in context.
