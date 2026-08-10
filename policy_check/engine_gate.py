# policy_check/engine_gate.py
"""Startup gate (#61): verify the *running* policy-check engine's own
version matches the repo's declared policy_version.

No R-xx rule can see this drift: every rule compares *declared* text
(README markers, workflow YAML, manifest files) against itself, never
against the engine code that is actually executing the check. A stale
installed engine can therefore read a bumped `policy_version` and report
all-green. This module gates CLI startup instead, before any rule runs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from policy_check import config as policy_config
from policy_check.preflight import _installed_version, _normalized_version

# This file lives at <engine_root>/policy_check/engine_gate.py, so its own
# package root is the engine's source-checkout root.
_ENGINE_ROOT = Path(__file__).resolve().parent.parent


class EngineVersionError(policy_config.ConfigError):
    """Fail-loud, configuration-error-tier: the running engine's version
    could not be determined, or disagrees with the declared policy_version
    and no release exemption applies. Mirrors the "Missing .project-policy.yml"
    handling path (same exception family, same CLI exit code)."""


@dataclass(frozen=True)
class EngineVersion:
    value: str
    source: str  # "installed package" | "source checkout"


@dataclass(frozen=True)
class GateResult:
    status: str  # "pass" | "warn"
    message: str
    engine_version: EngineVersion


def _find_release_label(labels: Optional[Iterable[str]]) -> Optional[str]:
    for label in labels or ():
        if label.startswith("release:"):
            return label
    return None


def _source_checkout_version() -> Optional[str]:
    version_file = _ENGINE_ROOT / "VERSION"
    if not version_file.is_file():
        return None
    text = version_file.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def resolve_engine_version() -> EngineVersion:
    """Resolve the running engine's own version.

    Primary source: the installed 'policy-check' distribution's metadata.
    Fallback: the VERSION file next to the running engine's own source
    checkout (only ever coincides with a *target* repo when that repo IS
    the engine, e.g. this repo dogfooding itself).

    Raises EngineVersionError (fail-closed) when neither source is available.
    """
    installed = _installed_version()
    if installed:
        return EngineVersion(installed, "installed package")
    source = _source_checkout_version()
    if source:
        return EngineVersion(source, "source checkout")
    raise EngineVersionError(
        "cannot determine the running policy-check engine version: no "
        "installed 'policy-check' distribution and no source-checkout "
        "VERSION file next to the running engine. Reinstall with "
        "`pip install --upgrade policy-check`."
    )


def format_report_header(engine_version: EngineVersion) -> str:
    return f"Engine: policy-check {engine_version.value} ({engine_version.source})"


def check(policy_version: str, pr_labels: Optional[Iterable[str]] = None) -> GateResult:
    """Startup gate: compare the running engine's own version against the
    repo's declared policy_version.

    - Match (after PEP 440 normalization) -> pass.
    - Mismatch with a `release:*` PR label present -> warn (same convention
      as R-07's release-window exemption: a release PR that bumps VERSION
      ahead of the installed engine shouldn't be blocked).
    - Mismatch, no release label -> raises EngineVersionError (fail-loud).
    - Engine version unavailable -> raises EngineVersionError regardless of
      labels (fail-closed; never silently skipped).
    """
    engine_version = resolve_engine_version()
    if _normalized_version(engine_version.value) == _normalized_version(policy_version):
        return GateResult(
            "pass",
            f"running engine {engine_version.value} ({engine_version.source}) "
            f"matches declared policy_version {policy_version}.",
            engine_version,
        )

    # pip install 需要合法的 PEP 440 版本字串；repo 宣告的 policy_version 允許
    # `-fix.N` 這種本 policy 自訂語法（PEP 440 不合法），所以重裝指令要用
    # _normalized_version() 轉換過的版本組 spec，沿用比對時已用過的同一個轉換
    # （見 preflight.py:424），否則 `-fix.N` 版號會組出裝不到的 pip spec。
    normalized_target = _normalized_version(policy_version)
    detail = (
        f"running policy-check engine is {engine_version.value} "
        f"({engine_version.source}) but this repo declares "
        f"policy_version: {policy_version}. Reinstall the engine to match: "
        f"pip install --upgrade 'policy-check=={normalized_target}'"
    )
    release_label = _find_release_label(pr_labels)
    if release_label:
        return GateResult(
            "warn",
            f"{detail} (downgraded to a warning by release label {release_label})",
            engine_version,
        )
    raise EngineVersionError(detail)
