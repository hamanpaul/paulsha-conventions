# tests/test_doc_drift_provision.py
import subprocess
from pathlib import Path

from policy_check.doc_drift import provision


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def _init(repo: Path) -> str:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "a.py").write_text("def f():\n    pass\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c")
    return _git(repo, "rev-parse", "HEAD")


def test_existing_object_is_present(tmp_path):
    sha = _init(tmp_path)
    assert provision.ensure_object(tmp_path, sha) is True


def test_missing_object_without_remote_returns_false(tmp_path):
    _init(tmp_path)
    bogus = "0" * 40
    assert provision.ensure_object(tmp_path, bogus) is False
