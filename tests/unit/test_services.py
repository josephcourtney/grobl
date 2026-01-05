from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from grobl import services
from grobl.constants import (
    ContentScope,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.services import ScanExecutor, ScanOptions
from tests.support import build_ignore_matcher

pytestmark = pytest.mark.small

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _write_noop(_: str) -> None:  # pragma: no cover - trivial
    pass


def _base_cfg(tmp_path: Path) -> dict[str, object]:
    ignores = build_ignore_matcher(repo_root=tmp_path, scan_paths=[tmp_path])
    return {"exclude_tree": [], "exclude_print": [], "_ignores": ignores}


def test_execute_emits_json_payload_and_summary(tmp_path):
    sample = tmp_path / "example.txt"
    sample.write_text("hello\n", encoding="utf-8")

    writes: list[str] = []

    def _sink(content: str) -> None:
        writes.append(content)

    executor = ScanExecutor(sink=_sink)
    cfg = _base_cfg(tmp_path)

    human, summary = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=ContentScope.ALL,
            payload_format=PayloadFormat.JSON,
            summary_format=SummaryFormat.JSON,
            summary_style=TableStyle.AUTO,
            repo_root=tmp_path,
        ),
    )

    assert not human
    assert summary["scope"] == ContentScope.ALL.value
    assert summary["style"] == TableStyle.AUTO.value
    assert writes, "expected JSON payload to be written"

    payload = json.loads(writes[0])
    assert payload["scope"] == ContentScope.ALL.value
    assert payload["summary"]["totals"] == summary["totals"]
    assert payload["summary"]["style"] == summary["style"]
    files = payload["summary"]["files"]
    assert any(entry["path"].endswith("example.txt") for entry in files)


def test_execute_skips_payload_when_disabled(tmp_path):
    sample = tmp_path / "solo.txt"
    sample.write_text("hello\n", encoding="utf-8")

    writes: list[str] = []

    executor = ScanExecutor(sink=writes.append)
    cfg = _base_cfg(tmp_path)

    human, summary = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=ContentScope.ALL,
            payload_format=PayloadFormat.NONE,
            summary_format=SummaryFormat.TABLE,
            summary_style=TableStyle.COMPACT,
            repo_root=tmp_path,
        ),
    )

    assert writes == []
    assert human
    assert summary["scope"] == ContentScope.ALL.value
    assert summary["style"] == TableStyle.COMPACT.value


def test_execute_summary_none_returns_minimal_structure(tmp_path):
    sample = tmp_path / "none.txt"
    sample.write_text("hello\n", encoding="utf-8")

    writes: list[str] = []

    executor = ScanExecutor(sink=writes.append)
    cfg = _base_cfg(tmp_path)

    human, summary = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=ContentScope.ALL,
            payload_format=PayloadFormat.NONE,
            summary_format=SummaryFormat.NONE,
            summary_style=TableStyle.AUTO,
            repo_root=tmp_path,
        ),
    )

    assert writes == []
    assert not human
    assert summary["root"] == str(tmp_path)
    assert summary["scope"] == ContentScope.ALL.value
    assert summary["style"] == TableStyle.AUTO.value
    assert summary["files"] == []
    totals = summary["totals"]
    assert totals["total_lines"] == 1
    assert totals["total_characters"] == len("hello\n")


def test_execute_delegates_payload_emission(monkeypatch, tmp_path):
    sample = tmp_path / "strategy.txt"
    sample.write_text("content\n", encoding="utf-8")

    writes: list[str] = []
    calls: list[dict[str, object]] = []

    class _StubStrategy:
        def emit(
            self,
            *,
            builder: object,
            context: object,
            result: object,
            sink: Callable[[str], None],
            logger: object,
            config: dict[str, object],
        ) -> None:
            calls.append({
                "builder": builder,
                "context": context,
                "result": result,
                "sink": sink,
                "logger": logger,
                "config": config,
            })

    stub_strategy = _StubStrategy()
    monkeypatch.setattr(
        services,
        "_PAYLOAD_STRATEGIES",
        {services.PayloadFormat.NONE: stub_strategy},
        raising=True,
    )

    executor = ScanExecutor(sink=writes.append)
    cfg = _base_cfg(tmp_path)

    executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=services.ContentScope.ALL,
            payload_format=services.PayloadFormat.NONE,
            summary_format=services.SummaryFormat.NONE,
            summary_style=services.TableStyle.AUTO,
            repo_root=tmp_path,
        ),
    )

    assert calls, "expected payload strategy to be invoked"
    emitted = calls[0]
    assert emitted["sink"].__self__ is writes
    assert emitted["context"].scope is services.ContentScope.ALL
    assert emitted["config"] is cfg


def test_execute_uses_summary_helper(monkeypatch, tmp_path):
    sample = tmp_path / "helper.txt"
    sample.write_text("line\n", encoding="utf-8")

    writes: list[str] = []
    summary_calls: list[dict[str, object]] = []

    def _build_summary_for_format(*, base_summary, fmt, renderer, builder, options, human_formatter):
        summary_calls.append({
            "base_summary": base_summary,
            "fmt": fmt,
            "renderer": renderer,
            "builder": builder,
            "options": options,
            "human_formatter": human_formatter,
        })
        return "human output", {"marker": True}

    monkeypatch.setattr(
        services,
        "build_summary_for_format",
        _build_summary_for_format,
        raising=True,
    )

    executor = ScanExecutor(sink=writes.append)
    cfg = _base_cfg(tmp_path)

    human, summary = executor.execute(
        paths=[tmp_path],
        cfg=cfg,
        options=ScanOptions(
            scope=services.ContentScope.ALL,
            payload_format=services.PayloadFormat.NONE,
            summary_format=services.SummaryFormat.TABLE,
            summary_style=services.TableStyle.COMPACT,
            repo_root=tmp_path,
        ),
    )

    assert human == "human output"
    assert summary == {"marker": True}
    assert summary_calls, "expected summary helper to be invoked"
