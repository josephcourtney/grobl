"""Project-wide constants, enums, and small helpers."""

from __future__ import annotations

from enum import StrEnum


class OutputMode(StrEnum):
    """Valid output modes for scanning."""

    ALL = "all"
    TREE = "tree"
    FILES = "files"
    SUMMARY = "summary"


class TableStyle(StrEnum):
    """Valid table styles for summary printing."""

    AUTO = "auto"
    FULL = "full"
    COMPACT = "compact"
    NONE = "none"


# "Common heavy directories that can cause very large scans when default ignores are disabled."
HEAVY_DIRS: set[str] = {"node_modules", "venv", ".venv", "env", "site-packages"}

# Add these constants:
CONFIG_EXCLUDE_TREE = "exclude_tree"
CONFIG_EXCLUDE_PRINT = "exclude_print"
CONFIG_INCLUDE_TREE_TAGS = "include_tree_tags"
CONFIG_INCLUDE_FILE_TAGS = "include_file_tags"

DEFAULT_TREE_TAG = "directory"
DEFAULT_FILE_TAG = "file"
