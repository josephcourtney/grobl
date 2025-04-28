from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DirectoryTreeBuilder:
    base_path: Path
    exclude_patterns: list[str]
    tree_output: list[str] = field(default_factory=list)
    all_metadata: dict[str, tuple[int, int]] = field(default_factory=dict)
    included_metadata: dict[str, tuple[int, int]] = field(default_factory=dict)
    file_contents: list[str] = field(default_factory=list)
    total_lines: int = 0
    total_characters: int = 0
    file_tree_entries: list[tuple[int, Path]] = field(default_factory=list)

    def add_directory(self, directory_path: Path, prefix: str, *, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        self.tree_output.append(f"{prefix}{connector}{directory_path.name}")

    def add_file_to_tree(self, file_path: Path, prefix: str, *, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        rel = file_path.relative_to(self.base_path)
        self.tree_output.append(f"{prefix}{connector}{file_path.name}")
        self.file_tree_entries.append((len(self.tree_output) - 1, rel))

    def record_metadata(self, rel: Path, lines: int, chars: int) -> None:
        self.all_metadata[str(rel)] = (lines, chars)

    def add_file(self, file_path: Path, rel: Path, lines: int, chars: int, content: str) -> None:
        self.included_metadata[str(rel)] = (lines, chars)
        if file_path.suffix == ".md":
            content = content.replace("```", r"\`\`\`")
        self.file_contents.extend([
            f'<file:content name="{rel}" lines="{lines}" chars="{chars}">',
            content,
            "</file:content>",
        ])
        self.total_lines += lines
        self.total_characters += chars

    def build_tree(self, *, include_metadata: bool = False) -> list[str]:
        if not include_metadata:
            return [self.base_path.name, *self.tree_output]

        name_width = max(len(line) for line in self.tree_output)
        max_line_digits = max((len(str(v[0])) for v in self.all_metadata.values()), default=1)
        max_char_digits = max((len(str(v[1])) for v in self.all_metadata.values()), default=1)

        header = f"{'':{name_width - 1}}{'lines':>{max_line_digits}} {'chars':>{max_char_digits}}"
        output = [header, self.base_path.name]
        entry_map = dict(self.file_tree_entries)

        for idx, text in enumerate(self.tree_output):
            if idx in entry_map:
                rel = entry_map[idx]
                ln, ch = self.all_metadata.get(str(rel), (0, 0))
                marker = " " if str(rel) in self.included_metadata else "*"
                line = f"{text:<{name_width}} {ln:>{max_line_digits}} {ch:>{max_char_digits}} {marker:>2}"
                output.append(line)
            else:
                output.append(text)

        return output

    def build_file_contents(self) -> str:
        return "\n".join(self.file_contents)


def filter_items(items: list[Path], paths: list[Path], patterns: list[str], base: Path) -> list[Path]:
    results: list[Path] = []
    for item in items:
        if not any(item.is_relative_to(p) for p in paths):
            continue
        if any(item.relative_to(base).match(pat) for pat in patterns):
            continue
        results.append(item)
    return sorted(results, key=lambda x: x.name)


def traverse_dir(
    path: Path, config: tuple[list[Path], list[str], Path], callback: Callable, prefix: str = ""
) -> None:
    paths, patterns, base = config
    items = filter_items(list(path.iterdir()), paths, patterns, base)
    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        callback(item, prefix, is_last=is_last)
        if item.is_dir():
            next_prefix = "    " if is_last else "│   "
            traverse_dir(item, config, callback, prefix + next_prefix)
