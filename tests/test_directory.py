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


def test_summary_alignment(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")
    builder = DirectoryTreeBuilder(tmp_path, [])
    builder.add_file_to_tree(file_a, "", is_last=False)
    builder.add_file_to_tree(file_b, "", is_last=True)
    rel_a = file_a.relative_to(tmp_path)
    rel_b = file_b.relative_to(tmp_path)
    builder.record_metadata(rel_a, 1, 1, 1)
    builder.record_metadata(rel_b, 1, 1, 2)
    builder.add_file(file_a, rel_a, 1, 1, 1, "a")
    builder.add_file(file_b, rel_b, 1, 1, 2, "b")
    lines = builder.build_tree(include_metadata=True)
    header_len = len(lines[0])
    assert header_len == len(lines[2])
    for line in lines[2:]:
        assert len(line) == header_len
