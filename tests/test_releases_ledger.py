from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASES_FILE = REPO_ROOT / "RELEASES.md"
TAG_ROW_RE = re.compile(r"^\|\s*(\d+\.\d+\.\d+)\s*\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{40})`\s*\|")


def _git(cmd: list[str]) -> str:
    return subprocess.check_output(["git", "-C", str(REPO_ROOT), *cmd], text=True).strip()


def _iter_tagged_rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in RELEASES_FILE.read_text(encoding="utf-8").splitlines():
        match = TAG_ROW_RE.match(line.strip())
        if not match:
            continue
        policy_version, tag, sha = match.groups()
        rows.append((policy_version, tag, sha))
    return rows


def test_release_ledger_tag_rows_must_point_to_authoritative_commit() -> None:
    rows = _iter_tagged_rows()
    assert rows, "RELEASES.md 沒有可解析到任何 tag 行"
    assert {version for version, _, _ in rows}.isdisjoint({"1.0.0", "1.0.1"})

    for policy_version, tag, expected_sha in rows:
        commit_sha = _git(["rev-parse", f"{tag}^{{commit}}"])
        assert commit_sha == expected_sha, f"{tag} SHA 不一致：ledger={expected_sha} 實際={commit_sha}"

        tag_version = _git(["show", f"{tag}:VERSION"]).strip()
        assert (
            tag_version == policy_version
        ), f"{tag}:VERSION={tag_version}，與 RELEASES.md policy_version={policy_version} 不一致"
