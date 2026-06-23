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
        "bad-policy-config/valid-project-policy",
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
        (
            "bad-policy-config/missing-config",
            "Missing .project-policy.yml or .paul-project.yml",
        ),
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


def test_r08_accepts_valid_tier(fixture_repo):
    repo = fixture_repo("policy-config/tier-valid")
    result = get_rule("R-08").check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r08_rejects_invalid_tier(fixture_repo):
    repo = fixture_repo("policy-config/tier-invalid")
    result = get_rule("R-08").check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "tier" in result.message


def _write_config(tmp_path: Path, cfg_text: str) -> Path:
    # 直接把 config 寫到 repo root，沿用 config_path 的 .paul-project.yml 解析
    (tmp_path / ".paul-project.yml").write_text(cfg_text, encoding="utf-8")
    return tmp_path


def test_r08_accepts_secret_scan_marker_lists(tmp_path):
    cfg = ("policy_profile: flat\npolicy_version: \"1.0.4\"\ntier: shareable\n"
           "secret_scan:\n  markers: [\"FOO123\"]\n  public_names: [\"broadcom\"]\n")
    repo = _write_config(tmp_path, cfg)
    result = get_rule("R-08").check(make_ctx(repo))
    assert result.status == Status.PASS


def test_r08_rejects_non_str_list_markers(tmp_path):
    cfg = ("policy_profile: flat\npolicy_version: \"1.0.4\"\ntier: shareable\n"
           "secret_scan:\n  markers: \"not-a-list\"\n")
    repo = _write_config(tmp_path, cfg)
    result = get_rule("R-08").check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "secret_scan.markers" in result.message


def test_r08_fail_when_doc_reference_allow_not_list(tmp_path):
    cfg = ("policy_profile: flat\npolicy_version: \"1.0.4\"\n"
           "doc_reference:\n  allow: \"docs/legacy\"\n")
    repo = _write_config(tmp_path, cfg)
    result = get_rule("R-08").check(make_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_reference.allow" in result.message


def test_r08_pass_when_doc_reference_allow_is_list(tmp_path):
    cfg = ("policy_profile: flat\npolicy_version: \"1.0.4\"\n"
           "doc_reference:\n  allow: [\"docs/legacy/**\"]\n")
    repo = _write_config(tmp_path, cfg)
    result = get_rule("R-08").check(make_ctx(repo))
    assert result.status == Status.PASS


def _r08():
    from policy_check.rules import registry
    return {r.rule_id: r for r in registry.load_all()}["R-08"]


def _ctx(repo_root):
    from policy_check.rules.base import RuleContext
    return RuleContext(repo_root=repo_root, profile="flat", policy_version="1.0.0")


def test_r08_fail_on_invalid_agent_files_mode(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nagent_files:\n  mode: link\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "agent_files.mode" in result.message


def test_r08_pass_on_valid_agent_files_mode(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nagent_files:\n  mode: symlink\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_on_non_string_engine_repo(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nconventions_engine:\n  repo: [a, b]\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "conventions_engine.repo" in result.message


def test_r08_pass_on_string_engine_repo(tmp_path):
    from policy_check.rules.base import Status
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nconventions_engine:\n  repo: hamanpaul/paulsha-conventions\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_on_malformed_engine_repo(tmp_path):
    # owner/repo 以外的形狀（trailing slash、額外路徑段）必須 FAIL，避免 R-23 靜默 NA
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nconventions_engine:\n  repo: hamanpaul/paulsha-conventions/\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "conventions_engine.repo" in result.message


def test_r08_pass_on_empty_engine_repo(tmp_path):
    # 空字串為「未設/NA」sentinel，須放行
    repo = _write_config(tmp_path, 'policy_profile: flat\npolicy_version: 1.0.0\nconventions_engine:\n  repo: ""\n')
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
