import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_CFG = """policy_profile: flat
policy_version: 1.0.10
generated_facts:
  - command: "cat VERSION"
    reflected_in: "README.md"
    marker: "repo-version"
"""
_MARK = (
    '<!-- BEGIN: generated-fact marker="repo-version" -->\n'
    "{v}\n"
    '<!-- END: generated-fact marker="repo-version" -->\n'
)


def _setup(root: Path, marker_version: str, file_version: str) -> None:
    (root / ".paul-project.yml").write_text(_CFG)
    (root / "VERSION").write_text(file_version + "\n")
    (root / "README.md").write_text("# demo\n\n" + _MARK.format(v=marker_version))


def _run_r26(root: Path):
    return subprocess.run(
        [sys.executable, "-m", "policy_check", "--repo", str(root), "--only", "R-26"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO), "GITHUB_STEP_SUMMARY": ""},
    )


def test_r26_dogfood_green_when_marker_matches_version(tmp_path):
    _setup(tmp_path, marker_version="1.0.10", file_version="1.0.10")
    proc = _run_r26(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_r26_dogfood_red_when_marker_drifts_from_version(tmp_path):
    # VERSION bump 到 1.0.11 但 README marker 仍 1.0.10 → 應被擋
    _setup(tmp_path, marker_version="1.0.10", file_version="1.0.11")
    proc = _run_r26(tmp_path)
    assert proc.returncode == 1
    assert "R-26" in proc.stdout
    assert "fail" in proc.stdout
    assert "output mismatch" in proc.stdout
