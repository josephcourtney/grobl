from pathlib import Path

from grobl.directory import DirectoryTreeBuilder, traverse_dir


def test_symlink_directories_are_not_followed(tmp_path: Path) -> None:
    base = tmp_path
    (base / "real").mkdir()
    (base / "real" / "child").mkdir()
    (base / "real" / "child" / "file.txt").write_text("hello", encoding="utf-8")

    # Create a symlink to the real directory
    (base / "link").symlink_to(base / "real", target_is_directory=True)

    builder = DirectoryTreeBuilder(base_path=base, exclude_patterns=[])

    def cb(item: Path, prefix: str, *, is_last: bool) -> None:
        if item.is_dir():
            builder.add_directory(item, prefix, is_last=is_last)
        else:
            builder.add_file_to_tree(item, prefix, is_last=is_last)

    traverse_dir(base, ([base], [], base), cb)
    # Expect both directories listed, but no recursion into the symlink
    names = "\n".join(builder.tree_output())
    assert "real" in names
    assert "link" in names
    # The nested child/file appear only under the real dir path
    # and should not be duplicated under the symlink
    assert names.count("child") == 1
