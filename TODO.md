# Testing and Quality Tasks

- [ ] fix typing in tests: annotate `monkeypatch` as `pytest.MonkeyPatch` (or remove the annotation) and update imports in tests using `monkeypatch` so `.venv/bin/ty check src/ tests/` passes
- [ ] suppress ruff security lints with `# noqa: S405,S314` and a brief comment explaining the trust boundary (or add a per-file ignore for these codes)
- [ ] refactor `tests/test_cli_features.py::test_interrupt_diagnostics_exit_code` to use `pytest.raises(SystemExit)` instead of a try/except with manual assertion (PT017)
- [ ] simplify truthy string checks in `tests/test_readme_smoke.py` per `PLC1901` (use `assert v.output.strip()` and similar)
- [ ] make `tests/test_error_paths.py::test_path_error_no_real_common_ancestor` platform-aware (avoid hard-coded `"/"` and `"/tmp"` or mark it to skip on non-POSIX) to improve portability

- [ ] raise branch coverage to ≥ 70%: add targeted tests in `src/grobl/cli.py` to exercise option branches (table modes `auto/compact/full`, clipboard gating for TTY/non-TTY, additional error exits and help/usage paths)
- [ ] add tests for `src/grobl/formatter.py` (`format_table`) covering grouped headers, empty labels, multi-level headers, and column width adjustments to improve line/branch coverage
- [ ] add tests for `src/grobl/utils.py` edge cases (e.g., odd ancestor relationships, single-path inputs, symlinks handling where relevant) to cover remaining branches
- [ ] add small tests for `src/grobl/errors.py` to ensure error-to-exit-code behavior is exercised

- [ ] harden performance testing: keep the opt-in marker, but reduce reliance on strict wall-clock budgets; validate logical work (file counts/line totals) and allow budgets to be controlled via env (`GROBL_PERF_BUDGET_SEC`) with generous defaults; document these env vars in README
- [ ] evaluate adopting `pytest-benchmark` (opt-in dev dependency) for more deterministic perf baselines without slowing PR runs

- [ ] introduce mutation testing (e.g., `mutmut` or `mutatest`) as an optional nightly job to validate assertion quality; start with a small subset of modules
- [ ] evaluate adding property-based tests (e.g., via `hypothesis`) for utilities like `find_common_ancestor` to strengthen edge-case coverage (opt-in dev dependency)

- [ ] enforce quality gates in CI: run `.venv/bin/ruff check`, `.venv/bin/ty check`, and `.venv/bin/pytest` on PRs; fail the job on violations
- [ ] add coverage thresholds to CI (e.g., fail if line coverage < 82% and track/improve branch coverage toward ≥ 70%); if branch threshold isn’t supported natively, parse `.coverage.xml` in a CI step and enforce target
- [ ] address existing ruff findings in `src/`: reduce `read_config` complexity in `src/grobl/config.py` (C901), reduce locals in `src/grobl/renderers.py` (PLR0914), fix import order issues in `src/grobl/tty.py` (E402), and narrow broad exception handling (BLE001)
- [ ] keep security hygiene: add dependency vulnerability scanning in CI (e.g., `pip-audit` or equivalent) and add a secret scan step; document how to run these locally

# Future

- [ ] when adding default config file, format it nicely (one list item per row, etc.)
- [ ] add `--format json` for machine-readable summary output (define and document a stable schema)
- [ ] make json printout pretty
- [ ] consider JSON formats for `tree`/`files` modes (investigate feasibility and size/streaming considerations)
- [ ] document JSON summary schema and provide examples in README
- [ ] add tests for JSON summary schema (structure, keys, determinism)
- [ ] add summary information about binary files. include relevant details about particular file types like images (resolution, color space, file size, etc.)
- [ ] add tests for binary summary details when implemented
