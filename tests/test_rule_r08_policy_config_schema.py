from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "fixture_name",
    [
        "bad-policy-config/valid-flat",
        "bad-policy-config/valid-stage-driven",
    ],
)
def test_r08_policy_config_schema_pass(fixture_repo, fixture_name: str):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-08").check(make_ctx(repo))

    assert result.status == Status.PASS


@pytest.mark.parametrize(
    "fixture_name, expected_text",
    [
        ("bad-policy-config/missing-config", "Missing .paul-project.yml"),
        ("bad-policy-config/missing-policy-profile", "missing required keys"),
        ("bad-policy-config/missing-policy-version", "missing required keys"),
        ("bad-policy-config/invalid-policy-profile", "policy_profile must be one of"),
        ("bad-policy-config/invalid-yaml", "not valid YAML"),
    ],
)
def test_r08_policy_config_schema_fail(fixture_repo, fixture_name: str, expected_text: str):
    repo = fixture_repo(fixture_name)
    result = get_rule("R-08").check(make_ctx(repo))

    assert result.status == Status.FAIL
    assert expected_text in result.message
