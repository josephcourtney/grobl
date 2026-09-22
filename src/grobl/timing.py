"""Lightweight phase timing used by the opt-in CLI debug report."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(slots=True)
class TimingRecorder:
    """Accumulate wall-clock durations while preserving first-seen order."""

    _started_at: float = field(default_factory=perf_counter)
    _durations: dict[tuple[int, str], float] = field(default_factory=dict)
    _order: list[tuple[int, str]] = field(default_factory=list)

    @contextmanager
    def measure(self, label: str, *, depth: int = 0) -> Iterator[None]:
        """Measure one phase, accumulating repeated measurements by label."""
        key = (depth, label)
        if key not in self._durations:
            self._durations[key] = 0.0
            self._order.append(key)
        started = perf_counter()
        try:
            yield
        finally:
            self._durations[key] += perf_counter() - started

    def report(self) -> str:
        """Render a compact human-readable timing report."""
        total = perf_counter() - self._started_at
        labels = [f"{'  ' * depth}{label}" for depth, label in self._order]
        width = max((len(label) for label in labels), default=0)
        lines = ["Grobl timings:"]
        for (depth, label), display in zip(self._order, labels, strict=True):
            seconds = self._durations[(depth, label)]
            lines.append(f"  {display:<{width}}  {seconds:8.3f} s")
        lines.append(f"  {'total':<{width}}  {total:8.3f} s")
        return "\n".join(lines)


@contextmanager
def measure_timing(
    recorder: TimingRecorder | None,
    label: str,
    *,
    depth: int = 0,
) -> Iterator[None]:
    """Measure a phase when a recorder is active; otherwise do nothing."""
    if recorder is None:
        yield
        return
    with recorder.measure(label, depth=depth):
        yield
