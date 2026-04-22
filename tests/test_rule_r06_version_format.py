from __future__ import annotations

from pathlib import Path

import pytest

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


EXPECTED_PATTERN = r"^\d+\.\d+\.\d+(-fix\.\d+)?$"


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


@pytest.mark.parametrize(
    "fixture_name, expected_status",
    [
        ("bad-version-format/valid-semver", Status.PASS),
        ("bad-version-format/valid-semver-fix", Status.PASS),
        ("bad-version-format/invalid-missing-patch", Status.FAIL),
        ("bad-version-format/invalid-fix-suffix", Status.FAIL),
    ],
)
def test_r06_version_format(fixture_repo, fixture_name: str, expected_status: Status):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-06").check(make_ctx(repo))

    assert result.status == expected_status
    if expected_status == Status.FAIL:
        assert "Invalid VERSION format" in result.message
        assert EXPECTED_PATTERN in result.detail


def test_r06_version_format_fail_when_missing_version_file(fixture_repo):
    repo = fixture_repo("missing-version")
    result = get_rule("R-06").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert "Missing VERSION" in result.message
