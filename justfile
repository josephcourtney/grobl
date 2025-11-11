# Global shell
set shell := ["bash", "-euo", "pipefail", "-O", "globstar", "-c"]

# Load .env if present (kept out of VCS)
set dotenv-load := true

# Show fewer internals in `just --list`
set allow-duplicate-recipes := false

# Defaults / Help
[private]
default: help

# Human-friendly task list
help:
  @just --list --unsorted --list-prefix "  "

# Echo effective configuration (useful for debugging CI/parity)
env:
  @echo "PYTHON_PACKAGE={{PYTHON_PACKAGE}}"
  @echo "PY_TESTPATH={{PY_TESTPATH}}"
  @echo "PY_SRC={{PY_SRC}}"
  @echo "UV={{UV}}"
  @echo "RUFF={{RUFF}}"
  @echo "PYTEST={{PYTEST}}"
  @echo "TYPES={{TYPES}}"
  @echo "SHOWCOV={{SHOWCOV}}"

# Config (overridable via env/.env)
export PYTHON_PACKAGE := env("PYTHON_PACKAGE", "grobl")
export PY_TESTPATH    := env(
  "PY_TESTPATH",
  "tests grobl-config/tests grobl-cli/tests grobl/tests",
)
export PY_SRC         := env("PY_SRC", "src")
export VERBOSE        := env("VERBOSE", "0")

# Tool wrappers
UV      := "uv"
RUFF    := "uv run ruff"
PYTEST  := "uv run pytest"
TYPES   := "uv run ty"
SHOWCOV := "uv run showcov"

# Plumbing (private)
[private]
guard-force:
  @: "${FORCE?Set FORCE=1 to run this destructive task}"

[private]
verbosity:
  @if [ "{{VERBOSE}}" = "1" ]; then set -x; fi

[private]
check-tools:
  @command -v {{UV}} >/dev/null      || { echo "[check-tools] missing: uv" >&2; exit 1; }
  @command -v {{RUFF}} >/dev/null 2>&1 || true
  @command -v {{PYTEST}} >/dev/null 2>&1 || true
  @command -v {{SHOWCOV}} >/dev/null 2>&1 || true

# Bootstrap: set up venv and update versions
setup: check-tools
  {{UV}} sync --dev

# Bootstrap: setu up venv obeying lockfile
setup-frozen: check-tools
  {{UV}} sync --frozen --no-dev

# Format
format *ARGS:
  @{{RUFF}} format {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}} || true

# Check formatting
format-no-fix *ARGS:
  @{{RUFF}} format --check {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}}

# Lint
lint *ARGS:
  @{{RUFF}} check {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}} || true

# Check lint rule compliance
lint-no-fix *ARGS:
  @{{RUFF}} check --no-fix {{PY_SRC}} {{PY_TESTPATH}} {{ARGS}}

# Typecheck
typecheck *ARGS:
  @{{TYPES}} check {{ARGS}} || true

# Test
test *ARGS:
  @{{PYTEST}} || true

# Show coverage summary
cov-summary *ARGS:
  @{{SHOWCOV}} --sections summary --format human {{ARGS}} || true

# List uncovered lines
cov *ARGS:
  @{{SHOWCOV}} --code --context 2,2 {{ARGS}} || true

# Build
build *ARGS:
  @{{UV}} build {{ARGS}}

# Build source distribution
sdist:
  @{{UV}} build --sdist

# Build wheel
wheel:
  @{{UV}} build --wheel

# Clean temporary files and caches
clean:
  @rm -rf **/__pycache__
  @rm -rf .ruff_cache .pytest_cache .mypy_cache .pytype
  @rm -rf .coverage .coverage.* coverage.xml htmlcov
  @rm -rf dist build
  @{{UV}} cache prune || true

[private]
stash-untracked:
  @set -euo pipefail
  @ts="$(date -u +%Y%m%dT%H%M%SZ)"; \
   msg="scour:untracked:$ts"; \
   paths="$(git ls-files -z --others --exclude-standard)"; \
   if [ -n "$paths" ]; then \
     printf '%s' "$paths" \
       | xargs -0 git stash push -m "$msg" -u -- >/dev/null; \
     echo "Stashed untracked (non-ignored) files as: $msg"; \
   else \
     echo "No untracked (non-ignored) paths to stash."; \
   fi

# Remove all files and directories that are ignored by git, except .venv
scour: clean stash-untracked
  @git clean -ffd

# Pipelines
# Validate rule compliance but make no changes
check: setup-frozen lint-no-fix typecheck format-no-fix test

# Fix all auto-fixable linting and formatting errors, check types, and run tests
fix: setup lint format typecheck test

