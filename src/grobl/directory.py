"""Directory traversal helpers and tree rendering utilities."""

from __future__ import annotations

import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

LAST_CONNECTOR = "└── "
BRANCH_CONNECTOR = "├── "
FileIdentity = tuple[int, int]


class TreeCallback(Protocol):
    """Directory traversal callback."""

    def __call__(self, item: Path, prefix: str, *, is_last: bool) -> bool: ...


@dataclass(frozen=True, slots=True)
class SymlinkInfo:
    """Logical symlink plus information about its physical target."""

    target: str
    resolved_target: Path | None
    broken: bool
    external: bool
    target_is_dir: bool
    target_is_file: bool
    identity: FileIdentity | None

    @property
    def scope(self) -> str:
        if self.broken:
            return "unknown"
        return "external" if self.external else "internal"


@dataclass(frozen=True, slots=True)
class TraverseConfig:
    """Configuration controlling directory traversal filtering."""

    paths: list[Path]
    base: Path
    repo_root: Path
    follow_symlinks: bool = False
    allow_external_symlinks: bool = False

    def ordering_key(self, p: Path) -> str:
        """Deterministic ordering: POSIX relpath from repo_root, case-folded."""
        try:
            rel = p.relative_to(self.repo_root)
        except ValueError:
            rel = p
        return rel.as_posix().casefold()


@dataclass(slots=True)
class TreeCollector:
    _tree_output: list[str] = field(default_factory=list)
    _file_tree_entries: list[tuple[int, Path]] = field(default_factory=list)
    _ordered: list[tuple[str, Path]] = field(default_factory=list)
    _symlinks: dict[str, SymlinkInfo] = field(default_factory=dict)

    def add_dir(self, base: Path, directory_path: Path, prefix: str, *, is_last: bool) -> None:
        connector = LAST_CONNECTOR if is_last else BRANCH_CONNECTOR
        self._tree_output.append(f"{prefix}{connector}{directory_path.name}/")
        self._ordered.append(("dir", directory_path.relative_to(base)))

    def add_file(self, base: Path, file_path: Path, prefix: str, *, is_last: bool) -> None:
        connector = LAST_CONNECTOR if is_last else BRANCH_CONNECTOR
        rel = file_path.relative_to(base)
        self._tree_output.append(f"{prefix}{connector}{file_path.name}")
        self._file_tree_entries.append((len(self._tree_output) - 1, rel))
        self._ordered.append(("file", rel))

    def add_symlink(
        self,
        base: Path,
        link_path: Path,
        info: SymlinkInfo,
        prefix: str,
        *,
        is_last: bool,
    ) -> None:
        connector = LAST_CONNECTOR if is_last else BRANCH_CONNECTOR
        marker = " [broken]" if info.broken else " [external]" if info.external else ""
        self._tree_output.append(f"{prefix}{connector}{link_path.name} -> {info.target}{marker}")
        rel = link_path.relative_to(base)
        self._ordered.append(("symlink", rel))
        self._symlinks[str(rel)] = info

    def lines(self) -> list[str]:
        return list(self._tree_output)

    def entries(self) -> list[tuple[int, Path]]:
        return list(self._file_tree_entries)

    def ordered(self) -> list[tuple[str, Path]]:
        return list(self._ordered)

    def symlink_for(self, rel: str | Path) -> SymlinkInfo | None:
        return self._symlinks.get(str(rel))


@dataclass(frozen=True, slots=True)
class FileSummary:
    lines: int
    chars: int
    tokens: int
    included: bool
    content_reason: dict[str, object] | None = None


@dataclass(slots=True)
class FileCollector:
    _metadata: dict[str, FileSummary] = field(default_factory=dict)
    _json_file_blobs: list[dict[str, Any]] = field(default_factory=list)

    def record_metadata(
        self,
        rel: Path,
        lines: int,
        chars: int,
        tokens: int,
        *,
        content_reason: dict[str, object] | None = None,
    ) -> None:
        self._metadata[str(rel)] = FileSummary(lines, chars, tokens, False, content_reason)

    def add_file(self, file_path: Path, rel: Path, lines: int, chars: int, tokens: int, content: str) -> None:
        self._metadata[str(rel)] = FileSummary(lines, chars, tokens, True, None)
        if file_path.suffix == ".md":
            content = content.replace("```", r"\`\`\`")
        self._json_file_blobs.append({
            "name": str(rel),
            "path": str(rel),
            "lines": lines,
            "chars": chars,
            "tokens": tokens,
            "included": True,
            "content": content,
        })

    def metadata_items(self) -> Iterable[tuple[str, FileSummary]]:
        return self._metadata.items()

    def get_metadata(self, key: str) -> FileSummary | None:
        return self._metadata.get(key)

    def files_json(self) -> list[dict[str, Any]]:
        return list(self._json_file_blobs)


