from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from grobl.app.command_support import ScanParams
from grobl.app.explain import build_explain_entries, render_explain
from grobl.app.scan_runtime import assemble_layered_ignores
from grobl.constants import ContentScope, InclusionLevel, PayloadFormat, SummaryFormat, TableStyle
from grobl.core import run_scan
from grobl.errors import ConfigLoadError
from grobl.file_handling import ScanDependencies
from grobl.generated import GeneratedAwareMatcher, relations_from_config
from grobl.ignore import LayeredIgnoreMatcher
from grobl.metadata_visibility import DEFAULT_METADATA_VISIBILITY
from grobl.resource_limits import UNLIMITED_RESOURCE_LIMITS
from grobl.summary import SummaryContext, build_ndjson_payload, build_sink_payload_json, build_summary

if TYPE_CHECKING:
    from pathlib import Path

    from grobl.utils import TextDetectionResult


def _params(root: Path, path: Path | None = None) -> ScanParams:
    target = root if path is None else path
    return ScanParams(
        paths=(target,),
        repo_root=root,
        config_path=None,
        scope=ContentScope.ALL,
        payload=PayloadFormat.NONE,
        summary=SummaryFormat.NONE,
        summary_style=TableStyle.AUTO,
        payload_copy=False,
        payload_output=None,
        visibility=DEFAULT_METADATA_VISIBILITY,
        limits=UNLIMITED_RESOURCE_LIMITS,
        pattern_base=root,
    )


def _matcher(
    root: Path,
    *,
    path: Path | None = None,
    runtime_exclude: tuple[str, ...] = (),
    runtime_tree_only: tuple[str, ...] = (),
    runtime_include: tuple[str, ...] = (),
) -> LayeredIgnoreMatcher:
    target = root if path is None else path
    return assemble_layered_ignores(
        repo_root=root,
        scan_paths=(target,),
        params=_params(root, target),
        ignore_policy="config",
        inherit_defaults=False,
        ignore_defaults_flag=False,
        no_ignore_config_flag=False,
        no_ignore_flag=False,
        runtime_exclude=runtime_exclude,
        runtime_tree_only=runtime_tree_only,
        runtime_include=runtime_include,
    )


@pytest.mark.small
def test_generated_parser_accepts_multiple_sources_and_deduplicates(tmp_path: Path) -> None:
    relations = relations_from_config(
        {
            "generated": [
                {
                    "path": "dist/**",
                    "from": ["src/", "tools/build.py", "src/"],
                }
            ]
        },
        base_dir=tmp_path,
        config_path=tmp_path / ".grobl.toml",
    )

    assert len(relations) == 1
    assert relations[0].pattern == "dist/**"
    assert relations[0].sources == ("src/", "tools/build.py")


@pytest.mark.small
@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"path": "out.js", "from": "src.ts"}, "array of strings"),
        ({"path": "", "from": ["src.ts"]}, "non-empty string 'path'"),
        ({"path": "!out.js", "from": ["src.ts"]}, "may not use gitignore negation"),
        ({"path": "out.js", "from": []}, "at least one source"),
        ({"path": "out.js", "from": [""]}, "must be a non-empty string"),
    ],
)
def test_generated_parser_rejects_ambiguous_or_empty_entries(
    tmp_path: Path,
    entry: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ConfigLoadError, match=message):
        relations_from_config(
            {"generated": [entry]},
            base_dir=tmp_path,
            config_path=tmp_path / ".grobl.toml",
        )


