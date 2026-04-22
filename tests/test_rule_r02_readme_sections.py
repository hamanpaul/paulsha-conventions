from __future__ import annotations

from pathlib import Path

import pytest

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status

EXEMPT_LABEL = "policy-exempt:readme-sections"


def make_ctx(repo_root: Path, pr_labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        pr_labels=pr_labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


@pytest.mark.parametrize(
    "fixture_name, expected_status",
    [
        ("missing-readme-sections/with-required-sections", Status.PASS),
        ("missing-readme-sections/without-required-sections", Status.FAIL),
    ],
)
def test_r02_readme_required_sections(fixture_repo, fixture_name: str, expected_status: Status):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-02").check(make_ctx(repo))

    assert result.status == expected_status
    if expected_status == Status.FAIL:
        assert "required sections" in result.message
        assert "Usage" in result.detail
        assert "Version" in result.detail


def test_r02_readme_required_sections_exempt_label_skip(fixture_repo):
    repo = fixture_repo("missing-readme-sections/without-required-sections")
    result = get_rule("R-02").check(make_ctx(repo, pr_labels=[EXEMPT_LABEL]))

    assert result.status == Status.SKIP
    assert result.exempt_label == EXEMPT_LABEL
