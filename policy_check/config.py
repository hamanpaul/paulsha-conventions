# policy_check/config.py
from pathlib import Path
import yaml


REQUIRED_KEYS = {"policy_profile", "policy_version"}
VALID_PROFILES = {"stage-driven", "flat"}
DEFAULT_CODE_PATHS = {
    "stage-driven": ["**/*.py", "**/*.sh", "scripts/**"],
    "flat":         ["**/*.py", "**/*.sh", "scripts/**"],
}


class ConfigError(Exception):
    pass


def load(repo_root: Path) -> dict:
    path = repo_root / ".paul-project.yml"
    if not path.exists():
        raise ConfigError(f".paul-project.yml not found at {path}")
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f".paul-project.yml is not valid YAML: {exc}") from exc
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ConfigError(f".paul-project.yml missing keys: {sorted(missing)}")
    if data["policy_profile"] not in VALID_PROFILES:
        raise ConfigError(
            f"policy_profile must be one of {VALID_PROFILES}, got {data['policy_profile']}"
        )
    data.setdefault("code_paths", DEFAULT_CODE_PATHS[data["policy_profile"]])
    data.setdefault("cli", [])
    return data
