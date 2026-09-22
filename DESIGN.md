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
- Performance guarantees beyond avoiding unnecessary work for omitted or hierarchy-only files.
- Independent hierarchy/content states beyond the three-state inclusion model.

## Architectural structure

The package is layered, and the dependency direction is enforced by `import-linter.toml`.

1. **CLI layer — `grobl.cli`**
   - Defines Click commands, options, help text, and argument normalization.
   - Delegates behavior to the application layer rather than owning scan policy or rendering logic.

2. **Application/configuration layer — `grobl.app`, `grobl.config*`, `grobl.services`**
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

## Compatibility and migration policy

Legacy `exclude_tree`, `exclude_print`, and `exclude_content` inputs remain supported because existing repositories may depend on them. They are compatibility syntax only; they do not define separate internal axes.

`grobl config migrate` is the supported path from legacy-only configuration to canonical `exclude`/`tree_only`/`include` configuration. Mixed legacy/canonical policy sources are rejected rather than interpreted ambiguously. Migration preserves the original by default and warns when overlapping legacy globs cannot be proven equivalent.

Canonical configuration maintenance distinguishes two pruning guarantees. Default pruning is structural and future-safe: it removes only same-source rules that are provably shadowed by an identical later matcher. Repository-state pruning is explicit: it considers only exact inherited same-base duplicates and removes a candidate after counterfactual matching proves that the currently traversable tree keeps the same effective states. Unique dormant rules are never removed merely for having no current matches.

## Scan pipeline

A scan proceeds conceptually through stable boundaries:

- resolve paths and repository root
- assemble the layered inclusion policy
- traverse deterministically while honoring possible reinclusion
- classify visible files by inclusion state
- perform text detection and content reads only for `full` files
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

Expected user errors are translated into stable CLI usage/config/path exits rather than uncaught tracebacks. Broken stdout pipes are treated as successful pipeline termination. Internal programming errors are not silently converted into user-facing success.

## Quality requirements

- `import-linter` contracts enforce the architectural dependency direction.
- Tests use strict resource-isolation categories: SMALL tests are hermetic; tests requiring real filesystem access are MEDIUM or larger.
- The canonical validation gate is `just check`; release validation is `just release-check`.
- Version reporting derives from installed package metadata and must remain consistent with `pyproject.toml` and the changelog.
