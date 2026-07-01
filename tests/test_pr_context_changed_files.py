import subprocess
from pathlib import Path

from policy_check import pr_context as prc


def _git(repo, *a):
    subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _repo(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (tmp_path / "b.py").write_text("y = 2\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "next")
    return tmp_path, base


def test_changed_files_by_sha_no_origin_prefix(tmp_path):
    repo, base = _repo(tmp_path)
    got = prc.changed_files(None, repo, base_sha=base)
    assert "b.py" in got


def test_changed_files_by_branch_no_origin_returns_empty(tmp_path):
    repo, _ = _repo(tmp_path)
    assert prc.changed_files("main", repo) == []


def test_changed_files_by_branch_uses_origin_prefix(tmp_path, monkeypatch):
    calls = []

    def fake_check_output(cmd, text=True, stderr=None):
        calls.append((cmd, text, stderr))
        return "fake.py\n"

    monkeypatch.setattr(prc.subprocess, "check_output", fake_check_output)

    got = prc.changed_files("main", tmp_path)

    assert got == ["fake.py"]
    assert calls == [(
        ["git", "-C", str(tmp_path), "diff", "--name-only", "origin/main...HEAD"],
        True,
        subprocess.DEVNULL,
    )]


def test_changed_files_without_inputs_returns_empty(tmp_path):
    assert prc.changed_files(None, tmp_path) == []
