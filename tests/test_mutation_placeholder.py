from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("GROBL_RUN_MUT", "0") != "1",
    reason="mutation tests are opt-in; set GROBL_RUN_MUT=1 to enable",
)


def test_mutation_placeholder() -> None:
    # Placeholder test to signal an opt-in mutation suite location.
    # Real mutation testing should be run via a dedicated tool (e.g., mutmut) outside pytest.
    assert True