@pytest.mark.medium
def test_generated_file_is_tree_only_without_being_read(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated content\n", encoding="utf-8")
    source = tmp_path / "source.txt"
    source.write_text("source\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '[[generated]]\npath = "generated.txt"\nfrom = ["source.txt"]\n',
        encoding="utf-8",
    )

    def fail_detect(_path: Path) -> TextDetectionResult:
        msg = "generated TREE_ONLY file was text-detected"
        raise AssertionError(msg)

    def fail_read(_path: Path) -> str:
        msg = "generated TREE_ONLY file was read"
        raise AssertionError(msg)

    matcher = _matcher(tmp_path)
    assert isinstance(matcher, GeneratedAwareMatcher)
    decision = matcher.explain_inclusion(target, is_dir=False)
    assert decision.level is InclusionLevel.TREE_ONLY

    result = run_scan(
        paths=[target],
        cfg={},
        ignores=matcher,
        repo_root=tmp_path,
        dependencies=ScanDependencies(text_detector=fail_detect, text_reader=fail_read),
    )

    tree = "\n".join(result.builder.tree_output())
    assert "generated.txt [generated from source.txt]" in tree
    assert result.builder.files_json() == []
    record = dict(result.builder.metadata_items())["generated.txt"]
    assert record.content_reason is not None
    assert record.content_reason["origin"] == "generated"
    assert record.content_reason["generated_from"] == ["source.txt"]


@pytest.mark.medium
def test_same_config_include_restores_generated_content_but_keeps_provenance(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated content\n", encoding="utf-8")
    (tmp_path / "source.txt").write_text("source\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '\n'.join((
            'include = ["generated.txt"]',
            "",
            "[[generated]]",
            'path = "generated.txt"',
            'from = ["source.txt"]',
            "",
        )),
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    decision = matcher.explain_inclusion(target, is_dir=False)
    assert decision.level is InclusionLevel.FULL
    assert matcher.generated_sources(target) == ("source.txt",)

    result = run_scan(paths=[target], cfg={}, ignores=matcher, repo_root=tmp_path)
    assert result.builder.files_json()[0]["content"] == "generated content\n"
    assert "generated.txt [generated from source.txt]" in "\n".join(result.builder.tree_output())


@pytest.mark.medium
def test_same_config_exclude_omits_generated_target(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '\n'.join((
            'exclude = ["generated.txt"]',
            "",
            "[[generated]]",
            'path = "generated.txt"',
            'from = ["source.txt"]',
            "",
        )),
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    assert matcher.explain_inclusion(target, is_dir=False).level is InclusionLevel.OMIT
    result = run_scan(paths=[tmp_path], cfg={}, ignores=matcher, repo_root=tmp_path)
    assert "generated.txt" not in "\n".join(result.builder.tree_output())


@pytest.mark.medium
def test_cli_include_overrides_generated_tree_only(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '[[generated]]\npath = "generated.txt"\nfrom = ["source.txt"]\n',
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path, runtime_include=("generated.txt",))
    decision = matcher.explain_inclusion(target, is_dir=False)

    assert decision.level is InclusionLevel.FULL
    assert decision.reason is not None
    assert decision.reason.source.value == "cli_runtime"
    assert matcher.generated_sources(target) == ("source.txt",)


@pytest.mark.medium
def test_deeper_include_restores_root_generated_target(tmp_path: Path) -> None:
    subtree = tmp_path / "pkg"
    subtree.mkdir()
    target = subtree / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '[[generated]]\npath = "pkg/generated.txt"\nfrom = ["schema.txt"]\n',
        encoding="utf-8",
    )
    (subtree / ".grobl.toml").write_text('include = ["generated.txt"]\n', encoding="utf-8")

    matcher = _matcher(tmp_path, path=subtree)
    decision = matcher.explain_inclusion(target, is_dir=False)

    assert decision.level is InclusionLevel.FULL
    assert decision.reason is not None
    assert decision.reason.config_path == (subtree / ".grobl.toml").resolve()
    assert matcher.generated_sources(target) == ("schema.txt",)


@pytest.mark.medium
def test_nested_generated_sources_render_relative_to_repository_root(tmp_path: Path) -> None:
    subtree = tmp_path / "pkg"
    output = subtree / "out"
    source = subtree / "src"
    output.mkdir(parents=True)
    source.mkdir()
    target = output / "client.js"
    target.write_text("generated\n", encoding="utf-8")
    (source / "client.ts").write_text("source\n", encoding="utf-8")
    (subtree / ".grobl.toml").write_text(
        '[[generated]]\npath = "out/**"\nfrom = ["src/"]\n',
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path, path=subtree)
    assert matcher.generated_sources(target) == ("pkg/src",)

    result = run_scan(paths=[subtree], cfg={}, ignores=matcher, repo_root=tmp_path)
    assert "client.js [generated from pkg/src]" in "\n".join(result.builder.tree_output())


@pytest.mark.medium
def test_overlapping_generated_relations_add_and_deduplicate_sources(tmp_path: Path) -> None:
    target = tmp_path / "generated" / "client.js"
    target.parent.mkdir()
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '\n'.join((
            "[[generated]]",
            'path = "generated/**"',
            'from = ["schema/", "templates/"]',
            "",
            "[[generated]]",
            'path = "generated/client.js"',
            'from = ["templates/", "tools/build.py"]',
            "",
        )),
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    assert matcher.generated_sources(target) == ("schema", "templates", "tools/build.py")

    result = run_scan(paths=[target], cfg={}, ignores=matcher, repo_root=tmp_path)
    assert (
        "client.js [generated from schema, templates, tools/build.py]"
        in "\n".join(result.builder.tree_output())
    )


@pytest.mark.medium
def test_directory_generated_pattern_applies_to_descendant_files(tmp_path: Path) -> None:
    target = tmp_path / "generated" / "nested" / "client.js"
    target.parent.mkdir(parents=True)
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '[[generated]]\npath = "generated/"\nfrom = ["src/"]\n',
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    assert matcher.explain_inclusion(target, is_dir=False).level is InclusionLevel.TREE_ONLY
    assert matcher.explain_inclusion(tmp_path / "ordinary.txt", is_dir=False).level is InclusionLevel.FULL


@pytest.mark.medium
def test_explicit_tree_only_duplicate_is_policy_reason_but_relationship_remains(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '\n'.join((
            'tree_only = ["generated.txt"]',
            "",
            "[[generated]]",
            'path = "generated.txt"',
            'from = ["source.txt"]',
            "",
        )),
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    decision = matcher.explain_inclusion(target, is_dir=False)
    assert decision.level is InclusionLevel.TREE_ONLY
    assert decision.reason is not None
    assert not hasattr(decision.reason, "generated_from")
    assert matcher.generated_sources(target) == ("source.txt",)


@pytest.mark.medium
def test_explain_reports_generated_provenance_for_tree_only_target(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '[[generated]]\npath = "generated.txt"\nfrom = ["source.txt"]\n',
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    entries = build_explain_entries(paths=(target,), ignores=matcher, repo_root=tmp_path)

    assert entries[0]["state"] == "tree_only"
    assert entries[0]["generated_from"] == ["source.txt"]
    assert entries[0]["reason"]["origin"] == "generated"
    assert entries[0]["reason"]["generated_from"] == ["source.txt"]
    human = render_explain(entries, explain_format="human")
    assert "generated from: source.txt" in human
    assert "origin=generated" in human


@pytest.mark.medium
def test_explain_retains_generated_relation_when_include_restores_full(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '\n'.join((
            'include = ["generated.txt"]',
            "",
            "[[generated]]",
            'path = "generated.txt"',
            'from = ["source.txt"]',
            "",
        )),
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    entry = build_explain_entries(paths=(target,), ignores=matcher, repo_root=tmp_path)[0]

    assert entry["state"] == "full"
    assert entry["generated_from"] == ["source.txt"]
    assert entry["reason"] is not None
    assert "origin" not in entry["reason"]


@pytest.mark.medium
def test_json_payload_exposes_generated_relationship_without_content(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '[[generated]]\npath = "generated.txt"\nfrom = ["source.txt"]\n',
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    result = run_scan(paths=[target], cfg={}, ignores=matcher, repo_root=tmp_path)
    context = SummaryContext(
        builder=result.builder,
        common=result.common,
        scope=ContentScope.ALL,
        style=TableStyle.AUTO,
    )
    payload = build_sink_payload_json(context)

    assert payload["files"] == []
    assert payload["relationships"] == [
        {
            "type": "generated_from",
            "path": "generated.txt",
            "sources": ["source.txt"],
        }
    ]
    tree_file = next(entry for entry in payload["tree"] if entry["type"] == "file")
    assert tree_file["generated_from"] == ["source.txt"]
    summary_file = payload["summary"]["files"][0]
    assert summary_file["generated_from"] == ["source.txt"]


@pytest.mark.medium
def test_ndjson_has_relationship_record_only_when_generated_relations_exist(tmp_path: Path) -> None:
    generated = tmp_path / "generated.txt"
    generated.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '[[generated]]\npath = "generated.txt"\nfrom = ["source.txt"]\n',
        encoding="utf-8",
    )
    matcher = _matcher(tmp_path)
    result = run_scan(paths=[generated], cfg={}, ignores=matcher, repo_root=tmp_path)
    context = SummaryContext(
        builder=result.builder,
        common=result.common,
        scope=ContentScope.ALL,
        style=TableStyle.AUTO,
    )

    records = [json.loads(line) for line in build_ndjson_payload(context).splitlines()]
    relation_record = next(record for record in records if record["type"] == "relationships")
    assert relation_record["entries"][0]["path"] == "generated.txt"

    plain_root = tmp_path / "plain"
    plain_root.mkdir()
    plain = plain_root / "ordinary.txt"
    plain.write_text("ordinary\n", encoding="utf-8")
    plain_matcher = _matcher(plain_root)
    assert not isinstance(plain_matcher, GeneratedAwareMatcher)
    plain_result = run_scan(paths=[plain], cfg={}, ignores=plain_matcher, repo_root=plain_root)
    plain_context = SummaryContext(
        builder=plain_result.builder,
        common=plain_result.common,
        scope=ContentScope.ALL,
        style=TableStyle.AUTO,
    )
    plain_records = [json.loads(line) for line in build_ndjson_payload(plain_context).splitlines()]
    assert all(record["type"] != "relationships" for record in plain_records)


@pytest.mark.medium
def test_summary_reports_generated_relation_even_when_content_is_restored(tmp_path: Path) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("generated\n", encoding="utf-8")
    (tmp_path / ".grobl.toml").write_text(
        '\n'.join((
            'include = ["generated.txt"]',
            "",
            "[[generated]]",
            'path = "generated.txt"',
            'from = ["source.txt"]',
            "",
        )),
        encoding="utf-8",
    )

    matcher = _matcher(tmp_path)
    result = run_scan(paths=[target], cfg={}, ignores=matcher, repo_root=tmp_path)
    summary = build_summary(
        SummaryContext(
            builder=result.builder,
            common=result.common,
            scope=ContentScope.ALL,
            style=TableStyle.AUTO,
        )
    )

    assert summary["files"][0]["included"] is True
    assert summary["files"][0]["generated_from"] == ["source.txt"]


@pytest.mark.medium
def test_malformed_nested_generated_config_fails_during_policy_assembly(tmp_path: Path) -> None:
    subtree = tmp_path / "pkg"
    subtree.mkdir()
    (subtree / "target.txt").write_text("target\n", encoding="utf-8")
    (subtree / ".grobl.toml").write_text(
        '[[generated]]\npath = "target.txt"\nfrom = "source.txt"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigLoadError, match="requires 'from' to be an array of strings"):
        _matcher(tmp_path, path=subtree)
