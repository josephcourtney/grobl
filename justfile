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
  uv run pytest --cov=grobl-config ./grobl-config/tests
  uv run pytest --cov=grobl ./grobl/tests 
  uv run pytest --cov=grobl-cli ./grobl-cli/tests
  # uv run pytest --cov=grobl-workspace ./tests

# ---- Build ----
build-all:
  # Build all member packages deterministically.
  for d in {{PKG_DIRS}}; do (cd "$d" && uv build); done

# ---- Clean ----
clean:
  rm -rf **/__pycache__
  rm -rf .pytest_cache .ruff_cache .coverage .coverage.* coverage.xml
  for d in {{PKG_DIRS}}; do rm -rf "$d/.pytest_cache" "$d/.ruff_cache" "$d/.coverage" "$d/.coverage.*" "$d/coverage.xml"; done
  uv cache prune || true
  rm -rf dist build
  for d in {{PKG_DIRS}}; do rm -rf "$d/dist" "$d/build"; done

qa: setup format lint typecheck test

