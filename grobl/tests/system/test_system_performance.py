from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pytest
from grobl.core import run_scan

if TYPE_CHECKING:
    from pathlib import Path

# Mark performance tests and set skip condition for CI
skip_in_ci = pytest.mark.skipif(
    os.environ.get("CI", "").lower() == "true" and os.environ.get("GROBL_RUN_PERF") != "1",
    reason="skip performance tests in CI; set GROBL_RUN_PERF=1 to enable",
)
pytestmark = [pytest.mark.perf, skip_in_ci]


def test_scan_performance_smoke(tmp_path: Path) -> None:
    # Build a moderate synthetic tree: ~300 small files in nested dirs
    root = tmp_path / "perf"
    for d in range(10):
        sub = root / f"d{d}"
        sub.mkdir(parents=True, exist_ok=True)
        for f in range(30):
            (sub / f"f{f}.txt").write_text("hello world\n" * 2, encoding="utf-8")

    cfg = {"exclude_tree": [], "exclude_print": []}

    t0 = time.perf_counter()
    res = run_scan(paths=[root], cfg=cfg)
    dt = time.perf_counter() - t0

    # Logical checks (deterministic)
    assert res.builder.total_lines >= 600  # 2 lines per file
    # Optional time check: enable by setting GROBL_CHECK_TIME=1
    if os.environ.get("GROBL_CHECK_TIME") == "1":
        budget = float(os.environ.get("GROBL_PERF_BUDGET_SEC", "3.0"))
        assert dt < budget
