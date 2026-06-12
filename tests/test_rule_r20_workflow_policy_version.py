from __future__ import annotations

from pathlib import Path

from policy_check.rules import registry
from policy_check.rules.base import RuleContext, Status


def make_ctx(repo_root: Path, policy_version: str = "1.0.2") -> RuleContext:
    return RuleContext(
        repo_root=repo_root,
        profile="flat",
        policy_version=policy_version,
    )


def get_rule():
    loaded = {rule.rule_id: rule for rule in registry.load_all()}
    assert "R-20" in loaded, "R-20 is not registered"
    return loaded["R-20"]


def _write_workflow(repo_root: Path, name: str, text: str) -> None:
    workflows = repo_root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / name).write_text(text, encoding="utf-8")


def test_r20_pass_when_caller_matches(tmp_path):
    _write_workflow(
        tmp_path,
        "policy-check.yml",
        'jobs:\n  check:\n    with:\n      policy_profile: flat\n      policy_version: "1.0.2"\n',
    )
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.PASS
    assert "match 1.0.2" in result.message


def test_r20_pass_with_unquoted_value(tmp_path):
    _write_workflow(
        tmp_path,
        "policy-check.yml",
        "jobs:\n  check:\n    with:\n      policy_version: 1.0.2\n",
    )
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.PASS


def test_r20_pass_with_env_style_uppercase(tmp_path):
    _write_workflow(
        tmp_path,
        "policy-check.yml",
        'jobs:\n  policy:\n    env:\n      POLICY_VERSION: "1.0.2"\n',
    )
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.PASS


def test_r20_fail_on_mismatch(tmp_path):
    _write_workflow(
        tmp_path,
        "policy-check.yml",
        'jobs:\n  check:\n    with:\n      policy_version: "1.0.1"\n',
    )
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.FAIL
    assert "1.0.1" in result.detail
    assert "1.0.2" in result.detail


def test_r20_ignores_input_declaration_and_template_expr(tmp_path):
    _write_workflow(
        tmp_path,
        "reusable-policy-check.yml",
        "on:\n  workflow_call:\n    inputs:\n      policy_version:\n"
        "        description: Policy version to enforce\n        type: string\n"
        "jobs:\n  check:\n    steps:\n      - env:\n"
        "          POLICY_VERSION: ${{ inputs.policy_version }}\n",
    )
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.PASS
    assert "not applicable" in result.message


def test_r20_pass_when_no_workflows_dir(tmp_path):
    result = get_rule().check(make_ctx(tmp_path))
    assert result.status == Status.PASS
    assert "not applicable" in result.message
