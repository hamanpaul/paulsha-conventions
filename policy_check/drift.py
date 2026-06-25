# policy_check/drift.py
"""Cross-repo policy_version drift detector (ops tool, NOT an R-xx rule)."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

CANONICAL_ORG = "hamanpaul"
CANONICAL_REPO = "paulsha-conventions"

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-fix\.(\d+))?$")
_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+(?:-fix\.\d+)?)$")


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


def highest_version(tag_names: list[str]) -> str:
    """From ['v1.0.7', 'v1.0.6', ...] pick the highest vX.Y.Z[-fix.N] tag.

    Returns the bare version ('1.0.7'); non-version tags are ignored.
    Raises ValueError if no vX.Y.Z[-fix.N] tag is present.
    """
    versions = [m.group(1) for name in tag_names if (m := _TAG_RE.match(name.strip()))]
    if not versions:
        raise ValueError("no vX.Y.Z[-fix.N] tags found")
    return max(versions, key=parse_version)


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


# --- I/O edges (gh CLI); not unit-tested, exercised via manual smoke ---


def _gh(args: list[str]) -> str:
    return subprocess.check_output(["gh", *args], text=True, stderr=subprocess.DEVNULL)


def local_policy_version(path: str = ".") -> str | None:
    """Read policy_version from the .paul-project.yml at `path` (cwd repo)."""
    cfg = Path(path) / ".paul-project.yml"
    if not cfg.exists():
        return None
    return parse_policy_version(cfg.read_text(encoding="utf-8"))


def canonical_version_live(org: str = CANONICAL_ORG, repo: str = CANONICAL_REPO) -> str:
    """Highest vX.Y.Z[-fix.N] tag of canonical repo, e.g. -> '1.0.7'.

    Uses tags (not GitHub Releases): the canonical repo ships version tags
    per RELEASES.md (merge -> tag), and may have no Release objects.
    """
    out = _gh(["api", f"repos/{org}/{repo}/tags", "--paginate", "--jq", ".[].name"])
    return highest_version(out.splitlines())


def list_managed_repos(org: str = CANONICAL_ORG) -> list[str]:
    out = _gh(["repo", "list", org, "--no-archived", "--limit", "200", "--json", "name"])
    return [r["name"] for r in json.loads(out)]


def fetch_policy_version(org: str, repo: str) -> str | None:
    """Fetch a repo's .paul-project.yml policy_version; None if file absent."""
    try:
        out = _gh([
            "api", f"repos/{org}/{repo}/contents/.paul-project.yml",
            "--header", "Accept: application/vnd.github.raw",
        ])
    except subprocess.CalledProcessError:
        return None
    return parse_policy_version(out)


# --- CLI ---


def cmd_report(args: argparse.Namespace) -> int:
    canonical = canonical_version_live()
    rows: list[tuple[str, str | None, str]] = []
    for name in list_managed_repos(args.org):
        ver = fetch_policy_version(args.org, name)
        rows.append((name, ver, classify(ver, canonical)))
    if args.json:
        print(json.dumps(
            {"canonical": canonical,
             "repos": [{"repo": r, "policy_version": v, "status": s} for r, v, s in rows]},
            ensure_ascii=False,
        ))
    else:
        print(format_report(rows, canonical))
    return 0  # report 永遠 exit 0


def cmd_check(args: argparse.Namespace) -> int:
    canonical = args.against or canonical_version_live()
    repo_ver = local_policy_version(args.repo)
    status = classify(repo_ver, canonical)
    print(f"policy-drift: {status} (repo={repo_ver or '—'} canonical={canonical})")
    return 1 if status == "behind" else 0  # 只有 behind 擋 merge


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="policy-check-drift")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("report", help="List drift across an org (read-only, exit 0)")
    pr.add_argument("--org", default=CANONICAL_ORG)
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_report)

    pc = sub.add_parser("check", help="Gate: fail (exit!=0) if THIS repo is behind canonical")
    pc.add_argument("--repo", default=".")
    pc.add_argument("--against", default=None, help="Override canonical version (skip gh)")
    pc.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
