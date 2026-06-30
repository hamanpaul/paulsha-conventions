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
    """Extract policy_version from a policy config's content.

    Returns None only when there is genuinely no declaration (empty config or a
    mapping without the key) → classified ``unmanaged``. Returns the empty
    string for a present-but-unusable declaration (broken YAML, non-mapping
    root, or a null value) so it classifies as ``invalid`` and the freshness
    gate fails closed instead of being silently waved through as unmanaged.
    """
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return ""  # broken YAML → present-but-invalid (not unmanaged)
    if data is None:
        return None  # empty config → no declaration
    if not isinstance(data, dict):
        return ""  # non-mapping root (scalar/list) → invalid, not unmanaged
    if "policy_version" not in data:
        return None  # mapping without the key → unmanaged
    ver = data["policy_version"]
    if ver is None:
        return ""  # present-but-null → invalid (fail closed in check mode)
    return str(ver)


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

GH_TIMEOUT = 30  # bound every gh call so report/check can't hang indefinitely


class DriftFetchError(Exception):
    """A gh/network failure (not a clean 404) while fetching repo data.

    Lets the report distinguish "couldn't fetch" from genuinely ``unmanaged``.
    """


def _gh(args: list[str], timeout: int = GH_TIMEOUT) -> str:
    proc = subprocess.run(["gh", *args], text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, ["gh", *args], output=proc.stdout, stderr=proc.stderr)
    return proc.stdout


def _is_not_found(exc: subprocess.CalledProcessError) -> bool:
    # Match gh's actual 404 signal ("... (HTTP 404)") specifically, so an
    # unrelated error that merely contains "404"/"Not Found" (e.g. a URL or a
    # 500 body) is NOT mistaken for clean absence — err toward 'error', not
    # 'unmanaged'.
    blob = f"{exc.stderr or ''}{exc.output or ''}"
    return "HTTP 404" in blob


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
    """Fetch a repo's policy_version; None if no policy config file exists (404).

    Tries both CONFIG_NAMES (preferring .project-policy.yml) so a downstream
    repo using the legacy name is not silently treated as unmanaged. Raises
    DriftFetchError on a gh/network failure that is NOT a clean 404, so a
    transient error is not misreported as ``unmanaged``.
    """
    for name in CONFIG_NAMES:
        try:
            out = _gh([
                "api", f"repos/{org}/{repo}/contents/{name}",
                "--header", "Accept: application/vnd.github.raw",
            ])
        except subprocess.CalledProcessError as exc:
            if _is_not_found(exc):
                continue  # this filename cleanly absent (404); try the next
            # A non-404 error on a (possibly higher-priority) name means we
            # cannot reliably determine the version — do NOT silently fall
            # through to a lower-priority file; surface it as a fetch error.
            raise DriftFetchError(str(exc)) from exc
        except (OSError, subprocess.SubprocessError) as exc:  # gh missing, timeout, etc.
            raise DriftFetchError(str(exc)) from exc
        return parse_policy_version(out)
    return None  # all names cleanly 404 → genuinely absent (unmanaged)


# --- CLI ---


def cmd_report(args: argparse.Namespace) -> int:
    # report is an operator dashboard: it MUST always exit 0 and never crash,
    # so canonical/listing failures degrade to a message rather than an error.
    try:
        canonical = canonical_version_live()
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        print(f"policy-drift report: 無法取得 canonical 版本，跳過：{exc}", file=sys.stderr)
        return 0
    try:
        names = list_managed_repos(args.org)
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        print(f"policy-drift report: 無法列出 {args.org} 的 repo，跳過：{exc}", file=sys.stderr)
        return 0
    rows: list[tuple[str, str | None, str]] = []
    for name in names:
        try:
            ver = fetch_policy_version(args.org, name)
            status = safe_classify(ver, canonical)
        except DriftFetchError as exc:
            ver, status = None, "error"  # couldn't fetch ≠ unmanaged
            print(f"policy-drift report: {name} 取版失敗（標為 error）：{exc}", file=sys.stderr)
        rows.append((name, ver, status))
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
    if args.against:
        canonical = args.against
    else:
        try:
            canonical = canonical_version_live()
        except (subprocess.SubprocessError, ValueError, OSError) as exc:
            # gate can't verify canonical → fail closed rather than wave merge through
            print(f"policy-drift: 無法取得 canonical 版本，fail-closed：{exc}", file=sys.stderr)
            return 1
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
