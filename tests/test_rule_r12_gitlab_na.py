from pathlib import Path

from policy_check.rules.base import RuleContext, Status
from policy_check.rules.r12_branch_source import R12BranchSource


def _ctx(**kw):
    return RuleContext(repo_root=Path("."), profile="flat", policy_version="1.0.10", **kw)


def test_r12_na_on_gitlab():
    res = R12BranchSource().check(
        _ctx(provider="gitlab", pr_base_ref="master", pr_head_ref="fix-x")
    )
    assert res.status == Status.PASS
    assert "GitLab" in res.message or "not applicable" in res.message.lower()


def test_r12_github_unchanged_fail():
    res = R12BranchSource().check(
        _ctx(provider="github", pr_base_ref="main", pr_head_ref="random")
    )
    assert res.status == Status.FAIL
