from __future__ import annotations

from pathlib import Path

import pytest

from policy_check import config as cfg
from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


EXEMPT_LABEL = "policy-exempt:cli-help"


def make_ctx(repo_root: Path, labels: list[str] | None = None) -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version="1.0.0",
        config=cfg.load(repo_root),
        pr_labels=labels or [],
    )


def get_rule(rule_id: str):
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert rule_id in loaded, f"{rule_id} is not registered"
    return loaded[rule_id]


@pytest.mark.parametrize(
    "fixture_name, expected_status",
    [
        ("cli-empty", Status.PASS),
        ("cli-help-synced", Status.PASS),
        ("cli-help-mismatch", Status.FAIL),
        ("cli-help-missing-marker", Status.FAIL),
    ],
)
def test_r16_cli_help_sync_status(fixture_repo, fixture_name: str, expected_status: Status):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-16").check(make_ctx(repo))

    assert result.status == expected_status


def test_r16_cli_help_sync_skip_on_exempt_label(fixture_repo):
    repo = fixture_repo("cli-help-mismatch")
    result = get_rule("R-16").check(make_ctx(repo, labels=[EXEMPT_LABEL]))

    assert result.status == Status.SKIP
    assert result.exempt_label == EXEMPT_LABEL
