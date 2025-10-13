"""Utilities for structured logging with sanitized context payloads."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

type LogValue = str | int | float | bool | list[LogValue] | dict[str, LogValue] | None


def _serialise_value(value: object) -> LogValue:
    """Convert ``value`` into a JSON/log-friendly representation."""
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, set):
        return sorted(_serialise_value(v) for v in value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_serialise_value(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _serialise_value(v) for k, v in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _mask_if_secret(key: str, value: object) -> LogValue:
    """Return ``value`` unless ``key`` appears to reference a secret."""
    lowered = key.lower()
    if any(token in lowered for token in ("secret", "token", "password", "key")):
        return "***"
    return _serialise_value(value)


@dataclass(frozen=True, slots=True)
class StructuredLogEvent:
    """Represents a structured log event for downstream handlers."""

    name: str
    message: str
    context: dict[str, object] = field(default_factory=dict)
    level: int = logging.INFO

    def sanitised_context(self) -> dict[str, LogValue]:
        """Return a sanitized copy safe for logging."""
        return {str(k): _mask_if_secret(str(k), v) for k, v in self.context.items()}


def get_logger(name: str) -> logging.Logger:
    """Return the configured logger for ``name``."""
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: StructuredLogEvent) -> None:
    """Emit ``event`` to ``logger`` with structured metadata."""
    logger.log(event.level, event.message, extra={"event": event.name, "context": event.sanitised_context()})


__all__ = ["StructuredLogEvent", "get_logger", "log_event"]
