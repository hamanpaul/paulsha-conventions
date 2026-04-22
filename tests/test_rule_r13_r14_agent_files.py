from __future__ import annotations

from pathlib import Path

import pytest

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status

EXEMPT_LABEL = "policy-exempt:agent-files"


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


@pytest.mark.parametrize(
    "fixture_name",
    [
        "agent-files-valid",
    ],
)
def test_r13_pass_when_all_agent_files_present(fixture_repo, fixture_name: str):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-13").check(make_ctx(repo))

    assert result.status == Status.PASS


@pytest.mark.parametrize(
    "fixture_name, expected_text",
    [
        ("missing-agent-files", "missing agent convention files"),
    ],
)
def test_r13_fail_when_missing_agent_file(fixture_repo, fixture_name: str, expected_text: str):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-13").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert expected_text in result.message


def test_r13_skip_when_exempt_label_present(fixture_repo):
    repo = fixture_repo("missing-agent-files")
    result = get_rule("R-13").check(make_ctx(repo, labels=[EXEMPT_LABEL]))

    assert result.status == Status.SKIP
    assert result.exempt_label == EXEMPT_LABEL


def test_r14_pass_when_policy_versions_match(fixture_repo):
    repo = fixture_repo("agent-files-valid")
    result = get_rule("R-14").check(make_ctx(repo))

    assert result.status == Status.PASS


@pytest.mark.parametrize(
    "fixture_name, expected_text",
    [
        ("agent-version-mismatch/mismatch", "!= declared"),
        ("agent-version-mismatch/missing-declaration", "policy_version not declared"),
    ],
)
def test_r14_fail_when_policy_versions_drift(
    fixture_repo,
    fixture_name: str,
    expected_text: str,
):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-14").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert expected_text in result.detail
