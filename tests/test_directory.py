from grobl.directory import DirectoryTreeBuilder


def test_build_tree_header_includes_marker(tmp_path):
    builder = DirectoryTreeBuilder(tmp_path, [])
    file_path = tmp_path / "a.txt"
    file_path.write_text("hi", encoding="utf-8")
    builder.add_file_to_tree(file_path, "", is_last=True)
    rel = file_path.relative_to(tmp_path)
    builder.record_metadata(rel, 1, 2, 0)
    builder.add_file(file_path, rel, 1, 2, 0, file_path.read_text(encoding="utf-8"))
    lines = builder.build_tree(include_metadata=True)
    assert lines[0].rstrip().endswith("included")
    assert lines[-1].endswith("         ")
