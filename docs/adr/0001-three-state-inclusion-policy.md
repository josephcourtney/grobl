# ADR-001: Use one three-state inclusion policy

- Date: 2026-09-21
- Status: Accepted

## Context

grobl historically modeled hierarchy visibility and content capture as independent exclusion scopes. Fully omitting a path therefore commonly required duplicate rules, and the model admitted a state in which content could be included while the corresponding hierarchy entry was absent. That state was not useful for grobl's context-payload purpose and made configuration, precedence, provenance, and explanation harder to reason about.

The project needed a policy that directly represented the outcomes users actually select while preserving compatibility with existing configuration.

## Decision

Represent every path with exactly one state:

- `full`: hierarchy included; text content eligible for capture.
- `tree_only`: hierarchy included; content not captured.
- `omit`: hierarchy and content omitted.

Canonical configuration uses `exclude`, `tree_only`, and `include`. Canonical CLI controls assign the same states. Rule sources remain layered, and the last matching rule wins within the established source precedence.

Legacy tree/content configuration and scoped CLI controls are accepted only as boundary compatibility inputs and are immediately compiled into the three states. The core does not preserve independent hierarchy/content axes.

Text/binary detection remains downstream: a non-text file can be in `full` state while its bytes are omitted from the payload.

## Consequences

### Positive

- Fully omitted paths require one rule rather than duplicate tree/content exclusions.
- Content capture always implies hierarchy representation.
- Matching, provenance, explain output, and traversal share one decision model.
- Configuration and CLI controls map directly to observable outcomes.
- Legacy inputs can remain supported without retaining legacy architecture.

### Negative

- The former “content without hierarchy” combination is intentionally unrepresentable.
- Translating arbitrary overlapping legacy tree/content globs cannot always be proven exactly equivalent.
- Compatibility adapters and migration warnings remain necessary while legacy syntax is supported.

## Alternatives considered

### Keep independent tree and content booleans

Rejected because it preserves duplicate configuration, permits an unwanted fourth state, and forces downstream code to reconcile two decisions repeatedly.

### Use only include/exclude

Rejected because hierarchy-only entries are useful for repository structure, legal files, assets, and documentation whose contents should not consume context.

### Preserve four states but hide one from the CLI

Rejected because an unsupported internal state would still complicate invariants, provenance, traversal, and compatibility without a user requirement that justifies it.
