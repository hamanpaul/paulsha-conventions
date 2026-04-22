from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    latest_tag: str | None,
    labels: list[str] | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        pr_labels=labels or [],
        latest_tag=latest_tag,
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


def test_r07_version_tag_sync_pass_when_matching_with_v_prefix(fixture_repo):
    repo = fixture_repo("version-tag-mismatch/match")
    result = get_rule("R-07").check(make_ctx(repo, latest_tag="v1.2.3"))

    assert result.status == Status.PASS


def test_r07_version_tag_sync_pass_when_matching_without_v_prefix(fixture_repo):
    repo = fixture_repo("version-tag-mismatch/match")
    result = get_rule("R-07").check(make_ctx(repo, latest_tag="1.2.3"))

    assert result.status == Status.PASS


def test_r07_version_tag_sync_pass_when_no_latest_tag(fixture_repo):
    repo = fixture_repo("version-tag-mismatch/match")
    result = get_rule("R-07").check(make_ctx(repo, latest_tag=None))

    assert result.status == Status.PASS


def test_r07_version_tag_sync_fail_on_mismatch_without_release_label(fixture_repo):
    repo = fixture_repo("version-tag-mismatch/mismatch")
    result = get_rule("R-07").check(make_ctx(repo, latest_tag="v9.9.9"))

    assert result.status == Status.FAIL
    assert "VERSION" in result.message
    assert "latest tag" in result.message


def test_r07_version_tag_sync_skip_on_mismatch_with_release_label(fixture_repo):
    repo = fixture_repo("version-tag-mismatch/mismatch")
    result = get_rule("R-07").check(
        make_ctx(repo, latest_tag="v9.9.9", labels=["bugfix", "release:minor"])
    )

    assert result.status == Status.SKIP
    assert result.exempt_label == "release:minor"
