from __future__ import annotations

from pathlib import Path

import pytest

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    *,
    pr_body: str | None = None,
    pr_labels: list[str] | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.1",
        pr_body=pr_body,
        pr_labels=pr_labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


def test_r17_pass_when_non_pr_context(tmp_path):
    result = get_rule("R-17").check(make_ctx(tmp_path, pr_body=None))

    assert result.status == Status.PASS


def test_r17_skip_on_exempt_label(tmp_path):
    result = get_rule("R-17").check(
        make_ctx(
            tmp_path,
            pr_body="related to #12 but does not close it",
            pr_labels=["policy-exempt:issue-link"],
        )
    )

    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:issue-link"


def test_r17_pass_when_body_has_no_issue_reference(tmp_path):
    body = "## Summary\n- just a docs tweak, no issue\n# A markdown heading"
    result = get_rule("R-17").check(make_ctx(tmp_path, pr_body=body))

    assert result.status == Status.PASS


@pytest.mark.parametrize(
    "body",
    [
        "Closes #12",
        "This PR Fixes #3 and adds tests",
        "Resolves: #45",
        "fixed #7",
        "closed #99\nmore text",
        "references #34 too; Closes #12",
    ],
)
def test_r17_pass_on_closing_keyword(tmp_path, body: str):
    result = get_rule("R-17").check(make_ctx(tmp_path, pr_body=body))

    assert result.status == Status.PASS, result.message


def test_r17_fail_when_issue_referenced_without_closing_keyword(tmp_path):
    body = "## Summary\nrelated to #12, see also #34"
    result = get_rule("R-17").check(make_ctx(tmp_path, pr_body=body))

    assert result.status == Status.FAIL
    assert "closing keyword" in result.message.lower()