@dataclass(frozen=True, slots=True)
class SummaryTotals:
    total_lines: int
    total_characters: int
    total_tokens: int
    all_total_lines: int
    all_total_characters: int
    all_total_tokens: int
    _files: Mapping[str, FileSummary]
    _directories_with_files: frozenset[Path]
    _directories_with_included: frozenset[Path]

    def to_dict(self) -> dict[str, int]:
        return {
            "total_lines": self.total_lines,
            "total_characters": self.total_characters,
            "total_tokens": self.total_tokens,
            "all_total_lines": self.all_total_lines,
            "all_total_characters": self.all_total_characters,
            "all_total_tokens": self.all_total_tokens,
        }

    def iter_files(self) -> Iterable[tuple[str, FileSummary]]:
        return tuple(self._files.items())

    def metadata_items(self) -> Iterable[tuple[str, FileSummary]]:
        return tuple(self._files.items())

    def for_path(self, rel: str | Path) -> FileSummary | None:
        return self._files.get(str(rel))

    def is_included(self, rel: str | Path) -> bool:
        record = self.for_path(rel)
        return False if record is None else record.included

    def marker_for_file(self, rel: Path) -> str:
        return "[INCLUDED:FULL]" if self.is_included(rel) else "[NOT_INCLUDED]"

    def marker_for_directory(self, rel: Path) -> str | None:
        if rel in self._directories_with_files and rel not in self._directories_with_included:
            return "[NOT_INCLUDED]"
        return None


@dataclass(slots=True)
class TotalsTracker:
    total_lines: int = 0
    total_characters: int = 0
    total_tokens: int = 0
    all_total_lines: int = 0
    all_total_characters: int = 0
    all_total_tokens: int = 0

    def record_seen(self, *, lines: int, chars: int, tokens: int) -> None:
        self.all_total_lines += lines
        self.all_total_characters += chars
        self.all_total_tokens += tokens

    def record_included(self, *, lines: int, chars: int, tokens: int) -> None:
        self.total_lines += lines
        self.total_characters += chars
        self.total_tokens += tokens

    def snapshot(self, metadata: Mapping[str, FileSummary]) -> SummaryTotals:
        files = dict(metadata.items())
        directories_with_files: set[Path] = set()
        directories_with_included: set[Path] = set()
        root = Path()
        for path_str, record in files.items():
            parent = Path(path_str).parent
            while parent != root:
                directories_with_files.add(parent)
                if record.included:
                    directories_with_included.add(parent)
                parent = parent.parent
        return SummaryTotals(
            self.total_lines,
            self.total_characters,
            self.total_tokens,
            self.all_total_lines,
            self.all_total_characters,
            self.all_total_tokens,
            files,
            frozenset(directories_with_files),
            frozenset(directories_with_included),
        )


