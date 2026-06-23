from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_EXTS = (".py", ".sh", ".yml", ".yaml", ".toml", ".js", ".ts",
              ".json", ".cfg", ".ini", ".md")


def looks_like_path(tok: str) -> bool:
    tok = tok.strip()
    if not tok or " " in tok or any(c in tok for c in "<>{}*$"):
        return False
    if tok.startswith(("./", "../")):
        return True
    return tok.endswith(_CODE_EXTS)


def path_candidates(doc_rel: str, target: str) -> list[str]:
    target = target.split("#", 1)[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return []
    doc_dir = Path(doc_rel).parent
    cands: list[str] = []
    for base in (doc_dir / target, Path(target)):
        norm = os.path.normpath(base.as_posix())
        if norm == "." or norm.startswith("..") or norm.startswith("/"):
            continue
        posix = Path(norm).as_posix()
        if posix not in cands:
            cands.append(posix)
    return cands


def git_tracked(root: Path, rev: str | None = None) -> set[str]:
    cmd = ["git", "-C", str(root)]
    cmd += (["ls-tree", "-r", "--name-only", rev] if rev else ["ls-files"])
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return set()
    return {l.strip() for l in out.splitlines() if l.strip()}


def resolve_base(root: Path, base_ref: str | None) -> str | None:
    if not base_ref:
        return None
    for cand in (base_ref, f"origin/{base_ref}"):
        try:
            sha = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "--verify", "-q", f"{cand}^{{commit}}"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            continue
        if not sha:
            continue
        try:
            mb = subprocess.check_output(
                ["git", "-C", str(root), "merge-base", sha, "HEAD"],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError:
            mb = ""
        return mb or sha
    return None
