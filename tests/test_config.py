from __future__ import annotations

import pytest

from policy_check import config as cfg


def test_load_missing_config_mentions_project_and_legacy_names(tmp_path):
    with pytest.raises(cfg.ConfigError) as excinfo:
        cfg.load(tmp_path)

    message = str(excinfo.value)
    assert ".project-policy.yml or .paul-project.yml" in message
