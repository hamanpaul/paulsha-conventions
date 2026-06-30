# tests/test_doc_drift_cli.py
import subprocess, sys
from pathlib import Path


def _git(repo: Path, *a): subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def _setup(repo: Path):
    _git(repo, "init", "-q"); _git(repo, "config", "user.email", "t@t"); _git(repo, "config", "user.name", "t")
    (repo / "pkg").mkdir(); (repo / "docs").mkdir()
    (repo / "pkg" / "m.py").write_text("def legacy_init():\n    pass\n")
    (repo / "docs" / "g.md").write_text("use `legacy_init`\n")
    _git(repo, "add", "-A"); _git(repo, "commit", "-q", "-m", "c")
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (repo / "pkg" / "m.py").write_text("# removed\n")
    _git(repo, "add", "-A"); _git(repo, "commit", "-q", "-m", "rm")
    return base


def _run(repo: Path, base: str):
    return subprocess.run(
        [sys.executable, "-m", "policy_check.doc_drift", "--mode", "doc-drift",
         "--repo", str(repo), "--base", base, "--head", "HEAD"],
        capture_output=True, text=True,
    )


def test_cli_fail_on_removed_symbol(tmp_path):
    base = _setup(tmp_path)
    proc = _run(tmp_path, base)
    assert proc.returncode != 0
    assert "legacy_init" in proc.stdout


def test_cli_pass_when_clean(tmp_path):
    base = _setup(tmp_path)
    # doc 不再引用被刪 symbol
    (tmp_path / "docs" / "g.md").write_text("clean\n")
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-aqm", "fix"], check=True, capture_output=True)
    proc = _run(tmp_path, base)
    assert proc.returncode == 0
