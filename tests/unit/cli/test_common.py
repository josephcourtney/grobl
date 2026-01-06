from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import grobl.cli.common as ccommon
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

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from typing import Any


# ------------------ iter_legacy_references / _scan_for_legacy -----------------
def test_iter_and_scan_legacy_references(tmp_path: Path) -> None:
    # Create files that do and don't contain the legacy name
    (tmp_path / "README.md").write_text("see .grobl.config.toml here", encoding="utf-8")
    (tmp_path / "note.txt").write_text("nothing to see", encoding="utf-8")
    hits = list(ccommon.iter_legacy_references(tmp_path))
    assert hits, "expected at least one legacy reference"
    # _scan_for_legacy_references returns the same results as a list
    scanned = ccommon._scan_for_legacy_references(tmp_path)
    assert scanned == hits
    # Spot check tuple structure: (Path, line_number, text)
    p, ln, text = hits[0]
    assert isinstance(p, Path)
    assert isinstance(ln, int)
    assert ".grobl.config.toml" in text


# --------------------------- print_interrupt_diagnostics ----------------------


def test_print_interrupt_diagnostics_prints_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    ccommon.print_interrupt_diagnostics(tmp_path, {"exclude_tree": []}, builder)

    out = capsys.readouterr().out
    assert "Interrupted by user. Dumping debug info:" in out
    assert f"cwd: {tmp_path}" in out
    assert "exclude_tree:" in out
    assert "DirectoryTreeBuilder(" in out


# ---------------------------- _execute_with_handling --------------------------
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


def _params_for(tmp_path: Path) -> ccommon.ScanParams:
    return ccommon.ScanParams(
        output=None,
        add_ignore=(),
        remove_ignore=(),
        unignore=(),
        add_ignore_file=(),
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


def test__execute_with_handling_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ccommon, "ScanExecutor", _DummyExecOK)
    writes: list[str] = []
    human, js = ccommon._execute_with_handling(
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
def test__execute_with_handling_exception_exit_code_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exc: BaseException, expected_code: int
) -> None:
    dummy = _DummyExecRaises(sink=None)
    dummy.exc = exc
    monkeypatch.setattr(ccommon, "ScanExecutor", lambda *, sink: dummy)  # type: ignore[misc]
    # Avoid making these tests depend on exact diagnostics formatting/contents.
    monkeypatch.setattr(ccommon, "print_interrupt_diagnostics", lambda *_: None)

    with pytest.raises(SystemExit) as excinfo:
        ccommon._execute_with_handling(
            params=_params_for(tmp_path),
            cfg=_cfg_with_ignores(tmp_path),
            cwd=tmp_path,
            write_fn=lambda _: None,
            summary_style=TableStyle.COMPACT,
        )
    e = excinfo.value
    assert isinstance(e, SystemExit)
    assert e.code == expected_code
