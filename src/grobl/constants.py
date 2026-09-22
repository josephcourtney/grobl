"""Project-wide constants, enums, and small helpers."""

from __future__ import annotations

from enum import StrEnum


class ContentScope(StrEnum):
    """Available content scopes for scan outputs."""

    ALL = "all"
    TREE = "tree"
    FILES = "files"


class InclusionLevel(StrEnum):
    """Effective amount of information exposed for a path."""

    OMIT = "omit"
    TREE_ONLY = "tree_only"
    FULL = "full"


class PayloadFormat(StrEnum):
    """Payload output formats."""

    LLM = "llm"
    MARKDOWN = "markdown"
    JSON = "json"
    NDJSON = "ndjson"
    NONE = "none"


class TableStyle(StrEnum):
    """Valid table styles for summary printing."""

    AUTO = "auto"
    FULL = "full"
    COMPACT = "compact"


class SummaryFormat(StrEnum):
    """Supported summary output formats."""

    AUTO = "auto"
    TABLE = "table"
    JSON = "json"
    NONE = "none"


class SummaryDestination(StrEnum):
    """Summary routing targets."""

    STDERR = "stderr"
    STDOUT = "stdout"
    FILE = "file"


class IgnorePolicy(StrEnum):
    AUTO = "auto"
    ALL = "all"
    NONE = "none"
    DEFAULTS = "defaults"
    CONFIG = "config"
    CLI = "cli"


# Canonical three-state configuration keys.
CONFIG_EXCLUDE = "exclude"
CONFIG_TREE_ONLY = "tree_only"
CONFIG_INCLUDE = "include"

# Legacy compatibility keys. These are accepted as inputs but are not canonical.
CONFIG_EXCLUDE_TREE = "exclude_tree"
CONFIG_EXCLUDE_PRINT = "exclude_print"
CONFIG_EXCLUDE_CONTENT = "exclude_content"

CONFIG_INCLUDE_TREE_TAGS = "include_tree_tags"
CONFIG_INCLUDE_FILE_TAGS = "include_file_tags"
CONFIG_INHERIT_DEFAULTS = "inherit_defaults"

# Exit codes
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFIG = 3
EXIT_PATH = 4
EXIT_IO = 5
EXIT_INTERRUPT = 130
