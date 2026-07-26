from __future__ import annotations

import pytest

from policy_check import config as cfg


def test_load_missing_config_mentions_project_and_legacy_names(tmp_path):
    with pytest.raises(cfg.ConfigError) as excinfo:
        cfg.load(tmp_path)

    message = str(excinfo.value)
    assert ".project-policy.yml or .paul-project.yml" in message


def test_load_defaults_agent_files_mode_to_copy(tmp_path):
    from policy_check import config as cfg
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.0\n", encoding="utf-8"
    )
    data = cfg.load(tmp_path)
    assert data["agent_files"]["mode"] == "copy"


def test_load_preserves_explicit_symlink_mode(tmp_path):
    from policy_check import config as cfg
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.0\nagent_files:\n  mode: symlink\n",
        encoding="utf-8",
    )
    data = cfg.load(tmp_path)
    assert data["agent_files"]["mode"] == "symlink"


def test_load_warns_on_legacy_only(tmp_path):
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.0\n",
        encoding="utf-8",
    )
    with pytest.warns(cfg.ConfigWarning, match="deprecated legacy alias"):
        data = cfg.load(tmp_path)
    assert data["policy_profile"] == "flat"
    assert cfg.resolve(tmp_path).legacy_only


def test_load_warns_on_dual_identical(tmp_path):
    content = "policy_profile: flat\npolicy_version: 1.0.0\n"
    (tmp_path / ".project-policy.yml").write_text(content, encoding="utf-8")
    (tmp_path / ".paul-project.yml").write_text(content, encoding="utf-8")
    with pytest.warns(cfg.ConfigWarning, match="identical semantics"):
        cfg.load(tmp_path)
    resolution = cfg.resolve(tmp_path)
    assert resolution.path.name == ".project-policy.yml"
    assert resolution.dual_identical


def test_load_conflict_fails_when_dual_semantics_differ(tmp_path):
    (tmp_path / ".project-policy.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.0\n",
        encoding="utf-8",
    )
    (tmp_path / ".paul-project.yml").write_text(
        "policy_profile: flat\npolicy_version: 1.0.1\n",
        encoding="utf-8",
    )
    with pytest.raises(cfg.ConfigError, match="config conflict"):
        cfg.load(tmp_path)


def test_load_reports_unreadable_utf8_as_config_error(tmp_path):
    (tmp_path / ".project-policy.yml").write_bytes(b"\xff")
    with pytest.raises(cfg.ConfigError, match="not readable"):
        cfg.load(tmp_path)