@dataclass(slots=True)
class DirectoryTreeBuilder:
    base_path: Path
    exclude_patterns: list[str]
    tree: TreeCollector = field(default_factory=TreeCollector)
    files: FileCollector = field(default_factory=FileCollector)
    _totals: TotalsTracker = field(default_factory=TotalsTracker)

    def tree_output(self) -> list[str]:
        return self.tree.lines()

    def metadata_items(self) -> Iterable[tuple[str, FileSummary]]:
        return self.files.metadata_items()

    def get_metadata(self, key: str) -> FileSummary | None:
        return self.files.get_metadata(key)

    def file_tree_entries(self) -> list[tuple[int, Path]]:
        return self.tree.entries()

    def ordered_entries(self) -> list[tuple[str, Path]]:
        return self.tree.ordered()

    def symlink_info(self, rel: str | Path) -> SymlinkInfo | None:
        return self.tree.symlink_for(rel)

    def files_json(self) -> list[dict[str, Any]]:
        return self.files.files_json()

    def add_directory(self, directory_path: Path, prefix: str, *, is_last: bool) -> None:
        self.tree.add_dir(self.base_path, directory_path, prefix, is_last=is_last)

    def add_file_to_tree(self, file_path: Path, prefix: str, *, is_last: bool) -> None:
        self.tree.add_file(self.base_path, file_path, prefix, is_last=is_last)

    def add_symlink_to_tree(
        self,
        link_path: Path,
        info: SymlinkInfo,
        prefix: str,
        *,
        is_last: bool,
    ) -> None:
        self.tree.add_symlink(self.base_path, link_path, info, prefix, is_last=is_last)

    def record_metadata(
        self,
        rel: Path,
        lines: int,
        chars: int,
        tokens: int,
        *,
        content_reason: dict[str, object] | None = None,
    ) -> None:
        self.files.record_metadata(rel, lines, chars, tokens, content_reason=content_reason)
        self._totals.record_seen(lines=lines, chars=chars, tokens=tokens)

    def add_file(self, file_path: Path, rel: Path, lines: int, chars: int, tokens: int, content: str) -> None:
        self.files.add_file(file_path, rel, lines, chars, tokens, content)
        self._totals.record_included(lines=lines, chars=chars, tokens=tokens)

    def summary_totals(self) -> SummaryTotals:
        return self._totals.snapshot(dict(self.files.metadata_items()))


def inspect_symlink(path: Path, *, root: Path) -> SymlinkInfo:
    """Inspect ``path`` without losing its logical location."""
    target = path.readlink().as_posix()
    try:
        resolved = path.resolve(strict=True)
        result = path.stat()
    except OSError:
        return SymlinkInfo(target, None, True, False, False, False, None)
    try:
        external = not resolved.is_relative_to(root.resolve(strict=False))
    except OSError:
        external = True
    return SymlinkInfo(
        target,
        resolved,
        False,
        external,
        stat.S_ISDIR(result.st_mode),
        stat.S_ISREG(result.st_mode),
        (result.st_dev, result.st_ino),
    )


def symlink_target_is_selected(info: SymlinkInfo, paths: Iterable[Path]) -> bool:
    target = info.resolved_target
    if target is None:
        return False
    for path in paths:
        if path.is_symlink():
            continue
        try:
            selected = path.resolve(strict=False)
            if target == selected or target.is_relative_to(selected):
                return True
        except OSError:
            continue
    return False


def should_follow_symlink(info: SymlinkInfo, config: TraverseConfig) -> bool:
    if not config.follow_symlinks or info.broken:
        return False
    if info.external and not config.allow_external_symlinks:
        return False
    return not symlink_target_is_selected(info, config.paths)


def filter_items(items: list[Path], config: TraverseConfig) -> list[Path]:
    results = [
        item
        for item in items
        if any(item.is_relative_to(path) or path.is_relative_to(item) for path in config.paths)
    ]
    return sorted(results, key=config.ordering_key)


def _directory_identity(path: Path) -> FileIdentity | None:
    try:
        result = path.stat()
    except OSError:
        return None
    if not stat.S_ISDIR(result.st_mode):
        return None
    return result.st_dev, result.st_ino


def traverse_dir(
    path: Path,
    config: TraverseConfig,
    callback: TreeCallback,
    prefix: str = "",
    *,
    _visited_directories: set[FileIdentity] | None = None,
) -> None:
    """Depth-first traversal applying ``callback`` to each logical item."""
    visited = set() if _visited_directories is None else _visited_directories
    if _visited_directories is None:
        identity = _directory_identity(path)
        if identity is not None:
            visited.add(identity)

    items = filter_items(list(path.iterdir()), config)
    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        if not callback(item, prefix, is_last=is_last):
            continue

        if item.is_symlink():
            info = inspect_symlink(item, root=config.repo_root)
            if not info.target_is_dir or not should_follow_symlink(info, config):
                continue
            identity = info.identity
        elif item.is_dir():
            identity = _directory_identity(item)
        else:
            continue

        if identity is not None:
            if identity in visited:
                continue
            visited.add(identity)
        next_prefix = "    " if is_last else "│   "
        traverse_dir(item, config, callback, prefix + next_prefix, _visited_directories=visited)
