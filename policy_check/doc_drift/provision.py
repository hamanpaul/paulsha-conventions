# policy_check/doc_drift/provision.py
from __future__ import annotations

import subprocess
from pathlib import Path


def _has_tree(repo_root: Path, sha: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{sha}^{{tree}}"],
        capture_output=True,
    ).returncode == 0


def ensure_object(repo_root: Path, sha: str) -> bool:
    """確保 sha 的樹物件在本地；缺則嘗試 fetch。回 True/False，不丟例外。"""
    if _has_tree(repo_root, sha):
        return True
    subprocess.run(
        ["git", "-C", str(repo_root), "fetch", "--quiet", "origin", sha],
        capture_output=True,
    )
    return _has_tree(repo_root, sha)
