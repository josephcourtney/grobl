set shell := ["bash", "-euo", "pipefail", "-c"]

# ---- Workspace layout (monorepo) ----
# All paths are POSIX-style and deterministic.
PKG_DIRS := "grobl grobl-cli grobl-config"
SRC_DIRS := "src grobl/src grobl-cli/src grobl-config/src"
TEST_DIRS := "tests grobl/tests grobl-cli/tests grobl-config/tests"

# ---- Tooling ----
check-tools:
  @command -v uv >/dev/null || { echo "[check-tools] missing: uv" >&2; exit 1; }

setup:
  uv sync

# ---- Format ----
format:
  uv run ruff format {{SRC_DIRS}} {{TEST_DIRS}}

format-check:
  uv run ruff format --check {{SRC_DIRS}} {{TEST_DIRS}}

# ---- Lint ----
lint:
  uv run ruff check {{SRC_DIRS}} {{TEST_DIRS}}

# ---- Typecheck ----
typecheck:
  uv run ty check

# ---- Test ----
test:
  uv run pytest

# ---- Clean ----
clean:
  rm -rf **/__pycache__
  rm -rf ./**/.pytest_cache ./**/.ruff_cache ./**/.coverage ./**/.coverage.* ./**/coverage.xml
  uv cache prune || true
  rm -rf ./**/dist ./**/build

coverage-report:
  uv run python scripts/report_coverage.py

qa: setup format lint typecheck test

