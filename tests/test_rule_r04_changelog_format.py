from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


EXEMPT_LABEL = "policy-exempt:changelog-format"


def make_ctx(repo_root: Path, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        pr_labels=labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


def test_r04_changelog_format_pass_when_required_sections_exist(fixture_repo):
    repo = fixture_repo("bad-changelog-format/valid-changelog-format")
    result = get_rule("R-04").check(make_ctx(repo))

    assert result.status == Status.PASS


def test_r04_changelog_format_fail_when_missing_changelog_heading(fixture_repo):
    repo = fixture_repo("bad-changelog-format/missing-changelog-heading")
    result = get_rule("R-04").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert "# Changelog" in result.message


def test_r04_changelog_format_fail_when_missing_unreleased_section(fixture_repo):
    repo = fixture_repo("bad-changelog-format/missing-unreleased-section")
    result = get_rule("R-04").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert "## [Unreleased]" in result.message


def test_r04_changelog_format_skip_when_exempt_label_present(fixture_repo):
    repo = fixture_repo("bad-changelog-format/missing-unreleased-section")
    result = get_rule("R-04").check(make_ctx(repo, labels=[EXEMPT_LABEL]))

    assert result.status == Status.SKIP
    assert result.exempt_label == EXEMPT_LABEL
