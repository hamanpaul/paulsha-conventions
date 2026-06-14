from __future__ import annotations

from pathlib import Path

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(repo_root: Path, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.3",
        config=cfg.load(repo_root),
        pr_labels=labels or [],
    )


def get_rule():
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert "R-21" in loaded, "R-21 is not registered"
    return loaded["R-21"]


def test_r21_pass_when_shareable_clean(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-clean")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r21_fail_when_shareable_has_marker(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-leak")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "BGW720" in result.detail or "platform.py" in result.detail


def test_r21_pass_when_work_tier_has_marker(fixture_repo):
    repo = fixture_repo("secret-scan/work-leak")
    result = get_rule().check(make_ctx(repo))
    assert result.status == Status.PASS
    assert "work" in result.message


def test_r21_skip_with_exemption_label(fixture_repo):
    repo = fixture_repo("secret-scan/shareable-leak")
    result = get_rule().check(
        make_ctx(repo, labels=["policy-exempt:secret-scan"])
    )
    assert result.status == Status.SKIP
    assert result.exempt_label == "policy-exempt:secret-scan"
