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

from policy_check.config import CONFIG_NAMES

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
    """Return one of: current | behind | ahead | unmanaged.

    Raises ValueError if a present version string is malformed.
    """
    if repo_ver is None:
        return "unmanaged"
    r = parse_version(repo_ver)
    c = parse_version(canonical_ver)
    if r < c:
        return "behind"
    if r > c:
        return "ahead"
    return "current"


def safe_classify(repo_ver: str | None, canonical_ver: str) -> str:
    """classify(), but a malformed version yields 'invalid' instead of raising.

    Keeps report mode from crashing on one bad downstream repo, and makes the
    gate fail closed (an unparseable local version is treated as non-passing).
    """
    try:
        return classify(repo_ver, canonical_ver)
    except ValueError:
        return "invalid"


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
    name_w = max([len("REPO"), *(len(r) for r, _, _ in rows)])
    lines = [
        f"canonical: {canonical}  ({CANONICAL_ORG}/{CANONICAL_REPO}, latest tag)",
        "",
        f"{'REPO':<{name_w}}  {'POLICY_VERSION':<16} STATUS",
    ]
    for repo, ver, status in rows:
        lines.append(f"{repo:<{name_w}}  {(ver or '—'):<16} {status}")
    return "\n".join(lines)


# --- I/O edges (gh CLI); not unit-tested, exercised via manual smoke ---


def _gh(args: list[str]) -> str:
    return subprocess.check_output(["gh", *args], text=True, stderr=subprocess.DEVNULL)


def local_policy_version(path: str = ".") -> str | None:
    """Read policy_version from the policy config at `path` (cwd repo).

    Honors both config filenames the engine accepts (CONFIG_NAMES, preferring
    .project-policy.yml) so a repo using the legacy name is not mis-read as
    unmanaged — which would silently pass the freshness gate.
    """
    root = Path(path)
    for name in CONFIG_NAMES:
        cfg = root / name
        if cfg.exists():
            return parse_policy_version(cfg.read_text(encoding="utf-8"))
    return None


def canonical_version_live(org: str = CANONICAL_ORG, repo: str = CANONICAL_REPO) -> str:
    """Highest vX.Y.Z[-fix.N] tag of canonical repo, e.g. -> '1.0.7'.

    Uses tags (not GitHub Releases): the canonical repo ships version tags
    per RELEASES.md (merge -> tag), and may have no Release objects.
    """
    out = _gh(["api", f"repos/{org}/{repo}/tags", "--paginate", "--jq", ".[].name"])
    return highest_version(out.splitlines())


def list_managed_repos(org: str = CANONICAL_ORG, limit: int = 200) -> list[str]:
    out = _gh(["repo", "list", org, "--no-archived", "--limit", str(limit), "--json", "name"])
    names = [r["name"] for r in json.loads(out)]
    if len(names) >= limit:
        print(f"warning: hit --limit {limit}; repos beyond this cap are omitted",
              file=sys.stderr)
    return names


def fetch_policy_version(org: str, repo: str) -> str | None:
    """Fetch a repo's policy_version; None if no policy config file exists.

    Tries both CONFIG_NAMES (preferring .project-policy.yml) so a downstream
    repo using the legacy name is not silently treated as unmanaged.
    """
    for name in CONFIG_NAMES:
        try:
            out = _gh([
                "api", f"repos/{org}/{repo}/contents/{name}",
                "--header", "Accept: application/vnd.github.raw",
            ])
        except subprocess.CalledProcessError:
            continue
        return parse_policy_version(out)
    return None


# --- CLI ---


def cmd_report(args: argparse.Namespace) -> int:
    canonical = canonical_version_live()
    rows: list[tuple[str, str | None, str]] = []
    for name in list_managed_repos(args.org):
        ver = fetch_policy_version(args.org, name)
        rows.append((name, ver, safe_classify(ver, canonical)))
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
    status = safe_classify(repo_ver, canonical)
    print(f"policy-drift: {status} (repo={repo_ver or '—'} canonical={canonical})")
    # behind 擋 merge；invalid 失敗關閉（無法解析的版本不放行）
    return 1 if status in ("behind", "invalid") else 0


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
