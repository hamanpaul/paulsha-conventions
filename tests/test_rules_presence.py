from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(repo_root: Path) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


def test_r01_readme_exists_pass_on_valid_minimal(fixture_repo):
    repo = fixture_repo("valid-minimal")
    result = get_rule("R-01").check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r01_readme_exists_fail_when_missing(fixture_repo):
    repo = fixture_repo("missing-readme")
    result = get_rule("R-01").check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "README.md" in result.message


def test_r01_readme_exists_fail_when_too_short(fixture_repo):
    repo = fixture_repo("short-readme")
    result = get_rule("R-01").check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "too short" in result.message


def test_r03_changelog_exists_pass_on_valid_minimal(fixture_repo):
    repo = fixture_repo("valid-minimal")
    result = get_rule("R-03").check(make_ctx(repo))

    assert result.status == Status.PASS


def test_r03_changelog_exists_fail_when_missing(fixture_repo):
    repo = fixture_repo("missing-changelog")
    result = get_rule("R-03").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert "CHANGELOG" in result.message


def test_r05_version_exists_pass_on_valid_minimal(fixture_repo):
    repo = fixture_repo("valid-minimal")
    result = get_rule("R-05").check(make_ctx(repo))

    assert result.status == Status.PASS


def test_r05_version_exists_fail_when_missing(fixture_repo):
    repo = fixture_repo("missing-version")
    result = get_rule("R-05").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert "VERSION" in result.message
