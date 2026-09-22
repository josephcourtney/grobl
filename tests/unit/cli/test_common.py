from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import grobl.app.command_support as command_support
from grobl.constants import (
    EXIT_INTERRUPT,
    EXIT_PATH,
    EXIT_USAGE,
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.directory import DirectoryTreeBuilder
from grobl.errors import PathNotFoundError
from tests.support import build_ignore_matcher

pytestmark = pytest.mark.medium

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


# --------------------------- print_interrupt_diagnostics ----------------------


def test_print_interrupt_diagnostics_prints_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    command_support.print_interrupt_diagnostics(
        tmp_path,
        {"exclude": [], "tree_only": [], "include": []},
        builder,
    )

    out = capsys.readouterr().out
    assert "Interrupted by user. Dumping debug info:" in out
    assert f"cwd: {tmp_path}" in out
    assert "exclude:" in out
    assert "tree_only:" in out
    assert "include:" in out
    assert "DirectoryTreeBuilder(" in out


# ---------------------------- execute_scan_with_handling --------------------------
class _DummyExecOK:
    def __init__(self, *, sink: object) -> None:
        self.sink = sink

    def execute(self, *, paths: list[Path], cfg: dict[str, Any], options: object) -> tuple[str, dict]:
        # basic sanity: got paths and cfg
        assert isinstance(paths, list)
        assert isinstance(cfg, dict)
        return "human", {"ok": 1}


class _DummyExecRaises:
    def __init__(self, *, sink: object) -> None:
        self.exc: BaseException | None = None

    def execute(self, *, paths: list[Path], cfg: dict[str, Any], options: object) -> tuple[str, dict]:
        assert paths or cfg or options is not None  # touch args
        assert self.exc is not None
        raise self.exc


def _params_for(tmp_path: Path) -> command_support.ScanParams:
    return command_support.ScanParams(
        scope=ContentScope.ALL,
        summary_style=TableStyle.COMPACT,
        config_path=None,
        payload=PayloadFormat.LLM,
        summary=SummaryFormat.TABLE,
        payload_copy=True,
        payload_output=None,
        paths=(tmp_path,),
        repo_root=tmp_path,
    )


def _cfg_with_ignores(tmp_path: Path) -> dict[str, object]:
    return {
        "exclude_tree": [],
        "exclude_print": [],
        "_ignores": build_ignore_matcher(repo_root=tmp_path, scan_paths=[tmp_path]),
    }


def test_execute_scan_with_handling_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(command_support, "ScanExecutor", _DummyExecOK)
    writes: list[str] = []
    human, js = command_support.execute_scan_with_handling(
        params=_params_for(tmp_path),
        cfg=_cfg_with_ignores(tmp_path),
        cwd=tmp_path,
        write_fn=writes.append,
        summary_style=TableStyle.COMPACT,
    )
    assert human == "human"
    assert js == {"ok": 1}


@pytest.mark.parametrize(
    ("exc", "expected_code"),
    [
        (PathNotFoundError("No common ancestor"), EXIT_PATH),
        (ValueError("bad"), EXIT_USAGE),
        (KeyboardInterrupt(), EXIT_INTERRUPT),
    ],
)
def test_execute_scan_with_handling_exception_exit_code_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exc: BaseException, expected_code: int
) -> None:
    dummy = _DummyExecRaises(sink=None)
    dummy.exc = exc
    monkeypatch.setattr(command_support, "ScanExecutor", lambda *, sink: dummy)  # type: ignore[misc]
    # Avoid making these tests depend on exact diagnostics formatting/contents.
    monkeypatch.setattr(command_support, "print_interrupt_diagnostics", lambda *_: None)

    with pytest.raises(SystemExit) as excinfo:
        command_support.execute_scan_with_handling(
            params=_params_for(tmp_path),
            cfg=_cfg_with_ignores(tmp_path),
            cwd=tmp_path,
            write_fn=lambda _: None,
            summary_style=TableStyle.COMPACT,
        )
    e = excinfo.value
    assert isinstance(e, SystemExit)
    assert e.code == expected_code
