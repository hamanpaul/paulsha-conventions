# tests/test_doc_drift_moc_cli.py
import os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _git(repo: Path, *a): subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)


def test_moc_mode_flags_dangling_map_ref_with_custom_prefix(tmp_path):
    _git(tmp_path, "init", "-q"); _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "a.md").write_text("x\n")
    (tmp_path / "MAP.md").write_text("map: [a](specs/a.md)\n")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-qm", "c")
    base = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / "specs" / "a.md").unlink()  # 本次刪除被 map 連結的產物
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-qm", "rm")
    proc = subprocess.run(
        [sys.executable, "-m", "policy_check.doc_drift", "--mode", "moc",
         "--repo", str(tmp_path), "--base", base, "--head", "HEAD",
         "--map", "MAP.md", "--governed-prefix", "specs/"],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO)})
    assert proc.returncode != 0
    assert "specs/a.md" in proc.stdout
