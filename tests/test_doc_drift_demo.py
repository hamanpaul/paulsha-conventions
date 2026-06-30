import os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_demo_bad_fails_and_good_passes(tmp_path):
    # 在 tmp 建一個 git repo，base 有 symbol、head 刪掉；good doc 不引用、bad doc 引用
    def git(*a): subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    git("init", "-q"); git("config", "user.email", "t@t"); git("config", "user.name", "t")
    (tmp_path / "pkg").mkdir(); (tmp_path / "docs").mkdir()
    (tmp_path / "pkg" / "api.py").write_text("def do_shutdown():\n    pass\n")
    (tmp_path / "docs" / "ok.md").write_text("nothing to see\n")
    git("add", "-A"); git("commit", "-qm", "c")
    base = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (tmp_path / "pkg" / "api.py").write_text("# do_shutdown removed\n")
    (tmp_path / "docs" / "bad.md").write_text("call `do_shutdown`\n")
    git("add", "-A"); git("commit", "-qm", "rm")

    def run():
        return subprocess.run([sys.executable, "-m", "policy_check.doc_drift",
                               "--repo", str(tmp_path), "--base", base, "--head", "HEAD"],
                              capture_output=True, text=True,
                              env={**os.environ, "PYTHONPATH": str(REPO)})
    proc = run()
    assert proc.returncode != 0 and "do_shutdown" in proc.stdout
