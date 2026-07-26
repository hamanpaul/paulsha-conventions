from pathlib import Path
import tomllib

import yaml

REPO = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    project = data.get("project")
    assert isinstance(project, dict), "pyproject [project] 區段找不到"
    version = project.get("version")
    assert isinstance(version, str), "pyproject [project].version 找不到"
    return version


def test_version_lockstep():
    v_file = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    cfg = yaml.safe_load((REPO / ".project-policy.yml").read_text(encoding="utf-8"))
    assert _pyproject_version() == v_file == str(cfg["policy_version"]), (
        f"版本不一致：pyproject={_pyproject_version()} VERSION={v_file} "
        f"policy_version={cfg['policy_version']}"
    )
