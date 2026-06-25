# policy_check/drift.py
"""Cross-repo policy_version drift detector (ops tool, NOT an R-xx rule)."""
from __future__ import annotations

import re

import yaml

CANONICAL_ORG = "hamanpaul"
CANONICAL_REPO = "paulsha-conventions"

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-fix\.(\d+))?$")


def parse_version(ver: str) -> tuple[int, int, int, int]:
    """Parse MAJOR.MINOR.PATCH[-fix.N] into a comparable tuple.

    Absent -fix suffix sorts below -fix.1 (fix component = 0), so
    1.0.7 < 1.0.7-fix.1 < 1.0.7-fix.2.
    """
    m = _VERSION_RE.match(ver.strip())
    if not m:
        raise ValueError(f"invalid policy version: {ver!r}")
    major, minor, patch, fix = m.groups()
    return (int(major), int(minor), int(patch), int(fix) if fix is not None else 0)


def parse_policy_version(yaml_text: str) -> str | None:
    """Extract policy_version from .paul-project.yml content; None if absent."""
    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return None
    ver = data.get("policy_version")
    return str(ver) if ver is not None else None


def classify(repo_ver: str | None, canonical_ver: str) -> str:
    """Return one of: current | behind | ahead | unmanaged."""
    if repo_ver is None:
        return "unmanaged"
    r = parse_version(repo_ver)
    c = parse_version(canonical_ver)
    if r < c:
        return "behind"
    if r > c:
        return "ahead"
    return "current"


def format_report(rows: list[tuple[str, str | None, str]], canonical: str) -> str:
    """rows: list of (repo, policy_version_or_None, status)."""
    lines = [
        f"canonical: {canonical}  ({CANONICAL_ORG}/{CANONICAL_REPO}, latest tag)",
        "",
        f"{'REPO':<32} {'POLICY_VERSION':<16} STATUS",
    ]
    for repo, ver, status in rows:
        lines.append(f"{repo:<32} {(ver or '—'):<16} {status}")
    return "\n".join(lines)
