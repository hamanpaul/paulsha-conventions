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


def test_r08_fail_on_moc_triggers_not_list(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc:\n  triggers: \"Dockerfile\"\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "moc.triggers" in result.message


def test_r08_fail_on_moc_static_not_str(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc:\n  static: [a, b]\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "moc.static" in result.message


def test_r08_pass_on_valid_moc(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc:\n  static: docs/ctx.yml\n  map: docs/MOC.md\n  triggers: [\"Dockerfile*\"]\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_on_moc_not_mapping(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc: notamap\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "moc must be a mapping" in result.message


def test_r08_fail_on_moc_map_not_str(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nmoc:\n  map: [a, b]\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "moc.map" in result.message


def test_r08_fail_when_doc_paths_is_not_list(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ndoc_paths: CLAUDE.md\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_paths" in result.message


def test_r08_pass_when_doc_paths_is_string_list(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\n"
        "doc_paths: [\"README.md\", \"docs/**\", \"CLAUDE.md\"]\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


# ---- doc_coverage schema (issue #26) ----

def test_r08_fail_when_doc_coverage_not_mapping(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ndoc_coverage: nope\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_coverage" in result.message


def test_r08_fail_when_doc_coverage_mode_invalid(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ndoc_coverage:\n  mode: sometimes\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_coverage.mode" in result.message


def test_r08_fail_when_doc_coverage_targets_not_list(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ndoc_coverage:\n  targets: README.md\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_coverage.targets" in result.message


def test_r08_fail_when_doc_coverage_sources_not_list(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ndoc_coverage:\n  sources:\n    kind: modules\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "doc_coverage.sources" in result.message


def test_r08_pass_valid_doc_coverage(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\n"
        "doc_coverage:\n  mode: changed\n  targets: [\"README.md\"]\n"
        "  sources:\n    - kind: modules\n      include: [\"pkg/**/*.py\"]\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


# ---- generated_facts schema (issue #26) ----

def test_r08_fail_when_generated_facts_not_list(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ngenerated_facts:\n  kind: cli_help\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "generated_facts" in result.message


def test_r08_fail_when_generated_facts_entry_not_mapping(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\ngenerated_facts:\n  - just-a-string\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "generated_facts" in result.message


def test_r08_pass_valid_generated_facts(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.7\n"
        "generated_facts:\n  - kind: fact_list\n    command: echo hi\n"
        "    reflected_in: README.md\n    marker: rpc\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_on_invalid_conventions_engine_mode(tmp_path):
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.0\nconventions_engine:\n  mode: pipp\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "conventions_engine.mode" in result.message


@pytest.mark.parametrize("mode", ["pip", "workflow", None])
def test_r08_pass_on_valid_or_unset_conventions_engine_mode(tmp_path, mode):
    cfg = "policy_profile: flat\npolicy_version: 1.0.0\n"
    if mode is not None:
        cfg += f"conventions_engine:\n  mode: {mode}\n"
    repo = _write_config(tmp_path, cfg)
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


# ---- auto_build schema (issue #30 提案 A) ----

def test_r08_pass_when_auto_build_absent(tmp_path):
    # 回歸：未宣告 auto_build 行為不變
    repo = _write_config(tmp_path, "policy_profile: flat\npolicy_version: 1.0.11\n")
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_when_auto_build_not_mapping(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build: make image\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build must be a mapping" in result.message


def test_r08_pass_on_empty_auto_build_mapping(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build: {}\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_fail_when_auto_build_steps_is_str(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  steps: make image\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build.steps" in result.message


def test_r08_fail_when_auto_build_steps_mixed_types(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  steps: [make, 42]\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build.steps" in result.message


def test_r08_fail_when_auto_build_description_not_str(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  description: [a, b]\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build.description" in result.message


def test_r08_pass_valid_full_auto_build(tmp_path):
    cfg = (
        "policy_profile: flat\npolicy_version: 1.0.11\n"
        "auto_build:\n"
        "  description: build router firmware image in docker\n"
        '  setup: ["docker pull registry.example/fw-builder:latest"]\n'
        '  steps: ["docker run --rm -v $PWD:/src fw-builder make image"]\n'
        '  artifacts: ["out/*.img"]\n'
        '  verify: ["test -s out/firmware.img"]\n'
    )
    repo = _write_config(tmp_path, cfg)
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_pass_partial_auto_build(tmp_path):
    repo = _write_config(
        tmp_path,
        'policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  steps: ["make"]\n',
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_pass_auto_build_unknown_subkey(tmp_path):
    # 未知 subkey 放行：per-project 擴充與欄位演進不需 engine release
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\n"
        'auto_build:\n  steps: ["make"]\n  timeout_minutes: 30\n',
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_never_executes_auto_build_commands(tmp_path):
    # R-08 只驗形狀：steps 內命令是純資料，驗證過程不得產生副作用
    marker = tmp_path / "side-effect-marker"
    cfg = (
        "policy_profile: flat\npolicy_version: 1.0.11\n"
        f'auto_build:\n  steps: ["touch {marker}"]\n'
    )
    repo = _write_config(tmp_path, cfg)
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
    assert not marker.exists()


def test_r08_fail_when_auto_build_is_bool(tmp_path):
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build: yes\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.FAIL
    assert "auto_build must be a mapping" in result.message


def test_r08_pass_on_empty_auto_build_steps_list(tmp_path):
    # spec：空 list 合法——釘住 all() 對空 iterable 的語意，防日後 truthiness 式重構回歸
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n  steps: []\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS


def test_r08_pass_on_bare_auto_build_key(tmp_path):
    # bare `auto_build:`（YAML null）視同未宣告——與其他 optional 區塊一致
    repo = _write_config(
        tmp_path,
        "policy_profile: flat\npolicy_version: 1.0.11\nauto_build:\n",
    )
    result = _r08().check(_ctx(repo))
    assert result.status == Status.PASS
