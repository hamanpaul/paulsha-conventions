# policy_check/config.py
from pathlib import Path
import yaml


REQUIRED_KEYS = {"policy_profile", "policy_version"}
VALID_PROFILES = {"stage-driven", "flat"}
CONFIG_NAMES = (".project-policy.yml", ".paul-project.yml")
CONFIG_NAMES_DISPLAY = " or ".join(CONFIG_NAMES)
DEFAULT_CODE_PATHS = {
    "stage-driven": ["**/*.py", "**/*.sh", "scripts/**"],
    "flat":         ["**/*.py", "**/*.sh", "scripts/**"],
}


class ConfigError(Exception):
    pass


def config_path(repo_root: Path) -> Path:
    project_policy = repo_root / ".project-policy.yml"
    if project_policy.exists():
        return project_policy
    return repo_root / ".paul-project.yml"


def load(repo_root: Path) -> dict:
    path = config_path(repo_root)
    if not path.exists():
        raise ConfigError(f"{CONFIG_NAMES_DISPLAY} not found at repository root.")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ConfigError(f"{path.name} missing keys: {sorted(missing)}")
    if data["policy_profile"] not in VALID_PROFILES:
        raise ConfigError(
            f"policy_profile must be one of {VALID_PROFILES}, got {data['policy_profile']}"
        )
    data.setdefault("code_paths", DEFAULT_CODE_PATHS[data["policy_profile"]])
    data.setdefault("cli", [])
    agent_files = data.get("agent_files")
    if not isinstance(agent_files, dict):
        agent_files = {}
    agent_files.setdefault("mode", "copy")
    data["agent_files"] = agent_files
    return data
