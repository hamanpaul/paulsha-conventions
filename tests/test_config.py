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
