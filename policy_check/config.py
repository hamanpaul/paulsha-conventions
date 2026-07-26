# policy_check/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import warnings

import yaml


REQUIRED_KEYS = {"policy_profile", "policy_version"}
VALID_PROFILES = {"stage-driven", "flat"}
CONFIG_NAMES = (".project-policy.yml", ".paul-project.yml")
CONFIG_NAMES_DISPLAY = " or ".join(CONFIG_NAMES)
DEFAULT_CODE_PATHS = {
    "stage-driven": ["**/*.py", "**/*.sh", "scripts/**"],
    "flat":         ["**/*.py", "**/*.sh", "scripts/**"],
}
DEFAULT_DOC_PATHS = ["README.md", "docs/**"]


class ConfigError(Exception):
    pass


class ConfigWarning(UserWarning):
    pass


@dataclass(frozen=True)
class ConfigResolution:
    path: Path
    data: dict
    legacy_only: bool = False
    dual_identical: bool = False

    @property
    def warning(self) -> str | None:
        if self.legacy_only:
            return (
                ".paul-project.yml is a deprecated legacy alias; "
                "migrate to .project-policy.yml."
            )
        if self.dual_identical:
            return (
                ".project-policy.yml and deprecated .paul-project.yml have "
                "identical semantics; remove the legacy alias."
            )
        return None


def config_path(repo_root: Path) -> Path:
    for name in CONFIG_NAMES:
        path = repo_root / name
        if path.exists():
            return path
    return repo_root / CONFIG_NAMES[0]


def _read_mapping(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigError(f"{path.name} is not readable: {exc}") from exc
    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML: {exc}") from exc
    data = loaded or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} top-level must be a mapping/object.")
    return data


def resolve(repo_root: Path) -> ConfigResolution:
    paths = [repo_root / name for name in CONFIG_NAMES]
    present = [path for path in paths if path.exists()]
    if not present:
        raise ConfigError(f"Missing {CONFIG_NAMES_DISPLAY} at repository root.")

    parsed = [(path, _read_mapping(path)) for path in present]
    if len(parsed) == 2 and parsed[0][1] != parsed[1][1]:
        raise ConfigError(
            "config conflict: .project-policy.yml and .paul-project.yml "
            "have different YAML semantics"
        )

    path, data = parsed[0]
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        raise ConfigError(f"{path.name} missing required keys: {sorted(missing)}")
    if data["policy_profile"] not in VALID_PROFILES:
        raise ConfigError(
            f"policy_profile must be one of {VALID_PROFILES}, got {data['policy_profile']}"
        )
    data.setdefault("code_paths", DEFAULT_CODE_PATHS[data["policy_profile"]])
    data.setdefault("doc_paths", list(DEFAULT_DOC_PATHS))
    data.setdefault("cli", [])
    agent_files = data.get("agent_files")
    if agent_files is None:
        agent_files = {}
        agent_files["mode"] = "copy"
        data["agent_files"] = agent_files
    elif isinstance(agent_files, dict):
        agent_files.setdefault("mode", "copy")
    return ConfigResolution(
        path=path,
        data=data,
        legacy_only=path.name == ".paul-project.yml",
        dual_identical=len(parsed) == 2,
    )


def load(repo_root: Path, *, warn: bool = True) -> dict:
    resolution = resolve(repo_root)
    if warn and resolution.warning:
        warnings.warn(resolution.warning, ConfigWarning, stacklevel=2)
    return resolution.data
