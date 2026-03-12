"""Shared metadata visibility settings for scan output surfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetadataVisibility:
    """Control which optional metadata fields are rendered in scan outputs."""

    lines: bool = True
    chars: bool = True
    tokens: bool = True
    inclusion_status: bool = True

    def shows_any_counts(self) -> bool:
        """Return whether any aggregate count fields are enabled."""
        return self.lines or self.chars or self.tokens

    def shows_any_tree_metadata(self) -> bool:
        """Return whether tree summaries should render metadata columns."""
        return self.shows_any_counts() or self.inclusion_status


DEFAULT_METADATA_VISIBILITY = MetadataVisibility()
