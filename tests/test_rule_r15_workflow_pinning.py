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


def test_r15_workflow_pinning_pass_with_tag_or_sha(fixture_repo):
    repo = fixture_repo("workflow-valid-pinned")
    result = get_rule("R-15").check(make_ctx(repo))

    assert result.status == Status.PASS


def test_r15_workflow_pinning_fail_on_branch_refs(fixture_repo):
    repo = fixture_repo("branch-ref-workflow")
    result = get_rule("R-15").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert "branch ref" in result.message
    assert "@main" in result.detail
    assert "@feature/policy-updates" in result.detail


def test_r15_workflow_pinning_pass_when_no_workflows(tmp_path):
    result = get_rule("R-15").check(make_ctx(tmp_path))

    assert result.status == Status.PASS
