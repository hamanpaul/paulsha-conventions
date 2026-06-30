# policy_check/doc_drift/symbols.py
from __future__ import annotations

import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Iterable

from policy_check.doc_drift import langs

Identity = tuple[str, str, str, str]  # (language, kind, scope, name)


def parse_ctags_json(lines: Iterable[str]) -> set[Identity]:
    """把 ctags --output-format=json 的每行 tag 收斂成 public scoped identity。"""
    out: set[Identity] = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # 跳過 ctags 偶發的非 tag 行
        if not isinstance(obj, dict):
            continue  # 合法 JSON 但非物件（如裸數字/字串/陣列）也跳過
        if obj.get("_type") != "tag":
            continue
        language = obj.get("language") or ""
        kind = obj.get("kind") or ""
        if kind not in langs.public_kinds(language):
            continue
        scope = obj.get("scope") or ""
        name = obj.get("name") or ""
        if name:
            out.add((language, kind, scope, name))
    return out


def _run_ctags(target_dir: Path) -> list[str]:
    langs_arg = ",".join(sorted(langs.supported_languages()))
    try:
        proc = subprocess.run(
            ["ctags", "--output-format=json", "--fields=+lnsSK",
             f"--languages={langs_arg}", "-R", "-f", "-", str(target_dir)],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as exc:
        # 缺 universal-ctags：給可行動訊息，取代難解的 traceback
        raise RuntimeError(
            "universal-ctags 未安裝或不在 PATH；doc-drift 的 symbol 分析需要它"
            "（CI 安裝：apt-get install -y universal-ctags）。"
        ) from exc
    return proc.stdout.splitlines()


def symbols_at(repo_root: Path, sha: str) -> set[Identity]:
    """對某 git ref 的內容跑 ctags，回 public scoped identity 集合。"""
    with tempfile.TemporaryDirectory() as tmp:
        archive = subprocess.run(
            ["git", "-C", str(repo_root), "archive", "--format=tar", sha],
            capture_output=True, check=True,
        ).stdout
        tar_path = Path(tmp) / "tree.tar"
        tar_path.write_bytes(archive)
        extract_dir = Path(tmp) / "tree"
        extract_dir.mkdir()
        with tarfile.open(tar_path) as tf:
            try:
                tf.extractall(extract_dir, filter="data")  # 安全過濾（Py>=3.12 / 回填版）
            except TypeError:
                tf.extractall(extract_dir)  # 舊 Python 無 filter 參數
        return parse_ctags_json(_run_ctags(extract_dir))
