# Plan

This file records the execution strategy for maintaining the design in [DESIGN.md](DESIGN.md). Current progress, gaps, and handoff state belong in [STATUS.md](STATUS.md); immediate tasks belong in [TODO.md](TODO.md).

## Change sequence

Behavioral changes should be implemented in dependency order so compatibility and presentation do not leak into the core model:

1. Define or amend the observable contract in `SPEC.md` and the durable invariant in `DESIGN.md`. Record an ADR when the decision is costly to reverse or likely to need future rationale.
2. Change foundation and policy abstractions first, preserving one canonical internal representation.
3. Update traversal, file handling, rendering, and application orchestration against that representation.
4. Adapt CLI/configuration inputs at the boundary. Legacy syntax should normalize immediately rather than create parallel core behavior.
5. Update user documentation and migration guidance only after the intended behavior is explicit.
6. Validate targeted regressions, then the full repository and release gates.

## Compatibility strategy

Canonical configuration and CLI surfaces are the preferred interfaces. Supported legacy configuration keys and hidden scoped CLI flags remain ingress adapters only. New features must not depend on those legacy shapes.

When a configuration model changes:

- provide an explicit migration path when existing files can be transformed safely;
- reject ambiguous mixed schemas rather than guessing;
- preserve source files by default for destructive migrations;
- surface cases that cannot be proven equivalent as warnings requiring review.

## Validation strategy

Development should use the narrowest relevant tests first, followed by the repository gates:

1. targeted unit/component/system tests for the changed behavior;
2. `just check` for syntax, formatting, lint, typing, import architecture, the full test suite, and coverage reporting;
3. `just release-check` before release to repeat repository validation and build distributions without local source overrides.

Resource isolation is part of test design: pure policy tests should remain SMALL, while tests that intentionally touch the real filesystem should be MEDIUM or larger.

## Release strategy

Version changes use semantic versioning in `pyproject.toml`. The matching release heading must exist in `CHANGELOG.md`, whose entries remain curated for users rather than mirroring commits or TODO history.

Publishing remains a separate explicit operation; validation recipes must not publish as a side effect.
