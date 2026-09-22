"""Resolution of persistent scan behavior from config and CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from click.core import ParameterSource

from grobl.constants import (
    CONFIG_INHERIT_DEFAULTS,
    ContentScope,
    IgnorePolicy,
    PayloadFormat,
    SummaryFormat,
    TableStyle,
)
from grobl.errors import ConfigLoadError
from grobl.resource_limits import ResourceLimits

if TYPE_CHECKING:
    import click


@dataclass(frozen=True, slots=True)
class ScanBehavior:
    """Effective persistent scan settings after config/CLI precedence."""

    scope: str
    payload_format: str
    summary: str
    summary_style: str | None
    show_lines: bool
    show_chars: bool
    show_tokens: bool
    show_inclusion_status: bool
    ignore_policy: str
    inherit_defaults: bool
    limits: ResourceLimits


def _use_config(ctx: click.Context, parameter: str) -> bool:
    return ctx.get_parameter_source(parameter) is ParameterSource.DEFAULT


def _configured_value(
    ctx: click.Context,
    cfg: dict[str, object],
    *,
    parameter: str,
    key: str,
    current: object,
    enabled: bool = True,
) -> object:
    if enabled and _use_config(ctx, parameter) and key in cfg:
        return cfg[key]
    return current


def _choice(value: object, *, key: str, choices: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        msg = f"config key {key!r} must be a string"
        raise ConfigLoadError(msg)
    normalized = value.lower()
    if normalized not in choices:
        expected = "|".join(choices)
        msg = f"invalid config value for {key!r}: {value!r}; expected {expected}"
        raise ConfigLoadError(msg)
    return normalized


def _boolean(value: object, *, key: str) -> bool:
    if not isinstance(value, bool):
        msg = f"config key {key!r} must be true or false"
        raise ConfigLoadError(msg)
    return value


def _resource_limit(
    ctx: click.Context,
    cfg: dict[str, object],
    *,
    parameter: str,
    key: str,
    current: int | None,
) -> int | None:
    value = _configured_value(
        ctx,
        cfg,
        parameter=parameter,
        key=key,
        current=current,
    )
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        msg = f"config key {key!r} must be a non-negative integer"
        raise ConfigLoadError(msg)
    return None if value == 0 else value


def resolve_resource_limits(
    ctx: click.Context,
    cfg: dict[str, object],
    *,
    max_file_bytes: int | None,
    max_total_bytes: int | None,
    max_tokens: int | None,
) -> ResourceLimits:
    """Resolve content budgets from config unless explicitly set on the CLI."""
    return ResourceLimits(
        max_file_bytes=_resource_limit(
            ctx,
            cfg,
            parameter="max_file_bytes",
            key="max_file_bytes",
            current=max_file_bytes,
        ),
        max_total_bytes=_resource_limit(
            ctx,
            cfg,
            parameter="max_total_bytes",
            key="max_total_bytes",
            current=max_total_bytes,
        ),
        max_tokens=_resource_limit(
            ctx,
            cfg,
            parameter="max_tokens",
            key="max_tokens",
            current=max_tokens,
        ),
    )


def config_inherit_defaults(cfg: dict[str, object]) -> bool:
    """Return whether configuration enables the bundled inclusion-policy layer."""
    return _boolean(cfg.get(CONFIG_INHERIT_DEFAULTS, True), key=CONFIG_INHERIT_DEFAULTS)


def resolve_ignore_policy(
    ctx: click.Context,
    cfg: dict[str, object],
    *,
    current: str,
) -> str:
    """Resolve ignore-policy config unless the CLI supplied it explicitly."""
    value = _configured_value(
        ctx,
        cfg,
        parameter="ignore_policy",
        key="ignore_policy",
        current=current,
    )
    return _choice(value, key="ignore_policy", choices=tuple(item.value for item in IgnorePolicy))


def resolve_scan_behavior(
    ctx: click.Context,
    cfg: dict[str, object],
    *,
    scope: str,
    payload_format: str,
    summary: str,
    summary_style: str | None,
    show_lines: bool,
    show_chars: bool,
    show_tokens: bool,
    show_inclusion_status: bool,
    ignore_policy: str,
    max_file_bytes: int | None,
    max_total_bytes: int | None,
    max_tokens: int | None,
    json_mode: bool,
) -> ScanBehavior:
    """Resolve persistent scan settings with explicit CLI values taking precedence."""
    use_config_output = not json_mode

    scope_value = _configured_value(
        ctx,
        cfg,
        parameter="scope",
        key="scope",
        current=scope,
    )
    payload_value = _configured_value(
        ctx,
        cfg,
        parameter="payload_format",
        key="format",
        current=payload_format,
        enabled=use_config_output,
    )
    summary_value = _configured_value(
        ctx,
        cfg,
        parameter="summary",
        key="summary",
        current=summary,
        enabled=use_config_output,
    )

    resolved_summary = _choice(
        summary_value,
        key="summary",
        choices=tuple(item.value for item in SummaryFormat),
    )
    summary_explicit = not _use_config(ctx, "summary")
    use_config_style = use_config_output and not (
        summary_explicit and resolved_summary != SummaryFormat.TABLE.value
    )
    style_value = _configured_value(
        ctx,
        cfg,
        parameter="summary_style",
        key="summary_style",
        current=summary_style,
        enabled=use_config_style,
    )
    if style_value is None:
        resolved_style = None
    else:
        resolved_style = _choice(
            style_value,
            key="summary_style",
            choices=tuple(item.value for item in TableStyle),
        )

    return ScanBehavior(
        scope=_choice(
            scope_value,
            key="scope",
            choices=tuple(item.value for item in ContentScope),
        ),
        payload_format=_choice(
            payload_value,
            key="format",
            choices=tuple(item.value for item in PayloadFormat),
        ),
        summary=resolved_summary,
        summary_style=resolved_style,
        show_lines=_boolean(
            _configured_value(
                ctx,
                cfg,
                parameter="show_lines",
                key="lines",
                current=show_lines,
            ),
            key="lines",
        ),
        show_chars=_boolean(
            _configured_value(
                ctx,
                cfg,
                parameter="show_chars",
                key="characters",
                current=show_chars,
            ),
            key="characters",
        ),
        show_tokens=_boolean(
            _configured_value(
                ctx,
                cfg,
                parameter="show_tokens",
                key="tokens",
                current=show_tokens,
            ),
            key="tokens",
        ),
        show_inclusion_status=_boolean(
            _configured_value(
                ctx,
                cfg,
                parameter="show_inclusion_status",
                key="inclusion_status",
                current=show_inclusion_status,
            ),
            key="inclusion_status",
        ),
        ignore_policy=resolve_ignore_policy(ctx, cfg, current=ignore_policy),
        inherit_defaults=config_inherit_defaults(cfg),
        limits=resolve_resource_limits(
            ctx,
            cfg,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            max_tokens=max_tokens,
        ),
    )
