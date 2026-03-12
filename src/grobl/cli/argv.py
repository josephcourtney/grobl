"""Compatibility wrappers for root argv helpers moved to :mod:`grobl.app.root_context`."""

from grobl.app.root_context import build_command_option_map, inject_default_scan, normalize_argv

__all__ = ["build_command_option_map", "inject_default_scan", "normalize_argv"]
