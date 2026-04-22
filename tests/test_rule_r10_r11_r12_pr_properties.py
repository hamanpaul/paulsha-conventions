from __future__ import annotations

from pathlib import Path

import pytest

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(
    repo_root: Path,
    *,
    pr_title: str | None = None,
    pr_body: str | None = None,
    pr_labels: list[str] | None = None,
    pr_base_ref: str | None = None,
    pr_head_ref: str | None = None,
) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        pr_title=pr_title,
        pr_body=pr_body,
        pr_labels=pr_labels or [],
        pr_base_ref=pr_base_ref,
        pr_head_ref=pr_head_ref,
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


@pytest.mark.parametrize(
    "title",
    [
        "feat: add policy check",
        "fix(parser): handle empty body",
        "chore!: drop deprecated path",
    ],
)
def test_r10_pr_title_pass_on_conventional_title(tmp_path, title: str):
    result = get_rule("R-10").check(make_ctx(tmp_path, pr_title=title))

    assert result.status == Status.PASS


def test_r10_pr_title_skip_on_exempt_label(tmp_path):
    result = get_rule("R-10").check(
        make_ctx(tmp_path, pr_title="invalid title", pr_labels=["policy-exempt:pr-title"])
    )

    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:pr-title"


def test_r10_pr_title_pass_when_non_pr_context(tmp_path):
    result = get_rule("R-10").check(make_ctx(tmp_path, pr_title=None))

    assert result.status == Status.PASS


def test_r10_pr_title_fail_on_non_conventional_title(tmp_path):
    result = get_rule("R-10").check(make_ctx(tmp_path, pr_title="Update docs"))

    assert result.status == Status.FAIL
    assert "conventional commit" in result.message


def test_r11_pr_body_checklist_pass_when_non_pr_context(tmp_path):
    result = get_rule("R-11").check(make_ctx(tmp_path, pr_body=None))

    assert result.status == Status.PASS


def test_r11_pr_body_checklist_skip_with_wip_label(tmp_path):
    result = get_rule("R-11").check(
        make_ctx(tmp_path, pr_body="- [ ] pending", pr_labels=["wip"])
    )

    assert result.status == Status.SKIP
    assert result.exempt_label == "wip"


def test_r11_pr_body_checklist_pass_when_all_checked(tmp_path):
    body = """
- [x] unit tests
- [X] docs updated
"""
    result = get_rule("R-11").check(make_ctx(tmp_path, pr_body=body))

    assert result.status == Status.PASS


def test_r11_pr_body_checklist_fail_on_unchecked_checkbox(tmp_path):
    body = """
- [x] unit tests
- [ ] docs updated
"""
    result = get_rule("R-11").check(make_ctx(tmp_path, pr_body=body))

    assert result.status == Status.FAIL
    assert "unchecked" in result.message


def test_r12_branch_source_pass_when_non_pr_context(tmp_path):
    result = get_rule("R-12").check(make_ctx(tmp_path, pr_base_ref=None, pr_head_ref=None))

    assert result.status == Status.PASS


def test_r12_branch_source_skip_on_exempt_label(tmp_path):
    result = get_rule("R-12").check(
        make_ctx(
            tmp_path,
            pr_base_ref="main",
            pr_head_ref="badbranch",
            pr_labels=["policy-exempt:branch-name"],
        )
    )

    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:branch-name"


def test_r12_branch_source_pass_on_feature_to_main(tmp_path):
    result = get_rule("R-12").check(
        make_ctx(tmp_path, pr_base_ref="main", pr_head_ref="feature/policy-rules")
    )

    assert result.status == Status.PASS


def test_r12_branch_source_fail_on_non_feature_to_main(tmp_path):
    result = get_rule("R-12").check(make_ctx(tmp_path, pr_base_ref="main", pr_head_ref="hotfix/x"))

    assert result.status == Status.FAIL
    assert "feature/<slug>" in result.message


def test_r12_branch_source_pass_on_worktree_to_feature_slug(tmp_path):
    result = get_rule("R-12").check(
        make_ctx(
            tmp_path,
            pr_base_ref="feature/policy-rules",
            pr_head_ref="wt/policy-rules/r10-r11-r12",
        )
    )

    assert result.status == Status.PASS


def test_r12_branch_source_fail_on_wrong_slug_to_feature_slug(tmp_path):
    result = get_rule("R-12").check(
        make_ctx(
            tmp_path,
            pr_base_ref="feature/policy-rules",
            pr_head_ref="wt/another/r10-r11-r12",
        )
    )

    assert result.status == Status.FAIL
    assert "wt/policy-rules/<subtask>" in result.message


def test_r12_branch_source_pass_for_other_base_branch(tmp_path):
    result = get_rule("R-12").check(
        make_ctx(tmp_path, pr_base_ref="release/1.0", pr_head_ref="hotfix/r1")
    )

    assert result.status == Status.PASS
