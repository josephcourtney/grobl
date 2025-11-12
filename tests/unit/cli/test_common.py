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
    PayloadSink,
    SummaryFormat,
    TableStyle,
)
from grobl.directory import DirectoryTreeBuilder
from grobl.errors import PathNotFoundError, ScanInterrupted

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
        ignore_defaults=False,
        output=None,
        add_ignore=(),
        remove_ignore=(),
        add_ignore_file=(),
        no_ignore=False,
        scope=ContentScope.ALL,
        summary_style=TableStyle.COMPACT,
        config_path=None,
        payload=PayloadFormat.LLM,
        summary=SummaryFormat.HUMAN,
        sink=PayloadSink.AUTO,
        paths=(tmp_path,),
    )


def test__execute_with_handling_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ccommon, "ScanExecutor", _DummyExecOK)
    writes: list[str] = []
    human, js = ccommon._execute_with_handling(
        params=_params_for(tmp_path),
        cfg={},
        cwd=tmp_path,
        write_fn=writes.append,
        summary_style=TableStyle.COMPACT,
    )
    assert human == "human"
    assert js == {"ok": 1}


def test__execute_with_handling_path_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy = _DummyExecRaises(sink=None)
    dummy.exc = PathNotFoundError("No common ancestor")
    monkeypatch.setattr(ccommon, "ScanExecutor", lambda *, sink: dummy)  # type: ignore[misc]
    with pytest.raises(SystemExit) as excinfo:
        ccommon._execute_with_handling(
            params=_params_for(tmp_path),
            cfg={},
            cwd=tmp_path,
            write_fn=lambda _: None,
            summary_style=TableStyle.COMPACT,
        )
    e = excinfo.value
    assert isinstance(e, SystemExit)
    assert e.code == EXIT_PATH


def test__execute_with_handling_usage_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy = _DummyExecRaises(sink=None)
    dummy.exc = ValueError("bad")
    monkeypatch.setattr(ccommon, "ScanExecutor", lambda *, sink: dummy)  # type: ignore[misc]
    with pytest.raises(SystemExit) as exc:
        ccommon._execute_with_handling(
            params=_params_for(tmp_path),
            cfg={},
            cwd=tmp_path,
            write_fn=lambda _: None,
            summary_style=TableStyle.COMPACT,
        )
    e = exc.value
    assert isinstance(e, SystemExit)
    assert e.code == EXIT_USAGE


def test__execute_with_handling_scan_interrupted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Make the executor raise ScanInterrupted and ensure we turn it into EXIT_INTERRUPT via diagnostics.
    builder = DirectoryTreeBuilder(base_path=tmp_path, exclude_patterns=[])
    interrupted = ScanInterrupted(builder, tmp_path)
    dummy = _DummyExecRaises(sink=None)
    dummy.exc = interrupted
    monkeypatch.setattr(ccommon, "ScanExecutor", lambda *, sink: dummy)  # type: ignore[misc]
    # Avoid printing by replacing diagnostics with a minimal stub that raises the expected SystemExit.
    monkeypatch.setattr(
        ccommon, "print_interrupt_diagnostics", lambda *_: (_ for _ in ()).throw(SystemExit(EXIT_INTERRUPT))
    )  # type: ignore[assignment]
    with pytest.raises(SystemExit) as exc:
        ccommon._execute_with_handling(
            params=_params_for(tmp_path),
            cfg={"exclude_tree": []},
            cwd=tmp_path,
            write_fn=lambda _: None,
            summary_style=TableStyle.FULL,
        )
    e = exc.value
    assert isinstance(e, SystemExit)
    assert e.code == EXIT_INTERRUPT


def test__execute_with_handling_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy = _DummyExecRaises(sink=None)
    dummy.exc = KeyboardInterrupt()
    monkeypatch.setattr(ccommon, "ScanExecutor", lambda *, sink: dummy)  # type: ignore[misc]
    monkeypatch.setattr(
        ccommon, "print_interrupt_diagnostics", lambda *_: (_ for _ in ()).throw(SystemExit(EXIT_INTERRUPT))
    )  # type: ignore[assignment]
    with pytest.raises(SystemExit) as exc:
        ccommon._execute_with_handling(
            params=_params_for(tmp_path),
            cfg={"exclude_tree": []},
            cwd=tmp_path,
            write_fn=lambda _: None,
            summary_style=TableStyle.FULL,
        )
    e = exc.value
    assert isinstance(e, SystemExit)
    assert e.code == EXIT_INTERRUPT
