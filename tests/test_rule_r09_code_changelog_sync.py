from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    changed_files: list[str] | None = None,
    labels: list[str] | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        config={"code_paths": ["**/*.py", "**/*.sh", "scripts/**"]},
        changed_files=changed_files or [],
        pr_labels=labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


def _make_fragment(repo: Path, rel: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntype: feat\n---\nx。\n", encoding="utf-8")


def test_r09_code_change_with_present_fragment_passes(tmp_path):
    _make_fragment(tmp_path, "changelog.d/24-foo.md")
    res = get_rule("R-09").check(
        make_ctx(tmp_path, changed_files=["policy_check/x.py", "changelog.d/24-foo.md"]))
    assert res.status == Status.PASS


def test_r09_code_change_without_fragment_fails(tmp_path):
    res = get_rule("R-09").check(make_ctx(tmp_path, changed_files=["policy_check/x.py"]))
    assert res.status == Status.FAIL
    assert "changelog.d" in res.message


def test_r09_deleted_fragment_does_not_count(tmp_path):
    # fragment is in changed_files but absent at HEAD (deleted/renamed) → must not pass.
    res = get_rule("R-09").check(
        make_ctx(tmp_path, changed_files=["policy_check/x.py", "changelog.d/deleted.md"]))
    assert res.status == Status.FAIL


def test_r09_gitkeep_does_not_count_as_fragment(tmp_path):
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / ".gitkeep").write_text("", encoding="utf-8")
    res = get_rule("R-09").check(
        make_ctx(tmp_path, changed_files=["policy_check/x.py", "changelog.d/.gitkeep"]))
    assert res.status == Status.FAIL


def test_r09_nested_fragment_path_does_not_count(tmp_path):
    _make_fragment(tmp_path, "changelog.d/sub/foo.md")
    res = get_rule("R-09").check(
        make_ctx(tmp_path, changed_files=["policy_check/x.py", "changelog.d/sub/foo.md"]))
    assert res.status == Status.FAIL


def test_r09_skip_changelog_label_skips(tmp_path):
    res = get_rule("R-09").check(
        make_ctx(tmp_path, changed_files=["policy_check/x.py"], labels=["skip-changelog"]))
    assert res.status == Status.SKIP
    assert res.exempt_label == "skip-changelog"


def test_r09_no_code_change_passes(tmp_path):
    res = get_rule("R-09").check(make_ctx(tmp_path, changed_files=["docs/x.md"]))
    assert res.status == Status.PASS
