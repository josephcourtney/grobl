from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from grobl.logging_utils import (
    StructuredLogEvent,
    get_logger,
    log_event,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_serialise_and_mask(tmp_path: Path) -> None:
    # use a fixture-backed path (avoid S108)
    p = tmp_path / "file.txt"
    p.write_text("x", encoding="utf-8")

    # build roles as a set to exercise serialisation; narrow type for sorting
    roles_set = {"user", "admin"}
    ctx: dict[str, object] = {
        "path": p,
        "roles": roles_set,
        "meta": {"a": 1, "b": p},
    }
    # add secret-looking keys via variables to keep linter quiet; still validate masking
    secret_key = "token"  # noqa: S105
    password_key = "password"  # noqa: S105
    ctx[secret_key] = "shh"
    ctx[password_key] = "p"

    event = StructuredLogEvent(name="x", message="m", context=ctx)
    sc = event.sanitised_context()

    # path -> posix string
    assert isinstance(sc["path"], str)
    assert str(sc["path"]).endswith("file.txt")

    # sets become sorted lists
    assert isinstance(sc["roles"], list)
    roles = cast("list[str]", sc["roles"])
    assert sorted(roles) == ["admin", "user"]

    # token/password masked
    assert sc["token"] == "***"  # noqa: S105
    assert sc["password"] == "***"  # noqa: S105

    # nested mapping converted; path inside mapping serialised to string
    assert isinstance(sc["meta"], dict)
    meta = sc["meta"]
    assert meta["a"] == 1
    assert isinstance(meta["b"], str)


def test_log_event_adds_extra_fields(caplog: pytest.LogCaptureFixture) -> None:
    logger = get_logger("grobl.tests.logging")
    with caplog.at_level(logging.INFO):
        log_event(logger, StructuredLogEvent(name="evt", message="hello", context={"k": "v"}))

    rec = caplog.records[-1]
    # Access extra attributes defensively to satisfy static typing
    event = getattr(rec, "event", None)
    ctx: Any = getattr(rec, "context", None)
    assert event == "evt"
    assert isinstance(ctx, dict)
    assert ctx["k"] == "v"
